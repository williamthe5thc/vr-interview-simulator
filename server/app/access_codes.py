"""
Access codes for the headset app (interview server, port 8765).

The Quest app reaches the server through a public hostname that is NOT behind Cloudflare Access, so a per-friend access code is the
only lock on it. After the websocket opens, the client's first message must be

    {"type": "auth", "code": "<code>", "client": "quest", "app_version": "<x>"}

within auth_timeout_seconds. The server answers {"type": "auth_result", "ok": true, "label", "limits"} and the normal protocol
continues, or {"type": "auth_result", "ok": false, "reason", "message"} and closes the socket (4401 invalid/revoked/expired,
4429 limit_reached/rate_limited, 4503 busy). Nothing else is processed before that. See docs/ACCESS_CODES.md.

Files (both outside git):
  config/access_codes.json   the codes: a salted PBKDF2 hash of each code, never the code itself (managed by tools/access_codes.py)
  data/access_state.json     interviews per code per day, and failed-attempt lockouts per client address (survive restarts)

Settings, all optional, under "access" in config/config.json:
  require_access_code      true                          false = the old open behaviour (an "auth" message is still answered ok)
  web_sessions_need_code   false                         browser sessions with a verified Cloudflare Access token skip the code
  cf_team_domain           ""   (env VRSIM_CF_TEAM_DOMAIN)   needed to verify that token (app/cf_access.py); empty = nobody skips
  cf_access_aud            []   (env VRSIM_CF_ACCESS_AUD)    the Access application's AUD tag(s); empty = nobody skips
  trusted_proxies          ["127.0.0.1", "::1"] + "YOUR_PROXY_IP"   only these peers may tell us the real client address in headers
  max_quest_sessions       1                             headset sessions at once over all codes (they share one language model)
  auth_timeout_seconds     10
  fail_limit 5, fail_window_minutes 10, lockout_minutes 15   per address
  global_fail_limit        50                            wrong codes from all addresses in the window -> all attempts paused
  quest_daily_usd_cap      1.00                          estimated API spend per day of all code sessions together
  code_usd_per_day         0.25                          per code per day (a code's own usd_per_day wins)
  kill_switch_file         "config/quest_disabled"       while it exists every code session is refused, no restart needed
"""

import asyncio
import datetime
import hashlib
import hmac
import json
import logging
import os
import secrets
import threading
import time

from app.cf_access import AccessTokenVerifier

log = logging.getLogger("access")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"      # no look-alikes: I L O 0 1
CODE_LENGTH = 8
PBKDF2_ITERATIONS = 20000

DEFAULTS = {
    "require_access_code": True,
    "web_sessions_need_code": False,
    "trusted_proxies": ["127.0.0.1", "::1"],   # add your tunnel/proxy host, e.g. "YOUR_PROXY_IP"
    "max_quest_sessions": 1,
    "auth_timeout_seconds": 10,
    "fail_limit": 5,
    "fail_window_minutes": 10,
    "lockout_minutes": 15,
    "cf_team_domain": "",
    "cf_access_aud": [],
    "global_fail_limit": 50,             # wrong codes from all addresses together in fail_window_minutes -> everyone waits lockout_minutes
    "quest_daily_usd_cap": 1.00,         # estimated API spend of all code sessions together per day
    "code_usd_per_day": 0.25,            # per code per day, unless the code has its own usd_per_day
    "kill_switch_file": "config/quest_disabled",   # while this file exists every code session is refused (no restart needed)
}

CLOSE_CODES = {"invalid": 4401, "revoked": 4401, "expired": 4401, "limit_reached": 4429, "rate_limited": 4429, "busy": 4503}

