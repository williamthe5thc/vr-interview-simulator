"""
Render ONE interviewer line for the static web demo (same recipe as the first render):
  Kokoro af_heart at speed 1.0 via the worker on 127.0.0.1:8771 -> silence trimmed at -45 dB (ffmpeg) -> trimmed WAV
  -> Rhubarb 1.14.0 `-d dialog.txt -r pocketSphinx -f json --extendedShapes GHX` -> cues [{"s","e","v"}]
  -> OGG Vorbis mono 64 kbps 24 kHz.

    .venv\\Scripts\\python.exe tools\\web_render.py NODE_ID "The line" OUT_DIR
writes OUT_DIR\\NODE_ID.ogg and OUT_DIR\\NODE_ID.cues.json. Local only: no API.
"""
import json
import os
import subprocess
import sys
import tempfile

import requests

RHUBARB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools", "rhubarb", "Rhubarb-Lip-Sync-1.14.0-Windows", "rhubarb.exe")
FFMPEG = "ffmpeg"
TRIM = ("silenceremove=start_periods=1:start_silence=0.05:start_threshold=-45dB,areverse,"
        "silenceremove=start_periods=1:start_silence=0.05:start_threshold=-45dB,areverse")


def render(node_id, text, out_dir, voice="af_heart"):
    os.makedirs(out_dir, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        raw, trimmed, dialog, cues = (os.path.join(tmp, n) for n in ("raw.wav", "trimmed.wav", "dialog.txt", "cues.json"))
        r = requests.post("http://127.0.0.1:8771/synthesize", json={"text": text, "voice": voice, "speed": 1.0}, timeout=60)
        r.raise_for_status()
        open(raw, "wb").write(r.content)
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", raw, "-af", TRIM, "-ac", "1", "-ar", "24000", trimmed], check=True)
        open(dialog, "w", encoding="utf-8").write(text)
        subprocess.run([RHUBARB, trimmed, "-d", dialog, "-r", "pocketSphinx", "-f", "json", "--extendedShapes", "GHX", "--quiet", "-o", cues], check=True)
        mouth = json.load(open(cues, encoding="utf-8"))["mouthCues"]
        out_cues = [{"s": round(c["start"], 2), "e": round(c["end"], 2), "v": c["value"]} for c in mouth]
        with open(os.path.join(out_dir, f"{node_id}.cues.json"), "w", encoding="utf-8") as f:
            json.dump(out_cues, f, separators=(",", ":"))
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", trimmed, "-c:a", "libvorbis", "-ac", "1", "-b:a", "64k", "-ar", "24000",
                        os.path.join(out_dir, f"{node_id}.ogg")], check=True)
    return os.path.join(out_dir, f"{node_id}.ogg")


if __name__ == "__main__":
    print(render(sys.argv[1], sys.argv[2], sys.argv[3]))
