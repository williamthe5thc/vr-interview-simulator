"""
Tests for the headset access codes (app/access_codes.py and the hook in app/websocket/server_enhanced_fixed.py).

Runs throwaway websocket servers on 127.0.0.1 (ports 18791-18792) with temporary code/state files; never touches the real
servers, config/access_codes.json or data/access_state.json.

  .venv\Scripts\python.exe -m unittest test_scripts.test_access_codes -v
"""

import asyncio
import datetime
import json
import logging
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import websockets  # noqa: E402
from websockets.exceptions import ConnectionClosed  # noqa: E402

from app import access_codes as ac  # noqa: E402

GATE_PORT = 18791
SERVER_PORT = 18792
LOCAL = ["127.0.0.1", "::1"]


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class GateFixture(unittest.TestCase):
    """A temporary codes file and state file, and a gate over them."""

    settings = {"trusted_proxies": LOCAL, "max_quest_sessions": 5, "auth_timeout_seconds": 2}

    def setUp(self):
        for var in ("VRSIM_CF_TEAM_DOMAIN", "VRSIM_CF_ACCESS_AUD"):     # this process only: tests run with Access verification unset
            os.environ.pop(var, None)
        self.dir = tempfile.mkdtemp(prefix="access_test_")
        self.codes_file = os.path.join(self.dir, "access_codes.json")
        self.state_file = os.path.join(self.dir, "access_state.json")
        self.codes = {}
        data = {"codes": []}
        for label, kw in [("Good", {}), ("Revoked", {}), ("Expired", {"expires": "2020-01-01"}), ("OnePerDay", {"per_day": 1}),
                          ("Single", {"per_day": 5})]:
            code = ac.new_code()
            e = ac.make_entry(code, label, **kw)
            if label == "Revoked":
                e["revoked"] = True
            data["codes"].append(e)
            self.codes[label] = code
        ac.save_codes(self.codes_file, data)
        self.gate = self.make_gate()

    def make_gate(self, **over):
        s = dict(self.settings)
        s["kill_switch_file"] = os.path.join(self.dir, "quest_disabled")      # never the real config/quest_disabled
        s.update(over)
        return ac.AccessGate(settings=s, codes_file=self.codes_file, state_file=self.state_file)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)


class FakeWS:
    def __init__(self, peer, headers=None):
        self.remote_address = (peer, 5555)
        self.request_headers = headers or {}


