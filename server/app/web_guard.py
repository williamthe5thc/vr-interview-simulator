"""
Guards for the gated live WEB version of the interview simulator (browser -> Cloudflare Access -> Mac nginx -> this server). Everything is
configurable in config.json under "web" and applies to WEB sessions only (a connection that sends an Origin header); the Quest sends none
and is never counted, limited or logged differently.

  max_sessions                      simultaneous web sessions (extra ones get a polite "busy" message)
  max_turns_per_session             candidate turns (speech or typed) per web session
  session_usd_cap, daily_usd_cap    estimated API spend per web session / per day (all web sessions together)
  interviews_per_hour_per_identity  interview starts (`begin`) per visitor per hour; the visitor is the Cloudflare Access e-mail, hashed
  export                            "none" (default: kept in memory for the coach only) or "anonymous" (exports/web, source=web, no e-mail)
  allowed_origins                   Origins that may open the websocket (native clients send none and are always allowed)
  heartbeat_seconds                 app-level keepalive frame for web sessions
  max_text_chars, max_text_words    limits for typed turns (text_data)
"""
import base64
import hashlib
import json
import logging
import os
import threading
import time

from services.llm.web_context import WEB

log = logging.getLogger("web_guard")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULTS = {
    "allowed_origins": ["https://interview.alearningmind.org"],
    "max_sessions": 2, "max_turns_per_session": 12, "session_usd_cap": 0.05, "daily_usd_cap": 2.0,
    "interviews_per_hour_per_identity": 3, "export": "none", "heartbeat_seconds": 25, "coach": "haiku",
    "max_text_chars": 1500, "max_text_words": 250,
}
BUSY = "The practice room is busy right now. Please try again in a few minutes."
CLOSED = "The practice room is closed for today. Please try again tomorrow."
LIMIT_TURNS = "This practice session has reached its limit. Please start a new session later."
LIMIT_HOUR = "You have reached the limit of practice interviews for this hour. Please try again later."


