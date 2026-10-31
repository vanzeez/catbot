"""P1 smoke: Bulbul v3 and v4-flash on Hindi. Model, speaker, format, sample rate, latency.

Run: python scripts/smoke_tts.py   (writes data/cache/tts_*.wav)
"""

from __future__ import annotations

import base64
import io
import time
import wave
from pathlib import Path

from _smoke_common import need, settings

OUT = Path(__file__).resolve().parents[1] / "data" / "cache"
CASES = [("bulbul:v3", "priya"), ("bulbul:v4-flash", None)]


def main() -> None:
    need(settings.has_sarvam, "SARVAM_API_KEY")
    from sarvamai import SarvamAI

    client = SarvamAI(api_subscription_key=settings.sarvam_api_key.get_secret_value())
    OUT.mkdir(parents=True, exist_ok=True)
    for model, speaker in CASES:
        kw = {"speaker": speaker} if speaker else {}
        t = time.perf_counter()
        try:
            r = client.text_to_speech.convert(
                text="Volume kam kar diya.",
                language_code="hi-IN",
                model=model,
                speech_sample_rate=16000,
                output_audio_codec="wav",
                **kw,
            )
        except Exception as exc:  # noqa: BLE001
            print(model, "failed:", type(exc).__name__, str(exc)[:300])
            continue
        ms = (time.perf_counter() - t) * 1000
        audio = base64.b64decode(r.audios[0])
        with wave.open(io.BytesIO(audio)) as w:
            info = (w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes())
        path = OUT / f"tts_{model.replace(':', '_')}.wav"
        path.write_bytes(audio)
        print(
            f"{model} speaker={speaker or 'default'} total={ms:.0f} ms n_audios={len(r.audios)} "
            f"bytes={len(audio)} rate/ch/width/frames={info} magic={audio[:4]!r} -> {path.name}"
        )


if __name__ == "__main__":
    main()
