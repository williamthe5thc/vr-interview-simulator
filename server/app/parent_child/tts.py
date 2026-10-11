"""Child-like voice for Maya: a light Kokoro voice, slowed a little and raised in pitch by resampling (this also raises the formants, like a
smaller vocal tract). Kokoro has no true child voices; whether this sounds right has to be judged by ear (tools/child_voice_test.py)."""
import io
import wave

import numpy as np
import requests

from services.audio.tts import TTSService

CHILD_VOICE = "af_jessica"       # measured about 264 Hz at x1.25 (an 8-year-old speaks at roughly 250-300 Hz)
CHILD_PITCH = 1.25
CHILD_SPEED = 0.85
NARRATOR_VOICE = "af_heart"      # calm adult voice for the fixed safety message


def pitch_shift(wav_bytes, factor):
    """Same samples played `factor` times faster: pitch and formants up by that factor, shorter by the same factor."""
    with wave.open(io.BytesIO(wav_bytes)) as w:
        rate, width, channels = w.getframerate(), w.getsampwidth(), w.getnchannels()
        samples = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
    n = max(1, int(len(samples) / factor))
    shifted = np.interp(np.linspace(0, len(samples) - 1, n), np.arange(len(samples)), samples)
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.setframerate(rate)
        w.writeframes(np.clip(shifted, -32768, 32767).astype(np.int16).tobytes())
    return out.getvalue()


class ChildTTSService(TTSService):
    def __init__(self, config=None, voice=CHILD_VOICE, pitch=CHILD_PITCH, speed=CHILD_SPEED):
        super().__init__(config=config)
        self.child_voice, self.child_pitch, self.child_speed = voice, pitch, speed
        self.narrator = False
        self.config.setdefault("cache", {})["enabled"] = False       # the cache key knows nothing of the voice or pitch

    def use_narrator(self, on):
        self.narrator = bool(on)

    def _pick_kokoro_voice(self):
        self.kokoro_voice = NARRATOR_VOICE if getattr(self, "narrator", False) else getattr(self, "child_voice", CHILD_VOICE)

    def _synthesize_kokoro(self, text):
        import time
        if time.time() < getattr(self, "_kokoro_retry_at", 0):
            return None
        cfg = self.config.get("kokoro", {})
        self._pick_kokoro_voice()
        child = not self.narrator
        try:
            response = requests.post(f"{cfg.get('url', 'http://127.0.0.1:8771')}/synthesize",
                                     json={"text": text, "voice": self.kokoro_voice, "speed": self.child_speed if child else 1.0},
                                     timeout=cfg.get("timeout", 20))
            if response.status_code == 200 and len(response.content) > 1000:
                return pitch_shift(response.content, self.child_pitch) if child else response.content
            raise RuntimeError(f"HTTP {response.status_code}: {response.text[:100]}")
        except Exception as e:
            self.logger.warning(f"Kokoro worker unavailable ({e}); using AllTalk or gTTS for the next 30 s (the voice will not be a child's)")
            self._kokoro_retry_at = time.time() + 30
            return None
