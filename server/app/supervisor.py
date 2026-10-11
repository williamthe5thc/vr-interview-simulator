"""Health checks and self-healing for the interview server's dependencies.

- Ollama (language model) and AllTalk (voice) are probed every few seconds.
- AllTalk can hang while still answering /api/ready (seen once: synthesis never returned), so the TTS results of real replies are
  counted too: after two failures in a row the voice engine is restarted automatically (with a cooldown), then warmed up.
- The headset is told the current state ("server_status" message) so the user sees a notice instead of silence.
"""
import asyncio
import logging
import os
import subprocess
import time
import urllib.request

logger = logging.getLogger("supervisor")

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class Supervisor:
    def __init__(self, tts_service=None, llm_client=None, auto_restart_voice=True, restart_cooldown=180.0):
        self.tts_service = tts_service
        self.llm_client = llm_client
        self.auto_restart_voice = auto_restart_voice
        self.restart_cooldown = restart_cooldown
        self.tts_failures = 0
        self.last_restart = 0.0
        self.restarting = False
        self.llm_ok = True
        self.voice_ok = True
        # AllTalk can need over 5 minutes to start (its RVC module imports very slowly), so a voice that has not been up yet
        # since this server started is given a long grace period before being treated as hung and restarted
        self.started = time.time()
        self.voice_seen_ok = False
        self.startup_grace = 600.0

    # ------------------------------------------------------------------ probes

    @staticmethod
    def _http_ok(url: str, timeout: float = 4.0) -> bool:
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return 200 <= r.status < 300
        except Exception:
            return False

    async def check(self):
        """Probe both dependencies. Returns (llm_ok, voice_ok)."""
        llm_url = getattr(self.llm_client, "url", "http://127.0.0.1:11434")
        self.llm_ok = await asyncio.to_thread(self._http_ok, f"{llm_url}/api/tags")
        self.voice_ok = await asyncio.to_thread(self._http_ok, self._voice_probe_url())
        if self.voice_ok:
            self.voice_seen_ok = True
        return self.llm_ok, self.voice_ok

    def _engine(self) -> str:
        """Voice engine in use: "alltalk" (XTTS) or "kokoro" (tools/tts_worker.py)."""
        return ((getattr(self.tts_service, "config", None) or {}).get("engine") or "alltalk").lower()

    def _voice_probe_url(self) -> str:
        if self._engine() == "kokoro":
            return ((getattr(self.tts_service, "config", None) or {}).get("kokoro", {}).get("url", "http://127.0.0.1:8771")) + "/health"
        return getattr(self.tts_service, "base_url", "http://127.0.0.1:7851") + "/api/ready"

    def status_text(self) -> str:
        """What to tell the user; empty when everything is fine."""
        if self.restarting:
            return "The voice engine stopped responding and is restarting. Replies may be silent for about a minute."
        parts = []
        if not self.llm_ok:
            parts.append("The language model (Ollama) is not responding")
        if not self.voice_ok:
            parts.append(f"The voice engine ({'Kokoro' if self._engine() == 'kokoro' else 'AllTalk'}) is not responding")
        return ". ".join(parts) + ("." if parts else "")

    # ------------------------------------------------------------------ results of real replies

    def note_tts(self, ok: bool):
        self.tts_failures = 0 if ok else self.tts_failures + 1
        if ok:
            self.voice_ok = True

    def voice_needs_restart(self) -> bool:
        if not self.voice_seen_ok and time.time() - self.started < self.startup_grace:
            return False   # still starting up: do not kill it halfway through loading
        return (self.auto_restart_voice and not self.restarting and self.tts_failures >= 2
                and time.time() - self.last_restart > self.restart_cooldown)

    # ------------------------------------------------------------------ restarting AllTalk

    def _alltalk_dir(self) -> str:
        return getattr(self.tts_service, "alltalk_dir", None) or "PATH_TO_ALLTALK/alltalk_tts"

    def _kill_alltalk(self):
        # the worker (tts_server.py) AND its launcher (script.py) must both go, or the new one cannot bind its ports
        ps = ("Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -and $_.ExecutablePath -match 'alltalk' "
              "-and $_.CommandLine -match 'script\\.py|tts_server\\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }")
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, timeout=60, creationflags=NO_WINDOW)

    def _start_alltalk(self):
        d = self._alltalk_dir()
        bat = os.path.join(d, "start_alltalk.bat")
        log = open(os.path.join(os.environ.get("TEMP", "."), "alltalk_supervised.log"), "ab")
        subprocess.Popen(["cmd.exe", "/c", bat], cwd=d, stdout=log, stderr=log, creationflags=NO_WINDOW)

    def _kill_kokoro(self):
        ps = ("Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'tools.tts_worker\\.py' } "
              "| ForEach-Object { Stop-Process -Id $_.ProcessId -Force }")
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, timeout=60, creationflags=NO_WINDOW)

    def _start_kokoro(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        log = open(os.path.join(os.environ.get("TEMP", "."), "tts_worker_supervised.log"), "ab")
        subprocess.Popen([os.path.join(root, ".venv_tts", "Scripts", "python.exe"), os.path.join("tools", "tts_worker.py"), "--port", "8771"],
                         cwd=root, stdout=log, stderr=log, creationflags=NO_WINDOW)

    async def restart_voice(self, notify=None) -> bool:
        """Kill and restart AllTalk, wait until it answers, warm it up. `notify` is an async callable run when the state changes."""
        if self.restarting or time.time() - self.last_restart < self.restart_cooldown:
            return False
        self.restarting = True
        self.last_restart = time.time()
        kokoro = self._engine() == "kokoro"
        logger.warning(f"Voice engine failed repeatedly: restarting {'the Kokoro worker' if kokoro else 'AllTalk'}")
        if notify:
            await notify()
        try:
            await asyncio.to_thread(self._kill_kokoro if kokoro else self._kill_alltalk)
            await asyncio.sleep(4)
            await asyncio.to_thread(self._start_kokoro if kokoro else self._start_alltalk)
            probe = self._voice_probe_url()
            ready = False
            for _ in range(30 if kokoro else 200):   # Kokoro is up in seconds; a cold AllTalk start takes over 5 minutes
                await asyncio.sleep(2)
                if await asyncio.to_thread(self._http_ok, probe):
                    ready = True
                    break
            if ready and self.tts_service is not None:
                try:   # the first synthesis after a start is slow (about 10 s); do it now instead of during an interview
                    await asyncio.wait_for(asyncio.to_thread(self.tts_service.synthesize, "Hello."), timeout=60)
                except Exception as e:
                    logger.warning(f"Voice warm-up failed: {e}")
            self.tts_failures = 0
            self.voice_ok = ready
            logger.info("AllTalk restart " + ("finished" if ready else "did NOT come back"))
            return ready
        finally:
            self.restarting = False
            if notify:
                await notify()
