"""
Enhanced Ollama client with fixed AI personality and improved prompt management.
This version fixes the AI role confusion by providing better system prompts and context management.
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


class OllamaClient:
    """
    Enhanced Ollama client with fixed AI personality management.
    
    Key fixes:
    - Proper role reinforcement in system prompts
    - Dynamic context management for better conversation flow
    - Stronger personality anchoring to prevent role confusion
    """
    
    def __init__(self, url: str, model: str, context_length: int = 8192, config=None):
        self.url = url.rstrip('/')
        self.model = model
        self.context_length = context_length
        self.logger = logging.getLogger("ollama")
        
        # Default configuration
        self.default_config = {
            "timeout": 15,
            "max_retries": 2,
            "use_streaming": False,
            "max_cache_entries": 500,
            "scenario_type": "interview",
            "precompute_enabled": True,
            "options": {
                "temperature": 0.7,
                "top_p": 0.85,
                "top_k": 30,
                "repeat_penalty": 1.2,
                "num_predict": 120,
                "seed": 42
            }
        }
        
        # Merge with provided config
        self.config = self.default_config.copy()
        if config:
            self._merge_config(self.config, config)
        
        # Store additional metadata
        self.scenario_type = self.config.get("scenario_type", "interview")
        
        # Enhanced conversation state tracking
        self.conversation_turn = 0
        self.interviewer_name = None
        self.company_name = None
        self.position_title = None
        
        # Load system prompt based on scenario type with proper context
        self.base_system_prompt = self._load_system_prompt()
        
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
        
        # Load cache from disk if available
        self._load_cache_from_disk()
        
        # Initialize precomputation queue and process
        self.precompute_queue = []
        if self.config.get("precompute_enabled", True):
            self._initialize_precomputation()
        
        self.logger.info(f"Initialized Enhanced Ollama client for model: {model}")
        self.logger.info(f"Response caching enabled with max size: {self.max_cache_size} entries")
        
        # Log active configuration
        options_str = json.dumps(self.config.get("options", {}), indent=2)
        self.logger.info(f"Using Ollama parameters: {options_str}")
    
    def _merge_config(self, base_config: Dict, new_config: Dict) -> None:
        """Recursively merge configuration dictionaries."""
        for key, value in new_config.items():
            if key in base_config and isinstance(base_config[key], dict) and isinstance(value, dict):
                self._merge_config(base_config[key], value)
            else:
                base_config[key] = value
    
    def _load_system_prompt(self) -> str:
        """Load the system prompt with enhanced role definition and context."""
        try:
            from services.llm.scenarios import job_interview
            
            if self.scenario_type == "interview":
                # Get a proper interview prompt with better parameters
                initial_prompt = job_interview.get_interview_prompt(
                    position_type="software_engineer",
                    interview_style="neutral",
                    experience_level="mid_level",
                    company_type="tech_startup",
                    stage="introduction",
                    context_memory="You are beginning a professional job interview. Stay in character as the interviewer."
                )
                
                # Extract key details for later use
                import random
                interviewer_names = job_interview.JOB_INTERVIEW_SCENARIO["interviewer_names"]["neutral"]
                self.interviewer_name = random.choice(interviewer_names)
                self.company_name = "TechStart Innovations"
                self.position_title = "Software Engineer"
                
                # Enhanced system prompt with stronger role reinforcement
                enhanced_prompt = f"""You are {self.interviewer_name}, a professional interviewer and hiring manager at {self.company_name}. You are conducting a job interview for a {self.position_title} position.

CRITICAL ROLE DEFINITION:
- YOU ARE THE INTERVIEWER - You ask questions and evaluate the candidate
- THE OTHER PERSON IS THE CANDIDATE - They answer your questions and try to get the job
- NEVER INTRODUCE YOURSELF AS THE CANDIDATE
- NEVER SAY "I'm [candidate name]" or claim to be applying for the job
- ALWAYS maintain your identity as {self.interviewer_name}, the interviewer

YOUR RESPONSIBILITIES AS INTERVIEWER:
- Ask thoughtful questions about the candidate's experience and skills
- Listen to their answers and ask follow-up questions
- Evaluate their fit for the {self.position_title} role
- Maintain a professional, friendly demeanor
- Guide the conversation through different interview stages

