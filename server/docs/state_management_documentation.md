# VR Interview System: State Management Documentation

## Title and Overview

The State Management component of the VR Interview System is responsible for maintaining and controlling the conversation state for each user session. It implements a state machine pattern that ensures orderly progression through the interview process. The state manager tracks the current state of each session, validates state transitions, prevents invalid state changes, and communicates state updates to clients. It includes mechanisms to prevent deadlocks and handle error recovery with sophisticated fallback strategies.

## Architecture

The State Management system consists of two primary classes:

1. **StateManager**: The core class that manages the state machine logic, handles state transitions, and broadcasts state changes to clients.
2. **Session**: A data class representing a client session that stores the conversation history and metadata.

The state management system interacts with the following components:
- WebSocket Server: Receives state change broadcasts
- Error Handler: For error recovery
- LLM Client: Uses state information for contextual responses
- Enhanced Stream Processor: Uses state transitions for processing pipeline

### State Flow Diagram
```
                                     ┌────────────────┐
                                     │      IDLE      │
                                     └───────┬────────┘
                                             │
                                             ▼
┌─────────────┐             ┌────────────────────────┐
│    ERROR    │◄────────────┤      LISTENING         │
└───────┬─────┘             └────────────┬───────────┘
        │                                │
        │                                ▼
        │                   ┌────────────────────────┐
        │                   │     PROCESSING_STT     │
        │                   └────────────┬───────────┘
        │                                │
        │                                ▼
        │                   ┌────────────────────────┐
        │                   │     PROCESSING_LLM     │
        │                   └────────────┬───────────┘
        │                                │
        │                                ▼
        │                   ┌────────────────────────┐
        │                   │     PROCESSING_TTS     │
        │                   └────────────┬───────────┘
        │                                │
        │                                ▼
        │                   ┌────────────────────────┐
        │                   │      RESPONDING        │
        └───────────────────►                        │
                  recovery  └────────────┬───────────┘
                                         │
                                         ▼
                              ┌────────────────────────┐
                              │        WAITING         │
                              └────────────────────────┘
```

## Key Classes/Functions

### States Enumeration
```python
class States(Enum):
    """Enumeration of possible states for the conversation"""
    IDLE = auto()
    LISTENING = auto()
    # Granular processing states
    PROCESSING = auto()          # Generic processing state (for backward compatibility)
    PROCESSING_STT = auto()      # Specifically transcribing speech to text
    PROCESSING_LLM = auto()      # Generating response with the language model 
    PROCESSING_TTS = auto()      # Converting text response to audio
    RESPONDING = auto()
    WAITING = auto()
    ERROR = auto()
```

### StateManager Class
```python
class StateManager:
    """
    Manages the state machine for conversation sessions.
    
    This class handles state transitions and ensures they follow the defined flow:
    IDLE → LISTENING → PROCESSING_STT → PROCESSING_LLM → PROCESSING_TTS → RESPONDING → WAITING → (repeat)
    
    It also handles broadcasting state changes to connected clients.
    """
```

#### Key Methods
- **`__init__()`**: Initializes state tracking structures and deadlock prevention
- **`create_session()`**: Creates a new session with initial IDLE state
- **`end_session()`**: Cleans up session resources
- **`transition_state()`**: Transitions a session to a new state with validation and deadlock prevention
- **`force_transition()`**: Forces a state transition without validation (emergency recovery)
- **`get_session()`**: Retrieves a session object by ID
- **`get_session_state()`**: Gets the current state for a session

### Session Class
```python
class Session:
    """
    Represents a conversation session with a client.
    
    Stores session-specific data including:
    - Connection information
    - Conversation history
    - State information
    - Session metadata
    """
```

#### Key Methods
- **`add_interaction()`**: Records a user-system interaction in history
- **`get_context()`**: Gets formatted conversation context for the LLM
- **`reset()`**: Resets the conversation history
- **`is_expired()`**: Checks if the session has expired due to inactivity
- **`to_dict()`**: Converts session to a dictionary for serialization
- **`save_to_file()`**: Saves the session data to a JSON file

## Usage Patterns

### State Transition Flow

The state transition flow has been improved with granular processing states for better progress tracking:

1. **IDLE**: Initial state, ready for conversation
   ```python
   # Create a new session
   state_manager.create_session(session_id, session)
   # Session is automatically set to IDLE
   ```

2. **LISTENING**: Receiving audio from the user
   ```python
   await state_manager.transition_state(session_id, "LISTENING", {
       "message": "Receiving audio"
   })
   ```

