"""
The child ("Maya") for the parent-child scenario: an OllamaClient whose prompt, state meter and fixed lines come from persona.py.
It reuses the interview client's streaming, hosted-model (Claude Haiku) switch, first-token fallback to the local model and sentence logic.
Nothing about the parent's words is logged: only the state moves and which moves the code saw.
"""
import logging
import re
import time

import os

from services.llm import anthropic_backend
from services.llm.Ollama_client import OllamaClient
from app.parent_child import persona as P

log = logging.getLogger("parent_child")


PC_SWITCH_FILE = os.path.join(anthropic_backend.CONFIG_DIR, "pc_llm_backend.txt")


def pc_wanted():
    """The parent-child server has its OWN switch (config/pc_llm_backend.txt: anthropic or local, default local), separate from the
    interview server's config/llm_backend.txt."""
    try:
        with open(PC_SWITCH_FILE, encoding="utf-8") as f:
            return f.read().strip().lower() == "anthropic"
    except OSError:
        return False


class PCBackend(anthropic_backend.AnthropicBackend):
    def active(self):
        if not pc_wanted():
            return False
        if self.spent >= self.cap:
            return False
        return bool(anthropic_backend._key())


class ParentChildClient(OllamaClient):
    STREAM_MAX_SENTENCES = 2         # Maya says one or two short sentences

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config.setdefault("options", {})["num_predict"] = 60
        self.config["keep_alive"] = "24h"      # shares the loaded qwen with the interview server's fallback: never shorten its keep-alive
        self._anth = PCBackend(self.config.get("anthropic_session_cap_usd", 2.0))     # its own switch: local by default
        self.tts = None              # set by the server: lets the safety message use a neutral voice
        self.scenario = P.SCENARIO_ID
        self._reset()

    # ---- scenario state -----------------------------------------------------------------------------------------------------------
    def _reset(self):
        self.state = "restless"
        self.turns = 0
        self.limit_stated = False
        self.ended = None            # None while running, else why it ended: complied / turns / gave_in / stopped / safety
        self.turn_log = []           # [{"turn", "flags", "state"}] (no words), also used as a hint by the coach
        self._last_fixed = None

    def set_job(self, job_id):       # the headset sends `job` for interviews; the scenario id is handled in begin_scenario
        return None

    def begin_scenario(self, scenario=None):
        self.scenario = scenario or P.SCENARIO_ID
        self._reset()

    def _end(self, why):
        self.ended = why
        log.info(f"Scenario ended: {why} after {self.turns} parent turn(s); states {[t['state'] for t in self.turn_log]}")

    def _say_fixed(self, text, narrator=False):
        if self.tts is not None and hasattr(self.tts, "use_narrator"):
            self.tts.use_narrator(narrator)
        self._last_fixed = text
        return text

    # ---- one reply -------------------------------------------------------------------------------------------------------------------
    def stream_response(self, prompt, context=None, interaction_stage=None):
        context = context or []
        self.last_stats = None
        text = (prompt or "").strip()
        if not context:                                  # `begin`: Maya speaks first, a fixed line
            self._reset()
            if self.tts is not None and hasattr(self.tts, "use_narrator"):
                self.tts.use_narrator(False)
            yield self._say_fixed(P.pick(P.OPENERS))
            return
        if self.ended:
            yield self._say_fixed(P.STOP_LINE)
            return
        if P.disclosure(text):                           # possible real harm: no improvising, fixed message, scene ends
            self._end("safety")
            yield self._say_fixed(P.SAFETY_MESSAGE, narrator=True)
            return
        if P.wants_stop(text):
            self._end("stopped")
            yield self._say_fixed(P.STOP_LINE)
            return
        self.turns += 1
        flags = P.read_parent_turn(text)
        before = self.state
        if flags["gave_in"] and not flags["harsh"]:
            self.turn_log.append({"turn": self.turns, "flags": {k: v for k, v in flags.items() if v}, "state": "gave_in"})
            self._end("gave_in")
            yield self._say_fixed(P.pick(P.GAVE_IN_LINES))
            return
        self.state = P.next_state(before, flags)
        self.limit_stated = self.limit_stated or flags["limit"]
        self.turn_log.append({"turn": self.turns, "flags": {k: v for k, v in flags.items() if v}, "state": self.state})
        log.info(f"Parent turn {self.turns}: {[k for k, v in flags.items() if v] or 'nothing notable'}; child {before} -> {self.state}")
        if self.state == "calming" and before == "calming" and self.limit_stated:
            self._end("complied")                        # calm for two turns in a row and the limit was stated: Maya does it
            yield self._say_fixed(P.pick(P.COMPLY_LINES, self._last_fixed))
            return
        if self.turns >= P.MAX_PARENT_TURNS:
            self._end("turns")
            yield self._say_fixed(P.pick(P.RESET_LINES, self._last_fixed))
            return
        self._say_fixed("", narrator=False)
        yield from super().stream_response(prompt, context, interaction_stage)

    # ---- prompt and filter (used by the inherited streaming code) -------------------------------------------------------------
    def _build_messages(self, user_input, context, interaction_stage=None):
        self.forced_question = self.forced_fixed_ack = self.fixed_reply = self.reply_prefix = None
        self.last_stage = "conversation"
        self._judgement = False
        history = []
        for turn in self._prune_context(context or []):
            content = (turn.get("content") or "").strip()
            if content and turn.get("role") in ("user", "assistant"):
                history.append({"role": turn["role"], "content": content})
        note = " ".join(P.STATE_NOTES.get(self.state, P.STATE_NOTES["restless"]).split())
        last = [h["content"] for h in history if h["role"] == "assistant"][-2:]
        if last:
            note += " Say something different from your last lines (" + " | ".join(last) + ")."
        return ([{"role": "system", "content": P.MAYA_PROMPT.format(state_note="")}] + history +
                [{"role": "user", "content": f"{user_input}\n\n[Private note to you, Maya, for your next reply only; your parent did not say this: {note}]"}])

    def _clean_response(self, text, done_reason=None):
        cleaned = super()._clean_response(text, done_reason)
        if not cleaned:
            return cleaned
        return P.clean_child_text(cleaned, self.state)
