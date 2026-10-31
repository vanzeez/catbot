# ---- CELL 6 replacement: load Catbot rows instead of LocalLLaMA/typed-decisions ----------------
import glob  # noqa: E402
import json  # noqa: E402

TRAIN = glob.glob("/kaggle/input/**/train.jsonl", recursive=True)[0]
rows = [json.loads(line) for line in open(TRAIN, encoding="utf-8") if line.strip()]
print(f"Loaded {len(rows)} Catbot rows from {TRAIN}")
# keep these two lines from the original cell:
# items, skipped = items_from_rows(tok, rows, cfg["max_len"], cfg["head_max_len"])
# torch.save(items, "/kaggle/working/train_items.pt")

# ---- CELL 12 replacement: accuracy per question and language on test.jsonl ---------------------
import collections  # noqa: E402

import laya  # noqa: E402

TEST = glob.glob("/kaggle/input/**/test.jsonl", recursive=True)[0]
test_rows = [json.loads(line) for line in open(TEST, encoding="utf-8") if line.strip()]
agent_ft = laya.Agent("/kaggle/working/laya_finetuned_typed_decisions", device="cuda")
hits = collections.Counter()
seen = collections.Counter()
for r in test_rows:
    ((qid, gold),) = r["expected"].items()
    pred = agent_ft.predict(r["state"], r["questions"])["answers"][qid]["choice"]
    key = (qid, r.get("lang", "en"))
    seen[key] += 1
    hits[key] += int(pred == gold)
for key in sorted(seen):
    print(f"{key[0]:<14} {key[1]:<9} acc={hits[key] / seen[key]:.3f} n={seen[key]}")
