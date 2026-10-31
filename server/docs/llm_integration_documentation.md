# VR Interview System: LLM Integration Documentation

## Title and Overview

The LLM Integration component provides the intelligent response generation capabilities of the VR Interview System. It connects with Ollama, a local large language model server, to generate contextually relevant responses for the interview simulation. This component handles prompt engineering, conversation context management, request optimization, response caching, and error handling to ensure reliable and performant LLM interactions.

## Architecture

The LLM Integration component is built around the `OllamaClient` class (located in `services.llm.Ollama_client`), which handles communication with the Ollama API. The system implements several optimizations:

1. **Advanced Caching System**: Stores and reuses responses with sophisticated prioritization
2. **Intelligent Context Management**: Preserves relevant conversation history with heuristic pruning
3. **Prompt Engineering**: Formats prompts optimally with stage-specific guidance
4. **Background Precomputation**: Proactively generates responses for common questions
5. **Comprehensive Error Handling**: Manages timeouts, retries with exponential backoff, and fallbacks
6. **Response Processing**: Formats, truncates, and validates LLM outputs
7. **Asynchronous Processing**: Non-blocking API interaction with progress updates

### Component Diagram
```
┌──────────────────────────────────────────────────────┐
│                LLM Integration System                 │
└───────────────────────┬──────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────┐
│               EnhancedOllamaClient                    │
│                                                       │
│  ┌─────────────────┐       ┌─────────────────────┐   │
│  │  Context Mgmt   │◄─────►│  Advanced Caching   │   │
│  │ (Pruning Logic) │       │  (Weighted Priority)│   │
│  └─────────────────┘       └─────────────────────┘   │
│                                                       │
│  ┌─────────────────┐       ┌─────────────────────┐   │
│  │ Prompt Engineer │─────► │  Response Generator │   │
│  │ (Stage-specific)│       │  (Smart Truncation) │   │
│  └─────────────────┘       └─────────────────────┘   │
│                                                       │
│  ┌─────────────────┐       ┌─────────────────────┐   │
│  │ Precomputation  │◄─────►│   Error Handling    │   │
│  │ (Background)    │       │ (Exponential Backoff)│   │
│  └─────────────────┘       └─────────────────────┘   │
└───────────────────────┬──────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────┐
│                     Ollama API                        │
│             (Local LLM Server - mistral)              │
└──────────────────────────────────────────────────────┘
```

## Key Classes/Functions

### OllamaClient

```python
class OllamaClient:
    """
    Enhanced client for interacting with the Ollama API.
    
    Features:
    - Optimized parameter settings for faster responses
    - Advanced context management with intelligent pruning
    - Sophisticated caching with priority-based invalidation
    - Background precomputation of responses
    - Improved error handling and recovery
    """
```

#### Core Methods

- **`__init__(url, model, context_length, config)`**: Initializes the client with configuration
- **`_load_system_prompt()`**: Loads the system prompt based on the scenario type
- **`_initialize_precomputation()`**: Sets up background processing for common questions
- **`_precompute_responses()`**: Processes a queue of common questions in the background
- **`_format_prompt(user_input, context, interaction_stage)`**: Formats prompt with context and stage guidance
- **`_prune_context(context)`**: Intelligently reduces context size while preserving important information
- **`_create_cache_key(prompt, context, interaction_stage)`**: Creates a sophisticated hash for response caching
- **`_check_cache(cache_key)`**: Checks cache with improved logging and metrics
- **`generate_response(prompt, context, timeout, max_retries, interaction_stage)`**: Generates a response synchronously
- **`generate_response_async(prompt, context, timeout, max_retries, progress_callback, interaction_stage)`**: Generates a response asynchronously
- **`_make_ollama_request(formatted_prompt, timeout, max_retries, cache_key, interaction_stage)`**: Makes HTTP request with retry logic
- **`_prune_cache()`**: Intelligently prunes cache based on a weighted algorithm
- **`_save_cache_to_disk()`**: Persists cache to disk with atomic write pattern
- **`_load_cache_from_disk()`**: Loads cache from disk with enhanced error handling
- **`cleanup()`**: Properly cleans up resources when shutting down