MESSAGES = {
    "invalid": "That access code didn't work. Check it and try again.",
    "missing": "No access code was sent. Enter your access code and try again.",
    "revoked": "This access code has been turned off. Ask the person who gave you the code for a new one.",
    "expired": "This access code has expired. Ask the person who gave you the code for a new one.",
    "limit_reached": "You've used all of today's interviews. Come back tomorrow!",
    "rate_limited": "Too many wrong codes. Please wait 15 minutes and try again.",
    "busy": "Someone else is practising right now. Please try again in a few minutes.",
    "busy_code": "This access code is already in use on another headset.",
    "rate_limited_all": "The server is getting too many wrong codes right now. Please try again in 15 minutes.",
    "disabled": "The interview practice is switched off right now. Please try again later.",
    "spend_code": "You've reached today's practice limit. Come back tomorrow!",
    "spend_all": "Today's practice time is used up for everyone. Come back tomorrow!",
}

# the internal reasons above that go out on the wire as one of the agreed reasons
WIRE = {"busy_code": "busy", "disabled": "busy", "rate_limited_all": "rate_limited", "spend_code": "limit_reached", "spend_all": "limit_reached"}


# ---- codes -----------------------------------------------------------------------------------------------------------------------
def normalize(code):
    """What the player typed -> the canonical code: upper case, spaces and dashes dropped."""
    return "".join(ch for ch in str(code or "").upper() if ch.isalnum())


def new_code():
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


def pretty(code):
    return code[:4] + "-" + code[4:]


def hash_code(code, salt_hex, iterations=PBKDF2_ITERATIONS):
    return hashlib.pbkdf2_hmac("sha256", normalize(code).encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)).hex()


def make_entry(code, label, per_day=3, expires=None, max_concurrent=1, usd_per_day=None):
    salt = secrets.token_hex(16)
    return {
        "id": secrets.token_hex(6),
        "label": label,
        "salt": salt,
        "hash": hash_code(code, salt),
        "iterations": PBKDF2_ITERATIONS,
        "created": datetime.datetime.now().isoformat(timespec="seconds"),
        "expires": expires,                # "YYYY-MM-DD" (valid through that day) or None
        "revoked": False,
        "interviews_per_day": int(per_day),
        "max_concurrent": int(max_concurrent),
        "usd_per_day": usd_per_day,        # None = the access.code_usd_per_day setting
    }


def _read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except Exception as e:
        log.error(f"could not read {os.path.basename(path)}: {e}")
        return default


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def load_codes(path):
    return _read_json(path, {"codes": []})


def save_codes(path, data):
    _write_json(path, data)


def today():
    return datetime.date.today().isoformat()


