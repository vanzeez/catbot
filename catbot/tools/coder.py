"""write_code: Codex CLI as a coding sub-agent (docs/CODING.md, FINDINGS "Codex CLI").

Builds a small web app in SHELL_CWD/<app_name>/ and opens its index.html. argv only, stdin
closed (a piped stdin makes codex wait for EOF), 3-minute cap, Codex's own sandbox on.
"""

from __future__ import annotations

import asyncio
import json
import platform
import re
from pathlib import Path

from catbot.contracts import ToolResult

SLUG = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
CAP_S = 180
RULES = (
    "Build this as a tiny web app in the current folder. Rules: plain HTML, CSS and JavaScript "
    "only, everything in one index.html (inline CSS and JS), no dependencies, no build step, no "
    "network calls, nice simple styling. Finish fast, in under 2 minutes. App: "
)


def codex_argv(target: Path, spec: str, model: str) -> list[str]:
    return [
        "codex",
        "exec",
        "-C",
        str(target),
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
        str(target / ".codex-last.txt"),
        RULES + spec,
    ]


def open_argv(path: Path) -> list[str]:
    if platform.system() == "Windows":
        return ["cmd", "/c", "start", "", str(path)]
    return ["open", str(path)]


async def write_code(
    app_name: str, spec: str, *, sandbox: Path, model: str
) -> tuple[list[str], ToolResult]:
    if not SLUG.fullmatch(app_name):
        return [], ToolResult(ok=False, summary="bad app name", error="app_name must be a slug")
    target = sandbox / app_name
    target.mkdir(parents=True, exist_ok=True)
    argv = codex_argv(target, spec, model)
    proc = await asyncio.create_subprocess_exec(
        *argv,
        cwd=str(target),
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=CAP_S)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        return argv, ToolResult(
            ok=False,
            summary=f"coding timed out after {CAP_S} s",
            error="timeout",
            data={"dir": str(target)},
        )
    errors = [
        json.loads(x).get("message", "")
        for x in out.decode(errors="replace").splitlines()
        if x.startswith('{"type":"error"')
    ]
    index = target / "index.html"
    if proc.returncode != 0 or not index.exists():
        return argv, ToolResult(
            ok=False,
            summary="coding failed",
            error=(errors[-1] if errors else f"exit {proc.returncode}")[:300],
            data={"dir": str(target)},
        )
    opener = await asyncio.create_subprocess_exec(*open_argv(index))
    await opener.wait()
    last = target / ".codex-last.txt"
    files = sorted(p.name for p in target.iterdir() if not p.name.startswith("."))
    return argv, ToolResult(
        ok=True,
        summary=f"built {app_name} ({', '.join(files)}) and opened it in the browser",
        data={
            "dir": str(target),
            "files": files,
            "codex_said": last.read_text()[:500] if last.exists() else "",
        },
    )