## Scenario Management

The LLM Integration includes a comprehensive framework for interview scenarios:

### Job Interview Scenario

```python
JOB_INTERVIEW_SCENARIO = {
    "system_prompt": "...",
    "stages": {
        "introduction": { ... },
        "background_experience": { ... },
        "technical_assessment": { ... },
        "behavioral_assessment": { ... },
        "candidate_questions": { ... },
        "conclusion": { ... }
    },
    "interviewer_styles": {
        "supportive": { ... },
        "neutral": { ... },
        "challenging": { ... },
        "technical": { ... }
    },
    "position_types": {
        "software_engineer": { ... },
        "product_manager": { ... },
        "marketing_specialist": { ... },
        "customer_service": { ... },
        "data_scientist": { ... },
        "project_manager": { ... }
    }
}
```

The scenario framework allows configuration of:
- Interview stages with appropriate questions for each
- Interviewer personality profiles
- Position-specific requirements and technical questions
- Experience levels and expectations
- Company profiles and work environments

### Response Templates

The system includes structured templates for different interaction types:

```python
INTERVIEW_TEMPLATES = {
    "greeting": "Hello, I'm your interviewer for today. {introduction}",
    "question": "{question}",
    "follow_up": "Thanks for sharing that. {follow_up_question}",
    "challenge": "That's interesting. {challenge_statement}",
    "clarification": "Could you elaborate more on {clarification_point}?",
    "positive_feedback": "That's a strong answer, especially regarding {highlight_point}.",
    "wrap_up": "Thank you for your answers so far. {wrap_up_statement}"
}
```

## Usage Patterns

### Standard LLM Request Flow

1. **Prompt Formatting**: The user's input is formatted with context and stage-specific guidance
   ```python
   formatted_prompt = self._format_prompt(prompt, context, interaction_stage)
   ```

2. **Cache Check**: The system checks if the response is already cached
   ```python
   cache_key = self._create_cache_key(prompt, context, interaction_stage)
   cached_response = self._check_cache(cache_key)
   if cached_response:
       return cached_response
   ```

3. **LLM Request**: If not cached, a request is sent to Ollama with optimized parameters
   ```python
   # Build the payload with optimized config values
   payload = {
       "model": self.model,
       "prompt": formatted_prompt,
       "stream": False,  # Streaming adds overhead, disable for fastest response
       "context": [],    # Ollama context is different from our context
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
   ```

4. **Response Processing**: The response is processed with smart truncation
   ```python
   # Truncate overly long responses for consistent timing
   if len(generated_text) > 250:  # About 2-3 sentences
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
   ```

5. **Response Caching**: The response is cached with extensive metadata
   ```python
   # Cache the response with metadata for future use and analysis
   if cache_key not in self.response_cache:
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
   ```

### Asynchronous LLM Request Flow

For non-blocking operation, the system uses an asynchronous flow with progress callbacks:

```python
async def generate_response_async(self, prompt, context=None, timeout=None, max_retries=None, 
                                 progress_callback=None, interaction_stage=None):
    # Check cache first
    cache_key = self._create_cache_key(prompt, context, interaction_stage)
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
            
        return response_text
    except Exception as e:
        self.logger.error(f"Async LLM error: {e}")
        return "I'm sorry, I encountered a problem with my thinking process. Let's try a different question."
```

## Implementation Details

### Prompt Engineering

The LLM client formats prompts with sophisticated context management and stage-specific guidance:

```python
def _format_prompt(self, user_input: str, context: List[Dict[str, str]], interaction_stage: str = None) -> str:
    """
    Format the prompt with system instructions and conversation history.
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
```

### Intelligent Context Pruning

The client implements sophisticated context pruning to maintain important conversation elements while reducing token count:

```python
def _prune_context(self, context: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Intelligently prune context to preserve meaningful conversation while reducing tokens.
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
```

### Advanced Caching System

The client implements a sophisticated caching system with weighted priority-based invalidation:

```python
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
```

### Background Precomputation

The client implements proactive response generation for common questions:

```python
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
```

### Error Handling and Retries