# ---- the decision, without sockets -------------------------------------------------------------------------------------------------
class TestCheck(GateFixture):
    def test_good_code_any_format(self):
        c = self.codes["Good"]
        for typed in (c, c.lower(), ac.pretty(c), " " + ac.pretty(c).lower() + " "):
            entry, why = self.gate.check(typed, "1.2.3.4", "s-" + typed)
            self.assertEqual(why, "")
            self.assertEqual(entry["label"], "Good")
            self.gate.release("s-" + typed)

    def test_bad_revoked_expired(self):
        self.assertEqual(self.gate.check("ABCD2345", "1.2.3.4", "s1"), (None, "invalid"))
        self.assertEqual(self.gate.check(self.codes["Revoked"], "1.2.3.4", "s2")[1], "revoked")
        self.assertEqual(self.gate.check(self.codes["Expired"], "1.2.3.4", "s3")[1], "expired")
        self.assertEqual(self.gate.check("", "1.2.3.4", "s4")[1], "invalid")
        self.assertEqual(self.gate.active, {})

    def test_daily_limit_survives_restart(self):
        entry, why = self.gate.check(self.codes["OnePerDay"], "1.2.3.4", "s1")
        self.assertEqual(why, "")
        self.assertEqual(self.gate.limits(entry), {"interviews_per_day": 1, "remaining_today": 1})
        self.assertEqual(self.gate.count_interview("s1"), (True, ""))
        ok, msg = self.gate.count_interview("s1")              # a second "begin" in the same connection
        self.assertFalse(ok)
        self.gate.release("s1")
        restarted = self.make_gate()                            # a new process reads the state file
        self.assertEqual(restarted.check(self.codes["OnePerDay"], "1.2.3.4", "s2")[1], "limit_reached")

    def test_concurrent_limit(self):
        self.assertEqual(self.gate.check(self.codes["Single"], "1.2.3.4", "a")[1], "")
        self.assertEqual(self.gate.check(self.codes["Single"], "5.6.7.8", "b")[1], "busy_code")
        self.gate.release("a")
        self.assertEqual(self.gate.check(self.codes["Single"], "5.6.7.8", "b")[1], "")

    def test_global_quest_limit(self):
        gate = self.make_gate(max_quest_sessions=1)
        self.assertEqual(gate.check(self.codes["Good"], "1.2.3.4", "a")[1], "")
        self.assertEqual(gate.check(self.codes["Single"], "5.6.7.8", "b")[1], "busy")

    def test_lockout_after_failures_and_persisted(self):
        for i in range(4):
            self.assertEqual(self.gate.check("WRONG%03d" % i, "9.9.9.9", "x")[1], "invalid")
        self.assertEqual(self.gate.check("WRONG999", "9.9.9.9", "x")[1], "invalid")     # the 5th failure starts the lockout
        self.assertEqual(self.gate.check(self.codes["Good"], "9.9.9.9", "x")[1], "rate_limited")
        self.assertEqual(self.make_gate().check(self.codes["Good"], "9.9.9.9", "y")[1], "rate_limited")   # survives a restart
        self.assertEqual(self.gate.check(self.codes["Good"], "8.8.8.8", "z")[1], "")      # other addresses are not affected

    def test_files_never_hold_the_code(self):
        self.gate.check(self.codes["Good"], "1.2.3.4", "s1")
        self.gate.count_interview("s1")
        self.gate.check("NOPE2345", "1.2.3.4", "s2")
        for path in (self.codes_file, self.state_file):
            with open(path, encoding="utf-8") as f:
                text = f.read()
            for code in self.codes.values():
                self.assertNotIn(code, text)

    def test_codes_reloaded_without_restart(self):
        code = ac.new_code()
        data = ac.load_codes(self.codes_file)
        data["codes"].append(ac.make_entry(code, "Late"))
        ac.save_codes(self.codes_file, data)
        os.utime(self.codes_file, (0, 0))                       # make sure the mtime differs even on a coarse clock
        self.assertEqual(self.gate.check(code, "1.2.3.4", "s")[1], "")

    def test_code_alphabet(self):
        for _ in range(200):
            c = ac.new_code()
            self.assertEqual(len(c), 8)
            self.assertFalse(set(c) & set("IL01O"))


class TestClientAddress(GateFixture):
    settings = {"trusted_proxies": ["100.64.0.2", "127.0.0.1", "::1"]}

    def test_headers_trusted_only_from_proxy(self):
        h = {"CF-Connecting-IP": "203.0.113.7", "X-Forwarded-For": "203.0.113.7, 127.0.0.1"}
        self.assertEqual(self.gate.client_address(FakeWS("100.64.0.2", h)), "203.0.113.7")
        self.assertEqual(self.gate.client_address(FakeWS("127.0.0.1", h)), "203.0.113.7")
        self.assertEqual(self.gate.client_address(FakeWS("100.64.0.9", h)), "100.64.0.9")     # another tailnet device: ignored
        self.assertEqual(self.gate.client_address(FakeWS("198.51.100.1", h)), "198.51.100.1")

    def test_forwarded_for_uses_rightmost_untrusted(self):
        h = {"X-Forwarded-For": "6.6.6.6, 203.0.113.7, 127.0.0.1"}        # 6.6.6.6 was made up by the client
        self.assertEqual(self.gate.client_address(FakeWS("100.64.0.2", h)), "203.0.113.7")

    def test_trusted_web_needs_origin_and_verified_token(self):
        """The token check itself is in test_cf_access.py; here a stand-in verifier accepts only "good-token"."""
        class Stub:
            configured = True
            verify = staticmethod(lambda t: {"email": "x"} if t == "good-token" else None)
        origins = ["https://interview.alearningmind.org"]
        web = {"Origin": origins[0], "Cf-Access-Jwt-Assertion": "good-token"}

        def trusted(headers, gate=None):
            gate = gate or self.gate
            gate.verifier = Stub()
            return run(gate.is_trusted_web(FakeWS("100.64.0.2", headers), origins))
        self.assertTrue(trusted(web))
        self.assertFalse(trusted(dict(web, **{"Cf-Access-Jwt-Assertion": "a.b.c"})))       # present but not genuine
        self.assertFalse(trusted({"Origin": origins[0]}))
        self.assertFalse(trusted(dict(web, **{"X-VRSim-Entry": "quest"})))
        self.assertFalse(trusted(dict(web, Origin="https://evil.example")))
        self.assertFalse(trusted({}))
        self.assertFalse(trusted(web, self.make_gate(web_sessions_need_code=True)))

    def test_unconfigured_verifier_trusts_nobody(self):
        origins = ["https://interview.alearningmind.org"]
        self.assertFalse(self.gate.verifier.configured)
        web = {"Origin": origins[0], "Cf-Access-Jwt-Assertion": "a.b.c"}
        self.assertFalse(run(self.gate.is_trusted_web(FakeWS("100.64.0.2", web), origins)))