CONVERSATION STYLE:
- Be natural and conversational, not robotic
- Keep responses brief (1-2 sentences typically)
- Show genuine interest in the candidate's responses
- Ask one question at a time
- Use natural speech patterns

REMEMBER: You are {self.interviewer_name}, the person conducting the interview. The candidate is trying to impress YOU to get the job."""
                
                return enhanced_prompt
            
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
            while self.precompute_queue:
                time.sleep(2.0)
                
                prompt = self.precompute_queue.pop(0)
                cache_key = self._create_cache_key(prompt, [], "background_experience")
                if cache_key in self.response_cache:
                    continue
                
                try:
                    self.logger.info(f"Precomputing response for: {prompt}")
                    self.generate_response(
                        prompt, 
                        [], 
                        self.config.get("timeout", 20) * 2,
                        interaction_stage="background_experience"
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to precompute response: {e}")
        
        except Exception as e:
            self.logger.error(f"Precomputation thread error: {e}")
    
    def _format_prompt(self, user_input: str, context: List[Dict[str, str]], interaction_stage: str = None) -> str:
        """
        Format the prompt with enhanced role reinforcement and conversation context.
        
        Args:
            user_input: The latest user input
            context: List of previous conversation turns
            interaction_stage: Current interaction stage
            
        Returns:
            Formatted prompt for LLM with strong role anchoring
        """
        # Increment conversation turn counter
        self.conversation_turn += 1
        
        # Start with enhanced system prompt
        formatted_prompt = self.base_system_prompt + "\n\n"
        
        # Add role reinforcement based on conversation turn
        if self.conversation_turn <= 3:
            # Strong reinforcement for early turns when confusion is most likely
            formatted_prompt += f"REMINDER: You are {self.interviewer_name or 'the interviewer'}, NOT the candidate. " \
                               f"Ask the candidate questions about their background and experience.\n\n"
        
        # Add brevity instruction
        formatted_prompt += "RESPONSE GUIDELINES: Keep responses brief (1-2 sentences). " \
                           "Ask one clear question at a time.\n\n"
        
        # Add stage-specific guidance
        if interaction_stage:
            if interaction_stage == "introduction":
                formatted_prompt += "STAGE: Introduction - Welcome the candidate and ask them to introduce themselves.\n\n"
            elif interaction_stage == "technical_assessment":
                formatted_prompt += "STAGE: Technical Assessment - Ask relevant technical questions for the software engineer role.\n\n"
            elif interaction_stage == "behavioral_assessment":
                formatted_prompt += "STAGE: Behavioral - Ask about soft skills, teamwork, and problem-solving approaches.\n\n"
            elif interaction_stage == "conclusion":
                formatted_prompt += "STAGE: Conclusion - Wrap up the interview and explain next steps.\n\n"
        
        # Add conversation history with enhanced role clarity
        if context:
            pruned_context = self._prune_context(context)
            
            formatted_prompt += "CONVERSATION HISTORY:\n"
            for turn in pruned_context:
                role = turn["role"]
                content = turn["content"]
                if role == "user":
                    formatted_prompt += f"CANDIDATE SAID: {content}\n"
                elif role == "assistant":
                    formatted_prompt += f"YOU (INTERVIEWER) SAID: {content}\n"
            formatted_prompt += "\n"
        
        # Add current user input with clear role labeling
        formatted_prompt += f"CANDIDATE JUST SAID: {user_input}\n\n"
        formatted_prompt += f"YOUR RESPONSE AS {self.interviewer_name or 'THE INTERVIEWER'}:"
        
        return formatted_prompt
    
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
        avg_tokens_per_char = 0.25
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
                    "?" in content or 
                    any(keyword in content for keyword in [
                        "experience", "project", "skill", "challenge", "example",
                        "background", "accomplishment", "difficulty", "learned",
                        "achievement", "success", "failure", "team", "leadership"
                    ]) or
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
            fingerprint = content[:50] if len(content) > 50 else content
            
            if fingerprint not in content_set:
                content_set.add(fingerprint)
                unique_turns.append(turn)
        
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
            recent_exchanges = context[-6:] if len(context) > 6 else context
            context_items = [ex.get("content", "")[:50] for ex in recent_exchanges]
            context_fingerprint = hashlib.md5(str(context_items).encode()).hexdigest()[:10]
        
        # Create a compound key
        stage_str = f"_{interaction_stage}" if interaction_stage else ""
        key_components = f"{self.scenario_type}{stage_str}_{context_fingerprint}_{prompt}"
        
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
            
        # Check cache first to prevent duplicate responses
        cache_key = self._create_cache_key(prompt, context, interaction_stage)
        
        cached_response = self._check_cache(cache_key)
        if cached_response:
            return cached_response
        
        # Format the prompt with enhanced role reinforcement
        formatted_prompt = self._format_prompt(prompt, context, interaction_stage)
        
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
                dynamic_timeout = min(30, max(timeout, 5 + len(formatted_prompt) // 200))
                return future.result(timeout=dynamic_timeout)
            except TimeoutError:
                self.logger.warning(f"LLM request timed out after {dynamic_timeout}s")
                return "I'm thinking about how to respond. Could you give me a moment?"
    
    def _check_cache(self, cache_key: str) -> Optional[str]:
        """Check cache with improved logging and metrics."""
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
        """Generate a response using the Ollama API (async version)."""
        if context is None:
            context = []
        
        # Use default values from config if not specified
        if timeout is None:
            timeout = self.config.get("timeout", 15)
        if max_retries is None:
            max_retries = self.config.get("max_retries", 2)
            
        # Format the prompt with enhanced role reinforcement
        formatted_prompt = self._format_prompt(prompt, context, interaction_stage)
        
        # Create a cache key for checking
        cache_key = self._create_cache_key(prompt, context, interaction_stage)
        
        # Check cache first before making network request
        cached_response = self._check_cache(cache_key)
        if cached_response:
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
                
            return response_text
            
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
        """Make the actual HTTP request to Ollama API with optimized settings."""
        # Use provided cache key or create one if not provided
        if cache_key is None:
            cache_key = hashlib.md5(formatted_prompt.encode()).hexdigest()
            
        api_url = f"{self.url}/api/generate"
        
        # Get options from config or use defaults
        options = self.config.get("options", {})
        
        # Define stop sequences to prevent role confusion
        stop_sequences = [
            "\n\n", 
            "CANDIDATE SAID:", 
            "CANDIDATE JUST SAID:",
            "YOU (INTERVIEWER) SAID:",
            "CONVERSATION HISTORY:",
            f"I'm {self.interviewer_name or 'the interviewer'}",  # Prevent self-introduction confusion
            "I am applying",  # Prevent candidate role confusion
            "I'm applying"
        ]
        
        # Build the payload with optimized config values
        payload = {
            "model": self.model,
            "prompt": formatted_prompt,
            "stream": False,
            "context": [],
            "options": {
                "temperature": options.get("temperature", 0.7),
                "top_p": options.get("top_p", 0.85),
                "top_k": options.get("top_k", 30),
                "repeat_penalty": options.get("repeat_penalty", 1.2),
                "num_predict": options.get("num_predict", 120),
                "stop": stop_sequences,
                "seed": options.get("seed", 42)
            }
        }
        
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
                
                # Parse the response
                result = response.json()
                generated_text = result.get("response", "")
                
                # Handle empty responses
                if not generated_text.strip():
                    self.logger.warning("Received empty response from Ollama")
                    return "Could you tell me about your technical background and experience?"
                
                # Post-process response to prevent role confusion
                generated_text = self._post_process_response(generated_text)
                
                # Truncate overly long responses for consistent timing
                if len(generated_text) > 250:
                    self.logger.info(f"Truncating long response (from {len(generated_text)} chars)")
                    
                    # Try to find a sentence break for clean truncation
                    sentences = re.split(r'(?<=[.!?])\s+', generated_text)
                    if len(sentences) > 2:
                        # Keep first two sentences
                        truncated = " ".join(sentences[:2])
                        if not truncated.endswith((".", "!", "?")):
                            truncated += "."
                    else:
                        # Just take the first 250 characters if we can't find sentence breaks
                        truncated = generated_text[:250].rstrip() + "..."
                        
                    generated_text = truncated
                
                # Record timing for monitoring
                elapsed = time.time() - start_time
                self.logger.info(f"Response generated in {elapsed:.2f}s after {attempt + 1} attempts")
                
                # Cache the response with metadata
                if cache_key not in self.response_cache:
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
                    time.sleep(2 ** attempt)
                else:
                    self.logger.error("Ollama API timeout after max retries")
                    return "Let me ask you about your experience with software development projects."
                    
            except requests.exceptions.ConnectionError:
                if attempt < max_retries:
                    self.logger.warning(f"Ollama API connection error. Retrying ({attempt + 1}/{max_retries})")
                    time.sleep(2 ** attempt)
                else:
                    self.logger.error("Ollama API connection error after max retries")
                    return "Tell me about your background in software engineering."
                    
            except Exception as e:
                if attempt < max_retries:
                    self.logger.warning(f"Ollama API error: {e}. Retrying ({attempt + 1}/{max_retries})")
                    time.sleep(2 ** attempt)
                else:
                    self.logger.error(f"Ollama API error after max retries: {e}")
                    return "What experience do you have with the technologies we use here?"
    
    def _post_process_response(self, response: str) -> str:
        """
        Post-process the LLM response to catch and fix any role confusion.
        
        Args:
            response: Raw response from LLM
            
        Returns:
            Cleaned response with role confusion fixed
        """
        # Check for common signs of role confusion
        confusion_patterns = [
            r"I'm\s+[\w\s]+(?:applying|candidate|interviewing)",
            r"I am\s+[\w\s]+(?:applying|candidate|interviewing)",
            r"My name is\s+[\w\s]+(?:and I|,)",
            r"I've been working at",
            r"In my role as\s+(?!interviewer|hiring)",
            r"I have\s+\d+\s+years?\s+of\s+experience"
        ]
        
        # Check if response shows role confusion
        for pattern in confusion_patterns:
            if re.search(pattern, response, re.IGNORECASE):
                self.logger.warning(f"Detected role confusion in response: {response[:50]}...")
                
                # Generate a corrective interviewer response
                fallback_responses = [
                    "Tell me about your background and experience.",
                    "What interests you about this software engineering position?",
                    "Could you walk me through your technical experience?",
                    "What programming languages are you most comfortable with?",
                    "Describe a challenging project you've worked on recently."
                ]
                
                import random
                return random.choice(fallback_responses)
        
        # Response looks good, return as-is
        return response
    
    def _prune_cache(self) -> None:
        """Intelligently prune cache entries based on usage patterns."""
        entries_to_score = []
        
        # Calculate score for each entry
        current_time = time.time()
        for key, value in self.response_cache.items():
            if isinstance(value, dict):
                # Calculate recency factor (0-1, higher = more recent)
                last_used = value.get("last_used", 0)
                recency = max(0, min(1, 1 - (current_time - last_used) / (86400 * 7)))
                
                # Calculate usage factor (0-1, higher = more used)
                used_count = value.get("used_count", 0)
                usage = min(1, used_count / 10)
                
                # Calculate age factor (0-1, higher = newer)
                created_at = value.get("created_at", 0)
                age = max(0, min(1, 1 - (current_time - created_at) / (86400 * 30)))
                
                # Weighted score
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
        """Save response cache to disk with improved error handling."""
        try:
            cache_file = f"{self.cache_dir}/llm_response_cache.json"
            
            # Convert cache to serializable format
            serializable_cache = {}
            for key, value in self.response_cache.items():
                if isinstance(value, dict):
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
                    serializable_cache[str(key)] = value
                    
            # Use atomic write pattern for reliability
            temp_file = f"{cache_file}.temp"
            with open(temp_file, 'w') as f:
                json.dump(serializable_cache, f)
                
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
                
                # Load entries with graceful error handling
                for key, value in serialized_cache.items():
                    try:
                        if isinstance(value, dict):
                            if "response" in value:
                                self.response_cache[key] = value
                                loaded_count += 1
                            else:
                                skipped_count += 1
                                continue
                        else:
                            self.response_cache[key] = value
                            loaded_count += 1
                    except Exception as item_error:
                        self.logger.warning(f"Skipped cache entry {key}: {item_error}")
                        skipped_count += 1
                    
                self.logger.info(f"Loaded {loaded_count} cache entries from disk (skipped {skipped_count})")
        except Exception as e:
            self.logger.error(f"Error loading cache from disk: {e}")
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
            
        self.logger.info("Enhanced Ollama client resources cleaned up")
