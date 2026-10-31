"""Native desktop tools per OS: set_volume, lock_screen, take_screenshot."""

from __future__ import annotations

import asyncio
import platform
import time
from pathlib import Path

from catbot.contracts import ToolResult

SHOTS = Path("~/Pictures/Catbot").expanduser()


async def _run(argv: list[str]) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    out, err = await asyncio.wait_for(proc.communicate(), timeout=10)
    return proc.returncode or 0, out.decode(errors="replace"), err.decode(errors="replace")


def _target(action: str, level: int | None, current: int) -> int:
    if action == "set":
        return max(0, min(100, level if level is not None else current))
    step = 10 if action == "up" else -10
    return max(0, min(100, current + step))


async def set_volume(action: str, level: int | None = None) -> tuple[list[str], ToolResult]:
    if platform.system() == "Windows":
        return await asyncio.to_thread(_set_volume_windows, action, level)
    if action in ("mute", "unmute"):
        argv = ["osascript", "-e", f"set volume output muted {str(action == 'mute').lower()}"]
        rc, _, err = await _run(argv)
        return argv, ToolResult(
            ok=rc == 0,
            summary=f"{action}d" if rc == 0 else err.strip(),
            error=None if rc == 0 else err.strip() or "osascript failed",
        )
    rc, out, err = await _run(["osascript", "-e", "output volume of (get volume settings)"])
    current = int(out.strip()) if rc == 0 and out.strip().isdigit() else 50
    new = _target(action, level, current)
    argv = ["osascript", "-e", f"set volume output volume {new}"]
    rc, _, err = await _run(argv)
    return argv, ToolResult(
        ok=rc == 0,
        summary=f"volume {current} -> {new}",
        data={"before": current, "after": new},
        error=None if rc == 0 else err.strip() or "osascript failed",
    )


def _set_volume_windows(action: str, level: int | None) -> tuple[list[str], ToolResult]:
    try:
        from ctypes import POINTER, cast

        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        dev = AudioUtilities.GetSpeakers()
        vol = cast(
            dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None),
            POINTER(IAudioEndpointVolume),
        )
        if action in ("mute", "unmute"):
            vol.SetMute(int(action == "mute"), None)
            return ["pycaw", "SetMute", action], ToolResult(ok=True, summary=f"{action}d")
        current = round(vol.GetMasterVolumeLevelScalar() * 100)
        new = _target(action, level, current)
        vol.SetMasterVolumeLevelScalar(new / 100, None)
        return ["pycaw", "SetMasterVolumeLevelScalar", str(new)], ToolResult(
            ok=True, summary=f"volume {current} -> {new}", data={"before": current, "after": new}
        )
    except Exception as exc:  # noqa: BLE001 - surface any COM failure as a tool error
        return ["pycaw", action], ToolResult(ok=False, summary="volume failed", error=str(exc))


def lock_argv() -> list[str]:
    if platform.system() == "Windows":
        return ["rundll32.exe", "user32.dll,LockWorkStation"]
    return ["pmset", "displaysleepnow"]


async def lock_screen() -> tuple[list[str], ToolResult]:
    argv = lock_argv()
    rc, _, err = await _run(argv)
    return argv, ToolResult(
        ok=rc == 0,
        summary="screen locked" if rc == 0 else "lock failed",
        error=None if rc == 0 else err.strip() or f"exit {rc}",
    )


def _grab(path: Path) -> None:
    import mss
    import mss.tools

    with mss.mss() as sct:
        img = sct.grab(sct.monitors[1])
        mss.tools.to_png(img.rgb, img.size, output=str(path))


async def take_screenshot() -> tuple[list[str], ToolResult]:
    SHOTS.mkdir(parents=True, exist_ok=True)
    path = SHOTS / f"shot-{time.strftime('%Y%m%d-%H%M%S')}.png"
    try:
        await asyncio.to_thread(_grab, path)
    except Exception as exc:  # noqa: BLE001
        return ["mss", str(path)], ToolResult(ok=False, summary="screenshot failed", error=str(exc))
    return ["mss", str(path)], ToolResult(
        ok=True, summary=f"saved {path.name}", data={"path": str(path)}
    )