The client implements a robust retry mechanism with exponential backoff:

```python
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
            return "I need a moment to think. Could you tell me about your technical skills?"
        
        # [Response processing code...]
        
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
```

### Persistent Cache Management

The client implements disk-based cache persistence with atomic write pattern:

```python
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
```

## Configuration

The LLM client is configured through the main system configuration:

```json
"ollama": {
  "url": "http://localhost:11434",
  "model": "mistral:latest",
  "context_length": 8192,
  "system_prompt": "You are a job interviewer conducting an interview...",
  "use_streaming": false,
  "max_cache_entries": 500,
  "scenario_type": "interview",
  "precompute_enabled": true,
  "options": {
    "temperature": 0.7,
    "top_p": 0.85,
    "top_k": 30,
    "repeat_penalty": 1.2,
    "num_predict": 120,
    "seed": 42,
    "timeout": 60
  }
}
```

Key configuration options:
- **url**: The URL of the Ollama API server
- **model**: The model to use (e.g., "mistral:latest", "phi")
- **context_length**: Maximum context length for the model
- **system_prompt**: Initial instructions for the LLM (optional, loads based on scenario)
- **use_streaming**: Whether to use streaming mode (disabled for optimal performance)
- **max_cache_entries**: Maximum number of cached responses
- **scenario_type**: Type of conversation scenario
- **precompute_enabled**: Whether to precompute responses for common questions
- **options**:
  - **temperature**: Randomness of responses (0.0-1.0)
  - **top_p**: Token selection cutoff for sampling
  - **top_k**: Number of tokens to consider for sampling
  - **repeat_penalty**: Penalty for repetition
  - **num_predict**: Maximum tokens to generate
  - **seed**: Random seed for reproducibility
  - **timeout**: Request timeout in seconds

## Common Issues

### API Communication Issues

1. **Connection Failures**:
   - **Symptoms**: "Ollama API connection error" in logs
   - **Causes**: Ollama server not running, network issues
   - **Solution**: Automatic retry with exponential backoff, then graceful fallback response

2. **Timeout Issues**:
   - **Symptoms**: "Ollama API timeout" in logs
   - **Causes**: Long processing time, large context, complex prompt
   - **Solution**: Dynamic timeout adjustment, automatic retries with increased timeout

3. **Empty Responses**:
   - **Symptoms**: "Received empty response from Ollama" in logs
   - **Causes**: Model issues, malformed prompt, context window limits
   - **Solution**: Fallback to a generic response with a prompt for the user

### Content Quality Issues

1. **Verbose Responses**:
   - **Symptoms**: Long, multi-paragraph responses
   - **Causes**: Model verbosity, insufficient prompt control
   - **Solution**: Smart truncation at sentence boundaries, brevity instructions in prompt

2. **Repetitive Responses**:
   - **Symptoms**: Similar responses to different questions, internal repetition
   - **Causes**: Limited context, insufficient prompt diversity
   - **Solution**: Increased repeat penalty, context pruning to maintain diversity

3. **Out-of-character Responses**:
   - **Symptoms**: Responses mention being an AI, break character
   - **Causes**: Model default behavior
   - **Solution**: Clear character instructions in system prompt, stage-specific guidance

### Performance Issues

1. **Slow Response Generation**:
   - **Symptoms**: High latency, timeouts
   - **Causes**: Large context, complex prompts, inefficient parameters
   - **Solution**: Context pruning, optimized parameter settings, response length limits

2. **Cache Inefficiency**:
   - **Symptoms**: Low cache hit rate despite similar questions
   - **Causes**: Overly specific cache keys, insufficient normalization
   - **Solution**: Sophisticated cache key generation, context fingerprinting

3. **Memory Growth**:
   - **Symptoms**: Increasing memory usage over time
   - **Causes**: Unbounded cache growth
   - **Solution**: Intelligent cache pruning with weighted prioritization

## Code Examples

### Using the OllamaClient in WebSocketServer

