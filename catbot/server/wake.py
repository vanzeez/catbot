"""Always-on wake word: a long-lived Sarvam STT session (server VAD) plus a router that decides
what each final transcript means. Audio arrives only while the renderer's energy gate is open."""

from __future__ import annotations

import asyncio
import base64
import contextlib
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from catbot.core.wake import split_wake

log = logging.getLogger("catbot.wake")


class WakeRouter:
    """Pure decision logic, so it is unit-testable without audio."""

    def __init__(
        self,
        *,
        has_confirm: Callable[[], bool],
        resolve_confirm: Callable[[str], Any],
        start_task: Callable[[str, str | None], Any],
        ack: Callable[[], Awaitable[None]],
        reply_lang: str,
    ) -> None:
        self.has_confirm, self.resolve_confirm = has_confirm, resolve_confirm
        self.start_task, self.ack, self.reply_lang = start_task, ack, reply_lang
        self.active = False  # after "meow": every sentence is a command until paused

    @property
    def armed(self) -> bool:  # kept for callers: true while in active mode
        return self.active

    @property
    def mode(self) -> str:
        return "active" if self.active else "waiting"

    def pause(self) -> None:
        self.active = False

    async def on_final(self, text: str) -> str:
        """Returns what happened: confirm | command | armed | ignored."""
        text = (text or "").strip()
        if not text:
            return "ignored"
        if self.has_confirm():  # an answer to "Shall I…?" needs no wake word
            self.resolve_confirm(split_wake(text)[1] or text)
            return "confirm"
        woke, rest = split_wake(text)
        if woke and not self.active:
            self.active = True
            await self.ack()
            if not rest:
                return "armed"
        if self.active:
            self.start_task(rest if woke else text, self.reply_lang)
            return "command"
        return "ignored"


class WakeListener:
    """Continuous Saaras session with server-side VAD; reconnects and pings to stay open."""

    def __init__(
        self,
        api_key: str,
        language: str,
        model: str,
        on_final: Callable[[str], Awaitable[Any]],
        on_partial: Callable[[str], None] | None = None,
    ) -> None:
        self.api_key, self.language, self.model = api_key, language, model
        self.on_final, self.on_partial = on_final, on_partial
        self._ws: Any = None
        self._task: asyncio.Task[None] | None = None
        self._ready = asyncio.Event()
        self._stop = False

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run())
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._ready.wait(), 10)

    async def _run(self) -> None:
        from sarvamai import AsyncSarvamAI, RealtimePing

        backoff = 1.0
        while not self._stop:
            try:
                client = AsyncSarvamAI(api_subscription_key=self.api_key)
                async with client.speech_to_text_realtime_streaming.connect(
                    language_code=self.language,
                    model=self.model,
                    stream_type="fast",
                    endpointing="vad",
                    silence_duration_ms="600",
                ) as ws:
                    self._ws, backoff = ws, 1.0
                    self._ready.set()

                    async def ping() -> None:
                        while True:
                            await asyncio.sleep(15)
                            await ws.send_realtime_ping(RealtimePing(event="ping"))

                    pinger = asyncio.create_task(ping())
                    try:
                        async for msg in ws:
                            ev = getattr(msg, "event", "")
                            if ev == "transcript.final":
                                await self.on_final(getattr(msg, "text", ""))
                            elif ev == "transcript.partial" and self.on_partial:
                                self.on_partial(getattr(msg, "text", ""))
                            elif ev == "error" and getattr(msg, "is_fatal", False):
                                break
                    finally:
                        pinger.cancel()
            except Exception as exc:  # noqa: BLE001 - reconnect on any socket failure
                log.warning("wake listener reconnecting after %s", type(exc).__name__)
            self._ws = None
            if not self._stop:
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 15)

    async def feed(self, pcm: bytes) -> None:
        if self._ws is None:
            return
        from sarvamai import RealtimeAudioInput

        with contextlib.suppress(Exception):
            await self._ws.send_realtime_audio_input(
                RealtimeAudioInput(audio=base64.b64encode(pcm).decode())
            )

    async def stop(self) -> None:
        self._stop = True
        if self._task:
            self._task.cancel()
            with contextlib.suppress(BaseException):
                await self._task
