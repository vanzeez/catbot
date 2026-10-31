"""Convert data/labels.jsonl into the row format `laya.train.items_from_rows` reads.

The Kaggle notebook (laya repo, notebooks/laya_finetune_typed_decisions_2xT4_kaggle.ipynb, cell 6)
builds rows `{"state", "questions", "gold"}` and calls `items_from_rows(tok, rows, max_len,
head_max_len)`. That function also accepts `{"state", "questions", "expected"}` where
`expected[qid]` is the label string (laya 0.4.18, laya/train.py). We write that form.

Run: python data/to_laya_format.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from catbot.decide.questions import QUESTIONS  # noqa: E402

SRC = ROOT / "data" / "labels.jsonl"
DST = ROOT / "data" / "finetune"


def convert_row(row: dict) -> dict:
    qid = row["question_id"]
    q = QUESTIONS[qid]
    if row["label"] not in q["criteria"]:
        raise ValueError(f"{row['id']}: label {row['label']!r} not in {list(q['criteria'])}")
    return {
        "id": row["id"],
        "lang": row.get("lang", "en"),
        "state": row["state"],
        "questions": {qid: q},
        "expected": {qid: row["label"]},
    }


def main() -> None:
    rows = [json.loads(line) for line in SRC.read_text().splitlines() if line.strip()]
    DST.mkdir(parents=True, exist_ok=True)
    counts: Counter[str] = Counter()
    for split in ("train", "test"):
        out = [convert_row(r) for r in rows if r.get("split", "train") == split]
        (DST / f"{split}.jsonl").write_text(
            "".join(json.dumps(o, ensure_ascii=False) + "\n" for o in out)
        )
        counts[split] = len(out)
    (DST / "questions.json").write_text(json.dumps(QUESTIONS, indent=2))
    print(f"train={counts['train']} test={counts['test']} -> {DST.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
