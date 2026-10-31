"""
Offline voice comparison, part 1: Kokoro (ONNX, CPU) and Piper. Writes WAV files + timings, nothing touches the headset.

    .venv_tts\\Scripts\\python.exe tools\\tts_ab_kokoro_piper.py

Output: tts_ab\\kokoro\\<voice>__<n>.wav, tts_ab\\piper\\<voice>__<n>.wav and tts_ab\\timings_kokoro_piper.json
(part 2, tools\\tts_ab_xtts.py, makes the XTTS control files in the server's own environment).
"""
import glob
import json
import os
import sys
import time
import wave

import site

for _sp in site.getsitepackages():   # pip-installed CUDA libraries for onnxruntime-gpu
    for _sub in (r"nvidia\cublas\bin", r"nvidia\cudnn\bin", r"nvidia\cuda_runtime\bin", r"nvidia\cufft\bin", r"nvidia\curand\bin", r"nvidia\cuda_nvrtc\bin", r"nvidia\nvjitlink\bin"):
        _d = os.path.join(_sp, _sub)
        if os.path.isdir(_d):
            os.add_dll_directory(_d)
            os.environ["PATH"] = _d + os.pathsep + os.environ["PATH"]
os.environ.setdefault("ONNX_PROVIDER", "CUDAExecutionProvider")   # kokoro-onnx reads this

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "tts_ab")
SENTENCES = [
    "Hi there, Marcus here from Harbor Telecom. Could you tell me a bit about yourself and why you're interested in this role?",
    "Okay, so you built a ticket triage process. How would you contact a customer about a problem when you do not yet have all the answers?",
    "Got it. Do you believe the customer is always right, and why or why not?",
    "Hm, that sounds like a tough spot. Can you walk me through what you did first?",
    "Do you have any questions for me about the role, the team, or the company?",
    "Sorry, I didn't quite catch that. Could you say that again?",
    "Thank you for your time today, I really enjoyed our conversation. We'll be in touch within about a week. Take care!",
]
KOKORO_FEMALE = ["af_heart", "af_bella", "af_nicole", "af_sarah", "af_sky", "af_nova", "af_jessica", "bf_emma", "bf_isabella", "bf_alice"]
KOKORO_MALE = ["am_adam", "am_michael", "am_eric", "am_liam", "am_onyx", "am_fenrir", "am_puck", "bm_george", "bm_lewis", "bm_daniel", "bm_fable"]


def main():
    from kokoro_onnx import Kokoro
    timings = {"kokoro": {}, "piper": {}}
    kdir = os.path.join(ROOT, "models", "kokoro")
    model_file = sys.argv[1] if len(sys.argv) > 1 else "kokoro-v1.0.onnx"
    k = Kokoro(os.path.join(kdir, model_file), os.path.join(kdir, "voices-v1.0.bin"))
    available = set(k.get_voices())
    print("kokoro voices available:", len(available), sorted(available)[:60])
    os.makedirs(os.path.join(OUT, "kokoro"), exist_ok=True)
    k.create("Warm up.", voice="af_heart", speed=1.0, lang="en-us")
    for voice in [v for v in KOKORO_FEMALE + KOKORO_MALE if v in available]:
        rows = []
        for i, text in enumerate(SENTENCES, 1):
            t = time.time()
            samples, sr = k.create(text, voice=voice, speed=1.0, lang="en-gb" if voice.startswith("b") else "en-us")
            dt = time.time() - t
            sf.write(os.path.join(OUT, "kokoro", f"{voice}__{i}.wav"), samples, sr, subtype="PCM_16")
            rows.append({"n": i, "chars": len(text), "synth_s": round(dt, 2), "audio_s": round(len(samples) / sr, 2)})
        timings["kokoro"][voice] = rows
        print(f"kokoro {voice:12s} avg synth {np.mean([r['synth_s'] for r in rows]):.2f}s per sentence, rtf {sum(r['synth_s'] for r in rows) / sum(r['audio_s'] for r in rows):.2f}")

    # Piper: the .onnx voices already downloaded for AllTalk
    try:
        from piper import PiperVoice
        piper_dir = r"D:\AllTalk\alltalk_tts\models\piper"
        models = sorted(glob.glob(os.path.join(piper_dir, "en_US-*.onnx")))[:6] + sorted(glob.glob(os.path.join(piper_dir, "en_GB-*.onnx")))[:6]
        os.makedirs(os.path.join(OUT, "piper"), exist_ok=True)
        for path in models:
            name = os.path.basename(path).replace(".onnx", "")
            try:
                voice = PiperVoice.load(path)
                rows = []
                for i, text in enumerate(SENTENCES[:3], 1):
                    t = time.time()
                    with wave.open(os.path.join(OUT, "piper", f"{name}__{i}.wav"), "wb") as w:
                        voice.synthesize_wav(text, w)
                    dt = time.time() - t
                    with wave.open(os.path.join(OUT, "piper", f"{name}__{i}.wav")) as w:
                        audio_s = w.getnframes() / w.getframerate()
                    rows.append({"n": i, "chars": len(text), "synth_s": round(dt, 2), "audio_s": round(audio_s, 2)})
                timings["piper"][name] = rows
                print(f"piper  {name:40s} avg synth {np.mean([r['synth_s'] for r in rows]):.2f}s per sentence")
            except Exception as e:
                print(f"piper {name} failed: {e}")
    except Exception as e:
        print("piper unavailable:", e)
    json.dump(timings, open(os.path.join(OUT, "timings_kokoro_piper.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
