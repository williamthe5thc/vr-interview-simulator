"""
Tests for the Cloudflare Access token check (app/cf_access.py) and its use for the web exemption in app/access_codes.py.

A 2048-bit test RSA key is made on the fly (standard library only) and its public half is served as a fake Cloudflare certs
endpoint on 127.0.0.1:18793. Nothing real is contacted.

  .venv\Scripts\python.exe -m unittest -v test_scripts.test_cf_access
"""

import asyncio
import base64
import hashlib
import http.server
import json
import os
import random
import sys
import tempfile
import threading
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app import cf_access  # noqa: E402
from app.access_codes import AccessGate  # noqa: E402

CERTS_PORT = 18793
TEAM = "testteam.cloudflareaccess.com"
AUD = "aud-tag-for-the-interview-app"
ORIGIN = "https://interview.alearningmind.org"


# ---- a throwaway RSA key and RS256 signing (tests only) -----------------------------------------------------------------------------
def _probable_prime(bits, rng):
    small = [p for p in range(3, 2000, 2) if all(p % q for q in range(3, int(p ** 0.5) + 1, 2))]
    while True:
        c = rng.getrandbits(bits) | (1 << (bits - 1)) | (1 << (bits - 2)) | 1
        if any(c % p == 0 for p in small):
            continue
        d, s = c - 1, 0
        while d % 2 == 0:
            d, s = d // 2, s + 1
        for _ in range(24):
            x = pow(rng.randrange(2, c - 2), d, c)
            if x in (1, c - 1):
                continue
            for _ in range(s - 1):
                x = pow(x, 2, c)
                if x == c - 1:
                    break
            else:
                break
        else:
            return c


def make_key(seed):
    rng = random.Random(seed)
    e = 65537
    while True:
        p, q = _probable_prime(1024, rng), _probable_prime(1024, rng)
        phi = (p - 1) * (q - 1)
        if p != q and phi % e and (p * q).bit_length() == 2048:
            return {"n": p * q, "e": e, "d": pow(e, -1, phi)}


def b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def jwk(key, kid):
    n = key["n"].to_bytes(256, "big")
    return {"kid": kid, "kty": "RSA", "alg": "RS256", "use": "sig", "n": b64(n), "e": b64(key["e"].to_bytes(3, "big"))}


def sign(key, kid, claims, alg="RS256"):
    head = b64(json.dumps({"alg": alg, "kid": kid, "typ": "JWT"}).encode())
    body = b64(json.dumps(claims).encode())
    t = cf_access.SHA256_PREFIX + hashlib.sha256(f"{head}.{body}".encode()).digest()
    em = b"\x00\x01" + b"\xff" * (256 - len(t) - 3) + b"\x00" + t
    sig = pow(int.from_bytes(em, "big"), key["d"], key["n"]).to_bytes(256, "big")
    return f"{head}.{body}.{b64(sig)}"


def claims(**over):
    now = int(time.time())
    c = {"aud": [AUD], "email": "friend@example.org", "exp": now + 600, "iat": now, "nbf": now,
         "iss": f"https://{TEAM}", "sub": "abc", "type": "app"}
    c.update(over)
    return c


KEY = make_key(1)
OTHER = make_key(2)        # an attacker's key


