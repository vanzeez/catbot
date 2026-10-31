"""Sarvam audio: realtime STT session per push-to-talk turn, Bulbul TTS. Shapes per FINDINGS.

STT uses endpointing="manual": PTT start -> speech_start, frames -> audio_input,
PTT stop -> speech_end + flush, then wait for transcript.final (docs: realtime-streaming.md).
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import logging
import time
from collections.abc import Callable
from typing import Any, Protocol

log = logging.getLogger("catbot.audio")

DEFAULT_SPEAKERS = {
    "bulbul:v4-flash": {
        "hi": "simran_hi_assistant",
        "en": "simran_en_customer",
        "ta": "vijay_ta_narration",
    },
    "bulbul:v3": {"hi": "priya", "en": "priya", "ta": "priya"},
}
TTS_LANGS = {
    "bn-IN",
    "en-IN",
    "gu-IN",
    "hi-IN",
    "kn-IN",
    "ml-IN",
    "mr-IN",
    "od-IN",
    "pa-IN",
    "ta-IN",
    "te-IN",
}


class SttSession(Protocol):
    async def start(self) -> None: ...
    async def feed(self, pcm: bytes) -> None: ...
    async def stop(self) -> tuple[str, str | None]: ...


class SarvamStt:
    def __init__(
        self, api_key: str, language: str, model: str, on_partial: Callable[[str, str | None], None]
    ) -> None:
        self.api_key, self.language, self.model, self.on_partial = (
            api_key,
            language,
            model,
            on_partial,
        )
        self._stack = contextlib.AsyncExitStack()
        self._ws: Any = None
        self._finals: list[str] = []
        self._lang: str | None = None
        self._lang_conf: float | None = None
        self._final_evt = asyncio.Event()
        self._rx: asyncio.Task[None] | None = None

    async def start(self) -> None:
        from sarvamai import AsyncSarvamAI, RealtimeSpeechStart

        client = AsyncSarvamAI(api_subscription_key=self.api_key)
        self._ws = await self._stack.enter_async_context(
            client.speech_to_text_realtime_streaming.connect(
                language_code=self.language,
                model=self.model,
                stream_type="fast",
                endpointing="manual",
            )
        )
        self._rx = asyncio.create_task(self._receive())
        await self._ws.send_realtime_speech_start(RealtimeSpeechStart())

    async def _receive(self) -> None:
        async for msg in self._ws:
            ev = getattr(msg, "event", "")
            if ev == "transcript.partial":
                self._lang = getattr(msg, "language", None) or self._lang
                self.on_partial(getattr(msg, "text", ""), self._lang)
            elif ev == "transcript.final":
                self._lang = getattr(msg, "language", None) or self._lang
                self._lang_conf = getattr(msg, "language_confidence", None)
                self._finals.append(getattr(msg, "text", ""))
                self._final_evt.set()
            elif ev == "error":
                log.warning(
                    "stt error %s: %s", getattr(msg, "code", "?"), getattr(msg, "message", "")
                )
                if getattr(msg, "is_fatal", False):
                    self._final_evt.set()
                    return

    async def feed(self, pcm: bytes) -> None:
        from sarvamai import RealtimeAudioInput

        await self._ws.send_realtime_audio_input(
            RealtimeAudioInput(audio=base64.b64encode(pcm).decode())
        )

    async def stop(self) -> tuple[str, str | None]:
        from sarvamai import RealtimeEnd, RealtimeFlush, RealtimeSpeechEnd

        try:
            await self._ws.send_realtime_speech_end(RealtimeSpeechEnd())
            await self._ws.send_realtime_flush(RealtimeFlush())
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._final_evt.wait(), timeout=5)
            with contextlib.suppress(Exception):
                await self._ws.send_realtime_end(RealtimeEnd())
        finally:
            if self._rx:
                self._rx.cancel()
            with contextlib.suppress(Exception):
                await self._stack.aclose()
        # FINDINGS: Hinglish audio is detected as en-IN at ~0.63; trust detection only when sure.
        lang = self._lang if (self._lang_conf is None or self._lang_conf >= 0.8) else None
        return " ".join(t for t in self._finals if t).strip(), lang


class FakeStt:
    """--fake / no key: ignores audio and returns a scripted transcript."""

    def __init__(
        self, text: str, lang: str | None, on_partial: Callable[[str, str | None], None]
    ) -> None:
        self.text, self.lang, self.on_partial, self.frames = text, lang, on_partial, 0

    async def start(self) -> None:
        self.on_partial("…", self.lang)

    async def feed(self, pcm: bytes) -> None:
        self.frames += 1

    async def stop(self) -> tuple[str, str | None]:
        return self.text, self.lang


def tts_speaker(model: str, lang: str, override: str = "") -> str:
    """Override wins when it fits the language (v4 personas are per language)."""
    short = lang.split("-")[0]
    if override and (model != "bulbul:v4-flash" or f"_{short}" in override):
        return override
    table = DEFAULT_SPEAKERS.get(model, DEFAULT_SPEAKERS["bulbul:v4-flash"])
    return table.get(short, table["hi"])


async def synthesize(
    text: str, lang: str, *, api_key: str, model: str = "bulbul:v4-flash", speaker: str = ""
) -> tuple[bytes, str, int]:
    """Returns (wav bytes, mime, latency ms)."""
    from sarvamai import SarvamAI

    lang = lang if lang in TTS_LANGS else "hi-IN"
    client = SarvamAI(api_subscription_key=api_key)
    t = time.perf_counter()
    resp = await asyncio.wait_for(
        asyncio.to_thread(
            client.text_to_speech.convert,
            text=text[:2500],
            language_code=lang,
            model=model,
            speaker=tts_speaker(model, lang, speaker),
            speech_sample_rate=24000,
            output_audio_codec="wav",
        ),
        timeout=15,
    )
    audio = base64.b64decode(resp.audios[0])
    return audio, "audio/wav", int((time.perf_counter() - t) * 1000)