3. **PROCESSING_STT**: Transcribing speech to text
   ```python
   await state_manager.transition_state(session_id, "PROCESSING_STT", {
       "message": "Transcribing your speech to text",
       "progress": 0.0
   })
   
   # Later, when transcription completes:
   await state_manager.transition_state(session_id, "PROCESSING_STT", {
       "message": "Speech transcribed successfully",
       "progress": 1.0
   })
   ```

4. **PROCESSING_LLM**: Generating response with language model
   ```python
   await state_manager.transition_state(session_id, "PROCESSING_LLM", {
       "message": "Generating response to your question",
       "transcript": transcript,
       "stage": interaction_stage,
       "progress": 0.0
   })
   
   # Progress updates can be sent during LLM processing:
   await state_manager.transition_state(session_id, "PROCESSING_LLM", {
       "message": "Still thinking about your question...",
       "progress": 0.4
   })
   
   # When LLM processing completes:
   await state_manager.transition_state(session_id, "PROCESSING_LLM", {
       "message": "Response generated successfully",
       "progress": 1.0
   })
   ```

5. **PROCESSING_TTS**: Converting text to speech
   ```python
   await state_manager.transition_state(session_id, "PROCESSING_TTS", {
       "message": "Converting response to speech",
       "progress": 0.0
   })
   
   # When TTS completes:
   await state_manager.transition_state(session_id, "PROCESSING_TTS", {
       "message": "Audio generation complete",
       "progress": 1.0
   })
   ```

6. **RESPONDING**: Sending audio response to client
   ```python
   await state_manager.transition_state(session_id, "RESPONDING", {
       "message": "Playing response"
   })
   ```

7. **WAITING**: Waiting for next user input
   ```python
   await state_manager.transition_state(session_id, "WAITING", {
       "message": "Waiting for user input"
   })
   ```

8. **ERROR**: Error state with recovery mechanisms
   ```python
   await state_manager.transition_state(session_id, "ERROR", {
       "message": "Audio generation error: timeout",
       "error_type": "TTS_ERROR"
   })
   ```

### Error Recovery Patterns

The system has enhanced error recovery with specific handling for different error types:

```python
# Using the error handler for TTS errors
await self.error_handler.handle_error(
    ErrorHandler.TTS_ERROR,
    session_id,
    e,
    {"websocket": websocket, "text_response": response}
)

# Force transition back to WAITING state
await state_manager.force_transition(session_id, "WAITING", {
    "message": "Ready for next question after error recovery",
    "error_recovered": True,
    "error_type": "TTS_ERROR"
})
```

### Progressive Updates

The system now supports progressive updates during long-running operations:

```python
# Start a progressive update task during LLM processing
heartbeat_task = asyncio.create_task(
    self._send_progressive_updates(session_id, websocket)
)

# In the update task:
update_messages = [
    "I'm thinking about your question...",
    "Still processing your question...",
    "This is a complex question, giving it some thought...",
    "Almost ready with a response...",
    "Finalizing my thoughts on this..."
]
progress_values = [0.2, 0.4, 0.6, 0.8, 0.9]

for i in range(len(update_messages)):
    await asyncio.sleep(5.0)
    await state_manager.transition_state(session_id, "PROCESSING_LLM", {
        "message": update_messages[i % len(update_messages)],
        "progress": progress_values[i % len(progress_values)]
    })
```

## Implementation Details

### Granular Processing States

The state management system now includes finer-grained processing states for better user experience and error tracking:

```python
# Granular processing states
PROCESSING = auto()          # Generic processing state (for backward compatibility)
PROCESSING_STT = auto()      # Specifically transcribing speech to text
PROCESSING_LLM = auto()      # Generating response with the language model 
PROCESSING_TTS = auto()      # Converting text response to audio
```

Each state represents a specific processing stage, allowing:
- More precise progress tracking
- More targeted error recovery
- Better user feedback about processing status
- Improved timeout handling for specific processing stages

### State Transition Validation

The state manager validates transitions with support for the new granular states:

```python
def _is_valid_transition(self, current, next_state):
    """
    Validate that a state transition follows the allowed flow.
    
    Modified with more flexible transitions to prevent deadlocks:
    - Any state can transition to ERROR state
    - Any state can transition to WAITING (helps recover from errors)
    - PROCESSING states can go to each other or to the next logical state
    - PROCESSING* states are compatible with older PROCESSING state for backward compatibility
    """
    # Allow these universal transitions
    if next_state in ["IDLE", "ERROR", "WAITING"]:
        return True
        
    # Handle the normal flow with refined processing states
    valid_transitions = {
        "IDLE": ["LISTENING", "WAITING", "PROCESSING", "PROCESSING_STT", "RESPONDING"],
        "LISTENING": ["PROCESSING", "PROCESSING_STT", "WAITING", "IDLE", "RESPONDING"],
        
        # Generic PROCESSING can go to any state (for backward compatibility)
        "PROCESSING": ["RESPONDING", "PROCESSING", "PROCESSING_STT", "PROCESSING_LLM", 
                      "PROCESSING_TTS", "WAITING", "IDLE", "LISTENING", "ERROR"],
        
        # Granular processing states
        "PROCESSING_STT": ["PROCESSING_LLM", "PROCESSING", "RESPONDING", "WAITING", "ERROR"],
        "PROCESSING_LLM": ["PROCESSING_TTS", "PROCESSING", "RESPONDING", "WAITING", "ERROR"],
        "PROCESSING_TTS": ["RESPONDING", "PROCESSING", "WAITING", "ERROR"],
        
        "RESPONDING": ["WAITING", "IDLE", "ERROR"],
        "WAITING": ["LISTENING", "IDLE", "PROCESSING", "PROCESSING_STT", "RESPONDING"],
        "ERROR": ["IDLE", "WAITING", "PROCESSING", "PROCESSING_STT", "LISTENING", "RESPONDING"]
    }
    
    return next_state in valid_transitions.get(current, [])
```

### Enhanced Deadlock Prevention

The state manager implements a more sophisticated deadlock prevention mechanism:

```python
async def _handle_deadlock(self, session_id, new_state, timeout):
    """
    Improved deadlock detection and resolution.
    Ensures conversations can continue even after state transition problems.
    
    Args:
        session_id: The session ID experiencing potential deadlock
        new_state: The state we're attempting to transition to
        timeout: The lock acquisition timeout
    """
    try:
        # Wait for the timeout period plus a buffer
        await asyncio.sleep(timeout + 0.5)
        
        # If we get here, the transition may be deadlocked
        self.logger.warning(
            f"Possible deadlock detected for session {session_id} "
            f"transitioning to {new_state}. Forcing resolution."
        )
        
        # Force a new lock to be created
        if session_id in self._state_locks:
            self._state_locks[session_id] = asyncio.Lock()
            
        # Force transition if the session still exists
        if session_id in self.sessions:
            session = self.sessions[session_id]
            previous_state = session.state
            
            # Update the state directly without lock
            session.state = new_state
            session.last_updated = time.time()
            
            self.logger.warning(
                f"Forced state transition after deadlock: {session_id}: {previous_state} to {new_state}"
            )
            
            # Try to broadcast the state change
            try:
                await self._broadcast_state_change(
                    session_id, previous_state, new_state, {"forced": True}
                )
            except Exception as broadcast_error:
                self.logger.error(f"Error broadcasting forced state change: {broadcast_error}")
            
            # If we've been stuck in a processing state for too long, force to WAITING
            if previous_state.startswith("PROCESSING") and new_state.startswith("PROCESSING"):
                self.logger.warning(f"Detected potential hang in processing state for {session_id}")
                try:
                    session.state = "WAITING"
                    await self._broadcast_state_change(
                        session_id, previous_state, "WAITING", 
                        {"message": "Ready for next question", "forced_recovery": True}
                    )
                    self.logger.info(f"Forced recovery to WAITING state for {session_id}")
                except Exception as recovery_error:
                    self.logger.error(f"Error during forced recovery: {recovery_error}")
                
        except asyncio.CancelledError:
            # Task was cancelled normally
            pass
        except Exception as e:
            self.logger.error(f"Error in deadlock handler: {e}")
```

### Redundant Update Prevention

The state manager now prevents redundant updates to improve performance:

```python
# Detect redundant processing state updates
if previous_state == new_state:
    # For processing states, limit updates to be less frequent
    if new_state.startswith("PROCESSING"):
        # Track updates per processing type to avoid redundancy
        last_update_key = f"last_{new_state.lower()}_update"
        last_update_time = getattr(session, last_update_key, 0)
        current_time = time.time()
        
        # Only allow updates every 3 seconds unless they contain progress info
        if (current_time - last_update_time < 3.0 and 
            (not metadata or "progress" not in metadata)):
            self.logger.debug(
                f"Limiting {new_state} state updates for {session_id}, "
                f"last update was {current_time - last_update_time:.1f}s ago"
            )
            return True
        
        # Update the last processing update time
        setattr(session, last_update_key, current_time)
    # For other states, check if metadata has meaningful changes
    elif metadata and "progress" not in metadata:
        # For progress updates, we still want to show them
        # But avoid redundant state broadcasts that have no meaningful changes
        redundant = True
        
        # Check if there's any meaningful difference in metadata
        if metadata and session.metadata:
            for key, value in metadata.items():
                if key not in session.metadata or session.metadata[key] != value:
                    redundant = False
                    break
        
        if redundant:
            self.logger.debug(f"Skipping redundant state update for {session_id}: {new_state}")
            return True
```

### State Change Broadcasting

The state manager broadcasts state changes to the client with improved error handling:

```python
async def _broadcast_state_change(self, session_id, previous, current, metadata):
    """Broadcast state change to the client"""
    session = self.sessions.get(session_id)
    if not session or not hasattr(session, 'websocket') or session.websocket is None:
        return
        
    try:
        # Create state update message
        message = {
            "type": "state_update",
            "session_id": session_id,
            "previous": previous,
            "current": current,
            "timestamp": time.time(),
            "metadata": metadata or {}
        }
        
        # Send message to client
        await session.websocket.send(json.dumps(message))
        
    except Exception as e:
        self.logger.error(f"Error broadcasting state change: {e}")
```

## Configuration

The State Management system has the following configurable parameters:

1. **Lock Timeout**: The maximum time to wait for acquiring a state lock (default: 5.0 seconds)
2. **Session Expiration**: The time after which inactive sessions are considered expired (default: 1800 seconds / 30 minutes)
3. **Deadlock Resolution Timeout**: Time after which deadlocks are forcibly resolved (equals lock timeout + 0.5 seconds)
4. **Update Rate Limiting**: Minimum time between identical state updates (default: 3.0 seconds)

## Common Issues

### State Transition Issues

1. **Processing State Hangs**:
   - **Symptoms**: Session gets stuck in a PROCESSING_* state
   - **Causes**: Long-running operations, task failures, network issues
   - **Solution**: Granular state timeouts and forced transitions to WAITING state

2. **Redundant State Updates**:
   - **Symptoms**: Excessive state updates for the same state
   - **Causes**: Frequent progress updates, polling code
   - **Solution**: Rate limiting for identical state updates with progress tracking

3. **Race Conditions Between Processing Stages**:
   - **Symptoms**: State jumps unexpectedly between processing stages
   - **Causes**: Asynchronous completion of different processing tasks
   - **Solution**: Improved state transition validation with more flexible paths

### Session Management Issues

1. **Error Recovery Cascades**:
   - **Symptoms**: Multiple error recoveries happen in sequence
   - **Causes**: One error recovery triggering another issue
   - **Solution**: Cooldown periods between recovery attempts and error tracking

2. **Delayed TTS Response Handling**:
   - **Symptoms**: Audio response arrives after timeout
   - **Causes**: TTS service slowness but eventual completion
   - **Solution**: Specialized recovery for delayed TTS responses

3. **Client Capability Mismatches**:
   - **Symptoms**: Client unable to handle certain state updates
   - **Causes**: Version differences between client and server
   - **Solution**: Client capability detection and adaptive state updates

## Code Examples

### Using Granular Processing States

```python
# Start with STT processing
await state_manager.transition_state(session_id, "PROCESSING_STT", {
    "message": "Transcribing your speech to text",
    "progress": 0.0
})

# Update with progress
await state_manager.transition_state(session_id, "PROCESSING_STT", {
    "message": "Speech transcribed successfully",
    "progress": 1.0
})

# Move to LLM processing
await state_manager.transition_state(session_id, "PROCESSING_LLM", {
    "message": "Generating response to your question",
    "transcript": transcript,
    "progress": 0.0
})

# Progress updates during LLM
await state_manager.transition_state(session_id, "PROCESSING_LLM", {
    "message": "Still thinking about your question...",
    "progress": 0.4
})

# Complete LLM processing
await state_manager.transition_state(session_id, "PROCESSING_LLM", {
    "message": "Response generated successfully",
    "progress": 1.0
})

# Move to TTS processing
await state_manager.transition_state(session_id, "PROCESSING_TTS", {
    "message": "Converting response to speech",
    "progress": 0.0
})

# Complete TTS processing
await state_manager.transition_state(session_id, "PROCESSING_TTS", {
    "message": "Audio generation complete",
    "progress": 1.0
})
```

