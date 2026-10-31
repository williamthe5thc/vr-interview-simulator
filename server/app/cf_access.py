"""
Checks a Cloudflare Access login token (the Cf-Access-Jwt-Assertion header) properly: RS256 signature against the team's public keys,
plus aud, iss, exp and nbf. Used by app/access_codes.py to decide whether a browser session may skip the access code.

Standard library only (the server venv has no JWT or crypto package): RSA PKCS#1 v1.5 with SHA-256 is checked by hand below.

Settings (config.json "access", or environment variables, which win):
  cf_team_domain   VRSIM_CF_TEAM_DOMAIN   "myteam.cloudflareaccess.com" (or just "myteam")
  cf_access_aud    VRSIM_CF_ACCESS_AUD    the Access application's AUD tag; several allowed, comma-separated or a list
  cf_certs_url     (tests only)           where to fetch the keys; default https://<team domain>/cdn-cgi/access/certs
Either one empty = nothing is ever verified = no browser session skips the code (fail closed).
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import threading
import time
import urllib.request

log = logging.getLogger("access")

# DER prefix of DigestInfo for SHA-256 (RFC 8017, section 9.2, note 1)
SHA256_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")
CERTS_TTL = 3600            # re-fetch the keys at least hourly
REFRESH_MIN_GAP = 60        # an unknown key id triggers a re-fetch, but at most once a minute
LEEWAY = 60                 # seconds of clock difference allowed on exp / nbf


def b64url(data):
    if isinstance(data, str):
        data = data.encode("ascii")
    return base64.urlsafe_b64decode(data + b"=" * (-len(data) % 4))


def _int(b64):
    return int.from_bytes(b64url(b64), "big")


def rsa_pkcs1_sha256_verify(n, e, message, signature):
    """True when signature is a valid RSASSA-PKCS1-v1_5 SHA-256 signature of message under the public key (n, e)."""
    k = (n.bit_length() + 7) // 8
    if len(signature) != k or k < 256:          # keys under 2048 bits are refused
        return False
    s = int.from_bytes(signature, "big")
    if s >= n:
        return False
    em = pow(s, e, n).to_bytes(k, "big")
    t = SHA256_PREFIX + hashlib.sha256(message).digest()
    expected = b"\x00\x01" + b"\xff" * (k - len(t) - 3) + b"\x00" + t
    return hmac.compare_digest(em, expected)


class AccessTokenVerifier:
    def __init__(self, team_domain="", audiences=None, certs_url="", fetch=None):
        team = (team_domain or "").strip().lower()
        team = team.replace("https://", "").replace("http://", "").strip("/")
        if team and "." not in team:
            team += ".cloudflareaccess.com"
        self.team = team
        if isinstance(audiences, str):
            audiences = [a.strip() for a in audiences.split(",")]
        self.audiences = [a for a in (audiences or []) if a]
        self.issuer = f"https://{team}" if team else ""
        self.certs_url = certs_url or (f"https://{team}/cdn-cgi/access/certs" if team else "")
        self._fetch = fetch or self._http_fetch
        self.keys = {}               # kid -> (n, e)
        self.fetched_at = 0.0
        self.lock = threading.Lock()

    @classmethod
    def from_settings(cls, cfg):
        team = os.environ.get("VRSIM_CF_TEAM_DOMAIN") or cfg.get("cf_team_domain") or ""
        aud = os.environ.get("VRSIM_CF_ACCESS_AUD") or cfg.get("cf_access_aud") or []
        return cls(team, aud, cfg.get("cf_certs_url") or "")

    @property
    def configured(self):
        return bool(self.team and self.audiences)

    # ---- keys ----
    @staticmethod
    def _http_fetch(url):
        with urllib.request.urlopen(url, timeout=5) as r:
            return json.loads(r.read().decode("utf-8"))

    def _load_keys(self):
        data = self._fetch(self.certs_url)
        keys = {}
        for jwk in data.get("keys", []):
            if jwk.get("kty") == "RSA" and jwk.get("kid") and jwk.get("n") and jwk.get("e"):
                keys[jwk["kid"]] = (_int(jwk["n"]), _int(jwk["e"]))
        self.keys = keys
        self.fetched_at = time.time()

    def _key(self, kid):
        """The public key for kid: from the cache, else after one (rate-limited) re-fetch. None when unknown or the fetch fails."""
        with self.lock:
            now = time.time()
            stale = now - self.fetched_at > CERTS_TTL
            if stale or (kid not in self.keys and now - self.fetched_at > REFRESH_MIN_GAP):
                try:
                    self._load_keys()
                except Exception as e:
                    log.warning(f"access: could not fetch Cloudflare Access keys: {e}")
                    if stale:
                        self.keys = {}               # never trust keys we could not refresh for over an hour
                    self.fetched_at = now - CERTS_TTL + REFRESH_MIN_GAP   # retry in a minute, not on every connection
            return self.keys.get(kid)

    # ---- the check ----
    def verify(self, token):
        """The token's claims when it is genuine and meant for us, else None. Never raises."""
        try:
            if not self.configured or not token:
                return None
            parts = token.split(".")
            if len(parts) != 3:
                return None
            header = json.loads(b64url(parts[0]))
            if header.get("alg") != "RS256":
                return None
            key = self._key(header.get("kid") or "")
            if key is None:
                return None
            if not rsa_pkcs1_sha256_verify(key[0], key[1], (parts[0] + "." + parts[1]).encode("ascii"), b64url(parts[2])):
                return None
            claims = json.loads(b64url(parts[1]))
            now = time.time()
            if float(claims.get("exp", 0)) < now - LEEWAY:
                return None
            if float(claims.get("nbf", 0)) > now + LEEWAY:
                return None
            if claims.get("iss") != self.issuer:
                return None
            aud = claims.get("aud")
            aud = aud if isinstance(aud, list) else [aud]
            if not any(a in self.audiences for a in aud):
                return None
            return claims
        except Exception:
            return None
