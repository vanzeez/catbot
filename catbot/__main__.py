"""CLI: --text "..." | --serve [--voice] | --fake | --yes | --no | --router keyword|laya"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys

from catbot.config import load_settings
from catbot.contracts import Event


def format_event(e: Event) -> str:
    p = e.payload
    if e.stage == "think":
        calls = " ".join(
            f"-> {c['tool']} {json.dumps(c['args'], ensure_ascii=False)}"
            for c in p.get("tool_calls", [])
        )
        return f'"{p.get("text", "")}" {calls}'.strip()
    if e.stage == "risk" and "tier" not in p:
        return f"utterance_floor={p.get('utterance_floor')} gate={p.get('source')}"
    if e.stage == "risk":
        t, v = p["tier"], p["verify"]
        extra = f" shadow={p['shadow']['tier']['choice']}" if p.get("shadow") else ""
        return (
            f"{e.tool} tier={t['choice']} ({t['confidence']:.2f} {t['source']}) "
            f"verify={v['choice']} ({v['confidence']:.2f}) floor={p.get('utterance_floor')}"
            f"{extra}"
        )
    if e.stage == "gate":
        v = p["verdict"]
        return f"{v['policy']} — {v['reason']}"
    if e.stage == "confirm":
        if "question" in p:
            return f"ask: {p['question']}"
        return f"reply={p.get('reply')!r} answer={p['answer']['choice']}"
    if e.stage == "execute":
        return f"{p['tool']} argv={json.dumps(p['argv'], ensure_ascii=False)}"
    if e.stage == "result":
        r = p["result"]
        flag = " PROVENANCE_FLAG" if p.get("provenance_flag") else ""
        return f"{'ok' if r['ok'] else 'FAIL'} {r['summary']}{flag}"
    if e.stage == "speak":
        return f"[{p['lang']}] {p['text']}"
    if e.stage == "done":
        return f"ok={p['ok']} stopped_by={p['stopped_by']} steps={p['steps']} {e.latency_ms} ms"
    return json.dumps(p, ensure_ascii=False)[:200]


def print_event(e: Event) -> None:
    gate = f" {e.verdict}" if e.stage == "gate" else ""
    print(f"{e.stage:<8}{gate:<9} {format_event(e)}", flush=True)


async def run_text(args: argparse.Namespace) -> int:
    from catbot.core.confirm import TextConfirm
    from catbot.core.runtime import PrintSpeaker, build

    settings = load_settings(**_overrides(args))
    auto = "haan" if args.yes else "nahi" if args.no else None
    rt = build(settings, confirm=TextConfirm(auto), speaker=PrintSpeaker())
    rt.bus.listen(print_event)
    shadow = rt.shadow_gate
    if shadow is not None and hasattr(shadow, "ready"):  # text mode: wait for the shadow load
        for _ in range(600):
            if shadow.ready or getattr(shadow, "error", None):
                break
            await asyncio.sleep(0.1)
    print(
        f"# llm={rt.llm.name} tools={rt.tools.name} gate={rt.gate.name} "
        f"shadow={rt.shadow_gate is not None} cwd={settings.shell_cwd}"
    )
    out = await rt.loop.handle(args.text, lang=args.lang)
    return 0 if out.ok or out.stopped_by else 1


def _overrides(args: argparse.Namespace) -> dict[str, object]:
    o: dict[str, object] = {}
    if args.fake:
        o["fakes"] = True
    if args.fake_tools:
        o["fake_tools"] = True
    if args.router:
        o["router"] = args.router
    return o


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="catbot")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--text", help="run one utterance in text mode")
    mode.add_argument("--serve", action="store_true", help="run the server + UI")
    ap.add_argument("--voice", action="store_true", help="enable the /audio voice path")
    ap.add_argument("--fake", action="store_true", help="fake Sarvam and tools")
    ap.add_argument("--fake-tools", action="store_true", help="real Sarvam, fake tools")
    yn = ap.add_mutually_exclusive_group()
    yn.add_argument("--yes", action="store_true", help="auto-answer confirmations yes")
    yn.add_argument("--no", action="store_true", help="auto-answer confirmations no")
    ap.add_argument("--router", choices=["keyword", "laya"])
    ap.add_argument("--lang", default=None, help="reply language, e.g. hi-IN")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    if args.serve:
        from catbot.server.app import serve

        return serve(load_settings(**_overrides(args)), voice=args.voice)
    return asyncio.run(run_text(args))


if __name__ == "__main__":
    sys.exit(main())
