"""
Speech-to-text worker: faster-whisper behind a tiny local HTTP API. It runs in its own virtual environment
(.venv_fw), so its CUDA libraries never mix with the interview server's PyTorch.

    .venv_fw\\Scripts\\python.exe tools\\stt_worker.py --model large-v3-turbo --compute int8_float16 --port 8770

    GET  /health      -> {"ok": true, "model": ...}
    POST /transcribe  body = a WAV file (any sample rate, 16-bit PCM) -> {"text": "...", "audio_seconds": 12.3, "seconds": 0.4}

The interview server (services/audio/stt_wrapper.py) calls it when config audio.stt_remote_url is set and falls back to
the built-in openai-whisper when the worker does not answer.
"""
import argparse
import io
import json
import os
import site
import sys
import threading
import time
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

for _sp in site.getsitepackages():   # the pip-installed CUDA libraries (cuBLAS, cuDNN) for CTranslate2
    for _sub in (r"nvidia\cublas\bin", r"nvidia\cudnn\bin", r"nvidia\cuda_nvrtc\bin"):
        _d = os.path.join(_sp, _sub)
        if os.path.isdir(_d):
            os.add_dll_directory(_d)
            os.environ["PATH"] = _d + os.pathsep + os.environ["PATH"]

import numpy as np  # noqa: E402
from faster_whisper import WhisperModel  # noqa: E402

LOCK = threading.Lock()
STATE = {"model": None, "name": "", "args": None}


def decode_wav(data: bytes) -> np.ndarray:
    with wave.open(io.BytesIO(data)) as w:
        if w.getsampwidth() != 2:
            raise ValueError(f"only 16-bit PCM WAV is supported (got {8 * w.getsampwidth()}-bit)")
        channels, rate = w.getnchannels(), w.getframerate()
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        pcm = pcm.reshape(-1, channels).mean(axis=1)
    if rate != 16000 and len(pcm):
        pcm = np.interp(np.linspace(0, len(pcm) - 1, int(len(pcm) * 16000 / rate)), np.arange(len(pcm)), pcm).astype(np.float32)
    return pcm


HOTWORDS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stt_hotwords.txt")
_HOT = {"mtime": 0.0, "text": None}


def load_hotwords():
    """Names and terms the recogniser should favour (tools/stt_hotwords.txt, one per line, '#' starts a comment). Re-read when the file changes."""
    try:
        mtime = os.path.getmtime(HOTWORDS_FILE)
        if mtime != _HOT["mtime"]:
            lines = [ln.strip() for ln in open(HOTWORDS_FILE, encoding="utf-8") if ln.strip() and not ln.lstrip().startswith("#")]
            _HOT["text"] = ", ".join(lines) or None
            _HOT["mtime"] = mtime
    except OSError:
        _HOT["text"] = None
    return _HOT["text"]


class Handler(BaseHTTPRequestHandler):
    def _reply(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/health"):
            self._reply(200, {"ok": STATE["model"] is not None, "model": STATE["name"]})
        else:
            self._reply(404, {"error": "not found"})

    def do_POST(self):
        if self.path.startswith("/warm"):          # the server calls this when an interview begins: a real speech clip keeps the decoder warm
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            return self._reply(200, {"seconds": warm()})
        if not self.path.startswith("/transcribe"):
            return self._reply(404, {"error": "not found"})
        try:
            data = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            audio = decode_wav(data)
            a = STATE["args"]
            started = time.time()
            hotwords = None if "hotwords=0" in self.path else load_hotwords()   # ?hotwords=0 switches the hint off (for A/B tests)
            with LOCK:
                segments, _ = STATE["model"].transcribe(
                    audio, beam_size=a.beam, language=a.language, vad_filter=True,
                    condition_on_previous_text=False, temperature=0.0, hotwords=hotwords)
                text = " ".join(s.text.strip() for s in segments).strip()
            self._reply(200, {"text": text, "hotwords": bool(hotwords), "audio_seconds": round(len(audio) / 16000, 2), "seconds": round(time.time() - started, 2)})
        except Exception as e:
            print(f"transcribe failed: {e}", flush=True)
            self._reply(500, {"error": str(e)})

    def log_message(self, fmt, *args):   # keep the console quiet
        pass


WARM_WAV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stt_warm.wav")


def warm():
    """Transcribe a short speech clip (silence never reaches the decoder, so only speech really warms it). Returns seconds taken."""
    started = time.time()
    try:
        with open(WARM_WAV, "rb") as f:
            audio = decode_wav(f.read())
        with LOCK:
            segments, _ = STATE["model"].transcribe(audio, beam_size=STATE["args"].beam, language=STATE["args"].language, vad_filter=True,
                                                    condition_on_previous_text=False, temperature=0.0, hotwords=load_hotwords())
            " ".join(s.text for s in segments)
    except Exception as e:
        print(f"warm-up failed: {e}", flush=True)
    return round(time.time() - started, 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="large-v3-turbo")
    ap.add_argument("--compute", default="int8_float16")
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--beam", type=int, default=1)
    ap.add_argument("--language", default="en")
    a = ap.parse_args()
    STATE["args"] = a
    print(f"loading {a.model} ({a.compute}) ...", flush=True)
    t0 = time.time()
    STATE["model"] = WhisperModel(a.model, device="cuda", compute_type=a.compute)
    STATE["name"] = f"{a.model}/{a.compute}"
    STATE["model"].transcribe(np.zeros(16000, dtype=np.float32), beam_size=1, language=a.language)   # warm-up
    warm()
    print(f"ready in {time.time() - t0:.1f}s on http://127.0.0.1:{a.port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