# ---- the gate ----------------------------------------------------------------------------------------------------------------------
class AccessGate:
    def __init__(self, base_dir=ROOT, settings=None, codes_file=None, state_file=None):
        self.cfg = dict(DEFAULTS)
        if settings is None:
            try:
                with open(os.path.join(base_dir, "config", "config.json"), encoding="utf-8") as f:
                    settings = json.load(f).get("access", {}) or {}
            except Exception as e:
                log.warning(f"access config not read, using defaults: {e}")
                settings = {}
        self.cfg.update(settings)
        self.codes_file = codes_file or os.path.join(base_dir, "config", "access_codes.json")
        self.state_file = state_file or os.path.join(base_dir, "data", "access_state.json")
        self.lock = threading.Lock()
        self._codes = []
        self._codes_mtime = None
        self.state = _read_json(self.state_file, {})
        self.state.setdefault("usage", {})         # code id -> {day: interviews started}
        self.state.setdefault("failures", {})      # address -> [timestamps of failed attempts]
        self.state.setdefault("lockouts", {})      # address -> locked until (epoch seconds)
        self.state.setdefault("global_failures", [])   # timestamps of failed attempts from every address together
        self.state.setdefault("global_lockout", 0)     # everyone locked until (epoch seconds)
        self.state.setdefault("spend", {})         # day -> {"total": usd, code id: usd}  (estimated API spend of code sessions)
        self.kill_switch = os.path.join(base_dir, self.cfg["kill_switch_file"])
        self.active = {}                           # session id -> code entry (in memory: a restart ends every session anyway)
        self.verifier = AccessTokenVerifier.from_settings(self.cfg)
        if not self.verifier.configured:
            log.info("access: Cloudflare Access team domain / AUD not set: every connection needs an access code")

    @property
    def required(self):
        return bool(self.cfg["require_access_code"])

    def disabled(self):
        """The kill switch: while config/quest_disabled exists every code session is refused (checked on every connection and turn)."""
        return os.path.exists(self.kill_switch)

    # ---- who is asking ----
    @staticmethod
    def _headers(websocket):
        h = getattr(websocket, "request_headers", None)
        if h is None:
            h = getattr(getattr(websocket, "request", None), "headers", None)
        return h if h is not None else {}

    def client_address(self, websocket):
        """The real client address. Forwarded headers count only when the peer is a trusted proxy (the Mac's tunnel, or localhost)."""
        peer = ""
        try:
            peer = str((websocket.remote_address or ("",))[0])
        except Exception:
            peer = ""
        trusted = set(self.cfg["trusted_proxies"] or [])
        if peer not in trusted:
            return peer or "unknown"
        h = self._headers(websocket)
        cf = (h.get("CF-Connecting-IP") or "").strip()
        if cf:
            return cf
        # nginx appends the address it saw, so the right-most entry that is not one of our own proxies is the real client
        for part in reversed([p.strip() for p in (h.get("X-Forwarded-For") or "").split(",") if p.strip()]):
            if part not in trusted:
                return part
        return peer

    async def is_trusted_web(self, websocket, allowed_origins):
        """A browser session that logged in through Cloudflare Access may skip the code: an allowed Origin and a Cf-Access-Jwt-Assertion
        whose signature, aud, iss and expiry check out (app/cf_access.py). Without cf_team_domain and cf_access_aud set, nobody skips.
        The quest hostname also clears Cf-Access-* and sets X-VRSim-Entry: quest (see docs/ACCESS_CODES.md)."""
        if self.cfg["web_sessions_need_code"]:
            return False
        h = self._headers(websocket)
        if (h.get("X-VRSim-Entry") or "").strip().lower() == "quest":
            return False
        origin = h.get("Origin") or ""
        token = h.get("Cf-Access-Jwt-Assertion") or ""
        if not origin or origin not in (allowed_origins or []) or not token:
            return False
        claims = await asyncio.get_running_loop().run_in_executor(None, self.verifier.verify, token)   # may fetch the keys
        if claims is None:
            log.info(f"access: web session from {self.client_address(websocket)} has no valid Cloudflare Access token; it needs a code")
            return False
        return True

    # ---- codes file (re-read when it changes, so add/revoke work without a restart) ----
    def codes(self):
        try:
            mtime = os.path.getmtime(self.codes_file)
        except OSError:
            mtime = None
        if mtime != self._codes_mtime:
            self._codes = load_codes(self.codes_file).get("codes", [])
            self._codes_mtime = mtime
        return self._codes

    def _find(self, code):
        code = normalize(code)
        if not code or len(code) > 64:
            return None
        found = None
        for e in self.codes():
            try:
                if hmac.compare_digest(hash_code(code, e["salt"], e.get("iterations", PBKDF2_ITERATIONS)), e["hash"]):
                    found = e         # keep looping: the time taken does not depend on which code matched
            except Exception:
                continue
        return found

    # ---- state file ----
    def _save_state(self):
        try:
            _write_json(self.state_file, self.state)
        except Exception as e:
            log.error(f"could not save access state: {e}")

    def used_today(self, entry):
        return int(self.state["usage"].get(entry["id"], {}).get(today(), 0))

    def _locked(self, addr, now):
        until = float(self.state["lockouts"].get(addr, 0))
        if until > now:
            return True
        if until:
            self.state["lockouts"].pop(addr, None)
        return False

    def _fail(self, addr, now):
        """Record a failed attempt; True when this one starts a lockout."""
        window = float(self.cfg["fail_window_minutes"]) * 60
        recent = [t for t in self.state["failures"].get(addr, []) if now - t < window] + [now]
        locked = len(recent) >= int(self.cfg["fail_limit"])
        if locked:
            self.state["lockouts"][addr] = now + float(self.cfg["lockout_minutes"]) * 60
            self.state["failures"].pop(addr, None)
        else:
            self.state["failures"][addr] = recent
        # every address together: many wrong codes from many addresses (a spread-out guess) stops all attempts for a while
        recent_all = [t for t in self.state["global_failures"] if now - t < window] + [now]
        if len(recent_all) >= int(self.cfg["global_fail_limit"]):
            self.state["global_lockout"] = now + float(self.cfg["lockout_minutes"]) * 60
            recent_all = []
            log.warning(f"access: {self.cfg['global_fail_limit']} wrong codes in {self.cfg['fail_window_minutes']} min from all addresses; "
                        f"all code attempts paused for {self.cfg['lockout_minutes']} min")
        self.state["global_failures"] = recent_all
        # drop stale addresses so the file stays small
        for a in [a for a, ts in self.state["failures"].items() if not ts or now - max(ts) > window]:
            self.state["failures"].pop(a, None)
        self._save_state()
        return locked

    # ---- the decision ----
    def check(self, code, addr, session_id):
        """(entry, "") when admitted (and registered as active), else (entry or None, reason). Hashing happens outside the lock."""
        now = time.time()
        if self.disabled():
            return None, "disabled"
        with self.lock:
            if self._locked(addr, now):
                return None, "rate_limited"
            if float(self.state["global_lockout"]) > now:
                return None, "rate_limited_all"
        entry = self._find(code)
        with self.lock:
            if self._locked(addr, now):
                return None, "rate_limited"
            if entry is None:
                self._fail(addr, now)
                return None, "invalid"
            if entry.get("revoked"):
                return entry, "revoked"
            exp = entry.get("expires")
            if exp and today() > str(exp)[:10]:
                return entry, "expired"
            if self.used_today(entry) >= int(entry.get("interviews_per_day", 0)):
                return entry, "limit_reached"
            over = self._spend_over(entry)
            if over:
                return entry, over
            same = sum(1 for e in self.active.values() if e["id"] == entry["id"])
            if same >= int(entry.get("max_concurrent", 1) or 1):
                return entry, "busy_code"
            if len(self.active) >= int(self.cfg["max_quest_sessions"]):
                return entry, "busy"
            self.active[session_id] = entry
        return entry, ""

    def limits(self, entry):
        per_day = int(entry.get("interviews_per_day", 0))
        return {"interviews_per_day": per_day, "remaining_today": max(0, per_day - self.used_today(entry))}

    def release(self, session_id):
        with self.lock:
            self.active.pop(session_id, None)

    # ---- spend (estimated API cost of code sessions; the web path has its own caps in app/web_guard.py) ----
    def _spend_over(self, entry):
        """"spend_all" / "spend_code" when today's spend cap is reached, else "". Call with the lock held."""
        day = self.state["spend"].get(today(), {})
        if float(day.get("total", 0.0)) >= float(self.cfg["quest_daily_usd_cap"]):
            return "spend_all"
        cap = entry.get("usd_per_day")
        cap = float(self.cfg["code_usd_per_day"] if cap is None else cap)
        if float(day.get(entry["id"], 0.0)) >= cap:
            return "spend_code"
        return ""

    def add_spend(self, session_id, usd):
        entry = self.active.get(session_id)
        if entry is None or not usd or usd <= 0:
            return
        with self.lock:
            day = self.state["spend"].setdefault(today(), {})
            day["total"] = round(float(day.get("total", 0.0)) + usd, 6)
            day[entry["id"]] = round(float(day.get(entry["id"], 0.0)) + usd, 6)
            for d in [d for d in self.state["spend"] if d < (datetime.date.today() - datetime.timedelta(days=60)).isoformat()]:
                self.state["spend"].pop(d, None)
            self._save_state()

    def allow_turn(self, session_id):
        """Before each candidate turn of a code session: (True, "") or (False, message): the kill switch and the spend caps."""
        entry = self.active.get(session_id)
        if entry is None:
            return True, ""
        if self.disabled():
            return False, MESSAGES["disabled"]
        with self.lock:
            over = self._spend_over(entry)
        if over:
            log.info(f"access: '{entry['label']}' turn refused: {over}")
            return False, MESSAGES[over]
        return True, ""

    def count_interview(self, session_id):
        """Called when an interview starts ("begin"). (True, "") and the day's count goes up, or (False, message) at the limit."""
        entry = self.active.get(session_id)
        if entry is None:
            return True, ""                        # not a code session (code not required, or a Cloudflare Access web session)
        ok, why = self.allow_turn(session_id)
        if not ok:
            return ok, why
        with self.lock:
            if self.used_today(entry) >= int(entry.get("interviews_per_day", 0)):
                log.info(f"access: '{entry['label']}' daily limit reached at begin")
                return False, MESSAGES["limit_reached"]
            usage = self.state["usage"].setdefault(entry["id"], {})
            usage[today()] = usage.get(today(), 0) + 1
            cutoff = (datetime.date.today() - datetime.timedelta(days=60)).isoformat()
            for day in [d for d in usage if d < cutoff]:
                usage.pop(day, None)
            self._save_state()
        return True, ""

    # ---- the handshake ----
    async def authenticate(self, websocket, session_id):
        """Wait for the auth message and answer it. Returns the code entry when the session may go on, else None (socket closed).
        Every other message before a good auth is ignored; nothing is logged but the label, the result and the address."""
        addr = self.client_address(websocket)
        deadline = time.monotonic() + float(self.cfg["auth_timeout_seconds"])
        msg = None
        ignored = 0
        try:
            while msg is None:
                left = deadline - time.monotonic()
                if left <= 0:
                    break
                raw = await asyncio.wait_for(websocket.recv(), timeout=left)
                try:
                    data = json.loads(raw) if isinstance(raw, str) else None
                except Exception:
                    data = None
                if isinstance(data, dict) and data.get("type") == "auth":
                    msg = data
                else:
                    ignored += 1
                    if ignored > 20:
                        break
        except asyncio.TimeoutError:
            pass
        except Exception:
            log.info(f"access: connection from {addr} closed before auth")
            return None

        if msg is None:
            log.info(f"access: no auth message from {addr} (ignored {ignored} other messages)")
            await self._refuse(websocket, "invalid", MESSAGES["missing"])
            return None

        entry, reason = await asyncio.get_running_loop().run_in_executor(None, self.check, msg.get("code"), addr, session_id)
        label = entry["label"] if entry else "-"
        client = str(msg.get("client", ""))[:20]
        version = str(msg.get("app_version", ""))[:20]
        if reason:
            log.info(f"access: refused label='{label}' reason={reason} addr={addr} client={client} app={version}")
            wire = WIRE.get(reason, reason)
            await self._refuse(websocket, wire, MESSAGES[reason])
            return None
        log.info(f"access: ok label='{label}' addr={addr} client={client} app={version} session={session_id}")
        try:
            await websocket.send(json.dumps({"type": "auth_result", "ok": True, "label": entry["label"], "limits": self.limits(entry)}))
        except Exception:
            self.release(session_id)
            return None
        return entry

    @staticmethod
    async def _refuse(websocket, reason, message):
        try:
            await websocket.send(json.dumps({"type": "auth_result", "ok": False, "reason": reason, "message": message}))
            await websocket.close(CLOSE_CODES[reason], reason)
        except Exception:
            pass
