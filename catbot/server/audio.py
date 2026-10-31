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
from catbot.server.wake import WakeListener, WakeRouter

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
    """PTT turns ({type: ptt}) and always-on wake word mode ({type: wake, action: on|off})."""
    await ws.accept()
    hub.sockets.add(ws)
    session: SttSession | None = None
    wake: WakeListener | None = None
    turn = "voice"
    live = settings.has_sarvam and not settings.fakes

    def partial(text: str, lang: str | None) -> None:
        bus.emit(turn, "listen", partial=text, lang=lang)

    def reply_lang(detected: str | None) -> str:
        if settings.match_user_lang and detected and detected != "auto":
            return detected
        return settings.reply_lang

    async def ack() -> None:  # bare "meow": chirp and listen for the command
        bus.emit(
            turn, "listen", partial="Meow? I'm listening…", lang=settings.reply_lang, wake="armed"
        )
        with contextlib.suppress(Exception):
            await ws.send_text(json.dumps({"type": "wake_ack"}))

    router = WakeRouter(
        has_confirm=lambda: confirm.has_pending,
        resolve_confirm=confirm.resolve_any,
        start_task=start_task,
        ack=ack,
        reply_lang=settings.reply_lang,
    )

    async def on_wake_final(text: str) -> None:
        outcome = await router.on_final(text)
        if outcome in ("command", "confirm"):  # ambient speech is never shown or stored
            bus.emit(turn, "listen", final=text, lang=settings.reply_lang, wake=outcome)

    def wake_partial(text: str) -> None:
        if router.armed and text:
            bus.emit(turn, "listen", partial=text, lang=settings.reply_lang)

    try:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            if msg.get("bytes") is not None:
                if session is not None:
                    await session.feed(msg["bytes"])
                elif wake is not None:
                    await wake.feed(msg["bytes"])
                continue
            data = json.loads(msg.get("text") or "{}")
            kind, action = data.get("type"), data.get("action")
            if kind == "wake" and action == "on" and wake is None:
                if live:
                    wake = WakeListener(
                        settings.sarvam_api_key.get_secret_value(),
                        settings.stt_language,
                        settings.stt_model,
                        on_wake_final,
                        wake_partial,
                    )
                    await wake.start()
                await ws.send_text(json.dumps({"type": "wake_state", "on": True, "live": live}))
            elif kind == "wake" and action == "off":
                if wake is not None:
                    await wake.stop()
                    wake = None
                await ws.send_text(json.dumps({"type": "wake_state", "on": False, "live": live}))
            elif kind == "wake_text":  # fakes / tests: simulate a heard sentence
                await on_wake_final(str(data.get("text", "")))
            elif kind == "ptt" and action == "start":
                hub.barge_in()
                if live:
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
            elif kind == "ptt" and action == "stop" and session is not None:
                text, lang = await session.stop()
                session = None
                lang = reply_lang(lang)
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
        if wake is not None:
            await wake.stop()
