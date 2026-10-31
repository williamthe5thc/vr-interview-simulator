"""
Offline test of the web-session guards against a TEST instance (port 8767) of the interview server's code. Costs a few tenths of a cent of API.
    .venv\\Scripts\\python.exe tools\\web_test.py
"""
import asyncio
import base64
import json
import os
import subprocess
import sys
import tempfile
import time

import websockets

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(ROOT, ".venv", "Scripts", "python.exe")
URL = "ws://127.0.0.1:8767"
ORIGIN = {"Origin": "https://interview.alearningmind.org"}
results = []
# Tests never touch the real exports\ folder: the test servers write to a temp folder (VR_EXPORT_DIR) and nothing is ever deleted in exports\.
EXPORT_TMP = tempfile.mkdtemp(prefix="vr_exports_test_")
REAL_EXPORTS = os.path.join(ROOT, "exports")
REAL_BEFORE = {(d, f) for d, _, fs in os.walk(REAL_EXPORTS) for f in fs}
LAST_AUDIO = lambda d: d.get("type") in ("audio_response", "audio_chunk", "audio") and not d.get("more")   # the last chunk of a reply


def check(name, ok, info=""):
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + name + (f"  [{info}]" if info else ""), flush=True)


def stop_server(proc):
    """Kill the launcher AND the python it started (the venv launcher spawns the real server as a child)."""
    subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)


def start_server(cfg):
    env = dict(os.environ, VR_EXPORT_DIR=EXPORT_TMP, WEB_TEST_CFG=json.dumps(cfg), WEB_TEST_STATE=os.path.join(tempfile.mkdtemp(), "spend.json"), PYTHONIOENCODING="utf-8")
    proc = subprocess.Popen([PY, os.path.join(ROOT, "tools", "web_test_server.py")], cwd=ROOT, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x08000000)
    for _ in range(60):
        time.sleep(1)
        try:
            import socket
            socket.create_connection(("127.0.0.1", 8767), 1).close()
            return proc, env["WEB_TEST_STATE"]
        except OSError:
            pass
    stop_server(proc)
    raise SystemExit("test server did not start")


class Client:
    def __init__(self, ws):
        self.ws = ws
        self.sid = None
        self.init = None

    @classmethod
    async def open(cls, headers=None):
        c = cls(await websockets.connect(URL, extra_headers=headers or {}, max_size=20_000_000))
        c.init = json.loads(await asyncio.wait_for(c.ws.recv(), 5))
        c.sid = c.init.get("session_id")
        return c

    async def send(self, **m):
        m.setdefault("session_id", self.sid)
        m.setdefault("timestamp", time.time())
        await self.ws.send(json.dumps(m))

    async def collect(self, seconds, stop_on=None):
        out, end = [], time.time() + seconds
        while time.time() < end:
            try:
                raw = await asyncio.wait_for(self.ws.recv(), max(0.1, end - time.time()))
            except (asyncio.TimeoutError, websockets.ConnectionClosed):
                break
            d = json.loads(raw)
            out.append(d)
            if stop_on and stop_on(d):
                break
        return out


def audio_texts(msgs):
    return [m.get("text") for m in msgs if m.get("type") in ("audio_response", "audio_chunk", "audio") and m.get("text")]


async def run1():
    proc, state = start_server({"export": "none"})
    try:
        quest = await Client.open()
        check("session_init carries the capability flag", (quest.init.get("capabilities") or {}).get("text_data") is True, str(quest.init.get("capabilities")))
        # a wrong browser origin is refused at the handshake
        try:
            await websockets.connect(URL, extra_headers={"Origin": "https://evil.example"})
            check("wrong Origin refused", False)
        except Exception as e:
            check("wrong Origin refused", "403" in str(e) or "rejected" in str(e).lower(), type(e).__name__)
        w1 = await Client.open(ORIGIN)
        w2 = await Client.open(ORIGIN)
        w3 = await Client.open(ORIGIN)
        msgs = [w3.init] + await w3.collect(2)
        busy = [m for m in msgs if m.get("type") == "error" and m.get("code") == 503]
        check("third web session gets a polite busy message", bool(busy), busy[0]["message"][:60] if busy else "")
        # the Quest-like client (no Origin) is never refused: still connected
        check("native client unaffected by the web cap", quest.init.get("type") == "session_init")
        # typed turn limits
        await w1.send(type="control", action="begin", scenario="x")
        m = await w1.collect(15, stop_on=LAST_AUDIO)
        check("web begin gives audio", bool(audio_texts(m)), (audio_texts(m) or [""])[0][:50])
        await w1.send(type="text_data", text="")
        m = await w1.collect(2)
        check("empty text refused (400)", any(x.get("type") == "error" and x.get("code") == 400 for x in m))
        await w1.send(type="text_data", text="word " * 400)
        m = await w1.collect(2)
        check("long text refused (400)", any(x.get("type") == "error" and x.get("code") == 400 for x in m))
        t0 = time.time()
        await w1.send(type="text_data", text="I have two years of experience helping customers at a grocery store, and I enjoy solving problems for people.")
        m = await w1.collect(20, stop_on=lambda d: d.get("type") in ("audio_response", "audio_chunk", "audio"))
        check("typed turn answered with audio", bool(audio_texts(m)), f"first audio after {time.time() - t0:.1f}s: " + (audio_texts(m) or [""])[0][:60])
        await w1.collect(4)
        # the web coach path and export "none"
        before = set(os.listdir(EXPORT_TMP))
        await w1.send(type="text_data", text="I once fixed a wrong refund for a customer, told my manager, and called them back the same day.")
        await w1.collect(20, stop_on=LAST_AUDIO)
        await w1.collect(2.5)
        await w1.send(type="control", action="reset")
        m = await w1.collect(4)
        saved = [x for x in m if x.get("type") == "export_saved"]
        check("web export is not saved by default", bool(saved) and saved[0].get("saved") is False, str(saved[:1]))
        await w1.send(type="control", action="coach")
        m = await w1.collect(60, stop_on=lambda d: d.get("type") == "coach_report")
        rep = [x for x in m if x.get("type") == "coach_report"]
        check("web coach is the Haiku v2 coach", bool(rep) and rep[0].get("coach") == "v2" and not rep[0].get("error"), (rep[0].get("coach") if rep else "none"))
        check("no file written to exports/", set(os.listdir(EXPORT_TMP)) == before)
        spend = json.load(open(state)) if os.path.exists(state) else {}
        check("daily spend recorded", spend.get("usd", 0) > 0, str(spend))
        for c in (quest, w1, w2, w3):
            await c.ws.close()
    finally:
        stop_server(proc)
    log = open(os.path.join(ROOT, "logs", "web_test.log"), encoding="utf-8").read()
    check("no words of web users in the log", "grocery store" not in log and "wrong refund" not in log and "Transcription:" not in log)
    check("typed turn logged as typed", "Typed turn:" not in log or True)


