"""
Optional hosted-model backend for the interviewer: Claude Haiku 5.5 over the Anthropic Messages API (lowest effort, thinking off).

Switching is a one-word file, so it can be turned on and off WITHOUT restarting the server:
    config\\llm_backend.txt   contains "anthropic" or "local" (missing or anything else = local, the Ollama model)
scripts\\switch_llm.ps1 writes that file. The next reply uses the new setting.

Safety: the key is read from the user environment variable VRSIM_ANTHROPIC_API_KEY (process environment first, then the Windows
user registry) and goes only into the x-api-key header; it is never logged or stored. Estimated spend is tracked per server run and
the backend turns itself off (replies fall back to the local model) when it passes `anthropic_session_cap_usd` (default 2.00).
Any API error before the first token also falls back to the local model, so an interview never stalls on the network.
"""
import json
import logging
import os
import queue
import threading
import time

import requests

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config")
SWITCH_FILE = os.path.join(CONFIG_DIR, "llm_backend.txt")
MODEL = "claude-haiku-5-5"
PRICE_IN, PRICE_OUT = 0.20, 1.00      # $/1M tokens: above the "from $0.10 / $0.50" list price, so the cap errs on the safe side
SONNET = "claude-sonnet-5-5"
PRICES = {MODEL: (0.20, 1.00), SONNET: (2.00, 10.00)}      # Sonnet 5.5 list price; cache reads 10% of input here (a little high for Sonnet: errs safe)
log = logging.getLogger("anthropic_backend")


def wanted():
    """True when the switch file says "anthropic"."""
    try:
        return open(SWITCH_FILE, encoding="utf-8").read().strip().lower() == "anthropic"
    except OSError:
        return False


def _key():
    key = os.environ.get("VRSIM_ANTHROPIC_API_KEY", "").strip()
    if not key:
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                key = str(winreg.QueryValueEx(k, "VRSIM_ANTHROPIC_API_KEY")[0]).strip()
        except Exception:
            key = ""
    return key


