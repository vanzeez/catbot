"""Demo runner (spec P7): seed SHELL_CWD, post the 4 demo lines to a running server, assert events.

Run (server already up): python scripts/demo.py [--port 8765] [--runs 3] [--no-seed]
Line 3 is auto-confirmed through POST /api/confirm, only if the command stays in the demo folder.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import subprocess
import sys
from pathlib import Path

import httpx
import websockets

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from catbot.config import load_settings  # noqa: E402

LINES = [
    "volume kam karo",
    "yahan ek project folder banao aur usme README likho",
    "purani screenshots Trash me daal do",
    "saari files delete kar do",
]


def safe_to_confirm(question: str) -> bool:
    """Auto-confirm only commands that stay in the demo folder (or move into the Trash).
    With a real LLM, an unconditional "haan" could approve a command on real files."""
    cmd = question.split("`")[1] if question.count("`") >= 2 else ""
    paths = re.findall(r"(?:^|\s)([~/][^\s;&|]*)", cmd)
    return (
        bool(cmd)
        and not re.search(r"\brm\b", cmd)
        and all("CatbotDemo" in p or p.startswith("~/.Trash") or p == "/dev/null" for p in paths)
    )


async def run_line(base: str, ws, utterance: str, timeout: float = 70) -> list[dict]:
    async with httpx.AsyncClient(base_url=base, timeout=10) as http:
        task_id = (await http.post("/api/text", json={"utterance": utterance})).json()["task_id"]
        events: list[dict] = []

        async def collect() -> None:
            while True:
                e = json.loads(await ws.recv())
                if e["task_id"] != task_id:
                    continue
                events.append(e)
                if e["stage"] == "confirm" and "question" in e["payload"]:
                    ok = safe_to_confirm(e["payload"]["question"])
                    reply = "haan" if ok else "nahi"
                    if not ok:
                        print(f"  guard refused: {e['payload']['question']}")
                    await http.post("/api/confirm", json={"task_id": task_id, "reply": reply})
                if e["stage"] == "done":
                    return

        await asyncio.wait_for(collect(), timeout)
        return events


def check(i: int, events: list[dict]) -> list[str]:
    stages = [e["stage"] for e in events]
    execs = [e["payload"]["tool"] for e in events if e["stage"] == "execute"]
    gates = [e["payload"]["verdict"] for e in events if e["stage"] == "gate"]
    done = events[-1]["payload"]
    fails = []
    if i == 0 and "set_volume" not in execs:
        fails.append("line 1: no execute set_volume")
    if i == 1:
        # Real Sarvam usually splits mkdir and the README write into 2 steps, but sometimes
        # chains them with && into 1. The outcome is what must hold.
        readme = any(load_settings().shell_cwd.glob("*/README*"))
        if not execs.count("run_command") or not done["ok"] or not readme:
            fails.append(
                f"line 2: want done ok and a README in SHELL_CWD, got {execs} "
                f"ok={done['ok']} readme={readme}"
            )
    if i == 2 and not ("confirm" in stages and "execute" in stages[stages.index("confirm") :]):
        fails.append(f"line 3: want confirm then execute, got {stages}")
    if i == 3 and (
        not any(g["verdict"] == "deny" and g["policy"] == "tier_t3" for g in gates) or execs
    ):
        fails.append(f"line 4: want gate deny tier_t3 and no execute, got {gates} {execs}")
    return fails


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--no-seed", action="store_true")
    args = ap.parse_args()
    base = f"http://127.0.0.1:{args.port}"
    for run in range(1, args.runs + 1):
        if not args.no_seed:
            subprocess.run([sys.executable, str(ROOT / "scripts" / "seed_demo.py")], check=True)
        async with websockets.connect(f"ws://127.0.0.1:{args.port}/events") as ws:
            fails: list[str] = []
            for i, line in enumerate(LINES):
                events = await run_line(base, ws, line)
                f = check(i, events)
                fails += f
                ms = events[-1]["latency_ms"]
                n = sum(e["stage"] == "execute" for e in events)
                print(
                    f"run {run} line {i + 1}: {'ok ' if not f else 'FAIL'} {ms:>5} ms "
                    f"steps={n}  {line}"
                )
        if fails:
            print("\n".join(fails))
            return 1
    print(f"demo passed {args.runs}x")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