### Handling TTS Errors with Fallback

```python
try:
    # Generate speech with timeout (increased from 8 to 15 seconds)
    tts_future = asyncio.create_task(
        asyncio.to_thread(self.tts_service.synthesize, text)
    )
    
    # Add timeout to prevent hanging
    audio_response = await asyncio.wait_for(tts_future, timeout=15.0)
    
    # Update TTS progress to complete
    await self.state_manager.transition_state(session_id, "PROCESSING_TTS", {
        "message": "Audio generation complete",
        "progress": 1.0
    })
    
except asyncio.TimeoutError:
    self.logger.warning(f"TTS timeout for session {session_id}")
    
    # Transition to ERROR state
    await self.state_manager.transition_state(session_id, "ERROR", {
        "message": "Audio generation timed out",
        "error_type": "TTS_TIMEOUT"
    })
    
    # Send text-only response as fallback
    fallback_message = {
        "type": "text_response",
        "session_id": session_id,
        "timestamp": time.time(),
        "text": text,
        "message": "Audio conversion timed out, showing text instead"
    }
    
    try:
        await websocket.send(json.dumps(fallback_message))
        
        # Update state
        await self.state_manager.transition_state(session_id, "WAITING", {
            "message": "Waiting for user input after fallback"
        })
    except Exception as e:
        self.logger.error(f"Error sending fallback message: {e}")
```

### Handling Delayed LLM Responses

```python
async def _handle_delayed_llm_response(self, session_id, llm_future, websocket):
    """
    Handle LLM response that completes after the timeout
    
    Args:
        session_id: Session identifier
        llm_future: Future for the LLM response
        websocket: WebSocket connection
    """
    try:
        # Wait for the LLM response (which is still running)
        response = await llm_future
        
        # Check if the session is still active
        session = self.state_manager.get_session(session_id)
        if not session:
            self.logger.warning(f"Session {session_id} no longer exists for delayed response")
            return
            
        # Add to session context if method exists
        if hasattr(session, 'add_assistant_message'):
            session.add_assistant_message(response)
        
        # Update the transcript with the delayed response
        await websocket.send(json.dumps({
            "type": "transcript_update",
            "session_id": session_id,
            "timestamp": time.time(),
            "transcript": response,
            "source": "llm",
            "delayed": True
        }))
        
        # Generate TTS for the delayed response
        try:
            # Transition to PROCESSING_TTS state for delayed response
            await self.state_manager.transition_state(session_id, "PROCESSING_TTS", {
                "message": "Converting delayed response to speech",
                "delayed": True
            })
            
            audio_response = await asyncio.to_thread(
                self.tts_service.synthesize, response, session_id
            )
            
            # Send audio response if we're in a state where it makes sense
            current_state = session.state if hasattr(session, 'state') else None
            if current_state in ["WAITING", "IDLE"]:
                # Update state to RESPONDING
                await self.state_manager.transition_state(session_id, "RESPONDING", {
                    "message": "Playing delayed response",
                    "delayed": True
                })
                
                # Send direct audio
                await websocket.send(json.dumps({
                    "type": "audio_response",
                    "session_id": session_id,
                    "timestamp": time.time(),
                    "format": "wav",
                    "data": base64.b64encode(audio_response).decode('utf-8'),
                    "text": response,
                    "delayed": True
                }))
                
                # Return to WAITING when done
                await self.state_manager.transition_state(session_id, "WAITING", {
                    "message": "Waiting for user input"
                })
        except Exception as e:
            self.logger.error(f"Error processing delayed TTS: {e}")
    except Exception as e:
        self.logger.error(f"Error handling delayed LLM response: {e}")
```

### Safety Timeout Mechanism

```python
async def _safety_timeout(self, session_id: str, timeout_seconds: float):
    """Force transition to WAITING state if processing takes too long"""
    try:
        await asyncio.sleep(timeout_seconds)
        
        # Check current state
        current_state = self.state_manager.get_session_state(session_id)
        
        # If still in PROCESSING state after timeout, force transition to WAITING
        if current_state.startswith("PROCESSING"):
            self.logger.warning(f"Safety timeout triggered for session {session_id}")
            await self.state_manager.transition_state(session_id, "WAITING", {
                "message": "Ready for next question (timeout recovery)"
            })
            
    except asyncio.CancelledError:
        # Task was cancelled normally
        pass
    except Exception as e:
        self.logger.error(f"Error in safety timeout: {e}")
```