class WebGuard:
    def __init__(self, base_dir=ROOT, name="interview"):
        """name: which experience this guard serves (e.g. "interview" on 8765): its own spend file and its own overrides
        under config.json web.<name> (for example web.<name>.daily_usd_cap), on top of the shared web settings."""
        self.base = base_dir
        self.name = name
        self.cfg = dict(DEFAULTS)
        try:
            with open(os.path.join(base_dir, "config", "config.json"), encoding="utf-8") as f:
                web = json.load(f).get("web", {}) or {}
            self.cfg.update({k: v for k, v in web.items() if not isinstance(v, dict)})
            self.cfg.update(web.get(name) or {})
        except Exception as e:
            log.warning(f"web config not read, using defaults: {e}")
        self.lock = threading.Lock()
        self.sessions = {}       # session id -> {"identity", "turns", "spent", "started"}
        self.begins = {}         # identity -> [timestamps of interview starts]
        self.state_file = os.path.join(base_dir, "data", "web_spend.json" if name == "interview" else f"web_spend_{name}.json")

    # ---- who is a web session ---------------------------------------------------------------------------------------------------
    @staticmethod
    def headers(websocket):
        h = getattr(websocket, "request_headers", None)
        return h if h is not None else {}

    def is_web(self, websocket):
        return bool(self.headers(websocket).get("Origin"))

    def identity(self, websocket):
        """A hash of who the visitor is: the e-mail in the Cloudflare Access token if there is one (read without verifying: used only for
        counting, the real check is Cloudflare Access), else the forwarded address. Never the e-mail itself."""
        h = self.headers(websocket)
        who = ""
        token = h.get("Cf-Access-Jwt-Assertion") or ""
        try:
            part = token.split(".")[1]
            payload = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
            who = payload.get("email") or payload.get("sub") or ""
        except Exception:
            who = ""
        who = who or h.get("X-Forwarded-For") or h.get("Cf-Connecting-Ip") or "unknown"
        return hashlib.sha256(who.encode("utf-8")).hexdigest()[:16]

    def email(self, websocket):
        """The tester's e-mail from Cloudflare Access (the forwarded e-mail header, else the claim in the Access token, read without verifying:
        it only labels the transcript, the login itself is checked by Cloudflare). "" when there is none."""
        h = self.headers(websocket)
        mail = h.get("Cf-Access-Authenticated-User-Email") or ""
        if not mail:
            try:
                part = (h.get("Cf-Access-Jwt-Assertion") or "").split(".")[1]
                mail = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))).get("email", "")
            except Exception:
                mail = ""
        return str(mail)[:120]

    def session_email(self, session_id):
        return (self.sessions.get(session_id) or {}).get("email", "")

    # ---- daily spend (a small JSON file; no words in it) ------------------------------------------------------------------------
    def _day(self):
        today = time.strftime("%Y-%m-%d")
        try:
            with open(self.state_file, encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            d = {}
        if d.get("date") != today:
            d = {"date": today, "usd": 0.0}
        return d

    def day_spent(self):
        with self.lock:
            return float(self._day().get("usd", 0.0))

    def _save_day(self, d):
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(d, f)

    def add_spend(self, session_id, usd):
        if usd <= 0:
            return
        with self.lock:
            d = self._day()
            d["usd"] = round(float(d.get("usd", 0.0)) + usd, 6)
            self._save_day(d)
            s = self.sessions.get(session_id)
            if s is not None:
                s["spent"] += usd

    # ---- admission and limits ---------------------------------------------------------------------------------------------------
    def admit(self, session_id, identity, email=""):
        """(True, "") and the session is registered, or (False, message)."""
        with self.lock:
            if len(self.sessions) >= int(self.cfg["max_sessions"]):
                return False, BUSY
            if float(self._day().get("usd", 0.0)) >= float(self.cfg["daily_usd_cap"]):
                return False, CLOSED
            self.sessions[session_id] = {"identity": identity, "email": email, "turns": 0, "spent": 0.0, "started": time.time()}
        return True, ""

    def release(self, session_id):
        with self.lock:
            self.sessions.pop(session_id, None)

    def is_web_session(self, session_id):
        return session_id in self.sessions

    def allow_begin(self, session_id):
        s = self.sessions.get(session_id)
        if s is None:
            return True, ""
        now = time.time()
        with self.lock:
            recent = [t for t in self.begins.get(s["identity"], []) if now - t < 3600]
            if len(recent) >= int(self.cfg["interviews_per_hour_per_identity"]):
                self.begins[s["identity"]] = recent
                return False, LIMIT_HOUR
            recent.append(now)
            self.begins[s["identity"]] = recent
        return True, ""

    def check_turn(self, session_id):
        """Before a candidate turn: (True, "") or (False, message). Counts the turn."""
        s = self.sessions.get(session_id)
        if s is None:
            return True, ""
        with self.lock:
            if float(self._day().get("usd", 0.0)) >= float(self.cfg["daily_usd_cap"]):
                return False, CLOSED
            if s["turns"] >= int(self.cfg["max_turns_per_session"]) or s["spent"] >= float(self.cfg["session_usd_cap"]):
                return False, LIMIT_TURNS
            s["turns"] += 1
        return True, ""

    def check_text(self, text):
        """Typed turn limits, the same size as speech: (clean text, "") or ("", reason)."""
        text = "".join(ch for ch in (text or "") if ch == "\n" or ch >= " ").strip()
        if not text:
            return "", "Empty text."
        if len(text) > int(self.cfg["max_text_chars"]) or len(text.split()) > int(self.cfg["max_text_words"]):
            return "", "That text is too long. Please keep it to about 250 words."
        return text, ""

    def capabilities(self):
        return {"text_data": True, "max_text_chars": int(self.cfg["max_text_chars"]), "max_text_words": int(self.cfg["max_text_words"])}

    def allowed_origins(self):
        origins = [o for o in (self.cfg.get("allowed_origins") or []) if o]
        return ([None] + origins) if origins else None      # None = native clients (the Quest) send no Origin header

    # ---- no words in the log for web sessions -----------------------------------------------------------------------------------
    class _Filter(logging.Filter):
        BLOCK = ("Transcription:", "LLM Response:", "Typed turn:")

        def filter(self, record):
            return not (WEB.get() and record.getMessage().startswith(self.BLOCK))

    def install_log_filter(self):
        f = self._Filter()
        for handler in logging.getLogger().handlers:
            handler.addFilter(f)
