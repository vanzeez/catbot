"""Shared helpers for P1 smoke scripts. Never prints secrets."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from catbot.config import load_settings  # noqa: E402

settings = load_settings()


def need(key_present: bool, name: str) -> None:
    if not key_present:
        print(f"not run: no key ({name} missing in .env)")
        raise SystemExit(0)


def show(label: str, obj: object) -> None:
    if hasattr(obj, "model_dump"):
        obj = obj.model_dump()
    print(f"--- {label}")
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=repr)[:4000])