# ---- a fake certs endpoint -------------------------------------------------------------------------------------------------------
class Certs:
    keys = []
    hits = 0


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        Certs.hits += 1
        body = json.dumps({"keys": Certs.keys}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class TestVerifier(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = http.server.HTTPServer(("127.0.0.1", CERTS_PORT), Handler)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def setUp(self):
        Certs.keys = [jwk(KEY, "kid-1")]
        Certs.hits = 0
        self.v = cf_access.AccessTokenVerifier(TEAM, [AUD], f"http://127.0.0.1:{CERTS_PORT}/certs")

    def test_good_token(self):
        c = self.v.verify(sign(KEY, "kid-1", claims()))
        self.assertIsNotNone(c)
        self.assertEqual(c["email"], "friend@example.org")
        self.v.verify(sign(KEY, "kid-1", claims()))
        self.assertEqual(Certs.hits, 1)                        # keys are cached

    def test_short_team_name_and_aud_string(self):
        v = cf_access.AccessTokenVerifier("testteam", AUD + ", another", f"http://127.0.0.1:{CERTS_PORT}/certs")
        self.assertEqual(v.issuer, f"https://{TEAM}")
        self.assertIsNotNone(v.verify(sign(KEY, "kid-1", claims())))

    def test_forged_signature(self):
        self.assertIsNone(self.v.verify(sign(OTHER, "kid-1", claims())))           # right kid, wrong key
        good = sign(KEY, "kid-1", claims())
        head, body, sig = good.split(".")
        tampered = b64(json.dumps(claims(email="someone-else@example.org")).encode())
        self.assertIsNone(self.v.verify(f"{head}.{tampered}.{sig}"))                # claims changed after signing

    def test_wrong_aud_iss_expired_not_yet(self):
        self.assertIsNone(self.v.verify(sign(KEY, "kid-1", claims(aud=["some-other-app"]))))
        self.assertIsNone(self.v.verify(sign(KEY, "kid-1", claims(aud="some-other-app"))))
        self.assertIsNone(self.v.verify(sign(KEY, "kid-1", claims(iss="https://evil.cloudflareaccess.com"))))
        self.assertIsNone(self.v.verify(sign(KEY, "kid-1", claims(exp=int(time.time()) - 3600))))
        self.assertIsNone(self.v.verify(sign(KEY, "kid-1", claims(nbf=int(time.time()) + 3600))))
        self.assertIsNotNone(self.v.verify(sign(KEY, "kid-1", claims(aud=AUD))))   # a single string aud is fine

    def test_alg_none_and_hs256_and_garbage(self):
        head = b64(json.dumps({"alg": "none", "kid": "kid-1"}).encode())
        self.assertIsNone(self.v.verify(f"{head}.{b64(json.dumps(claims()).encode())}."))
        self.assertIsNone(self.v.verify(sign(KEY, "kid-1", claims(), alg="HS256")))
        for junk in ("", "a.b.c", "a.b", "....", "x" * 5000):
            self.assertIsNone(self.v.verify(junk))

    def test_unknown_kid_refreshes_once(self):
        self.assertIsNotNone(self.v.verify(sign(KEY, "kid-1", claims())))
        Certs.keys = [jwk(KEY, "kid-1"), jwk(OTHER, "kid-2")]                     # Cloudflare rotated in a new key
        self.v.fetched_at -= cf_access.REFRESH_MIN_GAP + 1
        self.assertIsNotNone(self.v.verify(sign(OTHER, "kid-2", claims())))
        self.assertEqual(Certs.hits, 2)
        for _ in range(5):                                                         # made-up kids don't hammer the endpoint
            self.assertIsNone(self.v.verify(sign(KEY, "kid-made-up", claims())))
        self.assertEqual(Certs.hits, 2)

    def test_unreachable_certs_fail_closed(self):
        v = cf_access.AccessTokenVerifier(TEAM, [AUD], "http://127.0.0.1:1/certs")
        self.assertIsNone(v.verify(sign(KEY, "kid-1", claims())))

    def test_not_configured_verifies_nothing(self):
        for team, aud in (("", [AUD]), (TEAM, []), ("", "")):
            v = cf_access.AccessTokenVerifier(team, aud, f"http://127.0.0.1:{CERTS_PORT}/certs")
            self.assertFalse(v.configured)
            self.assertIsNone(v.verify(sign(KEY, "kid-1", claims())))
        self.assertEqual(Certs.hits, 0)

    def test_settings_and_env(self):
        old = {k: os.environ.pop(k, None) for k in ("VRSIM_CF_TEAM_DOMAIN", "VRSIM_CF_ACCESS_AUD")}
        try:
            self.assertFalse(cf_access.AccessTokenVerifier.from_settings({}).configured)
            v = cf_access.AccessTokenVerifier.from_settings({"cf_team_domain": "testteam", "cf_access_aud": [AUD]})
            self.assertTrue(v.configured)
            os.environ["VRSIM_CF_TEAM_DOMAIN"] = "envteam"
            os.environ["VRSIM_CF_ACCESS_AUD"] = "a1,a2"
            v = cf_access.AccessTokenVerifier.from_settings({})
            self.assertEqual((v.team, v.audiences), ("envteam.cloudflareaccess.com", ["a1", "a2"]))
        finally:
            for k, val in old.items():
                os.environ.pop(k, None)
                if val is not None:
                    os.environ[k] = val

    def test_web_exemption_end_to_end(self):
        """AccessGate.is_trusted_web with a real verifier: only a genuine token for our app skips the code."""
        class WS:
            remote_address = ("100.64.0.2", 1)

            def __init__(self, h):
                self.request_headers = h
        d = tempfile.mkdtemp(prefix="cf_test_")
        gate = AccessGate(settings={"cf_team_domain": TEAM, "cf_access_aud": [AUD],
                                    "cf_certs_url": f"http://127.0.0.1:{CERTS_PORT}/certs"},
                          codes_file=os.path.join(d, "c.json"), state_file=os.path.join(d, "s.json"))

        def trusted(token, **extra):
            h = dict({"Origin": ORIGIN, "Cf-Access-Jwt-Assertion": token}, **extra)
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(gate.is_trusted_web(WS(h), [ORIGIN]))
            finally:
                loop.close()
        self.assertTrue(trusted(sign(KEY, "kid-1", claims())))
        self.assertFalse(trusted(sign(OTHER, "kid-1", claims())))
        self.assertFalse(trusted(sign(KEY, "kid-1", claims(aud=["other"]))))
        self.assertFalse(trusted(sign(KEY, "kid-1", claims(exp=1))))
        self.assertFalse(trusted(sign(KEY, "kid-1", claims()), **{"X-VRSim-Entry": "quest"}))


class TestRsaPrimitive(unittest.TestCase):
    def test_small_keys_refused(self):
        self.assertFalse(cf_access.rsa_pkcs1_sha256_verify(3233, 17, b"x", b"\x00\x01"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
