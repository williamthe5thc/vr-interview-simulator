"""
Kokoro text-to-speech worker behind a tiny local HTTP API. Runs in its own virtual environment (.venv_tts) on the GPU
through onnxruntime-gpu; about 0.5 s per spoken sentence (the XTTS voice takes about 2.3 s).

    .venv_tts\\Scripts\\python.exe tools\\tts_worker.py --port 8771

    GET  /health      -> {"ok": true, "voices": N}
    POST /synthesize  {"text": "...", "voice": "af_heart", "speed": 1.0}  -> audio/wav (24 kHz, mono, 16-bit PCM, like XTTS)

The interview server (services/audio/tts.py, config engine = "kokoro") calls it and falls back to AllTalk when it is down.
"""
import argparse
import io
import json
import os
import site
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

for _sp in site.getsitepackages():   # pip-installed CUDA libraries for onnxruntime-gpu
    for _sub in (r"nvidia\cublas\bin", r"nvidia\cudnn\bin", r"nvidia\cuda_runtime\bin", r"nvidia\cufft\bin",
                 r"nvidia\curand\bin", r"nvidia\cuda_nvrtc\bin", r"nvidia\nvjitlink\bin"):
        _d = os.path.join(_sp, _sub)
        if os.path.isdir(_d):
            os.add_dll_directory(_d)
            os.environ["PATH"] = _d + os.pathsep + os.environ["PATH"]
os.environ.setdefault("ONNX_PROVIDER", "CUDAExecutionProvider")

import soundfile as sf  # noqa: E402
from kokoro_onnx import Kokoro  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCK = threading.Lock()
STATE = {"kokoro": None, "voices": set()}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, content_type="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/health"):
            self._send(200, json.dumps({"ok": STATE["kokoro"] is not None, "voices": len(STATE["voices"])}).encode())
        else:
            self._send(404, b'{"error": "not found"}')

    def do_POST(self):
        if not self.path.startswith("/synthesize"):
            return self._send(404, b'{"error": "not found"}')
        try:
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
            text = (req.get("text") or "").strip()
            voice = req.get("voice") or "af_heart"
            if voice not in STATE["voices"]:
                voice = "af_heart"
            if not text:
                return self._send(400, b'{"error": "empty text"}')
            started = time.time()
            with LOCK:
                samples, rate = STATE["kokoro"].create(text, voice=voice, speed=float(req.get("speed", 1.0)),
                                                       lang="en-gb" if voice.startswith("b") else "en-us")
            buf = io.BytesIO()
            sf.write(buf, samples, rate, format="WAV", subtype="PCM_16")
            print(f"{voice}: {len(text)} chars in {time.time() - started:.2f}s", flush=True)
            self._send(200, buf.getvalue(), "audio/wav")
        except Exception as e:
            print(f"synthesize failed: {e}", flush=True)
            self._send(500, json.dumps({"error": str(e)}).encode())

    def log_message(self, fmt, *args):
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8771)
    ap.add_argument("--model", default="kokoro-v1.0.onnx")
    a = ap.parse_args()
    kdir = os.path.join(ROOT, "models", "kokoro")
    print("loading Kokoro ...", flush=True)
    t0 = time.time()
    STATE["kokoro"] = Kokoro(os.path.join(kdir, a.model), os.path.join(kdir, "voices-v1.0.bin"))
    STATE["voices"] = set(STATE["kokoro"].get_voices())
    STATE["kokoro"].create("Warm up, one two three.", voice="af_heart", lang="en-us")
    print(f"ready in {time.time() - t0:.1f}s on http://127.0.0.1:{a.port} ({len(STATE['voices'])} voices)", flush=True)
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
