"""P1 smoke: Laya Router result shape, confidence location, pinning, CPU latency.

Run: USE_TF=0 python scripts/smoke_laya.py  (downloads checkpoints on first run)
"""

from __future__ import annotations

import json
import os
import statistics
import time

os.environ.setdefault("USE_TF", "0")

RISK_TIER = {
    "type": "choice",
    "instructions": "How risky is this action?",
    "criteria": {
        "T0": "only reads or looks",
        "T1": "local change, easy to undo",
        "T2": "sends, publishes, trashes or hard to undo",
        "T3": "destroys data, pays, or touches credentials or system",
    },
}
VERIFY_CALL = {
    "type": "choice",
    "instructions": "Does this action match the request?",
    "criteria": {
        "execute": "matches the request",
        "wrong_tool": "a different action fits",
        "unclear": "cannot tell",
    },
}
CONFIRM_REPLY = {
    "type": "choice",
    "instructions": "What did the user answer?",
    "criteria": {"A": "the user agrees", "B": "the user refuses", "C": "unclear"},
}
STATES = [
    'Request: lower the volume\nAction: set_volume {"action": "down"}',
    'Request: delete everything\nAction: run_command {"command": "rm -rf ~"}',
]


def dump(obj: object) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False, default=repr)[:4000]


def main() -> None:
    import laya
    from laya import Router

    print("laya version:", getattr(laya, "__version__", "?"))
    t = time.perf_counter()
    router = Router(preload=True)
    print(f"load (preload=True): {time.perf_counter() - t:.1f} s")

    qs = {"risk_tier": RISK_TIER, "verify_call": VERIFY_CALL}
    for state in STATES:
        t = time.perf_counter()
        res = router.predict(state, qs)
        print(f"\n=== state: {state!r}  ({(time.perf_counter() - t) * 1000:.0f} ms)")
        print(dump(res))

    print("\n=== confirm_reply, Latin + Devanagari")
    for reply in ["haan kar do", "हाँ कर दो", "nahi rehne do"]:
        res = router.predict(
            f"Question: Trash me daal doon?\nReply: {reply}", {"cr": CONFIRM_REPLY}
        )
        print(reply, "->", res["answers"]["cr"].get("choice"), res.get("routing", {}).get("model"))

    print("\n=== pinning: model='english' on Devanagari reply")
    try:
        res = router.predict("Question: Trash?\nReply: हाँ", {"cr": CONFIRM_REPLY}, model="english")
        print("pinned ok:", res.get("routing"), res["answers"]["cr"].get("choice"))
    except Exception as exc:  # noqa: BLE001 - smoke script prints whatever happens
        print("pin failed:", type(exc).__name__, exc)

    lat = []
    for _ in range(20):
        t = time.perf_counter()
        router.predict(STATES[0], qs)
        lat.append((time.perf_counter() - t) * 1000)
    lat.sort()
    print(f"\nCPU latency over 20: p50={statistics.median(lat):.0f} ms p95={lat[18]:.0f} ms")


if __name__ == "__main__":
    main()