# ---- the handshake over a real socket ------------------------------------------------------------------------------------------------
class TestHandshake(GateFixture):
    async def _serve(self, gate, body):
        processed = []

        async def handler(ws, path=None):
            entry = await gate.authenticate(ws, "sess")
            if entry is None:
                return
            async for m in ws:
                processed.append(json.loads(m))
                await ws.send(json.dumps({"echo": json.loads(m).get("type")}))

        async with websockets.serve(handler, "127.0.0.1", GATE_PORT):
            result = await body()
        return result, processed

    async def _attempt(self, first_messages, headers=None):
        """Send messages, return (auth_result, close code, the rest)."""
        async with websockets.connect(f"ws://127.0.0.1:{GATE_PORT}", extra_headers=headers or {}) as ws:
            for m in first_messages:
                await ws.send(json.dumps(m))
            reply = json.loads(await asyncio.wait_for(ws.recv(), 5))
            if reply.get("ok"):
                await ws.send(json.dumps({"type": "ping"}))
                rest = json.loads(await asyncio.wait_for(ws.recv(), 5))
                return reply, None, rest
            try:
                await asyncio.wait_for(ws.recv(), 5)
            except ConnectionClosed:
                pass
            return reply, ws.close_code, None

    def auth(self, code):
        return {"type": "auth", "code": code, "client": "quest", "app_version": "test"}

    def test_good_code(self):
        (reply, code, rest), processed = run(self._serve(self.gate, lambda: self._attempt([self.auth(self.codes["Good"])])))
        self.assertEqual(reply, {"type": "auth_result", "ok": True, "label": "Good",
                                 "limits": {"interviews_per_day": 3, "remaining_today": 3}})
        self.assertEqual(rest, {"echo": "ping"})

    def test_failures_and_close_codes(self):
        cases = [("ABCD2345", "invalid", 4401), (self.codes["Revoked"], "revoked", 4401), (self.codes["Expired"], "expired", 4401)]
        for code, reason, close in cases:
            (reply, cc, _), processed = run(self._serve(self.gate, lambda: self._attempt([self.auth(code)])))
            self.assertEqual((reply["ok"], reply["reason"], cc), (False, reason, close))
            self.assertTrue(reply["message"])
            self.assertEqual(processed, [])

    def test_limit_reached_and_busy_close_codes(self):
        self.gate.state["usage"][[e for e in self.gate.codes() if e["label"] == "OnePerDay"][0]["id"]] = {ac.today(): 1}
        (reply, cc, _), _ = run(self._serve(self.gate, lambda: self._attempt([self.auth(self.codes["OnePerDay"])])))
        self.assertEqual((reply["reason"], cc), ("limit_reached", 4429))
        self.gate.check(self.codes["Single"], "1.1.1.1", "other-headset")
        (reply, cc, _), _ = run(self._serve(self.gate, lambda: self._attempt([self.auth(self.codes["Single"])])))
        self.assertEqual((reply["reason"], cc), ("busy", 4503))

    def test_lockout_over_socket(self):
        async def body():
            out = []
            for i in range(6):
                out.append(await self._attempt([self.auth("BADC%04d" % i)]))
            out.append(await self._attempt([self.auth(self.codes["Good"])]))
            return out
        out, _ = run(self._serve(self.gate, body))
        self.assertEqual([o[0]["reason"] for o in out], ["invalid"] * 5 + ["rate_limited", "rate_limited"])
        self.assertEqual(out[-1][1], 4429)

    def test_lockout_uses_forwarded_address_from_trusted_proxy(self):
        async def body():
            for i in range(5):
                await self._attempt([self.auth("BADC%04d" % i)], {"CF-Connecting-IP": "203.0.113.50"})
            other = await self._attempt([self.auth(self.codes["Good"])], {"CF-Connecting-IP": "203.0.113.51"})
            same = await self._attempt([self.auth(self.codes["Good"])], {"CF-Connecting-IP": "203.0.113.50"})
            return other, same
        (other, same), _ = run(self._serve(self.gate, body))
        self.assertTrue(other[0]["ok"])
        self.assertEqual(same[0]["reason"], "rate_limited")

    def test_forwarded_header_ignored_from_untrusted_peer(self):
        gate = self.make_gate(trusted_proxies=["100.64.0.2"])      # localhost is NOT trusted here
        async def body():
            for i in range(5):
                await self._attempt([self.auth("BADC%04d" % i)], {"CF-Connecting-IP": "203.0.113.%d" % i})   # rotating a fake header
            return await self._attempt([self.auth(self.codes["Good"])], {"CF-Connecting-IP": "203.0.113.99"})
        (reply, cc, _), _ = run(self._serve(gate, body))
        self.assertEqual(reply["reason"], "rate_limited")            # all five counted against the real peer, 127.0.0.1

    def test_other_messages_before_auth_are_ignored(self):
        early = [{"type": "control", "action": "begin"}, {"type": "text_data", "text": "hi"}, {"type": "ping"}]
        (reply, cc, rest), processed = run(self._serve(self.gate, lambda: self._attempt(early + [self.auth(self.codes["Good"])])))
        self.assertTrue(reply["ok"])
        self.assertEqual(processed, [{"type": "ping"}])                # only the ping sent after auth

    def test_timeout_without_auth(self):
        async def body():
            async with websockets.connect(f"ws://127.0.0.1:{GATE_PORT}") as ws:
                await ws.send(json.dumps({"type": "control", "action": "begin"}))
                reply = json.loads(await asyncio.wait_for(ws.recv(), 5))
                try:
                    await asyncio.wait_for(ws.recv(), 5)
                except ConnectionClosed:
                    pass
                return reply, ws.close_code
        (reply, cc), processed = run(self._serve(self.gate, body))
        self.assertEqual((reply["ok"], reply["reason"], cc), (False, "invalid", 4401))
        self.assertEqual(processed, [])

    def test_log_never_has_the_code(self):
        records = []
        h = logging.Handler()
        h.emit = lambda r: records.append(r.getMessage())
        ac.log.addHandler(h)
        ac.log.setLevel(logging.INFO)
        try:
            run(self._serve(self.gate, lambda: self._attempt([self.auth(self.codes["Good"])])))
            run(self._serve(self.gate, lambda: self._attempt([self.auth("WXYZ2345")])))
        finally:
            ac.log.removeHandler(h)
        text = "\n".join(records)
        self.assertIn("label='Good'", text)
        self.assertIn("addr=127.0.0.1", text)
        self.assertNotIn(self.codes["Good"], text)
        self.assertNotIn("WXYZ2345", text)


