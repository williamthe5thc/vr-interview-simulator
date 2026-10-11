"""
Ollama client with optimized performance and response time.
This module provides an improved client for the Ollama API with
advanced caching, context pruning, and optimized parameter handling.
"""

import json
import logging
import requests
import time
import asyncio
import os
import hashlib
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional, Callable, Union
import re
import random
import importlib


class OllamaClient:
    """
     client for interacting with the Ollama API.
    
    Features:
    - Optimized parameter settings for faster responses
    - Advanced context management with intelligent pruning
    - Sophisticated caching with priority-based invalidation
    - Background precomputation of responses
    - Improved error handling and recovery
    """
    
    def __init__(self, url: str, model: str, context_length: int = 8192, config=None):
        self.url = url.rstrip('/')
        self.model = model
        self.context_length = context_length
        self.logger = logging.getLogger("ollama")
        
        # Default configuration
        self.default_config = {
            "timeout": 15,              # Default timeout in seconds
            "max_retries": 2,           # Maximum retry attempts
            "use_streaming": False,     # Use streaming mode
            "max_cache_entries": 500,   # Maximum cache entries
            "scenario_type": "interview",  # Default scenario type
            "precompute_enabled": False, # Canned precomputation only wastes GPU time at startup
            "interviewer_mode": "scripted",  # "judgement" = prompt for a strong hosted model (Claude), no forced topics / fixed lines; used only while the hosted backend is active
            "cache_enabled": False,      # A conversation must not replay identical answers for identical input
            "keep_alive": "30m",         # Keep the model loaded so the first reply is not slow
            "options": {
                "temperature": 0.8,      # Natural variation between replies
                "top_p": 0.9,
                "top_k": 40,
                "repeat_penalty": 1.1,
                "num_predict": 160,      # Room for 1-3 spoken sentences; the cleaner trims anything longer
                "seed": None             # No fixed seed (a fixed seed made identical inputs give identical outputs)
            }
        }
        
        # Merge with provided config
        self.config = self.default_config.copy()
        if config:
            self._merge_config(self.config, config)
        # optional hosted backend (Claude Haiku 5.5); switched by config\llm_backend.txt, falls back to the local model
        from services.llm.anthropic_backend import AnthropicBackend
        self._anth = AnthropicBackend(self.config.get("anthropic_session_cap_usd", 2.0))
        self._judgement = False
        self._force_scripted = False       # set while a hosted-model turn is being redone with the scripted prompt for the local model
        self._interview_mode = None

        # Store additional metadata
        self.scenario_type = self.config.get("scenario_type", "interview")
        self.cache_enabled = self.config.get("cache_enabled", False)

        # Interviewer persona: chosen once so the name and role stay stable for the whole run
        interview_cfg = self.config.get("interview", {}) or {}
        self.persona = {
            "position_type": interview_cfg.get("position_type", "software_engineer"),
            "interview_style": interview_cfg.get("interview_style", "neutral"),
            "experience_level": interview_cfg.get("experience_level", "mid_level"),
            "company_type": interview_cfg.get("company_type", "tech_startup"),
        }
        self.interviewer_name = interview_cfg.get("interviewer_name")
        self.last_stage = None
        self.candidate_ended = False
        self._reset_topics()
        self._fallback_index = 0
        
        # Load system prompt based on scenario type
        self.system_prompt = self._load_system_prompt()
        
        # Initialize thread pool
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # Initialize enhanced response cache
        self.cache_dir = "data/cache/llm"
        os.makedirs(self.cache_dir, exist_ok=True)
        self.response_cache = {}
        self.max_cache_size = self.config.get("max_cache_entries", 500)
        
        # Cache analytics
        self.cache_hits = 0
        self.cache_misses = 0
        
        # Load cache from disk if available (only when caching is enabled)
        if self.cache_enabled:
            self._load_cache_from_disk()
        
        # Initialize precomputation queue and process
        self.precompute_queue = []
        if self.config.get("precompute_enabled", True):
            self._initialize_precomputation()
        
        self.logger.info(f"Initialized Ollama client for model: {model}")
        self.logger.info(f"Response caching enabled with max size: {self.max_cache_size} entries")
        
        # Log active configuration
        options_str = json.dumps(self.config.get("options", {}), indent=2)
        self.logger.info(f"Using Ollama parameters: {options_str}")
    
    def set_job(self, job_id: Optional[str]) -> None:
        """Choose which job the next interview is for (a new interviewer name is picked for it)."""
        from services.llm.scenarios import job_interview
        if job_id and job_id in job_interview.JOB_CATALOG:
            self.persona["job_id"] = job_id
            self.interviewer_name = None   # every new interview (start or restart) gets a fresh interviewer name
            self._reset_topics()
            self.logger.info(f"Interview job set to {job_id}")
        elif job_id:
            self.logger.warning(f"Unknown job id {job_id!r}; keeping {self.persona.get('job_id')}")

    INTERVIEWER_MODE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config", "interviewer_mode.txt")

    def _read_interviewer_mode(self) -> str:
        """The interviewer mode, judgement or scripted: the word in config/interviewer_mode.txt (written by scripts/switch_interviewer.ps1), else the config value."""
        override = self.config.get("interviewer_mode_override")
        if override:
            return override
        try:
            value = open(self.INTERVIEWER_MODE_FILE, encoding="utf-8").read().strip().lower()
        except OSError:
            value = ""
        return value if value in ("judgement", "scripted") else self.config.get("interviewer_mode", "scripted")

    def warm_local(self):
        """In hosted mode keep the local model loaded (24 h) so a slow or failed API reply can be answered at once."""
        try:
            requests.post(f"{self.url}/api/chat", json={"model": self.model, "messages": [{"role": "user", "content": "Hi"}], "stream": False,
                          "keep_alive": "24h", "options": {"num_predict": 1, "num_ctx": self.config.get("options", {}).get("num_ctx", self.context_length)}}, timeout=120).raise_for_status()
            self.logger.info(f"Local model {self.model} warmed and kept loaded for 24h (hosted-model fallback)")
        except Exception as e:
            self.logger.warning(f"Could not warm the local model: {e}")

    def coach_completion(self, system: str, user: str, max_tokens: int = 230, timeout: float = 90.0, model: Optional[str] = None) -> str:
        """One plain chat completion (no interviewer persona, no reply cleaning), used by the job-coach review."""
        if self._anth.active():
            try:
                return self._anth.complete([{"role": "system", "content": system}, {"role": "user", "content": user}], max_tokens, 0.5,
                                           model=model, read_timeout=timeout)
            except Exception as e:
                self.logger.warning(f"Anthropic coach call failed ({str(e)[:120]}); using the local model")
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "stream": False,
            "keep_alive": self.config.get("keep_alive", "30m"),
            "options": {"temperature": 0.5, "top_p": 0.9, "num_predict": max_tokens, "num_ctx": self.config.get("options", {}).get("num_ctx", self.context_length)},   # same as live replies: a different size makes Ollama reload the model
        }
        if self.config.get("think") is not None:
            payload["think"] = self.config["think"]   # reasoning models (Qwen3.5, Gemma 4): false = answer at once, no hidden thinking
        response = requests.post(f"{self.url}/api/chat", json=payload, timeout=timeout)
        response.raise_for_status()
        return ((response.json().get("message") or {}).get("content") or "").strip()

    def _merge_config(self, base_config: Dict, new_config: Dict) -> None:
        """Recursively merge configuration dictionaries."""
        for key, value in new_config.items():
            if key in base_config and isinstance(base_config[key], dict) and isinstance(value, dict):
                self._merge_config(base_config[key], value)
            else:
                base_config[key] = value
    
    def _load_system_prompt(self) -> str:
        """Load the system prompt for the current scenario type."""
        try:
            # Try to import the scenario module
            from services.llm.scenarios import job_interview
            
            if self.scenario_type == "interview":
                # Get default interview prompt
                return job_interview.get_interview_prompt()
            
            # Custom prompt from config if specified
            if "system_prompt" in self.config:
                return self.config["system_prompt"]
                
            # Default fallback
            return "You are a helpful assistant conducting a professional conversation."
            
        except ImportError:
            self.logger.warning("Could not import scenario modules, using default prompt")
            
            # Use basic prompt from config or default
            if "system_prompt" in self.config:
                return self.config["system_prompt"]
                
            return "You are a helpful assistant conducting a professional conversation."
    
    def _initialize_precomputation(self) -> None:
        """Initialize background precomputation process."""
        # Create a low-priority thread for background computation
        self.precompute_thread = ThreadPoolExecutor(max_workers=1)
        
        # Queue common phrases for precomputation
        self.precompute_queue = [
            "Tell me about yourself",
            "What are your strengths",
            "What are your weaknesses",
            "Why do you want to work here",
            "Where do you see yourself in 5 years"
        ]
        
        # Start precomputation in background
        self.precompute_thread.submit(self._precompute_responses)
        
        self.logger.info("Background precomputation initialized")
    
    def _precompute_responses(self) -> None:
        """Background process to precompute responses for common questions."""
        try:
            # Process queue at low priority
            while self.precompute_queue:
                # Sleep to avoid resource contention
                time.sleep(2.0)
                
                # Get next item
                prompt = self.precompute_queue.pop(0)
                
                # Skip if already in cache
                cache_key = self._create_cache_key(prompt, [], "background_experience")
                if cache_key in self.response_cache:
                    continue
                
                try:
                    # Generate response with low priority
                    self.logger.info(f"Precomputing response for: {prompt}")
                    self.generate_response(
                        prompt, 
                        [], 
                        self.config.get("timeout", 20) * 2,  # Longer timeout for precomputation
                        interaction_stage="background_experience"
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to precompute response: {e}")
        
        except Exception as e:
            self.logger.error(f"Precomputation thread error: {e}")
    
    def _format_prompt(self, user_input: str, context: List[Dict[str, str]], interaction_stage: str = None) -> str:
        """
        Format the prompt with system instructions and conversation history.
        
        Args:
            user_input: The latest user input
            context: List of previous conversation turns
            interaction_stage: Current interaction stage
            
        Returns:
            Formatted prompt for LLM
        """
        # Start with system prompt
        formatted_prompt = self.system_prompt + "\n\n"
        
        # Add brevity instruction for faster responses
        formatted_prompt += "IMPORTANT: Keep your responses very brief - no more than 2-3 sentences. " \
                           "Provide direct and concise answers without unnecessary elaboration.\n\n"
        
        # Add stage-specific guidance if available
        if interaction_stage:
            if interaction_stage == "introduction":
                formatted_prompt += "This is the beginning of the conversation. Introduce yourself warmly.\n\n"
            elif interaction_stage == "technical_assessment":
                formatted_prompt += "Ask a relevant technical question that tests the candidate's knowledge.\n\n"
            elif interaction_stage == "behavioral_assessment":
                formatted_prompt += "Ask a behavioral question that reveals the candidate's soft skills and experience.\n\n"
            elif interaction_stage == "conclusion":
                formatted_prompt += "Begin to wrap up the interview with a summary and next steps.\n\n"
        
        # Add conversation history with intelligent pruning
        if context:
            # Apply context pruning to reduce token count
            pruned_context = self._prune_context(context)
            
            # Add pruned context to prompt
            for turn in pruned_context:
                role = turn["role"]
                content = turn["content"]
                if role == "user":
                    formatted_prompt += f"Candidate: {content}\n"
                elif role == "assistant":
                    formatted_prompt += f"Interviewer: {content}\n"
        
        # Add the current user input
        formatted_prompt += f"Candidate: {user_input}\n\nInterviewer:"
        
        return formatted_prompt
    
    # The candidate asks to end the interview. Only the END of what they said is checked (a long answer such as
    # "...how I wrap up a shift" or "...we end up in this crunch" is not a request), and the loose phrases
    # ("I'm done", "that's all") only count in a short utterance.
    _END_STRONG_RE = re.compile(
        r"\b(?:end|finish|stop|conclude|wrap(?:ping)?(?: up)?)\b[^.?!]{0,20}\b(?:interview|conversation|session)\b"
        r"|\bwrap (?:this|it|things|everything|us) up\b|\blet'?s wrap\b|\bwrap it\b"
        r"|\b(?:let'?s|can we|could we|shall we|i'?d like to|i want to|i would like to|i need to|i'?m going to)\s+(?:just\s+)?"
        r"(?:end|stop|finish|call it|wrap)\b"
        r"|\bgood ?bye\b|\bthanks? (?:so much )?for your time\b|\bi (?:have|need|got) to (?:go|leave|run)\b",
        re.IGNORECASE,
    )
    _END_SHORT_RE = re.compile(
        r"\b(?:i'?m|i am|we'?re|we are)\s+(?:all\s+)?(?:done|finished)"
        r"(?=\W*$|\s+(?:here|now|today|for (?:today|now)|with (?:this|it|the interview)))"
        r"|\bthat'?s (?:all|it|enough)\b|\bno more questions\b|\bbye\b",
        re.IGNORECASE,
    )

    @classmethod
    def wants_to_end(cls, user_input: str) -> bool:
        text = (user_input or "").strip()
        if not text:
            return False
        words = text.split()
        sentences = re.split(r"(?<=[.!?])\s+", text)
        tail = " ".join(" ".join(sentences[-2:]).split()[-30:])
        if cls._END_STRONG_RE.search(tail):
            return True
        return len(words) <= 12 and bool(cls._END_SHORT_RE.search(text))

    # The candidate asks to move on, or says the interviewer is repeating.
    _MOVE_ON_RE = re.compile(
        r"\b(move on|next question|something else|different question|change the subject|"
        r"you('?re| are) (repeating|asking (me )?the same)|(asked|said|told|answered)( me| you)?( that| this| it)? (already|before)|"
        r"already (asked|said|told|answered|covered))\b",
        re.IGNORECASE,
    )
    # Her last line asked for more detail on the SAME thing.
    _DIG_RE = re.compile(r"\b(example|specific|tell me more|walk me through|more about|describe|elaborate)\b", re.IGNORECASE)
    MAX_FOLLOWUPS = 1   # after a topic's opening question the interviewer may follow up this many times, then must open a new topic

    def _resolve_stage(self, context: List[Dict[str, str]], requested: Optional[str], user_input: str) -> str:
        """
        Work out which interview stage we are in from the number of candidate turns so far.

        The websocket server only ever reports "greeting" or "wrap_up" (or nothing), so the stage it passes is
        ignored here. A clear goodbye from the candidate moves straight to the conclusion.
        """
        from services.llm.scenarios import job_interview

        self.candidate_ended = False
        last_assistant = next((t.get("content", "") for t in reversed(context or []) if t.get("role") == "assistant"), "")
        offered_stop = last_assistant in self._OFFER_STOP_REPLIES
        if offered_stop and re.match(r"^\W*(?:yes|yeah|yep|yup|sure|ok|okay|please|stop|let'?s stop|i would|i'?d like to)\b", user_input or "", re.I):
            # "Would you like to stop here?" -> "Yes": that is an end request
            stage = "conclusion"
            self.candidate_ended = True
        elif self.wants_to_end(user_input):
            stage = "conclusion"
            self.candidate_ended = True
        else:
            turn = sum(1 for t in (context or []) if t.get("role") == "user") + 1
            # first candidate turn on which each stage begins
            plan = self.config.get("stage_plan") or [1, 2, 4, 6, 8, 10]
            stage = job_interview.STAGE_ORDER[0]
            for name, start in zip(job_interview.STAGE_ORDER, plan):
                if turn >= start:
                    stage = name
        self.last_stage = stage
        return stage

    @staticmethod
    def _content_words(text: str) -> set:
        stop = {"the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with", "that", "this", "it", "is", "are", "was",
                "were", "be", "you", "your", "me", "my", "how", "what", "did", "do", "does", "can", "could", "would", "about",
                "have", "has", "had", "so", "as", "at", "from", "by", "i", "we", "they", "their", "there", "when", "which"}
        return {w for w in re.findall(r"[a-z']+", (text or "").lower()) if w not in stop and len(w) > 2}

    @classmethod
    def _last_question_of(cls, text: str) -> str:
        sentences = re.split(r"(?<=[.!?])\s+", (text or "").strip())
        return next((s for s in reversed(sentences) if s.endswith("?")), sentences[-1] if sentences else "")

    def _reset_topics(self) -> None:
        self._topic_anchor = 0          # len(context) at the turn that opened the current topic
        self._used_topics = []          # question-bank questions already used to open a topic
        self._invited_questions = False # the candidate has been invited to ask their own questions
        self._minimal_streak = 0        # consecutive one-word answers to open questions
        self._recent_acks = []
        self._directive_memo = None

    _QUESTION_START_RE = re.compile(
        r"^(?:(?:so|well|um|uh|and|okay|ok|yeah|yes|right|but|also|actually)[,\s]+)*"
        r"(?:what|what's|whats|how|how's|hows|who|who's|when|where|why|which|is|are|do|does|did|can|could|would|will|should|"
        r"have|has|may i|tell me)\b", re.IGNORECASE)
    _SHORT_OK = {"yes", "no", "yeah", "yep", "yup", "nope", "sure", "okay", "ok", "thanks", "thank you", "correct", "right",
                 "exactly", "definitely", "absolutely", "maybe", "both", "neither", "nothing", "none", "hello", "hi", "sorry",
                 "i do", "i did", "i don't", "i have", "i haven't", "not really", "of course", "no thanks", "no thank you"}

    @classmethod
    def _is_question(cls, text: str) -> bool:
        """A question to the interviewer: has a question mark, or is a short sentence shaped like a question."""
        text = (text or "").strip()
        if not text:
            return False
        if "?" in text:
            return True
        return len(text.split()) <= 20 and bool(cls._QUESTION_START_RE.match(text))

    @classmethod
    def _is_non_answer(cls, text: str, assistant: List[str]) -> bool:
        """One or two words that are not a plain yes/no/thanks, right after the interviewer asked a question."""
        words = re.findall(r"[A-Za-z']+", text or "")
        if not words or len(words) > 2 or not assistant or not assistant[-1].strip().endswith("?"):
            return False
        return " ".join(w.lower() for w in words) not in cls._SHORT_OK

    def _topic_directive(self, context: List[Dict[str, str]], user_input: str, stage: str = None) -> str:
        """
        Keep the interview moving by enforcing it in code (a 7B model ignores "do not dig into the same story" in the prompt).

        A topic is opened by a question (the greeting, or a question-bank question) and may get MAX_FOLLOWUPS follow-ups; the
        turn after that must open a NEW topic from the job's question bank. A new topic is also forced when the last question
        asked for more detail on the same thing, when the last two questions are near-identical (a re-ask loop), or when the
        candidate asks to move on. Returns text to append to the system prompt ("" when the model may follow up normally).
        """
        from services.llm.scenarios import job_interview

        self.forced_question = None     # the question the code asks this turn (see _compose_forced), if any
        self.forced_fixed_ack = None
        self.reply_prefix = None        # a short human line the code speaks BEFORE the model's sentence (the gentle second try)
        self.fixed_reply = None         # a complete fixed reply (no model call, no new question), e.g. offering to stop
        n = len(context)
        if not hasattr(self, "_topic_anchor") or n == 0 or n < self._topic_anchor:
            self._reset_topics()
        if n == 0:
            return ""
        memo = getattr(self, "_directive_memo", None)
        if memo and memo[0] == (n, user_input):     # a retry of the same turn must give the same answer and not advance the state
            self.forced_question = memo[2]
            self.forced_fixed_ack = memo[3]
            self.fixed_reply = memo[4] if len(memo) > 4 else None
            self.reply_prefix = memo[5] if len(memo) > 5 else None
            return memo[1]

        assistant = [t.get("content", "") for t in context if t.get("role") == "assistant"]
        reason = None
        if (n - self._topic_anchor) // 2 > self.MAX_FOLLOWUPS:
            reason = "follow-up limit"
        elif assistant and self._DIG_RE.search(assistant[-1]):
            reason = "asked for more detail last turn"
        elif len(assistant) >= 2:
            a, b = self._content_words(self._last_question_of(assistant[-1])), self._content_words(self._last_question_of(assistant[-2]))
            if a and b and len(a & b) / len(a | b) >= 0.5:
                reason = "re-ask loop"
        if not reason and self._MOVE_ON_RE.search(user_input or ""):
            reason = "candidate asked to move on"

        directive = ""
        last_q = self._last_question_of(assistant[-1]) if assistant else ""

        if self._is_question(user_input):
            # The candidate asked something. Speech recognition often drops the "?", so the form of the sentence counts too.
            # The interviewer must answer first; the topic switch waits for the next turn.
            self._minimal_streak = 0
            directive = (
                "\n\nTHIS TURN: the candidate asked YOU a question. Answer it directly first, in one or two short sentences, "
                "as a real hiring manager would (modest, plausible details are fine if you do not know them). Do not ignore it, "
                "do not answer with another question, and do not repeat your last question. Then, only if it feels natural, "
                "add one short question of your own.")
            self._directive_memo = ((n, user_input), directive, None, None)
            self.logger.info("Candidate asked a question: the interviewer answers it first")
            return directive

        if self._TONE_RE.search(user_input or ""):
            # dismissive or condescending ("it would be jargon that you wouldn't understand"): react, do not carry on as if nothing happened
            self._minimal_streak = 0
            directive = (
                "\n\nTHIS TURN: the candidate was dismissive or condescending (for example they implied you would not understand, "
                "or showed they do not care). Do not ignore it and do not get angry. In ONE calm, firm sentence, in your own "
                "manner, say you would like them to explain it in plain terms, then ask your last question again in simpler "
                "words. No praise.")
            self._directive_memo = ((n, user_input), directive, None, None)
            self.logger.info("Dismissive remark: the interviewer reacts calmly")
            return directive

        forced, fixed_ack, probing = None, None, False
        resume = bool(assistant) and assistant[-1] in self._OFFER_STOP_REPLIES and bool(
            re.match(r"^\W*(?:no|nope|nah|not really|keep going|carry on|continue|let'?s continue)\b", user_input or "", re.I))
        if resume:
            # they were asked whether to stop and chose to carry on: say so like a person, then a fresh question
            self._minimal_streak = 0
            fixed_ack = "Alright, let's carry on."
            self.logger.info("Candidate chose to continue after the stop offer")
        elif self._is_minimal_answer(user_input) and self._is_open_question(last_q):
            # "Yes." / "Nothing." / "I didn't." / "No." to an open question. A person would not carry on as if a story had been
            # told: first a gentle second try, then (the second time in a row) an honest move-on, and an offer to stop.
            self._minimal_streak += 1
            streak = self._minimal_streak
            if streak == 1:
                # the gentle human line is chosen by the code; the model only has to rephrase the question more simply
                self.reply_prefix = self._rotate(self._GENTLE_LINES)
                directive = (
                    f"\n\nTHIS TURN: the candidate answered your question with just \"{(user_input or '').strip()}\". That is not an "
                    "answer. Write ONLY your previous question again, as ONE sentence, in simpler and different words (shorter, with "
                    "an easier way in). No preface, no praise, no summary, and do not say or imply that they told you anything.")
                reason, probing = None, True        # a gentle second try never forces a topic change in the same turn
                self.logger.info(f"Minimal answer #{streak} {user_input!r}: gentle second try")
            elif streak == 3:
                # three in a row: ask once, as a real question, whether they want to stop (answering "end the interview" ends it)
                self.fixed_reply = self._rotate(self._OFFER_STOP_REPLIES)
                self._directive_memo = ((n, user_input), "", None, None, self.fixed_reply, None)
                self.logger.info(f"Minimal answer #{streak} {user_input!r}: offering to stop")
                return ""
            else:
                fixed_ack = self._rotate(self._MOVE_ON_ACKS)
                self.logger.info(f"Minimal answer #{streak} {user_input!r}: moving on")
        else:
            self._minimal_streak = 0
            if self._is_non_answer(user_input, assistant):
                # one or two stray words after a question are most likely a mis-hearing or the candidate talking to themselves
                directive = (
                    "\n\nTHIS TURN: what the candidate said was only a word or two and did not answer your question (it may be a "
                    "speech recognition mistake). Do not move on, do not praise, and do not summarise it. In one short sentence ask "
                    "them to say that again, or to answer your last question.")
                self._directive_memo = ((n, user_input), directive, None, None)
                self.logger.info(f"Non-answer {user_input!r}: asking the candidate to repeat")
                return directive

        if fixed_ack:
            reason = "minimal answers in a row"
        if probing:
            pass
        elif stage == "candidate_questions" and not self._invited_questions and not fixed_ack:
            # a real interview gives the candidate room to ask about the role once, before the end
            self._invited_questions = True
            forced = "Do you have any questions for me about the role, the team, or the company?"
            self.logger.info("Topic switch (invite candidate questions)")
        elif reason:
            bank = [q for q in job_interview.get_job_info(self.persona.get("job_id")).get("questions", [])
                    if not re.search(r"about yourself|tell me about you\b", q, re.I)]
            fresh = [q for q in bank if q not in self._used_topics] or bank
            if fresh:
                forced = random.Random(f"{self.interviewer_name}-{n}-topic").choice(fresh)
                self._used_topics.append(forced)
                self.logger.info(f"Topic switch ({reason}): {forced}")
        if forced:
            # A 7B model keeps digging into the candidate's story when told to change topic, so the code asks the NEW question
            # itself: the model only writes the short acknowledgement and the question is appended word for word.
            self._topic_anchor = n
            self.forced_question = forced
            self.forced_fixed_ack = fixed_ack      # a fixed human line instead of a model-written acknowledgement
            if not fixed_ack:
                starter = self._pick_starter(assistant)
                directive = (
                    "\n\nTHIS TURN: reply with exactly ONE short sentence (at most 14 words) that acknowledges one concrete detail "
                    f"of what the candidate said in their LAST answer only (never an earlier answer), starting with \"{starter}\" "
                    "Do not praise, do not ask a question, do not add anything else: the next question is asked separately."
                    + (" The candidate asked to move on or said you were repeating yourself, so apologise in a few words instead."
                       if reason in ("candidate asked to move on", "re-ask loop") else ""))
        elif stage == "candidate_questions" and self._invited_questions and not directive:
            directive = (
                "\n\nTHIS TURN: you already offered them the chance to ask questions, so do not offer it again. React to what "
                "they said in a few words and ask ONE short question about their motivation or availability.")
        self._directive_memo = ((n, user_input), directive, forced, fixed_ack, None, self.reply_prefix)
        return directive

    _NEUTRAL_ACKS = ("Okay.", "Alright.", "I see.", "Right.", "Understood.", "Mm-hm.", "Thanks.")
    _STARTERS = ("I see,", "Right,", "Alright,", "Understood,", "Fair enough,", "Thanks,", "Okay,", "Mm-hm,")
    _GENTLE_LINES = ("Even a small example works.", "No pressure, anything that comes to mind is fine.", "Take your time, a short example is plenty.")
    _MOVE_ON_ACKS = ("That's okay, let's try a different one.", "Fair enough. Let's try something else.",
                     "No problem, let's move on to something different.")
    _OFFER_STOP_REPLIES = ("It sounds like this might not be the right moment. Would you like to stop here? If so, just say end the interview.",
                           "I get the feeling this is not working for you right now. If you would like to stop, just say end the interview, otherwise tell me and we will carry on.")
    _TONE_RE = re.compile(
        r"you (?:wouldn'?t|won'?t|can'?t|don'?t) understand|waste of (?:my |your )?time|this is (?:stupid|pointless|dumb|ridiculous)|"
        r"\bwhatever\b|i don'?t care|\bboring\b|are you (?:even )?(?:listening|serious)|looking for an expert|"
        r"don'?t have time for this", re.IGNORECASE)
    _MINIMAL_WORDS = {"yes", "no", "yeah", "yep", "yup", "nope", "nah", "nothing", "none", "never", "nobody", "not", "really", "sure",
                      "maybe", "ok", "okay", "i", "didn't", "didnt", "did", "haven't", "havent", "have", "don't", "dont", "do", "know",
                      "idk", "dunno", "can't", "cant", "idea", "either", "one", "whatever", "fine", "good", "great"}
    _YESNO_START_RE = re.compile(r"^(?:do|does|did|are|is|were|was|have|has|had|would|will|should|can|could)\b", re.IGNORECASE)
    _OPEN_REQUEST_RE = re.compile(
        r"^(?:can|could|would|will) you (?:please )?(?:tell|share|describe|walk|give|explain|talk|say|show|elaborate|think of)\b",
        re.IGNORECASE)
    # an acknowledgement that is only filler praise or a generic summary, so it is replaced by a short neutral one
    _STOCK_FIRST_RE = re.compile(
        r"^(?:got it|that'?s (?:a |an |quite |really |very |so )*(?:great|good|noble|wonderful|impressive|interesting|excellent|"
        r"amazing|fantastic|nice|solid|thoughtful|strategic|perfect|awesome|admirable|valuable|insightful|ambitious|lofty|worthy|commendable)|that sounds|it sounds|"
        r"sounds (?:like|great|good)|thank you for sharing|great (?:answer|example|point)|good (?:answer|example|point)|"
        r"wonderful|impressive|excellent|fantastic|amazing|interesting)\b", re.IGNORECASE)

    @classmethod
    def _is_minimal_answer(cls, text: str) -> bool:
        words = [w.lower() for w in re.findall(r"[A-Za-z']+", text or "")]
        return 0 < len(words) <= 4 and all(w in cls._MINIMAL_WORDS for w in words)

    @classmethod
    def _is_open_question(cls, question: str) -> bool:
        """False for a plain yes/no question ("Do you have any questions?"), where "No." is a real answer."""
        q = (question or "").strip()
        return bool(cls._OPEN_REQUEST_RE.match(q)) or not cls._YESNO_START_RE.match(q)

    def _recent_openers(self, assistant: List[str]) -> set:
        return {re.sub(r"[^a-z' -]", "", (a or "").lower().split(" ")[0] if a else "") for a in assistant[-3:]}

    def _pick_starter(self, assistant: List[str]) -> str:
        used = self._recent_openers(assistant)
        options = [s for s in self._STARTERS if s.rstrip(",").lower() not in used] or list(self._STARTERS)
        return random.choice(options)

    def _rotate(self, options):
        """A line from `options` that was not the one used last time."""
        last = getattr(self, "_rotation_last", None)
        if last is None:
            last = self._rotation_last = {}
        fresh = [o for o in options if o != last.get(id(options))] or list(options)
        pick = random.choice(fresh)
        last[id(options)] = pick
        return pick

    def _neutral_ack(self) -> str:
        options = [a for a in self._NEUTRAL_ACKS if a != getattr(self, "_last_neutral_ack", "")]
        self._last_neutral_ack = random.choice(options)
        return self._last_neutral_ack

    def _is_stock_ack(self, sentence: str) -> bool:
        s = (sentence or "").strip()
        return (not s.endswith("?")) and len(s.split()) <= 16 and bool(
            self._STOCK_FIRST_RE.search(s) or re.search(r"impressive|\bquite an?\b|great (skill|approach|answer)", s, re.I))

    def _maybe_replace_first(self, sentence: str) -> str:
        """First sentence of a normal (not forced) reply: filler praise becomes a short neutral acknowledgement."""
        if self._is_stock_ack(sentence):
            self.logger.info(f"Stock acknowledgement replaced: {sentence!r}")
            return self._neutral_ack()
        return sentence

    def _finish_text(self, text: str) -> str:
        """Final text of a non-streamed reply: compose a forced turn, or clean filler praise from the first sentence."""
        if getattr(self, "fixed_reply", None):
            return self.fixed_reply
        if getattr(self, "reply_prefix", None):
            return f"{self.reply_prefix} {(text or '').strip()}"
        if self.forced_question:
            return self._compose_forced(text)
        if getattr(self, "last_stage", None) == "conclusion":
            return text
        sentences = self._split_sentences(text or "")
        if len(sentences) >= 2:
            if not self._judgement:
                sentences[0] = self._maybe_replace_first(sentences[0])
            return " ".join(sentences)
        return text

    def _compose_forced(self, model_text: str) -> str:
        """Acknowledgement (a fixed line, or the model's first sentence) + the question the code chose to ask next."""
        question = self.forced_question
        if getattr(self, "forced_fixed_ack", None):
            return f"{self.forced_fixed_ack} {question}"
        sentences = self._split_sentences(model_text or "")
        ack = sentences[0] if sentences else ""
        recent = getattr(self, "_recent_acks", [])
        stale = any(len(self._content_words(ack) & self._content_words(r)) / max(1, len(self._content_words(ack) | self._content_words(r))) >= 0.6
                    for r in recent) if ack else False
        if not ack or ack.endswith("?") or len(ack) > 140 or self._is_stock_ack(ack) or stale:
            ack = self._neutral_ack()
        self._recent_acks = (recent + [ack])[-4:]
        return f"{ack} {question}"

    def _build_messages(self, user_input: str, context: List[Dict[str, str]], interaction_stage: str = None) -> List[Dict[str, str]]:
        """Build a chat-style message list: system prompt (with the current stage), history, then the new turn."""
        from services.llm.scenarios import job_interview

        self.forced_question = None
        stage = self._resolve_stage(context, interaction_stage, user_input)
        if not self.interviewer_name:
            self.interviewer_name = job_interview.pick_interviewer_name(self.persona["interview_style"])

        if not context:                    # a new interview: pick up config\interviewer_mode.txt (kept for the whole interview)
            self._interview_mode = self._read_interviewer_mode()
            try:        # and the latest prompt text and output guards, so editing them does not need a server restart
                from services.llm import judgement_guard
                importlib.reload(job_interview)
                importlib.reload(judgement_guard)
            except Exception as e:
                self.logger.warning(f"Could not reload the interview prompt: {e}")
        mode = self._interview_mode or self._read_interviewer_mode()
        self._judgement = mode == "judgement" and not self._force_scripted and self._anth.active()
        if self._judgement:
            # a strong hosted model gets the plan and the manner of a good interviewer, and decides each turn itself: no forced
            # topics, fixed lines or filler filters (those stay for the local model)
            self.forced_fixed_ack = self.fixed_reply = self.reply_prefix = None
            turn = sum(1 for t in (context or []) if t.get("role") == "user") + 1
            static, volatile = job_interview.get_judgement_prompt(
                position_type=self.persona["position_type"], interview_style=self.persona["interview_style"],
                experience_level=self.persona["experience_level"], company_type=self.persona["company_type"], turn=turn,
                interviewer_name=self.interviewer_name, job_id=self.persona.get("job_id"),
                question_ideas=job_interview.get_question_ideas(self.persona.get("job_id"), 4, seed=f"{self.interviewer_name}-{turn}"),
                closing=(stage == "conclusion"), candidate_ended=bool(getattr(self, "candidate_ended", False)))
            history = []
            for turn_msg in self._prune_context(context or []):
                content = (turn_msg.get("content") or "").strip()
                if content and turn_msg.get("role") in ("user", "assistant"):
                    history.append({"role": turn_msg["role"], "content": content})
            note = " ".join(volatile.split())
            self.logger.info(f"LLM stage: {stage} (judgement mode, turn {turn}, history messages: {len(history)})")
            return ([{"role": "system", "content": static}] + history +
                    [{"role": "user", "content": f"{user_input}\n\n[Private note to you, the interviewer, for your next reply only; "
                                                 f"the candidate did not say this: {note}]"}])

        static, volatile = job_interview.get_interview_prompt(
            position_type=self.persona["position_type"],
            interview_style=self.persona["interview_style"],
            experience_level=self.persona["experience_level"],
            company_type=self.persona["company_type"],
            stage=stage,
            interviewer_name=self.interviewer_name,
            job_id=self.persona.get("job_id"),
            question_ideas=job_interview.get_question_ideas(
                self.persona.get("job_id"), 4, seed=f"{self.interviewer_name}-{len(context or [])}"),
            split=True,
        )
        if stage == "conclusion":
            if self.candidate_ended:
                volatile += (
                    "\n\nTHIS TURN: the candidate has asked to end the interview. Respect that. Do NOT ask any question and do "
                    "not try to keep them talking. In two or three short sentences thank them, give one brief, honest and kind "
                    "remark based on what they actually said, and say goodbye.")
        else:
            volatile += self._topic_directive(context or [], user_input, stage)

        history = []
        for turn in self._prune_context(context or []):
            role = turn.get("role")
            content = (turn.get("content") or "").strip()
            if content and role in ("user", "assistant"):
                history.append({"role": role, "content": content})
        layout = self.config.get("prompt_layout", "usertail")
        if layout == "usertail":
            # same cached start, but the per-turn note is part of the final user message, which small models obey best
            messages = [{"role": "system", "content": static}] + history
            note = " ".join(volatile.split())
            messages.append({"role": "user", "content": f"{user_input}\n\n[Private note to you, the interviewer, for your next "
                                                        f"reply only; the candidate did not say this: {note}]"})
            self.logger.info(f"LLM stage: {stage} (history messages: {len(history)})")
            return messages
        if layout == "tail":
            # Fixed instructions first, then the history, then the per-turn part (stage, question ideas, topic directive)
            # right before the candidate's words: the model can reuse its cached start of the prompt on every turn, and the
            # per-turn instruction is the freshest thing it reads.
            messages = [{"role": "system", "content": static}] + history
            messages.append({"role": "system", "content": volatile})
        else:
            messages = [{"role": "system", "content": static + "\n\n" + volatile}] + history
        messages.append({"role": "user", "content": user_input})
        self.logger.info(f"LLM stage: {stage} (history messages: {len(history)})")
        return messages

    _REPEAT_RE = re.compile(
        r"\b(say (that|it) again|repeat (that|it|the question|yourself)|can you repeat|could you repeat|"
        r"what was the question|what did you (just )?say|didn'?t (hear|catch)|come again|pardon)\b",
        re.IGNORECASE,
    )

    def _repeat_request(self, prompt: str, context: Optional[List[Dict[str, str]]]) -> Optional[str]:
        """
        If the candidate asks her to repeat herself, restate her last question directly. Left to the model this
        produced replies like "Sure, let's try this again." that never actually repeated anything.
        """
        if not self._REPEAT_RE.search(prompt or ""):
            return None
        last = next((t.get("content", "") for t in reversed(context or [])
                     if t.get("role") == "assistant" and t.get("content")), "")
        if not last:
            return None
        sentences = re.split(r"(?<=[.!?])\s+", last.strip())
        question = next((x for x in reversed(sentences) if x.endswith("?")), None)
        lead = random.choice(["Sure.", "Of course.", "No problem."])
        self.last_stage = self.last_stage or "background_experience"
        return f"{lead} {question or last}"

    _FALLBACK_LINES = [
        "Sorry, I didn't quite catch that. Could you say that again?",
        "Hm, I lost you for a second there. Could you repeat that?",
        "Apologies, could you rephrase that for me?",
    ]

    def _fallback_line(self) -> str:
        line = self._FALLBACK_LINES[self._fallback_index % len(self._FALLBACK_LINES)]
        self._fallback_index += 1
        return line

    _ABBREVIATIONS = ("dr.", "mr.", "ms.", "mrs.", "st.", "vs.", "e.g.", "i.e.")
    STREAM_MAX_SENTENCES = 3

    def _split_sentences(self, text: str) -> List[str]:
        out: List[str] = []
        for part in re.split(r"(?<=[.!?])\s+", text.strip()):
            if out and out[-1].lower().endswith(self._ABBREVIATIONS):
                out[-1] += " " + part
            else:
                out.append(part)
        return [s for s in out if s]

    def stream_response(self, prompt: str, context: Optional[List[Dict[str, str]]] = None, interaction_stage: str = None):
        """
        Generator version of generate_response: yields the reply one cleaned sentence at a time as the model produces it,
        so the voice can start on sentence 1 while the rest is still being written.

        A sentence is only released once the next one has started (or the reply is over), because a later token can
        still change an earlier one (an abbreviation such as "Dr.", a trailing name). The reply stops after the first
        question or after STREAM_MAX_SENTENCES sentences, and the model is told to stop (saves tokens). The closing
        reply, repeat requests and failures use the normal non-streamed path, so the result is the same text.
        """
        context = context or []
        self.last_stats = None
        if not (prompt or "").strip():
            yield "I didn't catch that. Could you please repeat your question?"
            return
        repeated = self._repeat_request(prompt, context)
        if repeated:
            yield repeated
            return

        self._turn_args = (prompt, context, interaction_stage)
        messages = self._build_messages(prompt, context, interaction_stage)
        timeout = self.config.get("timeout", 15)
        retries = self.config.get("max_retries", 2)
        if self.last_stage == "conclusion":
            text = self._make_ollama_request(messages, timeout, retries, None, interaction_stage)
            if self._judgement:
                from services.llm import judgement_guard
                text = judgement_guard.ensure_next_steps(text)       # the close always says what happens next
            yield text
            return

        forced = self.forced_question      # this turn the code chooses the question (see _compose_forced)
        if self.fixed_reply:
            self.logger.info("Stream: fixed reply, no model call")
            yield self.fixed_reply
            return
        if forced and self.forced_fixed_ack:
            # a fixed human line plus the next question: nothing for the model to write, so the reply is instant
            self.logger.info("Stream: fixed acknowledgement, no model call")
            yield self.forced_fixed_ack
            yield forced
            return
        options = self.config.get("options", {})
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "keep_alive": self.config.get("keep_alive", "30m"),
            "options": {
                "temperature": options.get("temperature", 0.8),
                "top_p": options.get("top_p", 0.9),
                "top_k": options.get("top_k", 40),
                "repeat_penalty": options.get("repeat_penalty", 1.1),
                "num_predict": 48 if forced else options.get("num_predict", 160),
                "num_ctx": options.get("num_ctx", self.context_length),
                "stop": ["Candidate:", "User:", "Human:"],
            },
        }
        if options.get("seed") is not None:
            payload["options"]["seed"] = options["seed"]
        if self.config.get("think") is not None:
            payload["think"] = self.config["think"]

        def fallback_text():
            text = self._make_ollama_request(messages, timeout, retries, None, interaction_stage)
            return self._finish_text(text)

        raw, emitted, start = "", 0, time.time()
        self.last_stats = None
        hosted = {"on": False}       # set when this reply is really coming from the hosted model
        clause_sent = ""             # first clause already handed to the voice before its sentence was finished

        def chunks():
            """Ollama-style chunks from the hosted backend when it is switched on (and healthy), else from the local Ollama model."""
            if self._anth.active() and not self._force_scripted:
                got = False
                hosted["on"] = True
                a_msgs = [dict(m) for m in messages]
                if a_msgs and a_msgs[0]["role"] == "system":      # the voice starts on the first sentence, so make it short
                    a_msgs[0]["content"] += "\n\nSpeech timing: keep your first sentence under 15 words."
                limit = self.config.get("anthropic_first_token_timeout_s", 2.0)
                try:
                    for c in self._anth.stream_chunks(a_msgs, payload["options"]["num_predict"], payload["options"]["temperature"],
                                                      payload["options"]["stop"], limit):
                        got = True
                        yield c
                    return
                except Exception as e:
                    if got:
                        raise
                    self.logger.warning(f"FALLBACK to local model ({self.model}) for this reply: Anthropic stream gave no text "
                                        f"({type(e).__name__}: {str(e)[:100]}); fallbacks so far {self._anth.fallbacks}")
                    hosted["on"] = False
                    if self._judgement:      # the local model must not get the hosted-model prompt: redo this turn the scripted way
                        hosted["legacy"] = True
                        return
                    payload["keep_alive"] = "24h"
            with requests.post(f"{self.url}/api/chat", json=payload, stream=True, timeout=(5, 30)) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        yield json.loads(line)

        try:
            if True:
                finished, stop = False, False
                for chunk in chunks():
                    if chunk.get("done"):
                        # Ollama's own numbers for this reply (tokens and nanoseconds); read by tools\model_compare.py
                        self.last_stats = {k: chunk.get(k) for k in (
                            "total_duration", "load_duration", "prompt_eval_count", "prompt_eval_duration", "eval_count", "eval_duration")}
                    if stop:                      # reply already complete; with collect_stats keep reading only to get the numbers
                        if chunk.get("done"):
                            break
                        continue
                    raw += (chunk.get("message") or {}).get("content", "")
                    finished = bool(chunk.get("done"))
                    cleaned = self._clean_response(raw, chunk.get("done_reason") if finished else None)
                    sentences = self._split_sentences(cleaned)
                    if self._judgement:      # never speak narration about "the candidate" or a verdict on their answer
                        from services.llm import judgement_guard
                        sentences = judgement_guard.drop_bad(sentences)
                    # a question ends the turn, so it is complete the moment it is finished; anything else waits for the next sentence
                    ready = sentences if (finished or (sentences and sentences[-1].endswith("?"))) else sentences[:-1]
                    if (hosted["on"] and not clause_sent and emitted == 0 and not forced and not self.reply_prefix and not ready
                            and len(sentences) == 1 and self.config.get("clause_release", True)):
                        # a long opening sentence: hand its first clause to the voice now instead of when the sentence is finished
                        head = self._first_clause(sentences[0])
                        if head:
                            clause_sent = head
                            self.logger.info(f"Stream: first clause released after {time.time() - start:.2f}s ({len(head)} chars)")
                            yield head
                    for sentence in ready[emitted:]:
                        if emitted == 0:
                            self.logger.info(f"Stream: first sentence after {time.time() - start:.2f}s")
                        emitted += 1
                        if forced:
                            # acknowledgement from the model, then the question the code picked (two chunks for the voice)
                            composed = self._compose_forced(sentence)
                            yield composed[: len(composed) - len(forced)].strip()
                            yield forced
                            stop = True
                            break
                        if emitted == 1 and self.reply_prefix:
                            yield self.reply_prefix
                        elif emitted == 1 and clause_sent:
                            # the first clause is already spoken: only the rest of the sentence is left to say
                            rest = sentence[len(clause_sent):].strip() if sentence.startswith(clause_sent) else ""
                            if not rest:
                                if sentence.endswith("?") or emitted >= (5 if self._judgement else self.STREAM_MAX_SENTENCES):
                                    stop = True
                                    break
                                continue
                            sentence_full, sentence = sentence, rest
                        elif emitted == 1 and (len(sentences) > 1 or finished is False) and not self._judgement:
                            sentence = self._maybe_replace_first(sentence)   # filler praise -> short neutral acknowledgement
                        yield sentence
                        if emitted == 1 and clause_sent:
                            sentence = sentence_full         # the end checks below look at the whole sentence
                        if sentence.endswith("?") or emitted >= (5 if self._judgement else self.STREAM_MAX_SENTENCES):
                            stop = True
                            break
                    if finished or (stop and not self.config.get("collect_stats")):
                        break
            self.logger.info(f"Stream: {emitted} sentence(s) in {time.time() - start:.2f}s")
        except GeneratorExit:
            raise
        except Exception as e:
            self.logger.warning(f"Streaming reply failed after {emitted} sentence(s): {e}")
            if emitted == 0:
                yield fallback_text()
            return
        if emitted == 0 and hosted.get("legacy"):
            self.logger.info("Fallback turn: redoing it with the scripted prompt for the local model")
            self._force_scripted = True
            try:
                yield from self.stream_response(prompt, context, interaction_stage)
            finally:
                self._force_scripted = False
            return
        if emitted == 0:
            self.logger.warning(f"Streamed reply was empty (raw: {raw[:80]!r}); using the normal path")
            yield fallback_text()

    _CLAUSE_RE = re.compile(r"[,;:]\s+(?=\S)")

    def _first_clause(self, text: str) -> str:
        """The first clause of a sentence that is still being written ('' when it should wait for the whole sentence): at least
        18 characters and 3 words, ending at a comma/semicolon/colon that is followed by more text, and not an opening that the
        stock-praise filter would replace (that decision needs the whole sentence)."""
        text = (text or "").strip()
        if not text or text.endswith("?") or (not self._judgement and (self._STOCK_FIRST_RE.search(text) or self._is_stock_ack(text))):
            return ""
        if self._judgement:
            from services.llm import judgement_guard
            if judgement_guard.is_meta(text) or judgement_guard.is_verdict(text):
                return ""
        for m in self._CLAUSE_RE.finditer(text):
            head = text[:m.start() + 1].strip()
            if len(head) > 110:
                return ""
            if len(head) >= 18 and len(head.split()) >= 3 and not re.search(r"\d,$", head):
                return head
        return ""

    def finalize_raw(self, raw: str, meta: Dict[str, Any]) -> str:
        """
        Production post-processing for a COMPLETE raw model reply that was produced elsewhere (another model, a hosted API):
        the same cleaning, forced-question composition, gentle-line prefix, filler-praise filter and sentence limits that
        stream_response applies to the live stream. `meta` is the per-turn state exported by tools\\model_compare.py
        (forced_question, forced_fixed_ack, fixed_reply, reply_prefix, last_stage).
        """
        self.forced_question = meta.get("forced_question")
        self.forced_fixed_ack = meta.get("forced_fixed_ack")
        self.fixed_reply = meta.get("fixed_reply")
        self.reply_prefix = meta.get("reply_prefix")
        self.last_stage = meta.get("last_stage")
        if self.fixed_reply:
            return self.fixed_reply
        text = self._clean_response(raw or "", "stop")
        if self.last_stage == "conclusion":
            return text
        if self.forced_question:
            return self._compose_forced(text)
        sentences = self._split_sentences(text)
        out: List[str] = []
        for sentence in sentences:
            if not out:
                if self.reply_prefix:
                    out.append(self.reply_prefix)
                elif len(sentences) > 1:
                    sentence = self._maybe_replace_first(sentence)
            out.append(sentence)
            if sentence.endswith("?") or len(out) - (1 if self.reply_prefix else 0) >= self.STREAM_MAX_SENTENCES:
                break
        return " ".join(out) if out else self._fallback_line()

    def _clean_response(self, text: str, done_reason: Optional[str] = None) -> str:
        """
        Turn raw model output into something that sounds right when read aloud by the TTS voice.

        Removes speaker labels ("Alex Johnson:"), stage directions, markdown and emoji, keeps one paragraph,
        drops a half-finished last sentence when the model hit the token limit, and trims over-long replies while
        keeping the closing question.
        """
        if not text:
            return ""
        t = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
        t = t.replace("\r", "")
        # some models echo the per-turn instruction after their reply: never speak it
        t = re.split(r"\[\s*Private note", t, maxsplit=1, flags=re.IGNORECASE)[0]
        # the model sometimes continues the transcript by writing the candidate's next line
        t = re.split(r"\n\s*(?:Candidate|User|Human)\s*:", t)[0]
        # leading speaker labels such as "Alex Johnson:", "Interviewer:", "**Alex:**"
        for _ in range(2):
            t = re.sub(r"^\s*[*_]*[A-Z][\w.\-']*(?: [A-Z][\w.\-']*){0,2}[*_]*\s*:\s*[*_]*\s*", "", t, count=1)
        # *smiles*-style stage directions, markdown, emoji
        t = re.sub(r"\*[^*\n]{1,60}\*", "", t)
        t = re.sub(r"[*_`#>]+", "", t)
        t = re.sub("[\U0001F300-\U0001FAFF\u2600-\u27BF]", "", t)
        t = re.sub(r"\s*\n+\s*", " ", t)
        t = (t.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
              .replace("\u2013", "-").replace("\u2026", "..."))
        t = re.sub(r"\s*\u2014\s*", ", ", t)
        t = re.sub(r"\s{2,}", " ", t).strip().strip('"').strip()

        # token limit reached mid-sentence: keep only the complete sentences
        if done_reason == "length" and t and not re.search(r"[.!?][\"')]?$", t):
            ends = list(re.finditer(r"[.!?][\"')]?(?=\s|$)", t))
            if ends:
                t = t[:ends[-1].end()].strip()

        # the model sometimes addresses the candidate by the interviewer's own first name ("Thank you for your time, Alex.")
        first = (self.interviewer_name or "").replace(".", ". ").split()
        first = next((w for w in first if w.rstrip(".") not in ("Dr", "Mr", "Ms", "Mrs")), "")
        if first:
            t = re.sub(rf",\s*{re.escape(first)}(?=\s*[.!?])", "", t)
            t = re.sub(rf"^{re.escape(first)},\s*", "", t)
            t = re.sub(rf",\s*{re.escape(first)},", ",", t)
            t = t[:1].upper() + t[1:]

        sentences = re.split(r"(?<=[.!?])\s+", t)

        # a person asks ONE question per turn: stop after the first question if more follow
        question_idx = [i for i, sentence in enumerate(sentences) if sentence.endswith("?")]
        if len(question_idx) > 1:
            sentences = sentences[: question_idx[0] + 1]
            t = " ".join(sentences)

        # the goodbye must not end by asking something new
        if getattr(self, "last_stage", None) == "conclusion" and len(sentences) > 1 and sentences[-1].endswith("?"):
            sentences = sentences[:-1]
            t = " ".join(sentences)

        # a goodbye is short: at most three sentences (keep the opening acknowledgement, one more, and the final goodbye)
        if getattr(self, "last_stage", None) == "conclusion" and len(sentences) > 3:
            sentences = sentences[:2] + sentences[-1:]
            t = " ".join(sentences)

        # the closing reply must actually say goodbye (trimming above can leave only a filler line)
        if getattr(self, "last_stage", None) == "conclusion" and not re.search(
                r"thank|goodbye|take care|be in touch|hear from us|pleasure|great talking", t, re.I):
            t = (t + " " if t else "") + "Thank you for your time today, I really enjoyed our conversation. We'll be in touch soon. Take care!"

        # keep it speakable: trim long replies but keep the final question
        if len(t) > 420 and len(sentences) > 3:
            question = sentences[-1] if sentences[-1].endswith("?") else None
            body = sentences[:-1] if question else sentences
            kept, total = [], 0
            for sentence in body:
                if kept and total + len(sentence) > 300:
                    break
                kept.append(sentence)
                total += len(sentence) + 1
            t = " ".join(kept + ([question] if question else []))
        return t

    def _prune_context(self, context: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Intelligently prune context to preserve meaningful conversation while reducing tokens.
        
        Args:
            context: List of conversation turns
            
        Returns:
            Pruned context list
        """
        # If context is small, no pruning needed
        if len(context) <= 6:
            return context
        
        # Calculate estimated token count (rough approximation)
        total_length = sum(len(turn.get("content", "")) for turn in context)
        avg_tokens_per_char = 0.25  # Rough estimate of tokens per character
        estimated_tokens = total_length * avg_tokens_per_char
        
        # If within safe limit, return complete context
        if estimated_tokens < self.context_length * 0.7:
            return context
        
        # Apply sophisticated pruning strategy
        pruned_context = []
        
        # Always keep first exchange for context
        pruned_context.extend(context[:2] if len(context) >= 2 else context[:1])
        
        # Process middle part if needed
        if len(context) > 8:
            middle_turns = context[2:-4]
            
            # Keep important middle turns
            for turn in middle_turns:
                content = turn.get("content", "").lower()
                
                # Determine importance using heuristics
                is_important = (
                    # Keep questions
                    "?" in content or 
                    # Keep turns containing important keywords
                    any(keyword in content for keyword in [
                        "experience", "project", "skill", "challenge", "example",
                        "background", "accomplishment", "difficulty", "learned",
                        "achievement", "success", "failure", "team", "leadership"
                    ]) or
                    # Keep short responses (they're token-efficient)
                    len(content) < 100
                )
                
                if is_important:
                    pruned_context.append(turn)
        
        # Always keep most recent exchanges for continuity
        pruned_context.extend(context[-4:])
        
        # Ensure no duplicates from overlap
        unique_turns = []
        content_set = set()
        
        for turn in pruned_context:
            content = turn.get("content", "")
            # Use first 50 chars as fingerprint to avoid near-duplicates
            fingerprint = content[:50] if len(content) > 50 else content
            
            if fingerprint not in content_set:
                content_set.add(fingerprint)
                unique_turns.append(turn)
        
        # Log pruning statistics
        self.logger.info(f"Pruned context from {len(context)} to {len(unique_turns)} turns")
        
        return unique_turns
    
    def _create_cache_key(self, prompt: str, context: List[Dict[str, str]] = None, 
                         interaction_stage: str = None) -> str:
        """
        Create a sophisticated cache key based on prompt content and metadata.
        
        Args:
            prompt: The user input
            context: Optional conversation history
            interaction_stage: Optional interaction stage
            
        Returns:
            Cache key string
        """
        if context is None:
            context = []
            
        # Get a hash of the most recent context (last 2-3 exchanges)
        context_fingerprint = ""
        if context and len(context) > 0:
            # Get last few exchanges but limit size
            recent_exchanges = context[-6:] if len(context) > 6 else context
            # Create a fingerprint from their content
            context_items = [ex.get("content", "")[:50] for ex in recent_exchanges]
            context_fingerprint = hashlib.md5(str(context_items).encode()).hexdigest()[:10]
        
        # Create a compound key that includes prompt, context fingerprint and interaction stage
        stage_str = f"_{interaction_stage}" if interaction_stage else ""
        key_components = f"{self.scenario_type}{stage_str}_{context_fingerprint}_{prompt}"
        
        # Use MD5 hash for consistent keys
        return hashlib.md5(key_components.encode()).hexdigest()
    
    def generate_response(
        self, 
        prompt: str,
        context: Optional[List[Dict[str, str]]] = None,
        timeout: int = None,
        max_retries: int = None,
        interaction_stage: str = None
    ) -> str:
        """
        Generate a response using the Ollama API (synchronous version).
        
        Args:
            prompt: The user input to respond to
            context: Optional conversation history
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            interaction_stage: Current stage of the interaction
            
        Returns:
            Generated response text
        """
        if context is None:
            context = []
        
        # Use default values from config if not specified
        if timeout is None:
            timeout = self.config.get("timeout", 15)
        if max_retries is None:
            max_retries = self.config.get("max_retries", 2)
        
        if not prompt.strip():
            self.logger.warning("Empty prompt received")
            return "I didn't catch that. Could you please repeat your question?"
            
        repeated = self._repeat_request(prompt, context)
        if repeated:
            return repeated

        # Check cache first to prevent duplicate responses
        cache_key = self._create_cache_key(prompt, context, interaction_stage)
        
        cached_response = self._check_cache(cache_key)
        if cached_response:
            return cached_response
        
        # Format the prompt with context and stage information
        formatted_prompt = self._build_messages(prompt, context, interaction_stage)
        
        # Use thread pool for potentially blocking request
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                self._make_ollama_request,
                formatted_prompt, 
                timeout, 
                max_retries, 
                cache_key,
                interaction_stage
            )
            
            try:
                # Add dynamic timeout based on prompt length
                dynamic_timeout = min(30, max(timeout, 5 + len(json.dumps(formatted_prompt)) // 200))
                text = future.result(timeout=dynamic_timeout)
                return self._finish_text(text)
            except TimeoutError:
                self.logger.warning(f"LLM request timed out after {dynamic_timeout}s")
                return "I'm thinking about how to respond. Could you give me a moment?"
    
    def _check_cache(self, cache_key: str) -> Optional[str]:
        """
        Check cache with improved logging and metrics.
        
        Args:
            cache_key: The cache key to check
            
        Returns:
            Cached response or None
        """
        if not self.cache_enabled:
            return None
        if cache_key in self.response_cache:
            cache_entry = self.response_cache[cache_key]
            if isinstance(cache_entry, dict):
                cached_response = cache_entry.get("response", "")
                # Update usage statistics
                cache_entry["used_count"] = cache_entry.get("used_count", 0) + 1
                cache_entry["last_used"] = time.time()
            else:
                # Handle old cache format for backward compatibility
                cached_response = cache_entry
                
            self.logger.info(f"Cache hit for prompt")
            self.cache_hits += 1
            
            # Log cache metrics periodically
            if self.cache_hits % 10 == 0:
                hit_rate = self.cache_hits / (self.cache_hits + self.cache_misses) * 100
                self.logger.info(f"Cache performance: {hit_rate:.1f}% hit rate")
            
            return cached_response
            
        # Cache miss
        self.cache_misses += 1
        return None
    
    async def generate_response_async(
        self, 
        prompt: str,
        context: Optional[List[Dict[str, str]]] = None,
        timeout: int = None,
        max_retries: int = None,
        progress_callback: Optional[Callable[[str], None]] = None,
        interaction_stage: str = None
    ) -> str:
        """
        Generate a response using the Ollama API (async version).
        
        Args:
            prompt: The user input to respond to
            context: Optional conversation history
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            progress_callback: Optional callback for progress updates
            interaction_stage: Current stage of the interaction
            
        Returns:
            Generated response text
        """
        if context is None:
            context = []
        
        # Use default values from config if not specified
        if timeout is None:
            timeout = self.config.get("timeout", 15)
        if max_retries is None:
            max_retries = self.config.get("max_retries", 2)
            
        # Format the prompt with context and stage information
        formatted_prompt = self._build_messages(prompt, context, interaction_stage)
        
        repeated = self._repeat_request(prompt, context)
        if repeated:
            return repeated

        # Create a cache key for checking
        cache_key = self._create_cache_key(prompt, context, interaction_stage)
        
        # Check cache first before making network request
        cached_response = self._check_cache(cache_key)
        if cached_response:
            # Send update to callback if provided
            if progress_callback:
                await progress_callback("Using cached response")
                
            return cached_response
        
        # If progress callback provided, send initial update
        if progress_callback:
            await progress_callback("Starting LLM request...")
            
        # Run the actual API request in a thread pool executor to avoid blocking
        try:
            response_text = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                lambda: self._make_ollama_request(
                    formatted_prompt, timeout, max_retries, cache_key, interaction_stage
                )
            )
            
            # Send final progress update
            if progress_callback:
                await progress_callback("LLM response complete")
                
            return self._finish_text(response_text)
            
        except Exception as e:
            self.logger.error(f"Async LLM error: {e}")
            return "I'm sorry, I encountered a problem with my thinking process. Let's try a different question."
    
    def _make_ollama_request(
        self, 
        formatted_prompt: str, 
        timeout: int, 
        max_retries: int,
        cache_key: str = None,
        interaction_stage: str = None
    ) -> str:
        """
        Make the actual HTTP request to Ollama API with optimized settings.
        
        Args:
            formatted_prompt: The complete formatted prompt
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            cache_key: Cache key for storing response
            interaction_stage: Current interaction stage
            
        Returns:
            Generated text response
        """
        # Use provided cache key or create one if not provided
        if cache_key is None:
            cache_key = hashlib.md5(json.dumps(formatted_prompt).encode()).hexdigest()
            
        api_url = f"{self.url}/api/chat"

        # Get options from config or use defaults
        options = self.config.get("options", {})

        # Only stop if the model starts writing the candidate's side. (The old "\n\n" stop turned any reply that began
        # with a blank line into an empty one.)
        stop_sequences = ["Candidate:", "User:", "Human:"]
        if self.scenario_type == "conflict_resolution":
            stop_sequences.append("Colleague:")

        payload_options = {
            "temperature": options.get("temperature", 0.8),
            "top_p": options.get("top_p", 0.9),
            "top_k": options.get("top_k", 40),
            "repeat_penalty": options.get("repeat_penalty", 1.1),
            "num_predict": options.get("num_predict", 160),
            # must be large enough for the whole prompt, or Ollama drops the START of it (the system prompt)
            "num_ctx": options.get("num_ctx", self.context_length),
            "stop": stop_sequences,
        }
        if options.get("seed") is not None:
            payload_options["seed"] = options["seed"]

        messages = formatted_prompt if isinstance(formatted_prompt, list) else [{"role": "user", "content": formatted_prompt}]
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "keep_alive": self.config.get("keep_alive", "30m"),
            "options": payload_options,
        }
        if self.config.get("think") is not None:
            payload["think"] = self.config["think"]

        if self._anth.active() and not self._force_scripted:
            try:
                raw_text = self._anth.complete(messages, payload_options["num_predict"], payload_options["temperature"], stop_sequences)
                text = self._clean_response(raw_text, "stop")
                if text:
                    return text
                self.logger.warning("Anthropic reply was empty after cleaning; using the local model")
            except Exception as e:
                self.logger.warning(f"Anthropic call failed ({str(e)[:120]}); using the local model")
            if self._judgement and getattr(self, "_turn_args", None):
                # the local model gets the scripted prompt, not the one written for the hosted model
                self._force_scripted = True
                try:
                    messages = self._build_messages(*self._turn_args)
                finally:
                    self._force_scripted = False
                payload["messages"] = messages

        self.logger.debug(f"Sending request to Ollama: {api_url}")
        start_time = time.time()
        
        # Retry loop with exponential backoff
        for attempt in range(max_retries + 1):
            try:
                # Adjust timeout for retry attempts
                current_timeout = timeout * (1 + attempt * 0.5)
                
                # Send the request to Ollama
                response = requests.post(api_url, json=payload, timeout=current_timeout)
                response.raise_for_status()
                
                # Parse the response (chat API: message.content; legacy generate API: response)
                result = response.json()
                if isinstance(result.get("message"), dict):
                    raw_text = result["message"].get("content", "")
                else:
                    raw_text = result.get("response", "")
                generated_text = self._clean_response(raw_text, result.get("done_reason"))

                # Nothing usable came back: retry a bit warmer, then fall back to asking them to repeat
                if not generated_text:
                    self.logger.warning(f"Empty or unusable reply from Ollama (raw: {raw_text[:80]!r})")
                    if attempt < max_retries:
                        payload["options"]["temperature"] = min(1.0, payload["options"].get("temperature", 0.8) + 0.15)
                        continue
                    return self._fallback_line()

                # Record timing for monitoring
                elapsed = time.time() - start_time
                self.logger.info(f"Response generated in {elapsed:.2f}s after {attempt + 1} attempts")
                
                # Cache the response with metadata for future use and analysis
                if self.cache_enabled and cache_key not in self.response_cache:
                    # Store response with metadata for cache management
                    self.response_cache[cache_key] = {
                        "response": generated_text,
                        "created_at": time.time(),
                        "used_count": 1,
                        "last_used": time.time(),
                        "generation_time": elapsed,
                        "prompt_length": len(formatted_prompt),
                        "response_length": len(generated_text),
                        "scenario_type": self.scenario_type,
                        "interaction_stage": interaction_stage
                    }
                    
                    # Limit cache size using intelligent pruning
                    if len(self.response_cache) > self.max_cache_size:
                        self._prune_cache()
                    
                    # Periodically save cache to disk
                    if len(self.response_cache) % 10 == 0:
                        self._save_cache_to_disk()
                
                return generated_text
                
            except requests.exceptions.Timeout:
                if attempt < max_retries:
                    self.logger.warning(f"Ollama API timeout. Retrying ({attempt + 1}/{max_retries})")
                    # Exponential backoff
                    time.sleep(2 ** attempt)
                else:
                    self.logger.error("Ollama API timeout after max retries")
                    return "I apologize for the delay. Let's try a different question."
                    
            except requests.exceptions.ConnectionError:
                if attempt < max_retries:
                    self.logger.warning(f"Ollama API connection error. Retrying ({attempt + 1}/{max_retries})")
                    time.sleep(2 ** attempt)
                else:
                    self.logger.error("Ollama API connection error after max retries")
                    return "I'm having trouble connecting to our thinking engine. Let's pause for a moment."
                    
            except Exception as e:
                if attempt < max_retries:
                    self.logger.warning(f"Ollama API error: {e}. Retrying ({attempt + 1}/{max_retries})")
                    time.sleep(2 ** attempt)
                else:
                    self.logger.error(f"Ollama API error after max retries: {e}")
                    return "I encountered an unexpected issue. Let's move on to another question."
    
    def _prune_cache(self) -> None:
        """
        Intelligently prune cache entries based on usage patterns.
        
        Uses a weighted algorithm that considers:
        1. Last used time
        2. Usage count
        3. Creation time
        """
        entries_to_score = []
        
        # Calculate score for each entry (higher score = more likely to keep)
        current_time = time.time()
        for key, value in self.response_cache.items():
            if isinstance(value, dict):
                # Calculate recency factor (0-1, higher = more recent)
                last_used = value.get("last_used", 0)
                recency = max(0, min(1, 1 - (current_time - last_used) / (86400 * 7)))  # 7 day window
                
                # Calculate usage factor (0-1, higher = more used)
                used_count = value.get("used_count", 0)
                usage = min(1, used_count / 10)  # Cap at 10 uses
                
                # Calculate age factor (0-1, higher = newer)
                created_at = value.get("created_at", 0)
                age = max(0, min(1, 1 - (current_time - created_at) / (86400 * 30)))  # 30 day window
                
                # Weighted score (recency most important, then usage, then age)
                score = (recency * 0.6) + (usage * 0.3) + (age * 0.1)
                
                entries_to_score.append((key, score))
            else:
                # Old format entries get a low score
                entries_to_score.append((key, 0.1))
        
        # Sort by score (lowest first)
        entries_to_score.sort(key=lambda x: x[1])
        
        # Remove lowest 10% of entries
        entries_to_remove = entries_to_score[:max(1, int(len(entries_to_score) * 0.1))]
        for key, _ in entries_to_remove:
            self.logger.debug(f"Pruning cache entry: {key[:8]}...")
            self.response_cache.pop(key, None)
        
        self.logger.info(f"Pruned {len(entries_to_remove)} cache entries")
    
    def _save_cache_to_disk(self) -> None:
        """Save response cache to disk with improved error handling and compression."""
        try:
            cache_file = f"{self.cache_dir}/llm_response_cache.json"
            
            # Convert cache to serializable format
            serializable_cache = {}
            for key, value in self.response_cache.items():
                # Ensure we only save essential data to reduce file size
                if isinstance(value, dict):
                    # Keep only essential fields for disk storage
                    disk_entry = {
                        "response": value.get("response", ""),
                        "created_at": value.get("created_at", time.time()),
                        "used_count": value.get("used_count", 1),
                        "last_used": value.get("last_used", time.time()),
                        "scenario_type": value.get("scenario_type", self.scenario_type),
                        "interaction_stage": value.get("interaction_stage", None)
                    }
                    serializable_cache[str(key)] = disk_entry
                else:
                    # Legacy format - just store the string response
                    serializable_cache[str(key)] = value
                    
            # Use atomic write pattern for reliability
            temp_file = f"{cache_file}.temp"
            with open(temp_file, 'w') as f:
                json.dump(serializable_cache, f)
                
            # Rename temp file to final file (atomic operation on most file systems)
            os.replace(temp_file, cache_file)
                
            self.logger.info(f"Saved {len(serializable_cache)} cache entries to disk")
        except Exception as e:
            self.logger.error(f"Error saving cache to disk: {e}")
    
    def _load_cache_from_disk(self) -> None:
        """Load response cache from disk with improved error handling."""
        try:
            cache_file = f"{self.cache_dir}/llm_response_cache.json"
            if os.path.exists(cache_file):
                with open(cache_file, 'r') as f:
                    serialized_cache = json.load(f)
                    
                # Track stats for logging
                loaded_count = 0
                skipped_count = 0
                
                # Load entries with graceful error handling for each entry
                for key, value in serialized_cache.items():
                    try:
                        # Handle both new (dict) and old (string) format
                        if isinstance(value, dict):
                            # Convert to proper cache entry format
                            if "response" in value:
                                self.response_cache[key] = value
                                loaded_count += 1
                            else:
                                # Skip invalid entries
                                skipped_count += 1
                                continue
                        else:
                            # Legacy string format - keep as is
                            self.response_cache[key] = value
                            loaded_count += 1
                    except Exception as item_error:
                        # Skip problematic entries rather than failing entirely
                        self.logger.warning(f"Skipped cache entry {key}: {item_error}")
                        skipped_count += 1
                    
                self.logger.info(f"Loaded {loaded_count} cache entries from disk (skipped {skipped_count})")
        except Exception as e:
            self.logger.error(f"Error loading cache from disk: {e}")
            # Create fresh cache file on next save
            self.response_cache = {}
    
    def cleanup(self) -> None:
        """Clean up resources when shutting down."""
        # Save cache to disk before shutting down
        self._save_cache_to_disk()
        
        # Shutdown executor
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=True)
            
        # Shutdown precompute thread if active
        if hasattr(self, 'precompute_thread'):
            self.precompute_thread.shutdown(wait=False)
            
        self.logger.info("Ollama client resources cleaned up")
