"""ConfirmChannel implementations: TextConfirm (stdin / --yes / --no) and ServerConfirm."""

from __future__ import annotations

import asyncio
import contextlib
import threading
from collections.abc import Awaitable, Callable


class TextConfirm:
    def __init__(self, auto: str | None = None) -> None:
        self.auto = auto  # "haan" for --yes, "nahi" for --no

    async def ask(
        self, task_id: str, question: str, lang: str, timeout_s: float = 8.0
    ) -> str | None:
        print(f"  ? {question}")
        if self.auto is not None:
            print(f"  > {self.auto} (auto)")
            return self.auto
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[str] = loop.create_future()

        def read() -> None:  # daemon thread so a pending input() never blocks exit
            try:
                line = input("  > ")
            except EOFError:
                line = ""
            loop.call_soon_threadsafe(lambda: fut.done() or fut.set_result(line))

        threading.Thread(target=read, daemon=True).start()
        try:
            return await asyncio.wait_for(fut, timeout_s)
        except TimeoutError:
            return None


class ServerConfirm:
    """Resolves on the first of POST /api/confirm, the next voice transcript, or the timeout."""

    def __init__(self, speak: Callable[[str, str], Awaitable[None]] | None = None) -> None:
        self.speak = speak
        self.pending: dict[str, asyncio.Future[str]] = {}

    async def ask(
        self, task_id: str, question: str, lang: str, timeout_s: float = 8.0
    ) -> str | None:
        fut: asyncio.Future[str] = asyncio.get_running_loop().create_future()
        self.pending[task_id] = fut
        try:
            if self.speak is not None:
                with contextlib.suppress(Exception):
                    await asyncio.wait_for(asyncio.shield(self.speak(question, lang)), 6)
            return await asyncio.wait_for(fut, timeout_s)
        except TimeoutError:
            return None
        finally:
            self.pending.pop(task_id, None)

    def resolve(self, task_id: str, reply: str) -> bool:
        fut = self.pending.get(task_id)
        if fut is None or fut.done():
            return False
        fut.set_result(reply)
        return True

    def resolve_any(self, reply: str) -> bool:
        """Voice path: answer the oldest pending question, if any."""
        return any(self.resolve(tid, reply) for tid in list(self.pending))

    @property
    def has_pending(self) -> bool:
        return any(not f.done() for f in self.pending.values())