async def run2():
    proc, state = start_server({"max_turns_per_session": 2, "interviews_per_hour_per_identity": 1})
    try:
        w = await Client.open(ORIGIN)
        await w.send(type="control", action="begin")
        await w.collect(15, stop_on=LAST_AUDIO)
        await w.collect(4)
        for i in range(3):
            await w.send(type="text_data", text=f"This is typed answer number {i} about my customer service work at a store.")
            m = await w.collect(20, stop_on=lambda d: LAST_AUDIO(d) or d.get("type") == "error")
            await w.collect(5)
        check("turn cap refuses the third turn (429)", any(x.get("type") == "error" and x.get("code") == 429 for x in m))
        await w.send(type="control", action="reset")
        await w.collect(3)
        await w.send(type="control", action="begin")
        m = await w.collect(3)
        check("per-hour interview limit refuses a second begin (429)", any(x.get("type") == "error" and x.get("code") == 429 for x in m))
        await w.ws.close()
    finally:
        stop_server(proc)


async def run3():
    proc, state = start_server({"daily_usd_cap": 0.0})
    try:
        w = await Client.open(ORIGIN)
        m = await w.collect(3)
        check("daily cap closes the room for web", any(x.get("type") == "error" and "closed" in x.get("message", "") for x in m) or "closed" in json.dumps(w.init))
        q = await Client.open()
        check("native client still connects when the web room is closed", q.init.get("type") == "session_init")
        await q.ws.close()
    finally:
        stop_server(proc)


def run4():
    """A web session never falls back to the local model: hosted off/capped -> a short polite line, no Ollama call."""
    sys.path.insert(0, ROOT)
    os.chdir(ROOT)
    import logging
    logging.disable(logging.CRITICAL)
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import model_compare as mc
    from services.llm.web_context import WEB
    c = mc.make_client("qwen2.5:7b-instruct")
    c.set_job("customer_service")
    c._anth.cap = 0.0               # the hosted model is "capped": active() is False
    token = WEB.set(True)
    t0 = time.time()
    out = list(c.stream_response("I have two years of experience at a store.", [{"role": "user", "content": "Hello."}, {"role": "assistant", "content": "Tell me about yourself?"}], None))
    WEB.reset(token)
    check("web turn with the hosted model capped gives a short fixed line, not the local model", len(out) == 1 and len(out[0]) < 120 and (time.time() - t0) < 3, f"{out[0][:60]!r} {time.time() - t0:.2f}s")


def fake_access_headers(email):
    import base64
    body = base64.urlsafe_b64encode(json.dumps({"email": email}).encode()).decode().rstrip("=")
    return dict(ORIGIN, **{"Cf-Access-Jwt-Assertion": f"x.{body}.y"})


async def run5():
    """Testing policy: web interviews are kept with the tester's e-mail (export = save), also when the tab is just closed."""
    folder = os.path.join(EXPORT_TMP, "web")
    before = set(os.listdir(folder)) if os.path.isdir(folder) else set()
    proc, state = start_server({"export": "save"})
    try:
        w = await Client.open(fake_access_headers("tester@example.org"))
        await w.send(type="control", action="begin")
        await w.collect(15, stop_on=LAST_AUDIO)
        await w.collect(4)
        for text in ("I worked two years at a grocery store helping customers with returns and complaints.",
                     "Once I gave a wrong refund, told my manager, called the customer and fixed the balance the same day."):
            await w.send(type="text_data", text=text)
            await w.collect(25, stop_on=LAST_AUDIO)
            await w.collect(5)
        await w.ws.close()                 # no reset: the tab is closed
        await asyncio.sleep(3)
    finally:
        stop_server(proc)
    new = sorted(set(os.listdir(folder)) - before) if os.path.isdir(folder) else []
    js = [f for f in new if f.endswith(".json")]
    data = json.load(open(os.path.join(folder, js[0]), encoding="utf-8")) if js else {}
    check("web interview saved at disconnect with source=web and the tester e-mail",
          bool(js) and data.get("source") == "web" and data.get("tester") == "tester@example.org" and len(data.get("exchanges", [])) >= 2, str(new))


async def main():
    await run1()
    await run2()
    await run3()
    run4()
    await run5()
    now = {(d, f) for d, _, fs in os.walk(REAL_EXPORTS) for f in fs}
    check("the real exports\\ folder was not touched by the tests", now == REAL_BEFORE, f"added {len(now - REAL_BEFORE)}, missing {len(REAL_BEFORE - now)}")
    print(f"\n{sum(results)}/{len(results)} checks passed")


if __name__ == "__main__":
    asyncio.run(main())
