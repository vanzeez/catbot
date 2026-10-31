"""read_screen: mss grab -> RapidOCR -> text (<= 2,000 chars), origin=screen."""

from __future__ import annotations

import asyncio
from functools import cache
from typing import Any

from catbot.contracts import ToolResult

MAX_CHARS = 2000


@cache
def _engine() -> Any:
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


def ocr_image(img: Any) -> str:
    """img: numpy RGB/BGR array or path. Returns lines joined by newlines."""
    result, _ = _engine()(img)
    return "\n".join(str(r[1]) for r in (result or []))


def _grab_and_ocr() -> str:
    import mss
    import numpy as np

    with mss.mss() as sct:
        shot = sct.grab(sct.monitors[1])
        arr = np.array(shot)[:, :, :3]  # BGRA -> BGR
    return ocr_image(arr)


async def read_screen() -> tuple[list[str], ToolResult]:
    try:
        text = await asyncio.to_thread(_grab_and_ocr)
    except Exception as exc:  # noqa: BLE001
        return ["mss", "rapidocr"], ToolResult(
            ok=False, summary="read_screen failed", error=str(exc), origin="screen"
        )
    text = text[:MAX_CHARS]
    first = text.splitlines()[0][:80] if text else "(no text)"
    return ["mss", "rapidocr"], ToolResult(
        ok=True, summary=first, data={"text": text}, origin="screen"
    )
