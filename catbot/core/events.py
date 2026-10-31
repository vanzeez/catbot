"""EventBus: publish Events to SQLite, a 50-event ring, async subscribers and sync listeners."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections import deque
from collections.abc import Callable
from typing import Any

from catbot.contracts import Event, Stage
from catbot.core.store import Store, now

log = logging.getLogger("catbot.events")


class EventBus:
    def __init__(self, store: Store | None = None) -> None:
        self.store = store
        self.recent: deque[Event] = deque(maxlen=50)
        self._queues: set[asyncio.Queue[Event]] = set()
        self._listeners: list[Callable[[Event], None]] = []

    def listen(self, fn: Callable[[Event], None]) -> None:
        self._listeners.append(fn)

    def subscribe(self) -> asyncio.Queue[Event]:
        q: asyncio.Queue[Event] = asyncio.Queue(maxsize=500)
        self._queues.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[Event]) -> None:
        self._queues.discard(q)

    def publish(self, event: Event) -> Event:
        self.recent.append(event)
        if self.store is not None:
            self.store.add_event(event.task_id, event.stage, event.model_dump_json())
        for q in list(self._queues):
            with contextlib.suppress(asyncio.QueueFull):
                q.put_nowait(event)
        for fn in self._listeners:
            try:
                fn(event)
            except Exception:  # noqa: BLE001 - a listener must never break the loop
                log.exception("event listener failed")
        return event

    def emit(
        self,
        task_id: str,
        stage: Stage,
        *,
        step: int | None = None,
        tool: str | None = None,
        verdict: str | None = None,
        latency_ms: int | None = None,
        payload: dict[str, Any] | None = None,
        **kw: Any,
    ) -> Event:
        body = {**(payload or {}), **kw}
        return self.publish(
            Event(
                ts=now(),
                task_id=task_id,
                stage=stage,
                step=step,
                tool=tool,
                verdict=verdict,
                latency_ms=latency_ms,
                payload=body,
            )
        )
