"""Retry with exponential backoff on HTTP 429 / 503 and timeouts."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")
log = logging.getLogger("catbot.retry")
RETRY_STATUS = {429, 503}


def is_retryable(exc: BaseException) -> bool:
    status = getattr(exc, "status_code", None) or getattr(
        getattr(exc, "response", None), "status_code", None
    )
    return status in RETRY_STATUS or isinstance(exc, TimeoutError)


async def retry_async(
    fn: Callable[[], Awaitable[T]], *, attempts: int = 3, base_delay: float = 0.5
) -> T:
    for i in range(attempts):
        try:
            return await fn()
        except Exception as exc:
            if i == attempts - 1 or not is_retryable(exc):
                raise
            delay = base_delay * (2**i)
            log.warning("retryable %s, retry %d in %.1fs", type(exc).__name__, i + 1, delay)
            await asyncio.sleep(delay)
    raise RuntimeError("unreachable")
