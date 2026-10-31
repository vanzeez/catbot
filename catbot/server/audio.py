"""Voice plumbing: AudioHub (TTS out to renderers, barge-in) and the /audio WebSocket handler."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from catbot.config import Settings
from catbot.core.confirm import ServerConfirm
from catbot.core.events import EventBus
from catbot.integrations.sarvam_audio import FakeStt, SarvamStt, SttSession, synthesize

log = logging.getLogger("catbot.server.audio")


class AudioHub:
    def __init__(self, settings: Settings) -> None:
        self.s = settings
        self.sockets: set[WebSocket] = set()
        self._speaking: asyncio.Task[Any] | None = None

    @property
    def can_speak(self) -> bool:
        return self.s.has_sarvam and not self.s.fakes and bool(self.sockets)

    async def speak(self, text: str, lang: str) -> None:
        """Synthesize with Bulbul and push to every renderer. Cancelled by barge_in()."""
        if not self.can_speak:
            return
        self._speaking = asyncio.create_task(self._synth_and_send(text, lang))
        with contextlib.suppress(asyncio.CancelledError):
            await self._speaking

    async def _synth_and_send(self, text: str, lang: str) -> None:
        audio, mime, ms = await synthesize(
            text,
            lang,
            api_key=self.s.sarvam_api_key.get_secret_value(),
            model=self.s.tts_model or "bulbul:v4-flash",
            speaker=self.s.tts_speaker,
        )
        for ws in list(self.sockets):
            try:
                await ws.send_text(
                    json.dumps({"type": "tts", "lang": lang, "mime": mime, "tts_ms": ms})
                )
                await ws.send_bytes(audio)
            except Exception:  # noqa: BLE001
                self.sockets.discard(ws)

    def barge_in(self) -> None:
        if self._speaking and not self._speaking.done():
            self._speaking.cancel()


class HubSpeaker:
    """Serve-mode Speaker: Bulbul through the hub (no-op without key or renderer)."""

    def __init__(self, hub: AudioHub) -> None:
        self.hub = hub

    async def speak(self, text: str, lang: str) -> None:
        await self.hub.speak(text, lang)


async def audio_socket(
    ws: WebSocket,
    *,
    settings: Settings,
    hub: AudioHub,
    bus: EventBus,
    confirm: ServerConfirm,
    start_task: Any,
) -> None:
    await ws.accept()
    hub.sockets.add(ws)
    session: SttSession | None = None
    turn = "voice"

    def partial(text: str, lang: str | None) -> None:
        bus.emit(turn, "listen", partial=text, lang=lang)

    try:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            if msg.get("bytes") is not None:
                if session is not None:
                    await session.feed(msg["bytes"])
                continue
            data = json.loads(msg.get("text") or "{}")
            if data.get("type") != "ptt":
                continue
            if data.get("action") == "start":
                hub.barge_in()
                if settings.has_sarvam and not settings.fakes:
                    session = SarvamStt(
                        settings.sarvam_api_key.get_secret_value(),
                        settings.stt_language,
                        settings.stt_model,
                        partial,
                    )
                else:
                    session = FakeStt(
                        data.get("fake_text") or "volume kam karo",
                        data.get("lang") or settings.reply_lang,
                        partial,
                    )
                try:
                    await session.start()
                except Exception as exc:  # noqa: BLE001
                    bus.emit(turn, "error", message=f"stt start failed: {exc}")
                    session = None
            elif data.get("action") == "stop" and session is not None:
                text, lang = await session.stop()
                session = None
                # FINDINGS: Saaras tags Hinglish as en-IN; this product is Hinglish-first, so en-IN
                # replies use REPLY_LANG (Hindi voice, Hinglish copy). ta-IN and hi-IN pass through.
                lang = lang if lang and lang not in ("auto", "en-IN") else settings.reply_lang
                bus.emit(turn, "listen", final=text, lang=lang)
                if not text:
                    continue
                if confirm.has_pending:
                    confirm.resolve_any(text)
                else:
                    start_task(text, lang)
    except WebSocketDisconnect:
        pass
    finally:
        hub.sockets.discard(ws)
        if session is not None:
            with contextlib.suppress(Exception):
                await session.stop()
