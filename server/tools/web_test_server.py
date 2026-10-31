"""Offline test instance of the interview server's own code on port 8767 (never the live 8765): shared workers, its own log, a temp spend file,
config overrides from the environment (WEB_TEST_CFG json, WEB_TEST_STATE path). Used by tools/web_test.py."""
import asyncio, json, logging, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
from server import EnhancedServer  # noqa: E402


class NoSupervisor:
    llm_ok = voice_ok = voice_seen_ok = True
    restarting = auto_restart_voice = False
    tts_failures = 0

    def status_text(self): return ""
    async def check(self): return None
    def voice_needs_restart(self): return False
    def note_tts(self, ok): return None
    async def restart_voice(self, cb=None): return None


class TestServer(EnhancedServer):
    def _load_config(self, p):
        cfg = super()._load_config(p)
        cfg["server"]["port"] = 8767
        return cfg

    def __init__(self):
        super().__init__()
        root = logging.getLogger()
        for h in root.handlers[:]:
            root.removeHandler(h)
        fh = logging.FileHandler(os.path.join("logs", "web_test.log"), mode="w", encoding="utf-8")
        fh.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s"))
        root.addHandler(fh)
        root.setLevel(logging.INFO)
        ws = self.websocket_server
        ws.port = 8767
        ws.supervisor = NoSupervisor()
        ws.web.state_file = os.environ["WEB_TEST_STATE"]
        ws.web.cfg.update(json.loads(os.environ.get("WEB_TEST_CFG", "{}")))

    async def start(self):
        await self.websocket_server.start()


if __name__ == "__main__":
    server = TestServer()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(server.start())
    loop.run_forever()
