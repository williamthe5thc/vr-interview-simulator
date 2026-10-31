"""
Tiny web server for the blind rating page. Two addresses ONLY: this PC's Tailscale address and its home-LAN address. It never binds
to 0.0.0.0, so no other interface (WSL, VPN adapters, anything else) can reach it, and it is not exposed to the internet.

    .venv\\Scripts\\python.exe tools\\rating_server.py [--lan YOUR_PC_LAN_IP] [--port 8780]

Served: the page (GET / or /rate.html), and the ratings of ONE rater (GET/POST /ratings?rater=NAME). Everything else, including
key.json and any listing or reveal, is 404. Ratings live in model_compare\\ratings\\<rater>.json (merged on every POST).
On first start the old single ratings file is backed up and filed under "Owner".
"""
import argparse
import json
import os
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "model_compare")
PUBLIC = os.path.join(OUT, "public")
RATERS = os.path.join(OUT, "ratings")
OLD = os.path.join(OUT, "ratings.json")
LOCK = threading.Lock()


def safe_rater(name):
    return "".join(c for c in (name or "") if c.isalnum() or c in " _-").strip()[:30]


def migrate():
    os.makedirs(RATERS, exist_ok=True)
    target = os.path.join(RATERS, "Owner.json")
    if os.path.exists(OLD) and not os.path.exists(target):
        backup = os.path.join(OUT, "ratings.backup_before_raters.json")
        if not os.path.exists(backup):
            shutil.copy2(OLD, backup)
        shutil.copy2(OLD, target)
        print("filed the existing ratings under Owner (backup kept)", flush=True)


def tailscale_ip():
    exe = r"C:\Program Files\Tailscale\tailscale.exe"
    out = subprocess.run([exe, "ip", "-4"], capture_output=True, text=True, timeout=10).stdout.split()
    return out[0] if out and out[0].startswith("100.") else None


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="text/plain"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _rater(self):
        q = parse_qs(urlparse(self.path).query)
        return safe_rater((q.get("rater") or [""])[0])

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/rate.html"):
            with open(os.path.join(PUBLIC, "rate.html"), "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        if path == "/ratings":
            name = self._rater()
            if not name:
                return self._send(400, b"rater missing")
            f = os.path.join(RATERS, name + ".json")
            return self._send(200, open(f, "rb").read() if os.path.exists(f) else b"{}", "application/json")
        self._send(404, b"not found")

    def do_POST(self):
        if urlparse(self.path).path != "/ratings":
            return self._send(404, b"not found")
        name = self._rater()
        if not name:
            return self._send(400, b"rater missing")
        try:
            data = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", "0")), 1_000_000)))
            if not isinstance(data, dict):
                raise ValueError("expected an object")
            data = {k: v for k, v in data.items() if isinstance(k, str) and len(k) < 80 and isinstance(v, (int, str))}
            with LOCK:
                f = os.path.join(RATERS, name + ".json")
                cur = json.load(open(f, encoding="utf-8")) if os.path.exists(f) else {}
                cur.update(data)          # a browser that knows fewer ratings never wipes the others
                json.dump(cur, open(f, "w", encoding="utf-8"), indent=1)
            self._send(200, b"saved")
        except Exception as e:
            self._send(400, str(e).encode()[:200])

    def log_message(self, fmt, *args):
        pass


def serve(ip, port, label):
    try:
        srv = ThreadingHTTPServer((ip, port), Handler)
    except OSError as e:
        print(f"could not bind {label} {ip}:{port}: {e}", flush=True)
        return None
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f"rating page on http://{ip}:{port}/ ({label})", flush=True)
    return srv


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--lan", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8780)
    a = ap.parse_args()
    migrate()
    servers = []
    ts = tailscale_ip()
    if ts:
        servers.append(serve(ts, a.port, "Tailscale only"))
    if a.lan:
        servers.append(serve(a.lan, a.port, "home LAN only"))
    if not any(servers):
        raise SystemExit("no address could be bound; refusing to start")
    threading.Event().wait()
