"""Smoke test: one non-interactive Codex CLI job. Prints event types, timing, files written.

Run: python scripts/smoke_codex.py [workdir]
"""

from __future__ import annotations

import collections
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

work = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix="codex-smoke-"))
work.mkdir(parents=True, exist_ok=True)
last = work / "last.txt"
prompt = (
    "Create index.html: a page with a big number and a '+1 chai' button that increments it. "
    "Plain HTML, CSS and JS in one file, no dependencies, no network. Be quick."
)
model = sys.argv[2] if len(sys.argv) > 2 else "gpt-5.6-luna"
argv = [
    "codex",
    "exec",
    "-C",
    str(work),
    "-s",
    "workspace-write",
    "--skip-git-repo-check",
    "--ephemeral",
    "--json",
    "-m",
    model,
    "-c",
    "model_reasoning_effort=low",
    "-o",
    str(last),
    prompt,
]
t = time.time()
# stdin must be closed: if it is a pipe, codex reads it to EOF and appends it to the prompt
proc = subprocess.run(argv, capture_output=True, text=True, timeout=240, stdin=subprocess.DEVNULL)
kinds: collections.Counter[str] = collections.Counter()
samples: dict[str, str] = {}
for line in proc.stdout.splitlines():
    try:
        ev = json.loads(line)
    except json.JSONDecodeError:
        continue
    kind = ev.get("type") or ev.get("msg", {}).get("type") or "?"
    kinds[kind] += 1
    samples.setdefault(kind, line[:300])
print(f"rc={proc.returncode} seconds={time.time() - t:.1f} workdir={work}")
print("event types:", dict(kinds))
for k, v in samples.items():
    print(f"  {k}: {v}")
print("files:", sorted(p.name for p in work.iterdir()))
print("last message:", last.read_text()[:300] if last.exists() else None)
print("stderr tail:", proc.stderr[-300:])
