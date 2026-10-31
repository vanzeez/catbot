"""Fine-tune Laya locally on Apple Silicon (MPS) or CPU, instead of Kaggle (spec 7.2 alternative).

Uses the installed `laya.train.finetune` (same RLCD objective, calibration split and temperature
fit as the Kaggle notebook) on data/finetune/train.jsonl. Settings follow the Laya repo's
Apple Silicon script (micro-batch 2, grad-accum 16, no AMP), with a shorter max_len because
Catbot states are short.

Run: USE_TF=0 python data/finetune_local.py [--epochs 4] [--out checkpoints/catbot-laya]
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")


def base_checkpoint() -> str:
    hits = glob.glob(
        os.path.expanduser(
            "~/.cache/huggingface/hub/models--convaiinnovations--laya/snapshots/*/rl_agent_config.json"
        )
    )
    if hits:
        return str(Path(hits[0]).parent)
    from huggingface_hub import snapshot_download

    return snapshot_download("convaiinnovations/laya")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--micro-batch", type=int, default=2)
    ap.add_argument("--grad-accum", type=int, default=16)
    ap.add_argument("--max-len", type=int, default=384)
    ap.add_argument("--device", default="auto")
    ap.add_argument("--out", default=str(ROOT / "checkpoints" / "catbot-laya"))
    args = ap.parse_args()

    import torch
    from laya.train import TrainConfig, finetune

    torch.set_float32_matmul_precision("high")
    device = args.device
    if device == "auto":
        device = "mps" if torch.backends.mps.is_available() else "cpu"
    config = TrainConfig(
        epochs=args.epochs,
        micro_batch=args.micro_batch,
        grad_accum=args.grad_accum,
        calib_max=400,
        calib_seed=20260922,
        seed=42,
        max_len=args.max_len,
        head_max_len=192,
        gradient_checkpointing=True,
        amp=False,
        log_every=20,
    )
    data = ROOT / "data" / "finetune" / "train.jsonl"
    base = base_checkpoint()
    print(
        f"base={base}\ndata={data}\nout={args.out}\ndevice={device} epochs={args.epochs}",
        flush=True,
    )
    t = time.time()
    summary = finetune(
        data=str(data), model_dir=base, output_dir=args.out, config=config, device=device
    )
    # As the Laya Apple Silicon script does: question types with no calibration items get 1.2.
    cfg_path = Path(args.out) / "rl_agent_config.json"
    cfg = json.loads(cfg_path.read_text())
    for name, entry in (summary.get("calibration") or {}).items():
        idx = {"choice": 0, "score": 1, "noul": 2}.get(name)
        if isinstance(entry, dict) and entry.get("items") == 0 and idx is not None:
            cfg["temperature"][idx] = 1.2
    cfg["model_name"] = "catbot-laya"
    cfg_path.write_text(json.dumps(cfg, indent=2))
    print(
        f"done in {(time.time() - t) / 60:.1f} min; train_items={summary.get('train_items')} "
        f"calibration_items={summary.get('calibration_items')} "
        f"temperature={summary.get('temperature')}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
