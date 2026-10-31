"""P1 smoke: Sarvam realtime STT. Streams a 16 kHz int16 WAV in 100 ms chunks, prints every event.

Run: python scripts/smoke_tts.py first (creates data/cache/tts_bulbul_v3.wav), then this.
"""

from __future__ import annotations

import asyncio
import base64
import sys
import time
import wave
from pathlib import Path

from _smoke_common import need, settings, show

WAV = Path(__file__).resolve().parents[1] / "data" / "cache" / "tts_bulbul_v3.wav"


def pcm_from(path: Path) -> bytes:
    with wave.open(str(path)) as w:
        assert w.getframerate() == 16000 and w.getnchannels() == 1 and w.getsampwidth() == 2, (
            "need 16 kHz mono int16"
        )
        return w.readframes(w.getnframes())


async def main() -> None:
    need(settings.has_sarvam, "SARVAM_API_KEY")
    from sarvamai import AsyncSarvamAI, RealtimeAudioInput, RealtimeEnd

    path = Path(sys.argv[1]) if len(sys.argv) > 1 else WAV
    pcm = pcm_from(path) + b"\x00" * 32000  # 1 s trailing silence so VAD ends the turn
    client = AsyncSarvamAI(api_subscription_key=settings.sarvam_api_key.get_secret_value())
    t0 = time.perf_counter()
    async with client.speech_to_text_realtime_streaming.connect(
        language_code=settings.stt_language, model=settings.stt_model, stream_type="fast"
    ) as ws:

        async def send() -> None:
            for i in range(0, len(pcm), 3200):
                await ws.send_realtime_audio_input(
                    RealtimeAudioInput(audio=base64.b64encode(pcm[i : i + 3200]).decode())
                )
                await asyncio.sleep(0.1)
            await ws.send_realtime_end(RealtimeEnd())

        async def recv() -> None:
            async for msg in ws:
                print(f"{(time.perf_counter() - t0) * 1000:6.0f} ms", type(msg).__name__)
                show(getattr(msg, "event", "?"), msg)
                if getattr(msg, "event", "") in {"transcript.final", "session.end"}:
                    if msg.event == "session.end":
                        return
                if getattr(msg, "event", "") == "error" and getattr(msg, "is_fatal", False):
                    return

        await asyncio.wait_for(asyncio.gather(send(), recv()), timeout=30)


if __name__ == "__main__":
    asyncio.run(main())
