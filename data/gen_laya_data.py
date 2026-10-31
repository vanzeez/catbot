"""Generate labelled Laya rows (spec 7.1) -> data/labels.jsonl and data/handcheck.md.

Sources: `sarvam` (Sarvam-105B json_schema, cached in data/cache/) or `templates` (offline,
labels by construction). Default: sarvam when SARVAM_API_KEY is set, else templates.

Run: python data/gen_laya_data.py [--source sarvam|templates] [--seed 7]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from catbot.decide.keyword_gate import command_tier  # noqa: E402
from catbot.decide.questions import confirm_state, risk_state_text  # noqa: E402
from data import templates as T  # noqa: E402

CACHE = ROOT / "data" / "cache"
OUT = ROOT / "data" / "labels.jsonl"
HANDCHECK = ROOT / "data" / "handcheck.md"
TIER_DEF = (
    "T0 reads or looks only. T1 local change, easy to undo (create, move within cwd, open, "
    "volume). T2 deletes single items, sends, publishes, installs, or is hard to undo (rm file, "
    "trash, git push, mail, kill). T3 destroys data broadly or touches system, credentials or "
    "money (recursive rm, sudo, format, disk ops, passwords, payments)."
)


def fill(tpl: str, rng: random.Random) -> tuple[str, dict[str, str]]:
    slots = {
        "f": rng.choice(T.FILES),
        "d": rng.choice(T.DIRS),
        "a": rng.choice(T.APPS),
        "p": rng.choice(T.PKGS),
        "e": rng.choice(T.EXTS),
    }
    return tpl.format(**slots), slots


def template_pairs(rng: random.Random, per_tier_os: int = 150) -> list[dict]:
    rows: list[dict] = []
    for tier, entries in T.RISK.items():
        for os_i, os_name in enumerate(("zsh", "PowerShell")):
            seen: set[str] = set()
            for _ in range(per_tier_os * 20):
                if len(seen) >= per_tier_os:
                    break
                reqs, zsh, ps = rng.choice(entries)
                req_t = rng.choice(reqs)
                cmd_t = zsh if os_i == 0 else ps
                slots = {
                    "f": rng.choice(T.FILES),
                    "d": rng.choice(T.DIRS),
                    "a": rng.choice(T.APPS),
                    "p": rng.choice(T.PKGS),
                    "e": rng.choice(T.EXTS),
                }
                req, cmd = req_t.format(**slots), cmd_t.format(**slots)
                if req + cmd in seen:
                    continue
                seen.add(req + cmd)
                rows.append(
                    {
                        "request": req,
                        "tool": "run_command",
                        "args": {"command": cmd},
                        "tier": tier,
                        "os": os_name,
                    }
                )
    for _ in range(400):
        reqs, tool, args, tier = rng.choice(T.NATIVE)
        rows.append(
            {
                "request": rng.choice(reqs),
                "tool": tool,
                "args": dict(args),
                "tier": tier,
                "os": "any",
            }
        )
    return rows


def sarvam_pairs(rng: random.Random, per_tier_os: int = 150) -> list[dict]:
    from catbot.config import load_settings

    s = load_settings()
    if not s.has_sarvam:
        raise SystemExit("no SARVAM_API_KEY: use --source templates")
    from sarvamai import SarvamAI

    client = SarvamAI(api_subscription_key=s.sarvam_api_key.get_secret_value())
    schema = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"request": {"type": "string"}, "command": {"type": "string"}},
                    "required": ["request", "command"],
                },
            }
        },
        "required": ["items"],
    }
    rows: list[dict] = []
    for tier, entries in T.RISK.items():
        for os_i, os_name in enumerate(("zsh", "PowerShell")):
            # Prompt text is the cache key; examples keep their {slot} templates and _clean()
            # fills any placeholder Sarvam copies.
            examples = "\n".join(
                f"- request: {e[0][0]} | command: {e[1 + os_i]}" for e in entries[:3]
            )
            got: list[dict] = []
            for batch in range(per_tier_os // 25):
                prompt = (
                    f"Tier definitions: {TIER_DEF}\nWrite 25 different {os_name} shell "
                    f"commands of tier {tier}, each with a short English request a user "
                    f"would say. Write half of the requests in Hinglish (romanized Hindi mixed "
                    f"with English, e.g. 'notes.txt delete kar do') and half in English. "
                    f"Vary files, folders and verbs. Batch {batch}.\n"
                    f"Examples of {tier}:\n{examples}"
                )
                got += _cached_json(client, prompt, schema)["items"]
            cleaned = [_clean(g, rng) for g in got if g.get("request") and g.get("command")]
            got = [g for g in cleaned if g is not None]
            rows += [
                {
                    "request": g["request"],
                    "tool": "run_command",
                    "args": {"command": g["command"]},
                    "tier": tier,
                    "os": os_name,
                }
                for g in got
                # Sarvam's own tiering is loose (it filed `sudo apt install` under T2), so keep
                # only rows whose command the gate tiers the same way: labels match the gate.
                if g.get("request") and g.get("command") and command_tier(g["command"]) == tier
            ]
    # Template rows (labels by construction) add volume and the native-tool rows; dedupe later.
    rows += template_pairs(rng)
    return rows


def _clean(g: dict, rng: random.Random) -> dict | None:
    """Fix what Sarvam copies from the examples: slot placeholders ({f}, {s}) and the example
    layout (`| command_t0_1`). One value per placeholder name per row, so request and command
    name the same file; rows whose placeholders appear on one side only are dropped."""
    request = re.split(r"\s*\|\s*command\w*", str(g["request"]), maxsplit=1)[0]
    command = str(g["command"])
    in_req = set(re.findall(r"\{(\w+)\}", request))
    in_cmd = set(re.findall(r"\{(\w+)\}", command))
    if in_req != in_cmd:
        return None
    pools = {"f": T.FILES, "d": T.DIRS, "a": T.APPS, "p": T.PKGS, "e": T.EXTS}
    words = ["TODO", "error", "invoice", "budget", "meeting"]
    values = {k: rng.choice(pools.get(k, words)) for k in sorted(in_req)}
    for k, v in values.items():
        request, command = request.replace("{" + k + "}", v), command.replace("{" + k + "}", v)
    return {"request": " ".join(request.split()), "command": command.strip()}


def _cached_json(client: object, prompt: str, schema: dict) -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"gen_{hashlib.sha256(prompt.encode()).hexdigest()[:16]}.json"
    if path.exists():
        return json.loads(path.read_text())
    data: dict = {"items": []}
    for attempt in range(2):  # FINDINGS: a 50-row batch once overran max_tokens mid-JSON
        try:
            resp = client.chat.completions(  # type: ignore[attr-defined]
                model="sarvam-105b",
                messages=[
                    {"role": "user", "content": prompt + ("\nReturn compact JSON." * attempt)}
                ],
                reasoning_effort=None,
                max_tokens=6000,
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": "rows", "strict": True, "schema": schema},
                },
                request_options={"timeout_in_seconds": 120},
            )
        except Exception as exc:  # noqa: BLE001 - timeouts, 429/503: retry once, then skip
            print(f"  Sarvam call failed (attempt {attempt + 1}): {type(exc).__name__}")
            time.sleep(3)
            continue
        try:
            data = json.loads(resp.choices[0].message.content)
            break
        except json.JSONDecodeError:
            print(
                f"  bad JSON from Sarvam (attempt {attempt + 1}), finish="
                f"{resp.choices[0].finish_reason}"
            )
    else:
        return data  # skip this batch, do not cache
    path.write_text(json.dumps(data, ensure_ascii=False))
    return data


def build_rows(pairs: list[dict], rng: random.Random) -> list[dict]:
    out: list[dict] = []
    for p in pairs:
        state = risk_state_text(p["request"], p["tool"], p["args"])
        out.append(_row("risk_tier", state, p["tier"], p["request"], "en"))
    pool = [p for p in pairs]
    rng.shuffle(pool)
    for p in pool[:400]:
        out.append(
            _row(
                "verify_call",
                risk_state_text(p["request"], p["tool"], p["args"]),
                "execute",
                p["request"],
                "en",
            )
        )
    for p in pool[400:700]:
        other = rng.choice(
            [q for q in pool[:50] if q["tool"] != p["tool"] or q["args"] != p["args"]]
        )
        out.append(
            _row(
                "verify_call",
                risk_state_text(p["request"], other["tool"], other["args"]),
                "wrong_tool",
                p["request"],
                "en",
            )
        )
    for p in pool[700:800]:
        args = {k: rng.choice(["", "???", "asdf qwer"]) for k in (p["args"] or {"x": 1})}
        out.append(
            _row(
                "verify_call",
                risk_state_text(p["request"], p["tool"], args),
                "unclear",
                p["request"],
                "en",
            )
        )
    for lang, by_label in T.REPLIES.items():
        for label, replies in by_label.items():
            for _ in range(100):
                reply = _noisy(rng.choice(replies), lang, rng)
                q, _ = fill(rng.choice(T.QUESTIONS_CONFIRM), rng)
                out.append(
                    _row(
                        "confirm_reply",
                        confirm_state(q, reply),
                        label,
                        f"{lang}:{reply}",  # same reply text -> same split
                        lang,
                    )
                )
    return out


def _noisy(reply: str, lang: str, rng: random.Random) -> str:
    if rng.random() < 0.35:
        reply = f"{rng.choice(T.FILLERS[lang])} {reply}"
    if lang in ("hinglish", "en") and rng.random() < 0.15 and len(reply) > 3:
        i = rng.randrange(1, len(reply) - 1)
        reply = reply[:i] + reply[i] + reply[i:]  # ASR-style doubled letter
    return reply


def _row(qid: str, state: str, label: str, group: str, lang: str) -> dict:
    gid = hashlib.sha256(group.encode()).hexdigest()
    return {
        "id": f"{qid}-{gid[:10]}-{hashlib.sha256(state.encode()).hexdigest()[:6]}",
        "lang": lang,
        "question_id": qid,
        "state": state,
        "label": label,
        "split": "test" if int(gid[:8], 16) % 5 == 0 else "train",
    }  # 20% hold-out by request


def _dedupe(rows: list[dict]) -> list[dict]:
    """Drop repeated (question, state) rows so no state sits in both train and test."""
    seen: dict[tuple[str, str], dict] = {}
    for r in rows:
        seen.setdefault((r["question_id"], r["state"]), r)
    return list(seen.values())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["sarvam", "templates"], default=None)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    from catbot.config import load_settings

    source = args.source or ("sarvam" if load_settings().has_sarvam else "templates")
    rng = random.Random(args.seed)
    pairs = sarvam_pairs(rng) if source == "sarvam" else template_pairs(rng)
    rows = _dedupe(build_rows(pairs, rng))
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    pick = random.Random(7).sample(rows, 50)
    HANDCHECK.write_text(
        "# Hand-check: 50 random rows (seed 7)\n\nTick a box if the label is "
        "right. Fix wrong labels in data/labels.jsonl, then rerun "
        "data/to_laya_format.py.\n\n"
        + "".join(
            f"- [ ] `{r['id']}` **{r['question_id']} = {r['label']}**  \n"
            f"  `{r['state'].replace(chr(10), ' | ')}`\n"
            for r in pick
        )
    )
    counts = Counter((r["question_id"], r["split"]) for r in rows)
    print(f"source={source} rows={len(rows)} -> {OUT.relative_to(ROOT)}")
    for (qid, split), n in sorted(counts.items()):
        print(f"  {qid:<14} {split:<5} {n}")


if __name__ == "__main__":
    main()
