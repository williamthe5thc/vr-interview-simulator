# VR Interview System: Function Reference

This document provides an alphabetical reference to key functions and methods in the VR Interview System. Each function is documented with its purpose, parameters, return values, examples, and related functions.

## Table of Contents

1. [EnhancedServer](#enhancedserver)
2. [ErrorHandler](#errorhandler)
3. [EnhancedStreamProcessor](#enhancedstreamprocessor)
4. [HeartbeatService](#heartbeatservice)
5. [OllamaClient](#ollamaclient)
6. [Session](#session)
7. [StateManager](#statemanager)
8. [STTService](#sttservice)
9. [TTS Services](#tts-services)
10. [WebSocketServer](#websocketserver)

---

## EnhancedServer

### `__init__(self, config_path="config/config.json")`

**Purpose:**  
Initializes the enhanced server with all required components.

**Parameters:**  
- `config_path` (str): Path to the configuration file

**Returns:**  
None

**Example:**
```python
server = EnhancedServer("config/custom_config.json")
```

**Related Functions:**
- `start()`: Starts the server
- `_load_config()`: Loads configuration from file

### `start(self)`

**Purpose:**  
Starts the WebSocket server and initializes all services with preloading.

**Parameters:**  
None

**Returns:**  
None (asynchronous function)

**Example:**
```python
await server.start()
```

**Related Functions:**
- `shutdown()`: Shuts down the server
- `_setup_directories()`: Creates necessary directories

### `_load_config(self, config_path)`

**Purpose:**  
Loads configuration from a file with fallback to default configuration.

**Parameters:**  
- `config_path` (str): Path to the configuration file

**Returns:**  
- `dict`: Loaded configuration

**Example:**
```python
config = self._load_config("config/config.json")
```

**Related Functions:**
- `__init__()`: Main initialization function

### `_register_error_handlers(self)`

**Purpose:**  
Registers handlers for different error types with the error handler.

**Parameters:**  
None

**Returns:**  
None

**Example:**
```python
self._register_error_handlers()
```

**Related Functions:**
- `_handle_llm_error()`: Handles LLM errors
- `_handle_stt_error()`: Handles STT errors
- `_handle_tts_error()`: Handles TTS errors
- `_handle_websocket_error()`: Handles WebSocket connection errors
- `_handle_system_error()`: Handles general system errors

### `_handle_llm_error(self, session_id, exception, context)`

**Purpose:**  
Handle errors in LLM processing with improved recovery.

**Parameters:**  
- `session_id` (str): The affected session ID
- `exception` (Exception): The error that occurred
- `context` (dict): Additional context about the error situation

**Returns:**  
- `bool`: True if recovery was successful, False otherwise

**Example:**
```python
success = await self._handle_llm_error(session_id, exception, {"websocket": websocket})
```

**Related Functions:**
- `_handle_stt_error()`: Handles STT-specific errors
- `_handle_tts_error()`: Handles TTS-specific errors

### `_handle_tts_error(self, session_id, exception, context)`

**Purpose:**  
Handle errors in text-to-speech processing with improved recovery, including delayed response checking.

**Parameters:**  
- `session_id` (str): The affected session ID
- `exception` (Exception): The error that occurred
- `context` (dict): Additional context about the error situation

**Returns:**  
- `bool`: True if recovery was successful, False otherwise

**Example:**
```python
success = await self._handle_tts_error(
    session_id, 
    exception, 
    {"websocket": websocket, "text_response": text}
)
```

**Related Functions:**
- `_check_delayed_tts_response()`: Checks for delayed TTS response completion

### `_check_delayed_tts_response(self, session_id, text_response, context)`

**Purpose:**  
Check if a delayed TTS response becomes available and deliver it.

**Parameters:**  
- `session_id` (str): The session to check for delayed response
- `text_response` (str): The text that was being converted to speech
- `context` (dict): Additional context information

**Returns:**  
None (asynchronous function)

**Example:**
```python
asyncio.create_task(self._check_delayed_tts_response(
    session_id, 
    text_response, 
    context
))
```

**Related Functions:**
- `_handle_tts_error()`: Handler for TTS errors

### `_shutdown(self)`

**Purpose:**  
Gracefully shuts down the server and cleans up resources.

**Parameters:**  
None

**Returns:**  
None (asynchronous function)

**Example:**
```python
await server._shutdown()
```

**Related Functions:**
- `_signal_handler()`: Handles termination signals

---

## ErrorHandler

### `__init__(self)`

**Purpose:**  
Initializes the error handler with tracking structures, recovery limits, and cooldown periods.

**Parameters:**  
None

**Returns:**  
None

**Example:**
```python
error_handler = ErrorHandler()
```

**Related Functions:**
- `register_recovery_handler()`: Registers handlers for error types
- `handle_error()`: Main error handling method

### `handle_error(self, error_type, session_id, exception, context=None)`

**Purpose:**  
Handles errors with appropriate recovery strategies, considering recovery attempts and cooldowns.

**Parameters:**  
- `error_type` (str): Type of error (use class constants)
- `session_id` (str): Session identifier
- `exception` (Exception): The exception that occurred
- `context` (dict, optional): Additional context information for recovery

**Returns:**  
- `tuple`: (success, metadata)

**Example:**
```python
success, metadata = await error_handler.handle_error(
    ErrorHandler.LLM_ERROR,
    session_id,
    exception,
    {"websocket": websocket}
)
```

**Related Functions:**
- `_handle_exceeded_recovery_attempts()`: Handles excessive recovery attempts
- `_handle_cooldown_recovery()`: Handles recovery during cooldown

### `_handle_exceeded_recovery_attempts(self, error_type, session_id, exception, context=None)`

**Purpose:**  
Handle the case where we've exceeded maximum recovery attempts for an error type using more aggressive recovery strategies.

**Parameters:**  
- `error_type` (str): Type of error
- `session_id` (str): Session identifier
- `exception` (Exception): The exception that occurred
- `context` (dict, optional): Additional context information for recovery

**Returns:**  
- `tuple`: (success, metadata)

**Example:**
```python
success, metadata = await error_handler._handle_exceeded_recovery_attempts(
    error_type, 
    session_id, 
    exception, 
    context
)
```

**Related Functions:**
- `_handle_cooldown_recovery()`: Handles recovery during cooldown
- `handle_error()`: Main error handling method

### `_handle_cooldown_recovery(self, error_type, session_id, exception, context=None)`

**Purpose:**  
Handle the case where we're in a cooldown period for an error type using lighter recovery strategies.

**Parameters:**  
- `error_type` (str): Type of error
- `session_id` (str): Session identifier
- `exception` (Exception): The exception that occurred
- `context` (dict, optional): Additional context information for recovery

**Returns:**  
- `tuple`: (success, metadata)

**Example:**
```python
success, metadata = await error_handler._handle_cooldown_recovery(
    error_type, 
    session_id, 
    exception, 
    context
)
```

**Related Functions:**
- `_handle_exceeded_recovery_attempts()`: Handles excessive recovery attempts
- `handle_error()`: Main error handling method

### `register_recovery_handler(self, error_type, handler)`

**Purpose:**  
Registers a handler function for a specific error type.

**Parameters:**  
- `error_type` (str): Type of error to handle
- `handler` (callable): Function to handle the error

**Returns:**  
None

**Example:**
```python
error_handler.register_recovery_handler(
    ErrorHandler.LLM_ERROR,
    self._handle_llm_error
)
```

**Related Functions:**
- `handle_error()`: Main error handling method

### `get_error_statistics(self, session_id=None)`

**Purpose:**  
Gets error statistics for debugging and monitoring.

**Parameters:**  
- `session_id` (str, optional): Session ID for specific session stats

**Returns:**  
- `dict`: Error statistics

**Example:**
```python
stats = error_handler.get_error_statistics(session_id)
```

**Related Functions:**
- `_aggregate_error_types()`: Aggregates error types across sessions

### `reset_session_errors(self, session_id)`

**Purpose:**  
Resets error tracking for a specific session.

**Parameters:**  
- `session_id` (str): Session identifier to reset

**Returns:**  
None

**Example:**
```python
error_handler.reset_session_errors(session_id)
```

**Related Functions:**
- `cleanup_old_sessions()`: Cleans up error tracking for old sessions

### `cleanup_old_sessions(self, max_age_seconds=3600)`

**Purpose:**  
Clean up error tracking for old sessions to prevent memory leaks.

**Parameters:**  
- `max_age_seconds` (int): Maximum age in seconds for sessions to keep (default: 1 hour)

**Returns:**  
None

**Example:**
```python
error_handler.cleanup_old_sessions(7200)  # 2 hours
```

**Related Functions:**
- `reset_session_errors()`: Resets error tracking for a specific session

---

## EnhancedStreamProcessor

### `__init__(self, state_manager, stt_service, tts_service, llm_client, error_handler=None)`

**Purpose:**  
Initializes the enhanced stream processor with optimized processing pipeline.

**Parameters:**  
- `state_manager`: State management component
- `stt_service`: Speech-to-text service
- `tts_service`: Text-to-speech service
- `llm_client`: Language model client
- `error_handler`: Error handling component

**Returns:**  
None

**Example:**
```python
stream_processor = EnhancedStreamProcessor(
    state_manager,
    stt_service,
    tts_service,
    llm_client,
    error_handler
)
```

**Related Functions:**
- `process_streaming_audio_pipeline()`: Main processing pipeline

### `process_streaming_audio_pipeline(self, session_id, audio_data, websocket)`

**Purpose:**  
Process audio with optimized streaming pipeline for faster responses with parallel processing stages.

**Parameters:**  
- `session_id` (str): Session identifier
- `audio_data` (bytes): Raw audio data
- `websocket`: WebSocket connection for sending responses

**Returns:**  
None (asynchronous function)

**Example:**
```python
await stream_processor.process_streaming_audio_pipeline(
    session_id, 
    audio_data,
    websocket
)
```

**Related Functions:**
- `_generate_standard_tts()`: Generates speech using standard approach
- `_prewarm_tts()`: Preloads TTS engine to reduce latency
- `_send_progressive_updates()`: Sends progressive updates during LLM processing

### `_generate_standard_tts(self, session_id, text, websocket)`

**Purpose:**  
Generate TTS response using standard (non-streaming) approach with error handling and fallbacks.

**Parameters:**  
- `session_id` (str): Session identifier
- `text` (str): Text to convert to speech
- `websocket`: WebSocket connection for sending responses

**Returns:**  
None (asynchronous function)

**Example:**
```python
await stream_processor._generate_standard_tts(session_id, response_text, websocket)
```

**Related Functions:**
- `process_streaming_audio_pipeline()`: Main processing pipeline
- `_prewarm_tts()`: Preloads TTS engine to reduce latency

### `_prewarm_tts(self)`

**Purpose:**  
Prewarm TTS engine to reduce cold-start latency on first response.

**Parameters:**  
None

**Returns:**  
- `bool`: True if successful, False otherwise (asynchronous function)

**Example:**
```python
tts_prewarm_task = asyncio.create_task(stream_processor._prewarm_tts())
```

**Related Functions:**
- `_generate_standard_tts()`: Generates speech using standard approach

### `_handle_delayed_llm_response(self, session_id, llm_future, websocket)`

**Purpose:**  
Handle LLM response that completes after the timeout, allowing late responses to still be delivered.

**Parameters:**  
- `session_id` (str): Session identifier
- `llm_future`: Future for the LLM response
- `websocket`: WebSocket connection for sending responses

**Returns:**  
None (asynchronous function)

**Example:**
```python
asyncio.create_task(
    stream_processor._handle_delayed_llm_response(session_id, llm_future, websocket)
)
```

**Related Functions:**
- `process_streaming_audio_pipeline()`: Main processing pipeline

### `_send_progressive_updates(self, session_id, websocket)`

**Purpose:**  
Send progressive updates to client during long LLM operations.

**Parameters:**  
- `session_id` (str): Session identifier
- `websocket`: WebSocket connection for sending updates

**Returns:**  
None (asynchronous function)

**Example:**
```python
heartbeat_task = asyncio.create_task(
    stream_processor._send_progressive_updates(session_id, websocket)
)
```

**Related Functions:**
- `_send_progress_update()`: Sends a single progress update message
- `process_streaming_audio_pipeline()`: Main processing pipeline

### `_send_progress_update(self, websocket, message)`

**Purpose:**  
Send a single progress update message to the client.

**Parameters:**  
- `websocket`: WebSocket connection for sending updates
- `message` (str): Progress message

**Returns:**  
None (asynchronous function)

**Example:**
```python
await stream_processor._send_progress_update(websocket, "Still thinking about your question...")
```

**Related Functions:**
- `_send_progressive_updates()`: Sends multiple progressive updates during processing

---

## HeartbeatService

### `__init__(self, heartbeat_interval=5.0)`

**Purpose:**  
Initialize the heartbeat service for keeping WebSocket connections alive.

**Parameters:**  
- `heartbeat_interval` (float): Time between heartbeats in seconds

**Returns:**  
None

**Example:**
```python
heartbeat_service = HeartbeatService(5.0)
```

**Related Functions:**
- `start_heartbeat()`: Starts sending heartbeat messages for a session
- `stop_heartbeat()`: Stops heartbeat messages for a session

### `start_heartbeat(self, session_id, send_func, metadata=None)`

**Purpose:**  
Start sending heartbeat messages for a session to prevent connection timeouts.

**Parameters:**  
- `session_id` (str): Unique identifier for the session
- `send_func` (callable): Function to call to send the heartbeat
- `metadata` (dict, optional): Additional data to include in heartbeat

**Returns:**  
None (asynchronous function)

**Example:**
```python
await heartbeat_service.start_heartbeat(
    session_id,
    lambda msg: websocket.send(json.dumps(msg)),
    {"processing_stage": "generating_response"}
)
```

**Related Functions:**
- `stop_heartbeat()`: Stops heartbeat messages for a session
- `_heartbeat_loop()`: Internal loop that sends periodic heartbeat messages

### `stop_heartbeat(self, session_id)`

**Purpose:**  
Stop sending heartbeat messages for a session.

**Parameters:**  
- `session_id` (str): Unique identifier for the session

**Returns:**  
None (asynchronous function)

**Example:**
```python
await heartbeat_service.stop_heartbeat(session_id)
```

**Related Functions:**
- `start_heartbeat()`: Starts sending heartbeat messages
- `stop_all()`: Stops all active heartbeats

### `stop_all(self)`

**Purpose:**  
Stop all active heartbeats, typically used during shutdown.

**Parameters:**  
None

**Returns:**  
None (asynchronous function)

**Example:**
```python
await heartbeat_service.stop_all()
```

**Related Functions:**
- `stop_heartbeat()`: Stops heartbeat for a specific session

### `_heartbeat_loop(self, session_id, send_func, metadata)`

**Purpose:**  
Internal loop that sends periodic heartbeat messages with dynamic intervals.

**Parameters:**  
- `session_id` (str): Unique identifier for the session
- `send_func` (callable): Function to call to send the heartbeat
- `metadata` (dict): Additional data for heartbeat messages

**Returns:**  
None (asynchronous function)

**Example:**
```python
# Called internally by start_heartbeat()
```

**Related Functions:**
- `start_heartbeat()`: Public method to start the heartbeat loop

---

## OllamaClient

### `__init__(self, url, model, context_length=8192, config=None)`

**Purpose:**  
Initializes the Ollama client with configuration and improved caching.

**Note:** This class is imported from `services.llm.Ollama_client` (capital O in filename).

**Parameters:**  
- `url` (str): The URL of the Ollama API
- `model` (str): The model to use (e.g., "mistral:latest")
- `context_length` (int): Maximum context length for the model
- `config` (dict, optional): Additional configuration

**Returns:**  
None

**Example:**
```python
llm_client = OllamaClient(
    "http://localhost:11434",
    "mistral:latest",
    8192,
    config
)
```

**Related Functions:**
- `_load_system_prompt()`: Loads the system prompt for the scenario
- `generate_response()`: Generates a response from the LLM

### `generate_response(self, prompt, context=None, timeout=None, max_retries=None, interaction_stage=None)`

**Purpose:**  
Generates a response using the Ollama API with improved caching and retry logic.

**Parameters:**  
- `prompt` (str): The user input to respond to
- `context` (list, optional): Conversation history
- `timeout` (int, optional): Request timeout in seconds
- `max_retries` (int, optional): Maximum retry attempts
- `interaction_stage` (str, optional): Current stage of the interaction

**Returns:**  
- `str`: Generated response text

**Example:**
```python
response = llm_client.generate_response(
    "Tell me about your experience with Python",
    context,
    timeout=30,
    max_retries=2,
    interaction_stage="technical_question"
)
```

**Related Functions:**
- `_format_prompt()`: Formats the prompt with context
- `_create_cache_key()`: Creates a cache key for the request
- `_check_cache()`: Checks if a response is cached

### `generate_response_async(self, prompt, context=None, timeout=None, max_retries=None, progress_callback=None, interaction_stage=None)`

**Purpose:**  
Generates a response asynchronously with progress updates, without blocking the event loop.

**Parameters:**  
- `prompt` (str): The user input to respond to
- `context` (list, optional): Conversation history
- `timeout` (int, optional): Request timeout in seconds
- `max_retries` (int, optional): Maximum retry attempts
- `progress_callback` (callable, optional): Callback for progress updates
- `interaction_stage` (str, optional): Current stage of the interaction

**Returns:**  
- `str`: Generated response text

**Example:**
```python
async def update_progress(message, progress=None):
    await state_manager.transition_state(session_id, "PROCESSING_LLM", 
                                        {"message": message, "progress": progress})

response = await llm_client.generate_response_async(
    prompt,
    context,
    timeout=30,
    progress_callback=update_progress,
    interaction_stage="technical_question"
)
```

**Related Functions:**
- `_make_ollama_request()`: Makes the actual HTTP request to Ollama

### `_format_prompt(self, user_input, context, interaction_stage=None)`

**Purpose:**  
Formats the prompt with system instructions, conversation history, and stage-specific guidance.

**Parameters:**  
- `user_input` (str): The user's input
- `context` (list): Conversation history
- `interaction_stage` (str, optional): Current stage of the interaction

**Returns:**  
- `str`: Formatted prompt for the LLM

**Example:**
```python
formatted_prompt = llm_client._format_prompt(
    user_input,
    context,
    "technical_question"
)
```

**Related Functions:**
- `_prune_context()`: Intelligently prunes context to fit within token limits
- `generate_response()`: Generates a response using the formatted prompt

### `_prune_context(self, context)`

**Purpose:**  
Intelligently prune context to preserve meaningful conversation while reducing tokens.

**Parameters:**  
- `context` (list): List of conversation turns

**Returns:**  
- `list`: Pruned context list that fits token constraints

**Example:**
```python
pruned_context = llm_client._prune_context(context)
```

**Related Functions:**
- `_format_prompt()`: Formats the prompt using the pruned context

### `_create_cache_key(self, prompt, context=None, interaction_stage=None)`

**Purpose:**  
Create a sophisticated cache key based on prompt content and metadata.

**Parameters:**  
- `prompt` (str): The user input
- `context` (list, optional): Conversation history
- `interaction_stage` (str, optional): Current stage of the interaction

**Returns:**  
- `str`: Cache key string

**Example:**
```python
cache_key = llm_client._create_cache_key(prompt, context, "technical_question")
```

**Related Functions:**
- `_check_cache()`: Checks if a response is cached
- `_add_to_cache()`: Adds a response to the cache

### `_check_cache(self, cache_key)`

**Purpose:**  
Check cache with improved logging and metrics.

**Parameters:**  
- `cache_key` (str): The cache key to check

**Returns:**  
- `str` or `None`: Cached response or None

**Example:**
```python
cached_response = llm_client._check_cache(cache_key)
if cached_response:
    return cached_response
```

**Related Functions:**
- `_create_cache_key()`: Creates a cache key for checking
- `_prune_cache()`: Removes old entries when cache is full

### `_make_ollama_request(self, formatted_prompt, timeout, max_retries, cache_key=None, interaction_stage=None)`

**Purpose:**  
Make the actual HTTP request to Ollama API with optimized settings and retries.

**Parameters:**  
- `formatted_prompt` (str): The complete formatted prompt
- `timeout` (int): Request timeout in seconds
- `max_retries` (int): Maximum retry attempts
- `cache_key` (str, optional): Cache key for storing response
- `interaction_stage` (str, optional): Current interaction stage

**Returns:**  
- `str`: Generated text response

**Example:**
```python
# Called internally by generate_response methods
```

**Related Functions:**
- `_prune_cache()`: Intelligently prunes cache when full
- `_save_cache_to_disk()`: Saves cache to disk for persistence

### `_prune_cache(self)`

**Purpose:**  
Intelligently prune cache entries based on usage patterns when cache is full.

**Parameters:**  
None

**Returns:**  
None

**Example:**
```python
# Called internally when cache reaches max_cache_entries
```

**Related Functions:**
- `_save_cache_to_disk()`: Saves updated cache to disk

### `cleanup(self)`

**Purpose:**  
Clean up resources when shutting down.

**Parameters:**  
None

**Returns:**  
None

**Example:**
```python
llm_client.cleanup()
```

**Related Functions:**
- `_save_cache_to_disk()`: Saves cache before shutdown

---

## Session

### `__init__(self, session_id, websocket)`

**Purpose:**  
Initializes a new session with a client.

**Parameters:**  
- `session_id` (str): Unique identifier for the session
- `websocket`: WebSocket connection object

**Returns:**  
None

**Example:**
```python
session = Session(session_id, websocket)
```

**Related Functions:**
- `add_interaction()`: Records a user-system interaction
- `get_context()`: Gets conversation context for the LLM

### `add_interaction(self, user_input, system_response)`

**Purpose:**  
Records a user-system interaction in the conversation history.

**Parameters:**  
- `user_input` (str): User's input
- `system_response` (str): System's response

**Returns:**  
None

**Example:**
```python
session.add_interaction(transcript, response)
```

**Related Functions:**
- `get_context()`: Gets the conversation context from history

### `get_context(self)`

**Purpose:**  
Gets formatted conversation context for the LLM.

**Parameters:**  
None

**Returns:**  
- `list`: Conversation turns formatted for the LLM

**Example:**
```python
context = session.get_context()
```

**Related Functions:**
- `add_interaction()`: Adds to the conversation history

### `reset(self)`

**Purpose:**  
Resets the conversation history.

**Parameters:**  
None

**Returns:**  
None

**Example:**
```python
session.reset()
```

**Related Functions:**
- `add_interaction()`: Adds to the conversation history

### `is_expired(self, timeout_seconds=1800)`

**Purpose:**  
Checks if the session has expired due to inactivity.

**Parameters:**  
- `timeout_seconds` (int): Inactivity timeout in seconds (default: 30 minutes)

**Returns:**  
- `bool`: True if expired, False otherwise

**Example:**
```python
if session.is_expired(3600):  # 1 hour
    # Handle expired session
```

**Related Functions:**
- `to_dict()`: Converts session to a dictionary

### `to_dict(self)`

**Purpose:**  
Converts session to a dictionary for storage or serialization.

**Parameters:**  
None

**Returns:**  
- `dict`: Session data as a dictionary

**Example:**
```python
session_data = session.to_dict()
```

**Related Functions:**
- `save_to_file()`: Saves the session data to a file

---

## StateManager

### `__init__(self)`

**Purpose:**  
Initializes the state manager for conversation sessions with deadlock prevention.

**Parameters:**  
None

**Returns:**  
None

**Example:**
```python
state_manager = StateManager()
```

**Related Functions:**
- `create_session()`: Creates a new session
- `transition_state()`: Handles state transitions
- `_handle_deadlock()`: Deadlock detection and resolution

### `create_session(self, session_id, session)`

**Purpose:**  
Initializes a new session with IDLE state and required tracking structures.

**Parameters:**  
- `session_id` (str): Unique identifier for the session
- `session` (Session): Session object

**Returns:**  
None

**Example:**
```python
state_manager.create_session(session_id, session)
```

**Related Functions:**
- `end_session()`: Cleans up session resources
- `transition_state()`: Transitions a session to a new state

### `end_session(self, session_id)`

**Purpose:**  
Cleans up session resources, including any deadlock timeouts.

**Parameters:**  
- `session_id` (str): Session identifier to end

**Returns:**  
None (asynchronous function)

**Example:**
```python
await state_manager.end_session(session_id)
```

**Related Functions:**
- `create_session()`: Creates a new session
- `_handle_deadlock()`: Cancels any deadlock timers for the session

### `transition_state(self, session_id, new_state, metadata=None, timeout=5.0)`

**Purpose:**  
Transitions a session to a new state with validation, lock management, and deadlock prevention.

**Parameters:**  
- `session_id` (str): The session to update
- `new_state` (str): The new state to transition to
- `metadata` (dict, optional): Additional metadata for the state update
- `timeout` (float): Maximum time to wait for lock acquisition

**Returns:**  
- `bool`: True if successful, False otherwise

**Example:**
```python
success = await state_manager.transition_state(
    session_id,
    "PROCESSING_LLM",
    {
        "message": "Generating response to your question",
        "transcript": transcript,
        "progress": 0.0
    }
)
```

**Related Functions:**
- `_is_valid_transition()`: Validates state transitions
- `_broadcast_state_change()`: Broadcasts state changes to clients
- `_handle_deadlock()`: Detects and resolves deadlocks

### `force_transition(self, session_id, new_state, metadata=None)`

**Purpose:**  
Forces a state transition without validation or locks for emergency recovery.

**Parameters:**  
- `session_id` (str): The session to update
- `new_state` (str): The new state to transition to
- `metadata` (dict, optional): Additional metadata for the state update

**Returns:**  
- `bool`: True if successful, False otherwise

**Example:**
```python
success = await state_manager.force_transition(
    session_id,
    "WAITING",
    {
        "message": "Ready for next question",
        "recovery": True
    }
)
```

**Related Functions:**
- `transition_state()`: Normal state transition with validation

### `get_session(self, session_id)`

**Purpose:**  
Get the session object for a session ID.

**Parameters:**  
- `session_id` (str): The session to retrieve

**Returns:**  
- `Session` or `None`: Session object if found, None otherwise

**Example:**
```python
session = state_manager.get_session(session_id)
if session:
    # Use session object
```

**Related Functions:**
- `get_session_state()`: Gets just the current state for a session

### `get_session_state(self, session_id)`

**Purpose:**  
Gets the current state name for a session.

**Parameters:**  
- `session_id` (str): The session to query

**Returns:**  
- `str`: Current state name, or None if session not found

**Example:**
```python
current_state = state_manager.get_session_state(session_id)
if current_state == "PROCESSING_LLM":
    # Handle processing state
```

**Related Functions:**
- `get_session()`: Gets the full session object
- `transition_state()`: Changes the session state

### `_is_valid_transition(self, current, next_state)`

**Purpose:**  
Validate that a state transition follows the allowed flow, with support for granular processing states.

**Parameters:**  
- `current` (str): Current state
- `next_state` (str): Proposed new state

**Returns:**  
- `bool`: Whether the transition is valid

**Example:**
```python
# Called internally by transition_state
valid = self._is_valid_transition("LISTENING", "PROCESSING_STT")
```

**Related Functions:**
- `transition_state()`: Uses this for validation

### `_handle_deadlock(self, session_id, new_state, timeout)`

**Purpose:**  
Improved deadlock detection and resolution to ensure conversations can continue after state transition problems.

**Parameters:**  
- `session_id` (str): The session ID experiencing potential deadlock
- `new_state` (str): The state we're attempting to transition to
- `timeout` (float): The lock acquisition timeout

**Returns:**  
None (asynchronous function)

**Example:**
```python
# Called internally by transition_state
deadlock_task = asyncio.create_task(
    self._handle_deadlock(session_id, new_state, timeout)
)
```

**Related Functions:**
- `transition_state()`: Creates the deadlock detection task
- `force_transition()`: Used for recovery after deadlock

---

## STTService

### `__init__(self, model_name="base")`

**Purpose:**  
Initializes the STT service with cross-platform GPU support.

**Parameters:**  
- `model_name` (str): The Whisper model size to use ("tiny", "base", "small", "medium", "large")

**Returns:**  
None

**Example:**
```python
stt_service = STTService("medium")
```

**Related Functions:**
- `_get_optimal_device()`: Determines the best device for processing
- `_load_model()`: Lazy-loads the model on first use
- `transcribe()`: Transcribes audio to text

### `_get_optimal_device(self)`

**Purpose:**  
Determine the optimal device for speech recognition based on platform and available hardware.

**Parameters:**  
None

**Returns:**  
- `str`: Device identifier compatible with PyTorch

**Example:**
```python
device = stt_service._get_optimal_device()
```

**Related Functions:**
- `__init__()`: Uses this to set the device

### `_load_model(self)`

**Purpose:**  
Lazy-load the Whisper model with platform-specific optimizations.

**Parameters:**  
None

**Returns:**  
None

**Example:**
```python
stt_service._load_model()
```

**Related Functions:**
- `transcribe()`: Calls this to ensure model is loaded

### `transcribe(self, audio_data)`

**Purpose:**  
Transcribes audio data to text with platform-specific optimizations.

**Parameters:**  
- `audio_data` (bytes/ndarray/str): Audio data to transcribe

**Returns:**  
- `str`: Transcribed text

**Example:**
```python
transcript = stt_service.transcribe(audio_data)
```

**Related Functions:**
- `_load_model()`: Ensures the model is loaded
- `get_model_info()`: Gets information about the loaded model

### `get_model_info(self)`

**Purpose:**  
Gets information about the loaded model with platform-specific details.

**Parameters:**  
None

**Returns:**  
- `dict`: Model information including name, device, platform and GPU details

**Example:**
```python
model_info = stt_service.get_model_info()
```

**Related Functions:**
- `transcribe()`: Main transcription method

---

## TTS Services

### TTSService

#### `__init__(self, config=None)`

**Purpose:**  
Initializes the TTS service with AllTalk direct API and gTTS fallback.

**Parameters:**  
- `config` (dict): Configuration options

**Returns:**  
None

**Example:**
```python
tts_service = TTSService(config)
```

**Related Functions:**
- `synthesize()`: Converts text to speech
- `_check_alltalk_server()`: Checks if AllTalk server is available

#### `synthesize(self, text, session_id=None)`

**Purpose:**  
Convert text to speech using AllTalk with gTTS fallback and caching.

**Parameters:**  
- `text` (str): Text to convert to speech
- `session_id` (str, optional): Optional session ID for tracking

**Returns:**  
- `bytes`: WAV audio data

**Example:**
```python
audio_data = tts_service.synthesize(
    "Hello, how can I help you with your interview preparation?",
    session_id
)
```

**Related Functions:**
- `_try_alltalk_api_methods()`: Attempts different AllTalk APIs
- `_synthesize_gtts()`: Fallback synthesis using gTTS

#### `_try_alltalk_api_methods(self, text)`

**Purpose:**  
Try multiple AllTalk API methods in sequence for best reliability.

**Parameters:**  
- `text` (str): The text to convert to speech

**Returns:**  
- `bytes` or `None`: Audio data if successful, None otherwise

**Example:**
```python
audio_data = self._try_alltalk_api_methods(text)
```

**Related Functions:**
- `_try_tts_generate_api()`: Attempts using the tts-generate API
- `_try_synthesize_api()`: Attempts using the synthesize API
- `_try_tts_api()`: Attempts using the tts API
- `_try_load_output_file()`: Tries to find generated files

#### `_try_load_output_file(self, filename_base)`

**Purpose:**  
Try to find and load AllTalk output file from possible locations, even after API timeouts.

**Parameters:**  
- `filename_base` (str): Base filename without extension

**Returns:**  
- `bytes` or `None`: Audio data if found, None otherwise

**Example:**
```python
audio_data = self._try_load_output_file(filename_base)
```

**Related Functions:**
- `_try_alltalk_api_methods()`: Uses this to check for generated files
- `_find_most_recent_wav()`: Finds the most recent WAV file in a directory

#### `_synthesize_gtts(self, text)`

**Purpose:**  
Fallback synthesis using Google Text-to-Speech (gTTS).

**Parameters:**  
- `text` (str): The text to convert to speech

**Returns:**  
- `bytes`: WAV audio data

**Example:**
```python
audio_data = self._synthesize_gtts(text)
```

**Related Functions:**
- `_generate_silence()`: Generates silent audio as a last resort

#### `is_available(self)`

**Purpose:**  
Check if the TTS service is available (either AllTalk or gTTS).

**Parameters:**  
None

**Returns:**  
- `bool`: True if available, False otherwise

**Example:**
```python
if tts_service.is_available():
    # Use TTS service
```

**Related Functions:**
- `get_available_voices()`: Gets list of available voices

### EmotiVoiceTTSService

#### `__init__(self, config=None)`

**Purpose:**  
Initializes the EmotiVoice TTS service for emotional speech synthesis.

**Parameters:**  
- `config` (dict): Configuration options

**Returns:**  
None

**Example:**
```python
emotivoice_tts = EmotiVoiceTTSService(config)
```

**Related Functions:**
- `synthesize()`: Converts text to speech with emotion
- `_check_server()`: Checks if EmotiVoice server is available

#### `synthesize(self, text, emotion=None)`

**Purpose:**  
Synthesize speech from text with specified emotion.

**Parameters:**  
- `text` (str): The text to convert to speech
- `emotion` (str, optional): Emotion override (happy, sad, angry, etc.)

**Returns:**  
- `bytes`: WAV audio data

**Example:**
```python
audio_data = emotivoice_tts.synthesize("Hello there!", "happy")
```

**Related Functions:**
- `_create_cache_key()`: Creates a cache key for the request
- `_get_from_cache()`: Gets cached audio if available

### PiperTTSService

#### `__init__(self, voice="en_US-lessac-medium", model_dir="./models/piper")`

**Purpose:**  
Initializes the Piper TTS service for faster speech synthesis.

**Parameters:**  
- `voice` (str): The voice to use
- `model_dir` (str): Directory for voice models

**Returns:**  
None

**Example:**
```python
piper_tts = PiperTTSService("en_US-lessac-medium")
```

**Related Functions:**
- `synthesize()`: Converts text to speech
- `_ensure_model_available()`: Checks if the voice model is available

#### `synthesize(self, text)`

**Purpose:**  
Convert text to speech using Piper TTS with sentence-by-sentence processing for faster response times.

**Parameters:**  
- `text` (str): The text to convert to speech

**Returns:**  
- `bytes`: WAV audio data

**Example:**
```python
audio_data = piper_tts.synthesize("Welcome to your interview practice session.")
```

**Related Functions:**
- `_synthesize_text()`: Synthesizes a single piece of text
- `_synthesize_long_text()`: Breaks text into sentences for processing
- `_combine_audio_chunks()`: Combines multiple audio chunks into one

---

## WebSocketServer

### `__init__(self, host, port, state_manager, stt_service, tts_service, llm_client, error_handler=None, heartbeat_service=None)`

**Purpose:**  
Initializes the WebSocket server with all required components.

**Parameters:**  
- `host` (str): The network interface to bind to
- `port` (int): The port to listen on
- `state_manager`: State management component
- `stt_service`: Speech-to-text service
- `tts_service`: Text-to-speech service
- `llm_client`: Language model client
- `error_handler`: Error handling component
- `heartbeat_service`: Heartbeat mechanism for connection health

**Returns:**  
None

**Example:**
```python
websocket_server = WebSocketServer(
    "0.0.0.0",
    8765,
    state_manager,
    stt_service,
    tts_service,
    llm_client,
    error_handler,
    heartbeat_service
)
```

**Related Functions:**
- `start()`: Starts the WebSocket server
- `handle_connection()`: Processes new client connections
- `_track_task()`: Adds a task to tracking system

### `start(self)`

**Purpose:**  
Starts the WebSocket server with configurable ping interval and timeout.

**Parameters:**  
None

**Returns:**  
None (asynchronous function)

**Example:**
```python
await websocket_server.start()
```

**Related Functions:**
- `shutdown()`: Gracefully shuts down the server
- `handle_connection()`: Handles incoming connections

### `shutdown(self)`

**Purpose:**  
Gracefully shuts down the WebSocket server and cancels all tasks.

**Parameters:**  
None

**Returns:**  
None (asynchronous function)

**Example:**
```python
await websocket_server.shutdown()
```

**Related Functions:**
- `start()`: Starts the WebSocket server

### `handle_connection(self, websocket, path)`

**Purpose:**  
Handles a new WebSocket connection, creates a session, and processes messages.

**Parameters:**  
- `websocket`: WebSocket connection object
- `path`: Connection path

**Returns:**  
None (asynchronous function)

**Example:**
```python
# Called internally by websockets library
```

**Related Functions:**
- `process_message()`: Processes incoming messages
- `_cleanup_session()`: Cleans up when connection closes
- `_track_task()`: Tracks tasks for the session

### `process_message(self, session_id, message)`

**Purpose:**  
Processes an incoming WebSocket message with improved error handling.

**Parameters:**  
- `session_id` (str): Session identifier
- `message` (str): Message data

**Returns:**  
None (asynchronous function)

**Example:**
```python
# Called by handle_connection
task = asyncio.create_task(
    self.process_message(session_id, message)
)
```

**Related Functions:**
- `process_audio()`: Handles audio data messages
- `process_control()`: Handles control messages

### `process_audio(self, session_id, message)`

**Purpose:**  
Processes incoming audio data with choice of standard or streaming pipeline.

**Parameters:**  
- `session_id` (str): Session identifier
- `message` (dict): Message data including audio

**Returns:**  
None (asynchronous function)

**Example:**
```python
await websocket_server.process_audio(session_id, message)
```

**Related Functions:**
- `process_audio_pipeline()`: Full audio processing workflow
- `stream_processor.process_streaming_audio_pipeline()`: Streaming version

### `process_audio_pipeline(self, session_id, audio_data)`

**Purpose:**  
Orchestrates the full audio processing workflow with granular processing states.

**Parameters:**  
- `session_id` (str): Session identifier
- `audio_data` (bytes): Audio data to process

**Returns:**  
None (asynchronous function)

**Example:**
```python
task = asyncio.create_task(
    websocket_server.process_audio_pipeline(session_id, audio_data)
)
```

**Related Functions:**
- `send_audio_response()`: Sends audio response to client
- `_safety_timeout()`: Enforces timeout for safety

### `send_audio_response(self, session_id, audio_data, text_response=None)`

**Purpose:**  
Sends audio response to client using direct audio data with improved format validation.

**Parameters:**  
- `session_id` (str): Session identifier
- `audio_data` (bytes): Audio data to send
- `text_response` (str, optional): Text version for fallback

**Returns:**  
None (asynchronous function)

**Example:**
```python
await websocket_server.send_audio_response(
    session_id,
    audio_data,
    response_text
)
```

**Related Functions:**
- `_validate_wav_format()`: Validates WAV format
- `send_error()`: Sends error message to client

### `handle_client_capabilities(self, websocket, session_id, message)`

**Purpose:**  
Processes client capability information with improved format validation and recovery.

**Parameters:**  
- `websocket`: WebSocket connection object
- `session_id` (str): Session identifier
- `message` (dict): Message with capabilities

**Returns:**  
None (asynchronous function)

**Example:**
```python
await websocket_server.handle_client_capabilities(
    websocket,
    session_id,
    message
)
```

**Related Functions:**
- `handle_playback_complete()`: Processes playback completion notifications

### `_track_task(self, task, session_id=None)`

**Purpose:**  
Tracks a task for proper lifecycle management and cleanup.

**Parameters:**  
- `task` (asyncio.Task): Task to track
- `session_id` (str, optional): Associated session

**Returns:**  
None

**Example:**
```python
self._track_task(task, session_id)
```

**Related Functions:**
- `_remove_task()`: Removes completed task from tracking
- `_cleanup_session()`: Cleans up all session tasks

### `_remove_task(self, task, session_id=None)`

**Purpose:**  
Removes a completed task from the tracking system.

**Parameters:**  
- `task` (asyncio.Task): Task to remove
- `session_id` (str, optional): Associated session

**Returns:**  
None

**Example:**
```python
# Called automatically when task completes
```

**Related Functions:**
- `_track_task()`: Adds a task to tracking
- `_cleanup_session()`: Cleans up all session tasks

### `_send_heartbeat_during_llm(self, session_id, websocket)`

**Purpose:**  
Sends periodic heartbeat messages during LLM processing to prevent client timeouts.

**Parameters:**  
- `session_id` (str): Session identifier
- `websocket`: WebSocket connection object

**Returns:**  
None (asynchronous function)

**Example:**
```python
heartbeat_task = asyncio.create_task(
    self._send_heartbeat_during_llm(session_id, websocket)
)
```

**Related Functions:**
- `_safety_timeout()`: Enforces timeout for safety

### `_safety_timeout(self, session_id, timeout_seconds)`

**Purpose:**  
Force transition to WAITING state if processing takes too long, preventing client hangs.

**Parameters:**  
- `session_id` (str): Session identifier
- `timeout_seconds` (float): Maximum time to wait before forcing transition

**Returns:**  
None (asynchronous function)

**Example:**
```python
safety_timer = asyncio.create_task(
    self._safety_timeout(session_id, 25.0)
)
```

**Related Functions:**
- `process_audio_pipeline()`: Uses this for safety

### `_cleanup_session(self, session_id)`

**Purpose:**  
Cleans up a session's resources, including tasks, heartbeats, and connections.

**Parameters:**  
- `session_id` (str): Session to clean up

**Returns:**  
None (asynchronous function)

**Example:**
```python
await self._cleanup_session(session_id)
```

**Related Functions:**
- `handle_connection()`: Calls this when connection closes

### `_validate_wav_format(self, audio_data)`

**Purpose:**  
Perform basic validation on WAV format to ensure it's playable by the client.

**Parameters:**  
- `audio_data` (bytes): The WAV audio data bytes

**Returns:**  
- `bool`: True if valid WAV format, False otherwise

**Example:**
```python
is_valid = self._validate_wav_format(audio_data)
```

**Related Functions:**
- `send_audio_response()`: Uses this to validate audio before sending