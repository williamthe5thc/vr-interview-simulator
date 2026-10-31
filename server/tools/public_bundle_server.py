#!/usr/bin/env python3
"""
Rating page server for a PUBLIC copy of the blind rating page. Python standard library only (runs on the Mac's built-in python3).

    python3 server.py                 passcode ON (reads passcode.txt), listens on 127.0.0.1:8780 only
    python3 server.py --no-passcode   passcode OFF
    python3 server.py --port 8780

It serves ONLY: the page (GET / and /rate.html), GET /config, and GET/POST /ratings?rater=NAME[&pass=WORD].
It talks to nothing else, reads nothing outside this folder, and writes only to the ratings/ folder next to it.
Everything it accepts is validated: rater name <= 40 of [A-Za-z0-9 _-], at most 50 raters, only the known rating ids,
scores 1-5, best-pick letters only from the letters shown for that moment, body <= 20 KB, per-address request limits.
"""
import argparse
import hmac
import json
import os
import re
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
RATINGS = os.path.join(HERE, "ratings")
PAGE = os.path.join(HERE, "rate.html")
NAME_RE = re.compile(r"^[A-Za-z0-9 _-]{1,40}$")
MAX_RATERS = 50
MAX_BODY = 20000
LIMIT_PER_MIN = 90          # requests per address per minute
FAIL_PER_MIN = 10           # wrong passcodes per address per minute

ALLOWED = json.load(open(os.path.join(HERE, "allowed_ids.json"), encoding="utf-8"))
RATING_IDS = set(ALLOWED["rating_ids"])          # e.g. "cs|1|A"
BEST = ALLOWED["best"]                           # moment -> letters, e.g. {"cs|1": ["A", "B", ...]}
PASSCODE = None
LOCK = threading.Lock()
HITS = {}
FAILS = {}


def passcode_from_file():
    try:
        word = open(os.path.join(HERE, "passcode.txt"), encoding="utf-8").read().strip().splitlines()[0].strip()
        return word or None
    except (OSError, IndexError):
        return None


def too_many(table, who, limit):
    now = time.time()
    with LOCK:
        recent = [t for t in table.get(who, []) if now - t < 60]
        recent.append(now)
        table[who] = recent
        if len(table) > 5000:          # keep the tables small under attack
            table.clear()
        return len(recent) > limit


def validate(data):
    """The posted ratings must be an object of known ids with allowed values; anything else rejects the whole request."""
    if not isinstance(data, dict) or len(data) > len(RATING_IDS) + len(BEST):
        return False
    for k, v in data.items():
        if k in RATING_IDS:
            if isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= 5:
                return False
        elif k.startswith("best:best-") and k[len("best:best-"):] in BEST:
            if v not in BEST[k[len("best:best-"):]]:
                return False
        else:
            return False
    return True


class Handler(BaseHTTPRequestHandler):
    timeout = 10
    server_version = "ratings"
    sys_version = ""

    def _who(self):
        fwd = self.headers.get("X-Forwarded-For", "")
        return (fwd.split(",")[0].strip() or self.client_address[0])[:64]

    def _send(self, code, body, ctype="text/plain; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self' 'unsafe-inline'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _auth(self, q):
        """True when no passcode is needed or the right one was given. Counts wrong tries per address."""
        if not PASSCODE:
            return True
        now = time.time()
        with LOCK:
            if len([t for t in FAILS.get(self._who(), []) if now - t < 60]) >= FAIL_PER_MIN:
                return False          # too many wrong tries from this address: locked for a minute, even for the right word
        given = (q.get("pass") or [""])[0]
        if hmac.compare_digest(given.encode("utf-8"), PASSCODE.encode("utf-8")):
            return True
        too_many(FAILS, self._who(), FAIL_PER_MIN)
        return False

    def _rater(self, q):
        name = (q.get("rater") or [""])[0].strip()
        return name if NAME_RE.match(name) else None

    def _file(self, name):
        return os.path.join(RATINGS, name.lower().replace(" ", "_") + ".json")

    def do_GET(self):
        if too_many(HITS, self._who(), LIMIT_PER_MIN) or too_many(FAILS, self._who() + "#probe", 10 * LIMIT_PER_MIN):
            return self._send(429, "slow down")
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path in ("/", "/rate.html"):
            with open(PAGE, "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        if u.path == "/config":
            return self._send(200, json.dumps({"passcode_required": bool(PASSCODE)}), "application/json")
        if u.path == "/ratings":
            if not self._auth(q):
                return self._send(403, "passcode")
            name = self._rater(q)
            if not name:
                return self._send(400, "bad rater name")
            f = self._file(name)
            return self._send(200, open(f, "rb").read() if os.path.exists(f) else b"{}", "application/json")
        self._send(404, "not found")

    def do_POST(self):
        if too_many(HITS, self._who(), LIMIT_PER_MIN):
            return self._send(429, "slow down")
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path != "/ratings":
            return self._send(404, "not found")
        if not self._auth(q):
            return self._send(403, "passcode")
        name = self._rater(q)
        if not name:
            return self._send(400, "bad rater name")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self._send(400, "bad length")
        if length <= 0 or length > MAX_BODY:
            return self._send(413, "too large")
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            return self._send(400, "bad json")
        if not validate(data):
            return self._send(400, "invalid ratings")
        with LOCK:
            os.makedirs(RATINGS, exist_ok=True)
            f = self._file(name)
            if not os.path.exists(f) and len([x for x in os.listdir(RATINGS) if x.endswith(".json")]) >= MAX_RATERS:
                return self._send(403, "rater limit reached")
            cur = {}
            if os.path.exists(f):
                try:
                    cur = json.load(open(f, encoding="utf-8"))
                except ValueError:
                    cur = {}
            cur.update(data)          # a browser that knows fewer ratings never wipes the others
            fd, tmp = tempfile.mkstemp(dir=RATINGS, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as out:
                json.dump(cur, out, indent=1)
            os.replace(tmp, f)
        self._send(200, "saved")

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8780)
    ap.add_argument("--host", default="127.0.0.1", help="leave at 127.0.0.1: the funnel/proxy reaches it from the same machine")
    ap.add_argument("--no-passcode", action="store_true")
    a = ap.parse_args()
    PASSCODE = None if a.no_passcode else passcode_from_file()
    os.makedirs(RATINGS, exist_ok=True)
    print(f"serving on http://{a.host}:{a.port}/  passcode: {'ON (passcode.txt)' if PASSCODE else 'OFF'}", flush=True)
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()