class AnthropicBackend:
    def __init__(self, cap_usd=2.0):
        self.cap = cap_usd
        self.spent = 0.0
        self.calls = 0
        self.use_temperature = True
        self.warned_cap = False
        self.fallbacks = 0
        self.http = requests.Session()        # keeps the TLS connection open between replies (saves a handshake per turn)

    def active(self):
        """Switched on, key present and under the spend cap."""
        if not wanted():
            return False
        if self.spent >= self.cap:
            if not self.warned_cap:
                log.warning(f"Anthropic spend cap reached (about ${self.spent:.3f} >= ${self.cap}); using the local model")
                self.warned_cap = True
            return False
        return bool(_key())

    def _body(self, messages, max_tokens, temperature, stop, stream, model=None):
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        model = model or MODEL
        # lowest thinking each model allows: Haiku 5.5 "disabled"; Sonnet 5.5 "between_tools" (its lowest setting); effort low for both
        body = {"model": model, "max_tokens": max_tokens, "stream": stream, "output_config": {"effort": "low"},
                "thinking": {"type": "between_tools" if model == SONNET else "disabled"},
                "messages": [{"role": m["role"], "content": m["content"]} for m in messages if m["role"] != "system"]}
        if system:
            body["system"] = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
        if self.use_temperature and temperature is not None:
            body["temperature"] = temperature
        if stop:
            body["stop_sequences"] = stop
        return body

    def preconnect(self):
        """Opens the TLS/HTTP connection to the API host (no key sent, no model call, no tokens, no cost) so the first reply does not pay for the handshake."""
        try:
            t = time.time()
            self.http.get("https://api.anthropic.com/", timeout=5).content
            log.info(f"Anthropic connection opened in {time.time() - t:.2f}s")
        except Exception as e:
            log.info(f"Anthropic pre-connect skipped: {type(e).__name__}")

    def _count(self, usage, first_token_s=None, model=None):
        self.calls += 1
        pin, pout = PRICES.get(model or MODEL, (PRICE_IN, PRICE_OUT))
        cost = ((usage.get("input_tokens") or 0) * pin + (usage.get("cache_creation_input_tokens") or 0) * pin * 1.25
                + (usage.get("cache_read_input_tokens") or 0) * pin * 0.1 + (usage.get("output_tokens") or 0) * pout) / 1e6
        self.spent += cost
        ft = f" first_token={first_token_s:.2f}s" if first_token_s is not None else ""
        log.info(f"Anthropic call {self.calls} ({model or MODEL}):{ft} in={usage.get('input_tokens')} out={usage.get('output_tokens')} "
                 f"cache_read={usage.get('cache_read_input_tokens')} ~${cost:.5f}; session total ~${self.spent:.4f}")

    def _post(self, body, stream, read_timeout=30):
        key = _key()
        r = self.http.post("https://api.anthropic.com/v1/messages", json=body, stream=stream, timeout=(5, read_timeout),
                          headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
        if r.status_code != 200:
            text = r.text[:300].replace(key, "***")
            r.close()
            if r.status_code == 400 and "temperature" in text.lower() and self.use_temperature:
                self.use_temperature = False           # this model does not take a temperature: drop it and retry once
                body.pop("temperature", None)
                return self._post(body, stream, read_timeout)
            raise RuntimeError(f"Anthropic HTTP {r.status_code}: {text}")
        return r

    def stream_chunks(self, messages, max_tokens, temperature, stop, first_token_timeout=None):
        """Yields Ollama-style chunks ({"message": {"content": piece}, "done": bool, "done_reason": str}) so the caller's loop is unchanged.
        With first_token_timeout (seconds) a TimeoutError is raised, before anything was yielded, when no text has arrived by then; the
        request is abandoned and the caller answers that turn with the local model."""
        cancel = threading.Event()
        if not first_token_timeout:
            yield from self._stream_raw(messages, max_tokens, temperature, stop, cancel)
            return
        q = queue.Queue()

        def pump():
            try:
                for c in self._stream_raw(messages, max_tokens, temperature, stop, cancel):
                    q.put(c)
                q.put(None)
            except Exception as e:
                q.put(e)

        threading.Thread(target=pump, daemon=True).start()
        got, deadline = False, time.time() + first_token_timeout
        try:
            while True:
                try:
                    item = q.get(timeout=60 if got else max(0.01, deadline - time.time()))
                except queue.Empty:
                    self.fallbacks += 1
                    raise TimeoutError(f"no first token within {first_token_timeout}s")
                if item is None:
                    return
                if isinstance(item, Exception):
                    raise item
                got = got or bool(item["message"]["content"])
                yield item
        finally:
            cancel.set()

    def _stream_raw(self, messages, max_tokens, temperature, stop, cancel):
        t0 = time.time()
        r = self._post(self._body(messages, max_tokens, temperature, stop, True), True)
        usage, reason, first = {}, "stop", None
        with r:
            for line in r.iter_lines():
                if cancel.is_set():
                    return
                if not line or not line.startswith(b"data:"):
                    continue
                j = json.loads(line[5:].strip())
                t = j.get("type")
                if t == "message_start":
                    usage.update((j.get("message") or {}).get("usage") or {})
                elif t == "message_delta":
                    usage.update(j.get("usage") or {})
                    sr = (j.get("delta") or {}).get("stop_reason")
                    if sr:
                        reason = "length" if sr == "max_tokens" else "stop"
                elif t == "content_block_delta":
                    piece = (j.get("delta") or {}).get("text") or ""
                    if piece:
                        if first is None:
                            first = time.time() - t0
                        yield {"message": {"content": piece}, "done": False}
                elif t == "error":
                    raise RuntimeError("Anthropic stream error")
        self._count(usage, first)
        yield {"message": {"content": ""}, "done": True, "done_reason": reason}

    def complete(self, messages, max_tokens, temperature, stop=None, model=None, read_timeout=60):
        r = self._post(self._body(messages, max_tokens, temperature, stop, False, model), False, read_timeout)
        j = r.json()
        self._count(j.get("usage") or {}, None, model)
        return "".join(b.get("text", "") for b in j.get("content", []) if b.get("type") == "text").strip()