# ---- the real interview server class, with stand-in services --------------------------------------------------------------------------
class StubLLM:
    def __init__(self):
        self.calls = 0
        self.url, self.model, self.context_length, self.config = "", "stub", 0, {}

    def __getattr__(self, name):
        def anything(*a, **k):
            self.calls += 1
            return None
        return anything


class TestInterviewServer(GateFixture):
    """The hook in WebSocketServer.handle_connection: no message is processed and no service is used before auth."""

    def build(self):
        from app.websocket.server_enhanced_fixed import WebSocketServer
        from app.state.manager import StateManager
        self.llm, self.stt, self.tts = StubLLM(), StubLLM(), StubLLM()
        server = WebSocketServer("127.0.0.1", SERVER_PORT, StateManager(), self.stt, self.tts, self.llm)
        server.access = self.gate                     # temporary files, not the real config/access_codes.json
        self.seen = []
        original = server.process_message

        async def spy(session_id, message):
            self.seen.append(json.loads(message).get("type"))
            return await original(session_id, message)
        server.process_message = spy
        return server

    async def _session(self, server, messages, code):
        async with websockets.serve(server.handle_connection, "127.0.0.1", SERVER_PORT):
            async with websockets.connect(f"ws://127.0.0.1:{SERVER_PORT}") as ws:
                for m in messages:
                    await ws.send(json.dumps(m))
                await ws.send(json.dumps({"type": "auth", "code": code, "client": "quest", "app_version": "test"}))
                got = []
                try:
                    while True:
                        got.append(json.loads(await asyncio.wait_for(ws.recv(), 2)))
                        if got[-1].get("type") == "session_init":
                            await ws.send(json.dumps({"type": "ping"}))
                except (asyncio.TimeoutError, ConnectionClosed):
                    pass
                return got, ws.close_code

    def test_nothing_processed_before_auth(self):
        server = self.build()
        early = [{"type": "control", "action": "begin"}, {"type": "text_data", "text": "hello"}, {"type": "audio_data", "data": "AAAA"}]
        got, _ = run(self._session(server, early, self.codes["Good"]))
        self.assertEqual(got[0]["type"], "auth_result")
        self.assertTrue(got[0]["ok"])
        self.assertEqual(got[1]["type"], "session_init")             # the normal protocol starts only after auth
        self.assertEqual(self.seen, ["ping"])
        self.assertEqual((self.llm.calls, self.stt.calls, self.tts.calls), (0, 0, 0))
        self.assertEqual(server.access.active, {})                    # released when the socket closed

    def test_bad_code_never_reaches_the_server(self):
        server = self.build()
        got, cc = run(self._session(server, [{"type": "control", "action": "begin"}], "ABCD2345"))
        self.assertEqual([g["type"] for g in got], ["auth_result"])
        self.assertEqual(cc, 4401)
        self.assertEqual(self.seen, [])
        self.assertEqual(server.active_connections, {})

    def test_switch_off(self):
        server = self.build()
        server.access = self.make_gate(require_access_code=False)
        got, _ = run(self._session(server, [], "anything"))
        types = [g["type"] for g in got]
        self.assertIn("session_init", types)
        self.assertIn("auth_result", types)                            # an "auth" message is still answered ok
        self.assertTrue([g for g in got if g["type"] == "auth_result"][0]["ok"])

    def test_turn_spend_is_recorded_for_code_sessions(self):
        """process_audio_pipeline adds the shared client's spend during a code session's turn to that code."""
        server = self.build()

        class Anth:
            spent = 0.0
        self.llm._anth = Anth()

        async def fake_turn(session_id, audio, forced_transcript=None):
            self.llm._anth.spent += 0.03
        server._process_audio_pipeline_inner = fake_turn
        entry, _ = self.gate.check(self.codes["Good"], "1.1.1.1", "sess-spend")
        run(server.process_audio_pipeline("sess-spend", b"", "hello"))
        self.assertAlmostEqual(self.gate.state["spend"][ac.today()][entry["id"]], 0.03)
        self.gate.release("sess-spend")

    def test_kill_switch_refuses_at_connect(self):
        server = self.build()
        open(server.access.kill_switch, "w").close()
        got, cc = run(self._session(server, [], self.codes["Good"]))
        self.assertEqual((got[0]["reason"], cc), ("busy", 4503))
        self.assertIn("switched off", got[0]["message"])
        self.assertEqual(self.seen, [])