```python
# In WebSocketServer.process_audio_pipeline
session = self.state_manager.get_session(session_id)
metadata = session.metadata.copy() if session.metadata else {}

# Determine interaction stage based on context and metadata
interaction_stage = metadata.get("stage", None)

# If no explicit stage, try to infer it
if not interaction_stage:
    context = session.get_context()
    # First message is greeting
    if not context or len(context) <= 1:
        interaction_stage = "introduction"
    # Middle exchanges are behavioral/technical assessment
    elif len(context) > 2 and len(context) <= 10:
        interaction_stage = "behavioral_assessment"
    # Later stages inferred by counting turns
    elif len(context) > 10:
        interaction_stage = "conclusion"

# Generate LLM response with timeout and progress updates
try:
    # Start a new heartbeat for LLM processing to prevent connection timeout
    if self.heartbeat_service and websocket:
        heartbeat_task = asyncio.create_task(
            self.heartbeat_service.start_heartbeat(
                session_id,
                lambda msg: websocket.send(json.dumps(msg)),
                {"processing_stage": "generating_response"}
            )
        )

    # Use async version with progress callback
    response = await self.llm_client.generate_response_async(
        transcript,
        session.get_context(),
        None,  # default timeout
        None,  # default retries
        lambda msg: self.state_manager.transition_state(
            session_id, 
            "PROCESSING", 
            {"message": f"Generating response: {msg}", "progress": True}
        ),
        interaction_stage
    )
    
    # Add the exchange to session history
    session.add_interaction(transcript, response)
    
    # Log response
    self.logger.info(f"LLM Response: {response}")
    
except asyncio.TimeoutError:
    # Handle LLM timeout
    self.logger.warning(f"LLM timeout for session {session_id}")
    if self.error_handler:
        await self.error_handler.handle_error(
            ErrorHandler.LLM_ERROR,
            session_id,
            Exception("LLM response generation timed out"),
            {"websocket": websocket, "transcript": transcript}
        )
```

### Cleanup During Shutdown

```python
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
```

## Using the Scenario Framework

```python
from services.llm.scenarios import job_interview

# Get a formatted interview prompt with specific parameters
interview_prompt = job_interview.get_interview_prompt(
    position_type="software_engineer",
    interview_style="technical",
    experience_level="mid_level",
    company_type="tech_startup",
    stage="technical_assessment",
    context_memory="Candidate mentioned experience with Python and React."
)

# Get sample questions for a specific stage and position
technical_questions = job_interview.get_stage_questions(
    position_type="software_engineer", 
    stage="technical_assessment"
)

# Generate a context for LLM from previous conversation
previous_exchanges = session.get_context()
context_memory = job_interview.generate_interview_context(
    previous_exchanges, 
    max_tokens=1000
)
```

## Best Practices

### Optimizing Response Time

1. **Use Focused Prompts**:
   - Add explicit brevity instructions in the system prompt
   - Use stage-specific guidance to direct the model
   - Implement smart context pruning to reduce token count

2. **Optimize Model Parameters**:
   - Reduce temperature for more consistent responses
   - Lower num_predict to focus on shorter responses
   - Increase repeat_penalty to discourage verbosity
   - Use appropriate stop sequences to prevent overgeneration

3. **Leverage Caching**:
   - Implement effective cache key generation
   - Precompute responses for common questions
   - Use intelligent cache pruning to maintain relevance

### Ensuring Response Quality

1. **Character Consistency**:
   - Use the scenario framework to maintain interviewer persona
   - Include clear character instructions in system prompt
   - Use stage-specific guidance for appropriate questioning

2. **Natural Dialogue**:
   - Implement smart truncation at sentence boundaries
   - Maintain essential context for continuity
   - Use appropriate follow-up prompts based on conversation

3. **Error Resilience**:
   - Implement retry mechanisms with exponential backoff
   - Use graceful fallback responses for failures
   - Handle edge cases like empty responses and timeouts

## Conclusion

The LLM Integration component serves as the intelligence behind the VR Interview System, providing contextually relevant, character-consistent responses in a timely manner. Through sophisticated context management, advanced caching, and efficient error handling, it achieves a balance of response quality and performance critical for real-time VR interaction. The scenario framework allows for customizable interview experiences across various job types, interviewer styles, and experience levels.