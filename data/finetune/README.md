# Laya fine-tune

## Option A (default): on this Mac, no Kaggle

```bash
python data/gen_laya_data.py && python data/to_laya_format.py
USE_TF=0 python data/finetune_local.py          # Apple Silicon GPU (MPS); about 45 min on an M1 Pro
python data/eval.py --checkpoint checkpoints/catbot-laya
```

`data/finetune_local.py` calls the installed `laya.train.finetune` (the same RLCD objective, calibration split and temperature fit as the Kaggle notebook) with the Laya repo's Apple Silicon settings. Output: `checkpoints/catbot-laya/`. Peak memory fits in 16 GB.

## Option B: Kaggle 2×T4 (faster GPU, needs a Kaggle account)

Time: about 15 minutes of clicking plus about 10 minutes of training.

## 0. Before you upload

1. Tick the 50 rows in `data/handcheck.md`. Fix any wrong label in `data/labels.jsonl`.
2. Run `python data/to_laya_format.py`. It writes `train.jsonl`, `test.jsonl` and `questions.json` here.

## 1. Upload

1. Kaggle → Datasets → New dataset → upload `train.jsonl`, `test.jsonl`, `questions.json`. Name it `catbot-laya`.
2. Open the Laya notebook: https://github.com/NandhaKishorM/laya/blob/main/notebooks/laya_finetune_typed_decisions_2xT4_kaggle.ipynb → File → Import notebook into Kaggle.
3. Notebook options: **Accelerator GPU T4 x2**, **Internet On**. Add input → your `catbot-laya` dataset.

## 2. Edit two cells, run the rest

- Run cells 1–4 unchanged (GPU check, install).
- **Cell 6:** replace the `load_dataset(...)` block and the `rows = []` loop with the snippet in `catbot_cells.py` section CELL 6. Keep the `items_from_rows(...)` and `torch.save(...)` lines.
- Run cells 8 and 10 unchanged (writes `train_ddp.py`, trains 4 epochs, fits temperatures).
- **Cell 12:** replace it with `catbot_cells.py` section CELL 12. It prints accuracy per question on `test.jsonl`.
- Skip cells 14–18 (typed-decisions benchmark tables and the Hub push).

## 3. Where the outputs land

`/kaggle/working/laya_finetuned_typed_decisions/` holds `model.safetensors`, `encoder/`, `tokenizer/`, `rl_agent_config.json`.

1. Download that folder (Output tab → download).
2. Unzip it to `checkpoints/catbot-laya/` in this repo (gitignored).
3. In `.env`: `LAYA_CHECKPOINT_DIR=checkpoints/catbot-laya`.

## 4. Calibration temperatures

The training script fits temperatures and writes them **into** `rl_agent_config.json` (`temperature`, `temperature_by_options`). `laya.load` applies them on every prediction. So `catbot/decide/calibration.json` stays at 1.0. Only change it if `data/eval.py` reports ECE above 0.10 for a question.

## 5. Tell the agent

Say "checkpoint is in checkpoints/catbot-laya". P6 then runs `data/eval.py` and switches `ROUTER=laya` only if the bars pass.
