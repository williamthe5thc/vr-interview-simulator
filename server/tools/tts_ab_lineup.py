"""
Offline voice comparison, part 3: the 11 headset interviewers, each saying the same two lines, in the current XTTS voice and in a
suggested Kokoro voice. Then builds tts_ab\\index.html (double-click it to listen).

    .venv_tts\\Scripts\\python.exe tools\\tts_ab_lineup.py kokoro     # needs the GPU libraries of .venv_tts
    .venv\\Scripts\\python.exe     tools\\tts_ab_lineup.py xtts       # needs AllTalk running
    .venv\\Scripts\\python.exe     tools\\tts_ab_lineup.py page       # writes tts_ab\\index.html
"""
import glob
import html
import io
import json
import os
import site
import sys
import time
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "tts_ab")

# name -> (current XTTS voice file from the headset roster, suggested Kokoro voice)
CAST = {
    "Dana Whitfield":  ("female_06.wav", "af_heart"),
    "Margaret Ellis":  ("female_03.wav", "bf_emma"),
    "Linda Foster":    ("female_01.wav", "af_nicole"),
    "Rachel Grant":    ("female_05.wav", "af_bella"),
    "Daniel Hayes":    ("male_01.wav", "am_michael"),
    "Marcus Reed":     ("male_02.wav", "am_onyx"),
    "Eric Carter":     ("male_03.wav", "am_eric"),
    "Victor Brooks":   ("male_04.wav", "bm_george"),
    "Samuel Hughes":   ("male_05.wav", "am_adam"),
    "Thomas Irwin":    ("male_02.wav", "bm_lewis"),
    "Gregory Jensen":  ("male_01.wav", "bm_daniel"),
}


def lines(name):
    first = name.split()[0]
    return [f"Hi there, {first} here from Harbor Telecom. Could you tell me a bit about yourself and why you're interested in this role?",
            "Okay, so you built a ticket triage process. How would you contact a customer about a problem when you do not yet have all the answers?"]


def make_kokoro():
    for sp in site.getsitepackages():
        for sub in (r"nvidia\cublas\bin", r"nvidia\cudnn\bin", r"nvidia\cuda_runtime\bin", r"nvidia\cufft\bin", r"nvidia\curand\bin", r"nvidia\cuda_nvrtc\bin", r"nvidia\nvjitlink\bin"):
            d = os.path.join(sp, sub)
            if os.path.isdir(d):
                os.add_dll_directory(d)
                os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]
    os.environ.setdefault("ONNX_PROVIDER", "CUDAExecutionProvider")
    import numpy as np
    import soundfile as sf
    from kokoro_onnx import Kokoro
    kd = os.path.join(ROOT, "models", "kokoro")
    k = Kokoro(os.path.join(kd, "kokoro-v1.0.onnx"), os.path.join(kd, "voices-v1.0.bin"))
    os.makedirs(os.path.join(OUT, "lineup_kokoro"), exist_ok=True)
    for name, (_, voice) in CAST.items():
        parts, sr = [], 24000
        for text in lines(name):
            t = time.time()
            a, sr = k.create(text, voice=voice, lang="en-gb" if voice.startswith("b") else "en-us")
            parts += [a, np.zeros(int(0.5 * sr), dtype=np.float32)]
        sf.write(os.path.join(OUT, "lineup_kokoro", name.replace(" ", "_") + ".wav"), np.concatenate(parts), sr, subtype="PCM_16")
        print("kokoro", name, voice, flush=True)


def make_xtts():
    sys.path.insert(0, ROOT)
    os.chdir(ROOT)
    from services.audio.tts import TTSService
    tts = TTSService(config=json.load(open(os.path.join(ROOT, "config", "config.json"), encoding="utf-8")))
    os.makedirs(os.path.join(OUT, "lineup_xtts"), exist_ok=True)
    for name, (voice, _) in CAST.items():
        tts.set_voice(voice)
        frames, params = [], None
        for text in lines(name):
            with wave.open(io.BytesIO(tts.synthesize(text))) as w:
                params = w.getparams()
                frames.append(w.readframes(w.getnframes()))
                frames.append(b"\x00\x00" * int(0.5 * w.getframerate()))
        with wave.open(os.path.join(OUT, "lineup_xtts", name.replace(" ", "_") + ".wav"), "wb") as w:
            w.setparams(params)
            w.writeframes(b"".join(frames))
        print("xtts", name, voice, flush=True)


def make_page():
    def audio(path):
        return f'<audio controls preload="none" src="{html.escape(os.path.relpath(path, OUT).replace(os.sep, "/"))}"></audio>'
    rows = []
    for name, (xv, kv) in CAST.items():
        f = name.replace(" ", "_") + ".wav"
        rows.append(f"<tr><td><b>{html.escape(name)}</b></td><td>{audio(os.path.join(OUT, 'lineup_xtts', f))}<br><small>XTTS {xv}</small></td>"
                    f"<td>{audio(os.path.join(OUT, 'lineup_kokoro', f))}<br><small>Kokoro {kv}</small></td></tr>")
    timing = {}
    for fn in ("timings_xtts.json", "timings_kokoro_piper.json"):
        p = os.path.join(OUT, fn)
        if os.path.exists(p):
            timing.update(json.load(open(p)) if fn != "timings_xtts.json" else {"xtts": json.load(open(p))})

    def avg(group):
        rows_ = [r["synth_s"] for v in group.values() for r in v]
        return sum(rows_) / len(rows_) if rows_ else float("nan")
    speed = (f"XTTS (now): {avg(timing.get('xtts', {})):.2f} s per sentence, "
             f"Kokoro on GPU: {avg(timing.get('kokoro', {})):.2f} s per sentence, "
             f"Piper on CPU: {avg(timing.get('piper', {})):.2f} s per sentence (same machine, same 7 sentences)")
    more = []
    for engine in ("xtts", "kokoro"):
        names = sorted({os.path.basename(p).split("__")[0] for p in glob.glob(os.path.join(OUT, engine, "*__1.wav"))})
        cells = "".join(f"<tr><td>{n}</td>" + "".join(f"<td>{audio(os.path.join(OUT, engine, f'{n}__{i}.wav'))}</td>" for i in (1, 2, 7)) + "</tr>" for n in names)
        more.append(f"<h2>All {engine} voices (greeting, question, goodbye)</h2><table>{cells}</table>")
    page = f"""<!doctype html><meta charset="utf-8"><title>Voice comparison</title>
<style>body{{font-family:Segoe UI,Arial,sans-serif;margin:24px;max-width:1000px}}td{{padding:6px 12px;vertical-align:top}}table{{border-collapse:collapse}}tr:nth-child(even){{background:#f3f3f3}}</style>
<h1>Interviewer voice comparison</h1><p>{html.escape(speed)}</p>
<h2>The 11 interviewers: same two lines, current voice vs suggested Kokoro voice</h2>
<table><tr><th></th><th>Now (XTTS)</th><th>Kokoro</th></tr>{''.join(rows)}</table>{''.join(more)}"""
    open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(page)
    print("wrote", os.path.join(OUT, "index.html"))


if __name__ == "__main__":
    {"kokoro": make_kokoro, "xtts": make_xtts, "page": make_page}[sys.argv[1]]()
