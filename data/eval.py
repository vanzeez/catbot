"""Evaluate a Laya checkpoint on data/finetune/test.jsonl -> docs/EVAL.md (spec 7.3).

Accuracy per question and language, ECE (10 bins), risk_tier confusion matrix, bars check.
Run: python data/eval.py [--checkpoint DIR | --zero-shot] [--limit N]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from catbot.decide.laya_gate import ZERO_SHOT, calibrate  # noqa: E402

BARS = {"risk_tier": 0.90, "verify_call": 0.85, "confirm_reply": 0.90}
ECE_BAR = 0.10
TIERS = ["T0", "T1", "T2", "T3"]


def ece(pairs: list[tuple[float, bool]], bins: int = 10) -> float:
    if not pairs:
        return 0.0
    total, buckets = 0.0, defaultdict(list)
    for conf, ok in pairs:
        buckets[min(int(conf * bins), bins - 1)].append((conf, ok))
    for items in buckets.values():
        acc = sum(ok for _, ok in items) / len(items)
        avg = sum(c for c, _ in items) / len(items)
        total += len(items) / len(pairs) * abs(acc - avg)
    return total


def evaluate(agent, rows: list[dict], calibration: dict[str, float]) -> dict:
    hits: Counter = Counter()
    seen: Counter = Counter()
    confs: dict[str, list[tuple[float, bool]]] = defaultdict(list)
    confusion: Counter = Counter()
    lat = []
    for r in rows:
        ((qid, gold),) = r["expected"].items()
        t = time.perf_counter()
        raw = agent.predict(r["state"], r["questions"])["answers"][qid]
        lat.append((time.perf_counter() - t) * 1000)
        probs = calibrate(raw.get("probabilities") or {}, calibration.get(qid, 1.0))
        pred, conf = max(probs.items(), key=lambda kv: kv[1]) if probs else (raw["choice"], 0.0)
        ok = pred == gold
        seen[(qid, r.get("lang", "en"))] += 1
        hits[(qid, r.get("lang", "en"))] += ok
        confs[qid].append((conf, ok))
        if qid == "risk_tier":
            confusion[(gold, pred)] += 1
    lat.sort()
    return {
        "hits": hits,
        "seen": seen,
        "confs": confs,
        "confusion": confusion,
        "p50": lat[len(lat) // 2] if lat else 0,
        "p95": lat[int(len(lat) * 0.95)] if lat else 0,
    }


def report(res: dict, label: str, n: int) -> tuple[str, bool]:
    lines = [
        f"# Laya evaluation — {label}",
        "",
        f"Test rows: {n} (data/finetune/test.jsonl, 20% held out by request). "
        f"Latency p50 {res['p50']:.0f} ms, p95 {res['p95']:.0f} ms.",
        "",
        "| question | lang | accuracy | n |",
        "| --- | --- | --- | --- |",
    ]
    for key in sorted(res["seen"]):
        lines.append(
            f"| {key[0]} | {key[1]} | {res['hits'][key] / res['seen'][key]:.3f} | "
            f"{res['seen'][key]} |"
        )
    lines += ["", "| question | accuracy | bar | ECE | pass |", "| --- | --- | --- | --- | --- |"]
    passed = True
    for qid, bar in BARS.items():
        pairs = res["confs"].get(qid, [])
        if not pairs:
            continue
        acc = sum(ok for _, ok in pairs) / len(pairs)
        e = ece(pairs)
        ok = acc >= bar and e < ECE_BAR
        passed &= ok
        lines.append(f"| {qid} | {acc:.3f} | {bar:.2f} | {e:.3f} | {'yes' if ok else 'no'} |")
    lines += [
        "",
        "risk_tier confusion (rows = gold, columns = predicted):",
        "",
        "| gold \\ pred | " + " | ".join(TIERS) + " |",
        "| --- |" + " --- |" * len(TIERS),
    ]
    for g in TIERS:
        lines.append(f"| {g} | " + " | ".join(str(res["confusion"][(g, p)]) for p in TIERS) + " |")
    verdict = (
        "**Bars met.** Set `ROUTER=laya` in `.env`."
        if passed
        else "**Bars not met.** `ROUTER=keyword` stays; Laya runs in shadow mode (`SHADOW=1`). "
        "The pitch says so."
    )
    lines += ["", verdict, ""]
    return "\n".join(lines), passed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", default=None)
    ap.add_argument("--zero-shot", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default=str(ROOT / "docs" / "EVAL.md"))
    args = ap.parse_args()
    os.environ.setdefault("USE_TF", "0")
    import laya

    from catbot.config import load_settings

    s = load_settings()
    src = ZERO_SHOT if args.zero_shot else (args.checkpoint or s.laya_checkpoint_dir)
    if not src:
        raise SystemExit("give --checkpoint DIR, set LAYA_CHECKPOINT_DIR, or pass --zero-shot")
    label = "zero-shot English checkpoint (no fine-tune)" if args.zero_shot else f"checkpoint {src}"
    rows = [
        json.loads(x) for x in (ROOT / "data/finetune/test.jsonl").read_text().splitlines() if x
    ]
    if args.limit:
        rows = rows[:: max(1, len(rows) // args.limit)][: args.limit]
    agent = laya.Agent(src)
    md, passed = report(evaluate(agent, rows, s.calibration), label, len(rows))
    Path(args.out).write_text(md)
    print(md)
    raise SystemExit(0 if passed else 2)


if __name__ == "__main__":
    main()
