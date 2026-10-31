import asyncio
import json
import time

from pydantic import SecretStr

from catbot.config import load_settings
from catbot.server import audio


class FakeWS:
    def __init__(self):
        self.sent = []

    async def send_text(self, t):
        self.sent.append(("text", json.loads(t)))

    async def send_bytes(self, b):
        self.sent.append(("bytes", b))


def hub(monkeypatch, delay):
    async def fake_synth(text, lang, **kw):
        await asyncio.sleep(delay)
        return b"RIFFfake", "audio/wav", int(delay * 1000)

    monkeypatch.setattr(audio, "synthesize", fake_synth)
    s = load_settings(fakes=False, sarvam_api_key=SecretStr("k"), failproof_mode="off")
    h = audio.AudioHub(s)
    ws = FakeWS()
    h.sockets.add(ws)
    return h, ws


async def test_tts_sent_header_then_bytes(monkeypatch):
    h, ws = hub(monkeypatch, 0.01)
    await h.speak("Volume kam kar diya.", "hi-IN")
    assert ws.sent[0] == (
        "text",
        {"type": "tts", "lang": "hi-IN", "mime": "audio/wav", "tts_ms": 10},
    )
    assert ws.sent[1] == ("bytes", b"RIFFfake")


async def test_barge_in_cancels_synthesis_fast(monkeypatch):
    h, ws = hub(monkeypatch, 2.0)
    task = asyncio.create_task(h.speak("long answer", "hi-IN"))
    await asyncio.sleep(0.05)
    t = time.perf_counter()
    h.barge_in()
    await task
    assert (time.perf_counter() - t) < 0.1 and ws.sent == []


async def test_no_speech_without_key_or_renderer(monkeypatch):
    h, ws = hub(monkeypatch, 0.0)
    h.s.fakes = True
    await h.speak("x", "hi-IN")
    assert ws.sent == []
