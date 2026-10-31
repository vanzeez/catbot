"""Reset SHELL_CWD for the demo: empty it and add 3 dummy shot-*.png files.

Run: python scripts/seed_demo.py [--cwd PATH]
Refuses to touch any folder whose name does not contain "Catbot" or "catbot".
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from catbot.config import load_settings  # noqa: E402

# 1x1 transparent PNG
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082"
)


def seed(cwd: Path) -> list[Path]:
    if "catbot" not in str(cwd).lower():
        raise SystemExit(f"refusing to reset {cwd}: path must contain 'catbot'")
    if cwd.exists():
        shutil.rmtree(cwd)
    cwd.mkdir(parents=True)
    shots = [cwd / f"screenshot-old-{i}.png" for i in (1, 2, 3)]
    for p in shots:
        p.write_bytes(PNG)
    return shots


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cwd", type=Path, default=None)
    cwd = (ap.parse_args().cwd or load_settings().shell_cwd).expanduser()
    shots = seed(cwd)
    print(f"seeded {cwd}: {', '.join(p.name for p in shots)}")


if __name__ == "__main__":
    main()
