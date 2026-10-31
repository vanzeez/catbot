"""run_command: one shell command as an argv list, sandbox cwd, scrubbed env (spec 5.3)."""

from __future__ import annotations

import asyncio
import os
import platform
import re
from pathlib import Path

from catbot.contracts import ToolResult

CAP = 8 * 1024
_SECRET_ENV = re.compile(r"KEY|TOKEN|SECRET|PASSWORD", re.I)


def shell_argv(command: str, os_name: str | None = None) -> list[str]:
    os_name = os_name or platform.system()
    if os_name in ("Windows", "windows"):
        return ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command]
    # nonomatch: an unmatched glob passes through (bash-like) instead of aborting the command
    return ["/bin/zsh", "-o", "nonomatch", "-lc", command]


_LAUNCHER_ENV = re.compile(r"^(npm_|NPM_)")  # set by `npm start`; nvm warns about npm_config_prefix


def scrubbed_env() -> dict[str, str]:
    return {
        k: v
        for k, v in os.environ.items()
        if not _SECRET_ENV.search(k) and not _LAUNCHER_ENV.match(k)
    }


def resolve_cwd(cwd: str | None, default: Path) -> Path:
    if cwd:
        p = Path(cwd).expanduser()
        if not p.is_absolute():
            p = default / p
        if p.is_dir():
            return p
    default.mkdir(parents=True, exist_ok=True)
    return default


async def run_command(
    command: str, cwd: str | None, timeout_s: int | None, *, default_cwd: Path
) -> tuple[list[str], ToolResult]:
    argv = shell_argv(command)
    timeout = max(1, min(int(timeout_s or 15), 30))
    workdir = resolve_cwd(cwd, default_cwd)
    proc = await asyncio.create_subprocess_exec(
        *argv,
        cwd=str(workdir),
        env=scrubbed_env(),
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        return argv, ToolResult(
            ok=False,
            summary=f"timeout after {timeout} s",
            error="timeout",
            data={"cwd": str(workdir)},
        )
    stdout = out[:CAP].decode(errors="replace")
    stderr = err[:CAP].decode(errors="replace")
    rc = proc.returncode or 0
    first = (stdout or stderr).strip().splitlines()[:1]
    return argv, ToolResult(
        ok=rc == 0,
        summary=f"exit {rc}: {first[0][:200] if first else ''}".rstrip(),
        data={"stdout": stdout, "stderr": stderr, "rc": rc, "cwd": str(workdir)},
        origin="command_output",
        error=None if rc == 0 else (stderr.strip()[:200] or f"exit {rc}"),
    )