class TestSpendKillSwitchAndGlobalBrake(GateFixture):
    def test_code_spend_cap(self):
        entry, why = self.gate.check(self.codes["Good"], "1.1.1.1", "s1")
        self.assertEqual(why, "")
        self.gate.add_spend("s1", 0.20)
        self.assertEqual(self.gate.allow_turn("s1"), (True, ""))
        self.gate.add_spend("s1", 0.06)                                     # over the default $0.25 per code
        ok, msg = self.gate.allow_turn("s1")
        self.assertFalse(ok)
        self.assertFalse(self.gate.count_interview("s1")[0])                 # no new interview either
        self.gate.release("s1")
        self.assertEqual(self.make_gate().check(self.codes["Good"], "1.1.1.1", "s2")[1], "spend_code")   # persisted
        self.assertEqual(self.gate.check(self.codes["Single"], "1.1.1.1", "s3")[1], "")                # other codes fine

    def test_code_own_cap_and_global_cap(self):
        data = ac.load_codes(self.codes_file)
        for e in data["codes"]:
            e["usd_per_day"] = 5.0
        ac.save_codes(self.codes_file, data)
        os.utime(self.codes_file, (0, 0))
        gate = self.make_gate(quest_daily_usd_cap=1.0)
        gate.check(self.codes["Good"], "1.1.1.1", "s1")
        gate.add_spend("s1", 0.9)
        self.assertEqual(gate.allow_turn("s1"), (True, ""))                 # own cap $5 wins over the $0.25 default
        gate.add_spend("s1", 0.2)
        self.assertFalse(gate.allow_turn("s1")[0])                           # all codes together passed $1
        gate.release("s1")
        self.assertEqual(gate.check(self.codes["Single"], "1.1.1.1", "s2")[1], "spend_all")

    def test_spend_reasons_on_the_wire(self):
        self.assertEqual(ac.WIRE["spend_code"], "limit_reached")
        self.assertEqual(ac.WIRE["spend_all"], "limit_reached")
        self.assertEqual(ac.WIRE["disabled"], "busy")
        self.assertEqual(ac.WIRE["rate_limited_all"], "rate_limited")
        for internal, wire in ac.WIRE.items():
            self.assertIn(wire, ac.CLOSE_CODES)

    def test_non_code_sessions_untouched(self):
        self.gate.add_spend("web-session", 5.0)
        self.assertEqual(self.gate.state["spend"], {})
        self.assertEqual(self.gate.allow_turn("web-session"), (True, ""))

    def test_kill_switch_without_restart(self):
        self.gate.check(self.codes["Good"], "1.1.1.1", "running")
        open(self.gate.kill_switch, "w").close()
        self.assertEqual(self.gate.check(self.codes["Single"], "1.1.1.1", "new")[1], "disabled")
        self.assertFalse(self.gate.allow_turn("running")[0])                 # a running interview gets no more turns
        self.assertFalse(self.gate.count_interview("running")[0])
        os.remove(self.gate.kill_switch)
        self.assertEqual(self.gate.allow_turn("running"), (True, ""))
        self.assertEqual(self.gate.check(self.codes["Single"], "1.1.1.1", "new")[1], "")

    def test_global_brake_on_spread_out_guessing(self):
        gate = self.make_gate(global_fail_limit=6, fail_limit=5)
        for i in range(6):
            self.assertEqual(gate.check("WRONG%03d" % i, "10.0.0.%d" % i, "x")[1], "invalid")   # 6 addresses, 1 try each
        self.assertEqual(gate.check(self.codes["Good"], "10.9.9.9", "y")[1], "rate_limited_all")
        self.assertEqual(self.make_gate().check(self.codes["Good"], "10.9.9.9", "y")[1], "rate_limited_all")   # persisted

    def test_revoke_takes_effect_without_restart(self):
        self.assertEqual(self.gate.check(self.codes["Good"], "1.1.1.1", "a")[1], "")
        self.gate.release("a")
        data = ac.load_codes(self.codes_file)
        for e in data["codes"]:
            if e["label"] == "Good":
                e["revoked"] = True
        ac.save_codes(self.codes_file, data)
        os.utime(self.codes_file, (1, 1))
        self.assertEqual(self.gate.check(self.codes["Good"], "1.1.1.1", "b")[1], "revoked")


class TestMacNginxHeaders(GateFixture):
    """The Mac sends CF-Connecting-IP (set by Cloudflare) and X-Forwarded-For = $http_cf_connecting_ip (one value, overwritten)."""
    settings = {"trusted_proxies": ["100.64.0.2", "127.0.0.1", "::1"]}

    def test_cf_connecting_ip_first(self):
        h = {"CF-Connecting-IP": "203.0.113.7", "X-Forwarded-For": "198.51.100.9"}
        self.assertEqual(self.gate.client_address(FakeWS("100.64.0.2", h)), "203.0.113.7")

    def test_single_forwarded_value(self):
        self.assertEqual(self.gate.client_address(FakeWS("100.64.0.2", {"X-Forwarded-For": "203.0.113.7"})), "203.0.113.7")

    def test_appended_localhost_is_skipped(self):
        """Even with the old $proxy_add_x_forwarded_for, cloudflared's 127.0.0.1 is skipped, so friends don't share one bucket."""
        h = {"X-Forwarded-For": "203.0.113.7, 127.0.0.1"}
        self.assertEqual(self.gate.client_address(FakeWS("100.64.0.2", h)), "203.0.113.7")


if __name__ == "__main__":
    unittest.main(verbosity=2)
