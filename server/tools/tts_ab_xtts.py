"""
Offline voice comparison, part 2: the current XTTS voices (through the running AllTalk) on the SAME sentences.

    .venv\\Scripts\\python.exe tools\\tts_ab_xtts.py

Writes tts_ab\\xtts\\<voice>__<n>.wav and tts_ab\\timings_xtts.json. Needs AllTalk running. Part 1: tools\\tts_ab_kokoro_piper.py.
"""
import io
import json
import os
import sys
import time
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
from services.audio.tts import TTSService  # noqa: E402
import ast  # noqa: E402
_src = open(os.path.join(ROOT, 'tools', 'tts_ab_kokoro_piper.py'), encoding='utf-8').read()
SENTENCES = ast.literal_eval(_src.split("SENTENCES = ")[1].split("KOKORO_FEMALE")[0])   # same sentences as part 1

VOICES = ["female_06.wav", "female_03.wav", "female_01.wav", "female_05.wav",
          "male_01.wav", "male_02.wav", "male_03.wav", "male_04.wav", "male_05.wav"]


def main():
    cfg = json.load(open(os.path.join(ROOT, "config", "config.json"), encoding="utf-8"))
    tts = TTSService(config=cfg)
    out = os.path.join(ROOT, "tts_ab", "xtts")
    os.makedirs(out, exist_ok=True)
    timings = {}
    tts.synthesize("Warm up.")
    for voice in VOICES:
        tts.set_voice(voice)
        rows = []
        for i, text in enumerate(SENTENCES, 1):
            t = time.time()
            data = tts.synthesize(text)
            dt = time.time() - t
            with open(os.path.join(out, f"{voice.replace('.wav', '')}__{i}.wav"), "wb") as f:
                f.write(data)
            with wave.open(io.BytesIO(data)) as w:
                audio_s = w.getnframes() / w.getframerate()
            rows.append({"n": i, "chars": len(text), "synth_s": round(dt, 2), "audio_s": round(audio_s, 2)})
        timings[voice] = rows
        print(f"xtts {voice:14s} avg synth {sum(r['synth_s'] for r in rows) / len(rows):.2f}s per sentence", flush=True)
    json.dump(timings, open(os.path.join(ROOT, "tts_ab", "timings_xtts.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
