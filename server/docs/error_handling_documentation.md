# VR Interview System: Error Handling Documentation

## Title and Overview

The Error Handling component of the VR Interview System provides a sophisticated framework for detecting, managing, and recovering from errors throughout the system. It implements specialized recovery strategies for different error types, tracks error patterns, and ensures graceful degradation to maintain system availability. This component features cooldown periods, recovery attempt tracking, and pattern detection to provide a seamless user experience even when underlying components encounter issues.

## Architecture

The Error Handling system is designed around the central `ErrorHandler` class that acts as the orchestrator for all error recovery operations. It uses a modular architecture with specialized recovery handlers for different types of errors, allowing for targeted recovery strategies based on error classification, frequency, and severity.

Key architectural elements include:
1. **Error Type Categorization**: Different error types are defined and handled separately
2. **Recovery Handler Registry**: Recovery strategies are registered for each error type
3. **Error Tracking System**: Error patterns are tracked for analytics and recovery optimization
4. **Graceful Degradation Paths**: Fallback mechanisms ensure continued operation
5. **Recovery Cooldowns**: Prevents excessive recovery attempts
6. **Pattern Detection**: Identifies recurring errors for more aggressive recovery
7. **Delayed Response Handling**: Special handling for responses that arrive after timeout

### Component Diagram
```
┌──────────────────────────────────────────────────────┐
│                   Error Handler                       │
└───────────────┬───────────────────────┬──────────────┘
                │                       │
    ┌───────────▼─────────┐    ┌────────▼──────────┐
    │ Recovery Handlers   │    │   Error Tracking  │
    └───────────┬─────────┘    └────────┬──────────┘
                │                       │
                ▼                       ▼
┌─────────────────────────────────────────────────────┐
│              Error Recovery System                  │
│                                                     │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐    │
│ │LLM Recovery │ │STT Recovery │ │TTS Recovery │    │
│ └─────────────┘ └─────────────┘ └─────────────┘    │
│                                                     │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐    │
│ │WebSocket    │ │System       │ │State        │    │
│ │Recovery     │ │Recovery     │ │Recovery     │    │
│ └─────────────┘ └─────────────┘ └─────────────┘    │
└─────────────────────────────────────────────────────┘
```

### Error Recovery Flow Diagram

```
┌─────────────┐
│ Error       │
│ Detected    │
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌─────────────┐
│ Track Error │────►│ Error       │
│ Statistics  │     │ Database    │
└──────┬──────┘     └─────────────┘
       │
       ▼
┌─────────────┐  No  ┌─────────────┐
│ Specific    │─────►│ Generic     │
│ Handler?    │      │ Fallback    │
└──────┬──────┘      └──────┬──────┘
       │ Yes                │
       ▼                    │
┌─────────────┐             │
│ Check       │             │
│ Max Retries │             │
└──────┬──────┘             │
       │                    │
       ▼                    │
┌─────────────┐  Yes ┌──────▼──────┐
│ Max Retries │─────►│ Aggressive  │
│ Exceeded?   │      │ Recovery    │
└──────┬──────┘      └─────────────┘
       │ No
       ▼
┌─────────────┐  Yes ┌─────────────┐
│ In Cooldown │─────►│ Lite        │
│ Period?     │      │ Recovery    │
└──────┬──────┘      └─────────────┘
       │ No
       ▼
┌─────────────┐
│ Execute     │
│ Recovery    │
│ Strategy    │
└──────┬──────┘
       │
       ▼
┌─────────────┐  No  ┌─────────────┐
│ Recovery    │─────►│ Final       │
│ Successful? │      │ Fallback    │
└──────┬──────┘      └─────────────┘
       │ Yes
       ▼
┌─────────────┐
│ Return to   │
│ Normal Flow │
└─────────────┘
```

## Key Classes/Functions

### ErrorHandler Class

```python
class ErrorHandler:
    """
    Enhanced error handler with improved recovery mechanisms and diagnostics
    """
    
    # Error type constants
    LLM_ERROR = "llm_error"
    STT_ERROR = "stt_error"
    TTS_ERROR = "tts_error"
    WEBSOCKET_ERROR = "websocket_error"
    SYSTEM_ERROR = "system_error"
```

#### Core Methods

- **`__init__()`**: Initializes error tracking structures and default settings
- **`register_recovery_handler(error_type, handler)`**: Registers a handler for a specific error type
- **`handle_error(error_type, session_id, exception, context)`**: Main error handling method that routes to appropriate recovery handler
- **`_handle_exceeded_recovery_attempts(error_type, session_id, exception, context)`**: Handles the case when maximum recovery attempts are exceeded
- **`_handle_cooldown_recovery(error_type, session_id, exception, context)`**: Handles recovery during cooldown periods
- **`get_error_statistics(session_id)`**: Retrieves error statistics for analysis
- **`reset_session_errors(session_id)`**: Resets error tracking for a session
- **`cleanup_old_sessions(max_age_seconds)`**: Cleans up error tracking for old sessions
- **`_aggregate_error_types()`**: Aggregates error types across all sessions

### Specialized Recovery Handlers

The system includes specialized handlers for each error type, each with custom recovery strategies:

1. **LLM Error Handler**: 
   - Handles errors in LLM processing
   - Transitions to WAITING state
   - Provides fallback response text
   - Tracks error frequency for client refresh recommendations

2. **STT Error Handler**: 
   - Handles errors in speech-to-text processing
   - Transitions to WAITING state
   - Informs user about speech recognition issues

3. **TTS Error Handler**: 
   - Handles errors in text-to-speech processing
   - Distinguishes between timeout and other errors
   - Provides text fallback when audio fails
   - Implements delayed TTS response checking

4. **WebSocket Error Handler**: 
   - Handles WebSocket connection errors
   - Attempts to send final error message
   - Schedules session cleanup after delay

5. **System Error Handler**: 
   - Handles general system errors
   - Attempts to recover to known good state
   - Provides fallback to IDLE state if necessary

## Usage Patterns

### Error Handling Flow

1. **Error Detection**: Error is detected in a system component
   ```python
   try:
       # Component operation
       transcript = await asyncio.wait_for(transcript_future, timeout=15.0)
   except asyncio.TimeoutError:
       # Handle STT timeout specifically
       self.logger.warning(f"STT timeout for session {session_id}")
       if self.error_handler:
           await self.error_handler.handle_error(
               ErrorHandler.STT_ERROR,
               session_id,
               Exception("Speech transcription timed out"),
               {"websocket": websocket}
           )
   ```

2. **Error Tracking and Analysis**: The error is tracked for statistics and pattern detection
   ```python
   # Add to error tracking
   if session_id not in self.error_counts:
       self.error_counts[session_id] = 0
       self.error_types[session_id] = {}
       self.session_recovery_attempts[session_id] = {}
       self.last_recovery_times[session_id] = {}
   
   self.error_counts[session_id] += 1
   
   # Track error type
   error_name = error_type if isinstance(error_type, str) else error_type.__name__
   if error_name not in self.error_types[session_id]:
       self.error_types[session_id][error_name] = 0
   self.error_types[session_id][error_name] += 1
   
   # Track recovery attempts for this error type
   if error_name not in self.session_recovery_attempts[session_id]:
       self.session_recovery_attempts[session_id][error_name] = 0
   self.session_recovery_attempts[session_id][error_name] += 1
   
   # Track recent errors for pattern detection (keep last 10)
   self.recent_errors.append({
       "time": current_time,
       "session_id": session_id,
       "error_type": error_name,
       "exception": str(exception)
   })
   ```

3. **Recovery Strategy Selection**: Choose the appropriate recovery strategy based on error type and history
   ```python
   # Check if we've exceeded the maximum recovery attempts for this error type
   max_attempts = self.max_recovery_attempts.get(error_name, 3)
   if self.session_recovery_attempts[session_id][error_name] > max_attempts:
       self.logger.warning(f"Exceeded max recovery attempts ({max_attempts}) for {error_name} in session {session_id}")
       # Use more aggressive fallback strategy when max attempts exceeded
       return await self._handle_exceeded_recovery_attempts(error_name, session_id, exception, context)
   
   # Check for cooldown period
   cooldown_period = self.recovery_cooldowns.get(error_name, 5)
   last_recovery_time = self.last_recovery_times.get(session_id, {}).get(error_name, 0)
   time_since_last = current_time - last_recovery_time
   
   if time_since_last < cooldown_period and last_recovery_time > 0:
       self.logger.info(f"In cooldown period for {error_name} ({time_since_last:.1f}s < {cooldown_period}s)")
       # Use lite recovery during cooldown
       return await self._handle_cooldown_recovery(error_name, session_id, exception, context)
   ```

4. **Handler Execution**: Execute the specialized handler for the error type
   ```python
   # Get special handler if available
   if error_type in self.recovery_handlers:
       handler = self.recovery_handlers[error_type]
       
       # Provide enhanced context with error tracking
       enhanced_context = context or {}
       enhanced_context.update({
           "error_count": self.error_counts[session_id],
           "error_types": self.error_types[session_id],
           "recurring": recurring,
           "recent_errors": self.recent_errors,
           "recovery_attempts": self.session_recovery_attempts[session_id]
       })
       
       # Call the handler
       try:
           success, metadata = await handler(session_id, exception, enhanced_context)
           return success, metadata
       except Exception as handler_error:
           self.logger.error(f"Error in error handler for {error_type}: {handler_error}")
           # Continue to fallback
   ```

5. **Fallback Mechanisms**: Provide fallback when specialized handling fails
   ```python
   # If handler not available or failed, use generic fallback
   websocket = context.get("websocket") if context else None
   
   # Send user-friendly message
   if websocket:
       try:
           message = {
               "type": "system_message",
               "session_id": session_id,
               "timestamp": time.time(),
               "message": "The system encountered an issue. Let's continue from here."
           }
           await websocket.send(json.dumps(message))
       except Exception as ws_error:
           self.logger.error(f"Error sending error message: {ws_error}")
   ```

### Specialized Recovery Patterns

#### Delayed TTS Response Handling

```python
async def _check_delayed_tts_response(self, session_id, text_response, context):
    """Check if a delayed TTS response becomes available"""
    try:
        self.logger.info(f"Starting delayed TTS response check for session {session_id}")
        
        # Wait a bit to allow TTS to finish
        await asyncio.sleep(10)
        
        # Check if session still exists
        session = self.state_manager.get_session(session_id)
        if not session:
            self.logger.warning(f"Session {session_id} no longer exists for delayed TTS")
            return
            
        # Check if websocket is still connected
        websocket = self.websocket_server.active_connections.get(session_id)
        if not websocket:
            self.logger.warning(f"Websocket for session {session_id} no longer connected")
            return
            
        # Try to find the audio file that might have been generated
        try:
            # Construct a filename pattern that matches what alltalk_tts_direct would use
            timeframe = int(time.time()) - 120  # Look for files from the last 2 minutes
            file_pattern = f"vr_interview_{timeframe}"
            
            # Ask the TTS service to look for recent files
            if hasattr(self.tts_service, '_try_load_output_file'):
                audio_data = self.tts_service._try_load_output_file(file_pattern)
                
                if audio_data and len(audio_data) > 1000:
                    self.logger.info(f"Found delayed TTS response for session {session_id}: {len(audio_data)} bytes")
                    
                    # Send the audio to the client
                    audio_message = {
                        "type": "audio_response",
                        "timestamp": time.time(),
                        "format": "wav",
                        "data": base64.b64encode(audio_data).decode('utf-8'),
                        "text": text_response  # Include text as fallback
                    }
                    await websocket.send(json.dumps(audio_message))
                    
                    self.logger.info(f"Sent delayed audio response to {session_id}")
                    return
        except Exception as e:
            self.logger.error(f"Error checking for delayed TTS files: {e}")
            
        # No audio found, or exception occurred - send text fallback
        self.logger.warning(f"No delayed TTS response found for session {session_id}, using text fallback")
        try:
            fallback_message = {
                "type": "text_response",
                "text": text_response,
                "message": "Audio generation took too long. Displaying text instead."
            }
            await websocket.send(json.dumps(fallback_message))
        except Exception as e:
            self.logger.error(f"Error sending delayed text fallback: {e}")
            
    except Exception as e:
        self.logger.error(f"Error in delayed TTS response check: {e}")
```

#### Aggressive Recovery for Recurrent Errors

```python
async def _handle_exceeded_recovery_attempts(self, error_type: str, session_id: str, 
                                          exception: Exception, context: Optional[Dict[str, Any]] = None):
    """
    Handle the case where we've exceeded maximum recovery attempts for an error type
    
    This uses more aggressive recovery strategies:
    - Resets session state completely
    - Suggests client restart if applicable
    - Uses simpler fallback mechanisms
    """
    self.logger.info(f"Using aggressive recovery for {error_type} in {session_id} - exceeded max attempts")
    
    websocket = context.get("websocket") if context else None
    
    # Send reset notice to client
    if websocket:
        try:
            reset_message = {
                "type": "system_message",
                "session_id": session_id,
                "timestamp": time.time(),
                "message": "The system needs to reset. Please try asking a new question."
            }
            await websocket.send(json.dumps(reset_message))
        except Exception as ws_error:
            self.logger.error(f"Error sending reset message: {ws_error}")
    
    # Try to reset session state completely
    try:
        # Import here to avoid circular imports
        from app.state.manager import StateManager
        state_manager = None
        
        # Try to get the StateManager instance
        if hasattr(StateManager, 'get_instance'):
            state_manager = StateManager.get_instance()
        else:
            state_manager = context.get('state_manager') if context else None
        
        if state_manager:
            # Reset session completely
            if hasattr(state_manager, 'reset_session'):
                await state_manager.reset_session(session_id)
                self.logger.info(f"Reset session {session_id} completely")
            
            # Force transition to IDLE (fresh start)
            await state_manager.transition_state(session_id, "IDLE", {
                "message": "Session reset due to recurring errors",
                "error_recovered": True,
                "error_type": error_type,
                "recovery_strategy": "aggressive"
            })
    except Exception as reset_error:
        self.logger.error(f"Error during aggressive session reset: {reset_error}")
    
    # Reset the error counters for this session to give a fresh start
    if session_id in self.session_recovery_attempts:
        for err_type in self.session_recovery_attempts[session_id]:
            self.session_recovery_attempts[session_id][err_type] = 0
            
    # Return success=False to indicate we used fallback mechanisms
    return False, {"strategy": "aggressive_reset"}
```

#### Lite Recovery During Cooldown

```python
async def _handle_cooldown_recovery(self, error_type: str, session_id: str,
                                   exception: Exception, context: Optional[Dict[str, Any]] = None):
    """
    Handle the case where we're in a cooldown period for an error type
    
    This uses lighter recovery strategies to avoid spamming the client with messages
    """
    self.logger.info(f"Using lite recovery for {error_type} in {session_id} - in cooldown period")
    
    websocket = context.get("websocket") if context else None
    
    # Only try to transition state, but don't send user-facing messages
    try:
        # Import here to avoid circular imports
        from app.state.manager import StateManager
        state_manager = None
        
        # Try to get the StateManager instance
        if hasattr(StateManager, 'get_instance'):
            state_manager = StateManager.get_instance()
        else:
            state_manager = context.get('state_manager') if context else None
        
        if state_manager:
            # Check current state
            current_state = state_manager.get_session_state(session_id)
            
            # Only transition if in a "stuck" state
            if current_state in ["PROCESSING", "PROCESSING_LLM", "PROCESSING_STT", 
                                "PROCESSING_TTS", "RESPONDING", "ERROR"]:
                await state_manager.transition_state(session_id, "WAITING", {
                    "message": "Ready for next question",
                    "error_recovered": True,
                    "error_type": error_type,
                    "recovery_strategy": "lite"
                })
                self.logger.info(f"Transitioned {session_id} from {current_state} to WAITING (lite recovery)")
    except Exception as state_error:
        self.logger.error(f"Error during lite recovery: {state_error}")
    
    # Return success=False to indicate we used fallback mechanisms
    return False, {"strategy": "lite_recovery"}
```

## Implementation Details

### Error Type Constants

The error handler defines specific error type constants for consistent categorization:

```python
# Error type constants
LLM_ERROR = "llm_error"       # Language model processing errors
STT_ERROR = "stt_error"       # Speech-to-text errors
TTS_ERROR = "tts_error"       # Text-to-speech errors
WEBSOCKET_ERROR = "websocket_error"  # WebSocket connection errors
SYSTEM_ERROR = "system_error"  # General system errors
```

### Error Tracking for Pattern Detection

The system tracks error patterns to optimize recovery and detect recurring issues:

```python
# Track recent errors for pattern detection (keep last 10)
self.recent_errors.append({
    "time": current_time,
    "session_id": session_id,
    "error_type": error_name,
    "exception": str(exception)
})
if len(self.recent_errors) > 10:
    self.recent_errors.pop(0)
    
# Log error with traceback
self.logger.error(f"Error in session {session_id}: {exception}")
self.logger.error(traceback.format_exc())

# Log error counts
self.logger.info(f"Session {session_id} has {self.error_counts[session_id]} errors")
self.logger.info(f"Error types: {self.error_types[session_id]}")
self.logger.info(f"Recovery attempts: {self.session_recovery_attempts[session_id]}")
```

### Dynamic Handler Registration

Handlers are registered dynamically to allow extension and customization:

```python
def register_recovery_handler(self, error_type: str, handler: Callable):
    """Register a handler for a specific error type"""
    self.recovery_handlers[error_type] = handler
    self.logger.info(f"Registered recovery handler for {error_type}")
```

### Timeout Differentiation

The system distinguishes between different types of timeouts for appropriate recovery:

```python
# Check if this is a timeout error
is_timeout = isinstance(exception, asyncio.TimeoutError) or "timeout" in str(exception).lower()

# For timeout errors, inform the client that we're still trying
if is_timeout:
    trying_message = {
        "type": "system_message",
        "message": "Still generating audio, please wait a moment..."
    }
    try:
        await websocket.send(json.dumps(trying_message))
    except:
        # Connection might be closed, ignore
        pass
    
    # Schedule a task to keep trying to get the audio
    asyncio.create_task(self._check_delayed_tts_response(
        session_id, 
        text_response, 
        context
    ))
```

### Memory Management for Error Tracking

To prevent memory leaks, the system cleans up old error tracking data:

```python
def cleanup_old_sessions(self, max_age_seconds: int = 3600):
    """
    Clean up error tracking for old sessions to prevent memory leaks
    
    Args:
        max_age_seconds: Maximum age in seconds for sessions to keep
    """
    current_time = time.time()
    sessions_to_remove = []
    
    # Find old sessions based on last recovery time
    for session_id, error_times in self.last_recovery_times.items():
        if not error_times:  # Empty dict
            sessions_to_remove.append(session_id)
            continue
            
        # Get the most recent error time
        most_recent = max(error_times.values())
        age = current_time - most_recent
        
        if age > max_age_seconds:
            sessions_to_remove.append(session_id)
    
    # Remove old sessions
    for session_id in sessions_to_remove:
        if session_id in self.error_counts:
            del self.error_counts[session_id]
        if session_id in self.error_types:
            del self.error_types[session_id]
        if session_id in self.session_recovery_attempts:
            del self.session_recovery_attempts[session_id]
        if session_id in self.last_recovery_times:
            del self.last_recovery_times[session_id]
            
    if sessions_to_remove:
        self.logger.info(f"Cleaned up error tracking for {len(sessions_to_remove)} old sessions")
```

## Configuration

The error handling system is configurable through several internal settings:

### Attempt Limits and Cooldowns

```python
# Maximum recovery attempts per error type
self.max_recovery_attempts = {
    self.LLM_ERROR: 3,
    self.STT_ERROR: 2,
    self.TTS_ERROR: 3,
    self.WEBSOCKET_ERROR: 3,
    self.SYSTEM_ERROR: 2
}

# Cooldown periods between recovery attempts (seconds)
self.recovery_cooldowns = {
    self.LLM_ERROR: 5,
    self.STT_ERROR: 2,
    self.TTS_ERROR: 3,
    self.WEBSOCKET_ERROR: 10,
    self.SYSTEM_ERROR: 5
}
```

### Error Tracking Settings

```python
# Recent error tracking capacity
self.recent_errors = []  # Track last 10 errors

# Session cleanup interval
max_age_seconds = 3600  # Clean up sessions older than 1 hour
```

### Configurable Behaviors

1. **Aggressive Recovery Threshold**: Number of attempts before using aggressive recovery (default: max_recovery_attempts per error type)
2. **Cooldown Periods**: Time between recovery attempts for each error type
3. **Session Reset**: Whether to reset session upon repeated errors (default: true)
4. **Client Notification**: Whether to notify client of error recovery (default: true)
5. **Error History Size**: Number of recent errors to track (default: 10)

## Common Issues and Solutions

### Error Recovery Issues

1. **Recovery Loop Detection**:
   - **Symptoms**: Repeated errors of the same type in quick succession
   - **Causes**: Failed recovery triggering new errors
   - **Solution**: Cooldown periods and lite recovery

   ```python
   # Check for cooldown period
   cooldown_period = self.recovery_cooldowns.get(error_name, 5)
   last_recovery_time = self.last_recovery_times.get(session_id, {}).get(error_name, 0)
   time_since_last = current_time - last_recovery_time
   
   if time_since_last < cooldown_period and last_recovery_time > 0:
       # Use lite recovery during cooldown
       return await self._handle_cooldown_recovery(error_name, session_id, exception, context)
   ```

2. **Unhandled Timeout Recovery**:
   - **Symptoms**: Client hangs during processing
   - **Causes**: Timeouts not properly handled
   - **Solution**: Specialized timeout handlers with delayed response checking

   ```python
   # Schedule a task to keep trying to get the audio
   asyncio.create_task(self._check_delayed_tts_response(
       session_id, 
       text_response, 
       context
   ))
   ```

3. **Error Handler Exceptions**:
   - **Symptoms**: Error handler itself throws exceptions
   - **Causes**: Bugs in recovery logic
   - **Solution**: Double-layered try-except in error handlers

   ```python
   try:
       # Call the handler
       try:
           success, metadata = await handler(session_id, exception, enhanced_context)
           return success, metadata
       except Exception as handler_error:
           self.logger.error(f"Error in error handler for {error_type}: {handler_error}")
           # Continue to fallback
   except Exception as e:
       # Meta-error: error in error handler
       self.logger.critical(f"Critical error in error handler: {e}")
       self.logger.critical(traceback.format_exc())
       return False, {}
   ```

### State Management Issues

1. **Inconsistent State After Recovery**:
   - **Symptoms**: User unable to continue after error
   - **Causes**: Failed state transitions during recovery
   - **Solution**: Multiple fallback transitions with different approaches

   ```python
   # Always try to transition back to WAITING to prevent client hang
   try:
       await self.state_manager.transition_state(session_id, "WAITING", {
           "message": "Ready for next question after error"
       })
   except Exception as transition_error:
       self.logger.error(f"Failed to transition to WAITING after error: {transition_error}")
       # As a last resort, try IDLE
       try:
           await self.state_manager.transition_state(session_id, "IDLE", {
               "message": "System reset after error"
           })
       except:
           pass
   ```

2. **Session Leakage**:
   - **Symptoms**: Memory usage increases over time
   - **Causes**: Error tracking data not cleaned up
   - **Solution**: Periodic cleanup of old sessions

   ```python
   # Clean up old sessions
   for session_id in sessions_to_remove:
       if session_id in self.error_counts:
           del self.error_counts[session_id]
       if session_id in self.error_types:
           del self.error_types[session_id]
       if session_id in self.session_recovery_attempts:
           del self.session_recovery_attempts[session_id]
       if session_id in self.last_recovery_times:
           del self.last_recovery_times[session_id]
   ```

### WebSocket Communication Issues

1. **Client Disconnects During Recovery**:
   - **Symptoms**: WebSocket errors during recovery
   - **Causes**: Client connection lost during error handling
   - **Solution**: Try-except around all WebSocket operations

   ```python
   # Try to send a final error message if websocket is still valid
   if "websocket" in context:
       try:
           websocket = context["websocket"]
           message = {
               "type": "error",
               "code": 1001,
               "message": "Connection interrupted. Please reconnect.",
               "session_id": session_id,
               "timestamp": time.time()
           }
           await websocket.send(json.dumps(message))
       except:
           # Ignore errors in sending the message
           pass
   ```

2. **Websocket Timeout During Recovery**:
   - **Symptoms**: Client disconnects during recovery
   - **Causes**: Recovery takes too long
   - **Solution**: Immediate feedback with delayed processing

   ```python
   # Tell the user about the delay
   await websocket.send(json.dumps({
       "type": "system_message",
       "message": "I'm still thinking about your question. This might take a moment..."
   }))
   
   # Create a background task to handle it when it completes
   asyncio.create_task(
       self._handle_delayed_llm_response(session_id, llm_future, websocket)
   )
   ```

## Code Examples

### LLM Error Recovery with TTS Fallback

```python
async def _handle_llm_error(self, session_id, exception, context):
    """Handle errors in LLM processing with improved recovery"""
    try:
        # Log the detailed error
        self.logger.error(f"LLM error recovery for {session_id}: {exception}")
        
        # Always transition to WAITING state to prevent client hang
        await self.state_manager.transition_state(session_id, "WAITING", {
            "message": "Ready for next question",
            "error": "Interview system needed to reset"
        })
        
        # Send fallback response directly if possible
        if "websocket" in context:
            websocket = context["websocket"]
            fallback_message = {
                "type": "text_response",  # Use text_response type for better client handling
                "text": "I had a bit of trouble processing that. Let's continue the interview. Could you please ask me another question?",
                "message": "LLM processing error, showing text response instead"
            }
            await websocket.send(json.dumps(fallback_message))
            
        # Mark that this session had an error to avoid repeated failures
        session = self.state_manager.get_session(session_id)
        if session:
            if not hasattr(session, 'error_count'):
                session.error_count = 0
            session.error_count += 1
            
            # If multiple errors occur, suggest refreshing the client
            if session.error_count >= 3:
                if "websocket" in context:
                    websocket = context["websocket"]
                    reset_message = {
                        "type": "system_message",
                        "message": "Multiple errors detected. Consider refreshing your client application."
                    }
                    await websocket.send(json.dumps(reset_message))
            
        return True  # Indicate successful recovery
    except Exception as e:
        self.logger.error(f"Error during LLM error recovery: {e}")
        return False
```

### TTS Error Recovery with Delayed Response Checking

```python
async def _handle_tts_error(self, session_id, exception, context):
    """Handle errors in text-to-speech processing with improved recovery"""
    try:
        # Check if this is a timeout error
        is_timeout = isinstance(exception, asyncio.TimeoutError) or "timeout" in str(exception).lower()
        
        # If we have the text response, send it directly as a fallback
        text_response = context.get("text_response")
        if text_response and "websocket" in context:
            websocket = context["websocket"]
            
            # For timeout errors, inform the client that we're still trying
            if is_timeout:
                trying_message = {
                    "type": "system_message",
                    "message": "Still generating audio, please wait a moment..."
                }
                try:
                    await websocket.send(json.dumps(trying_message))
                except:
                    # Connection might be closed, ignore
                    pass
                
                # Schedule a task to keep trying to get the audio
                asyncio.create_task(self._check_delayed_tts_response(
                    session_id, 
                    text_response, 
                    context
                ))
            else:
                # For non-timeout errors, just show text
                fallback_message = {
                    "type": "text_response",
                    "text": text_response,
                    "message": "Audio couldn't be generated. Displaying text instead."
                }
                await websocket.send(json.dumps(fallback_message))
            
        # Transition to WAITING state
        await self.state_manager.transition_state(session_id, "WAITING", {
            "message": "Ready for next question" if not is_timeout else "Still generating audio..."
        })
        
        return True  # Indicate successful recovery
    except Exception as e:
        self.logger.error(f"Error during TTS error recovery: {e}")
        # Final fallback - always try to get back to WAITING state
        try:
            await self.state_manager.transition_state(session_id, "WAITING", {})
        except:
            pass
        return False
```

### System Error Recovery with Multiple Fallbacks

```python
async def _handle_system_error(self, session_id, exception, context):
    """Handle general system errors with improved recovery"""
    try:
        self.logger.error(f"System error in session {session_id}: {exception}")
        
        # Try to send error notification
        if "websocket" in context:
            websocket = context["websocket"]
            try:
                message = {
                    "type": "system_message",
                    "message": "The system encountered an error. Please try again."
                }
                await websocket.send(json.dumps(message))
            except:
                # Ignore errors in sending the message
                pass
                
        # Always try to transition back to WAITING state after system errors
        # This is crucial to prevent client hangs
        try:
            await self.state_manager.transition_state(session_id, "WAITING", {
                "message": "Ready for next question after system error"
            })
        except Exception as state_error:
            self.logger.error(f"Failed to transition to WAITING after system error: {state_error}")
            # As a last resort, try IDLE
            try:
                await self.state_manager.transition_state(session_id, "IDLE", {
                    "message": "System reset after error"
                })
            except:
                pass
        
        return True  # Indicate successful recovery
    except Exception as e:
        self.logger.error(f"Error during system error recovery: {e}")
        return False
```

### Delayed LLM Response Handling

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
            }
        except Exception as e:
            self.logger.error(f"Error processing delayed TTS: {e}")
    except Exception as e:
        self.logger.error(f"Error handling delayed LLM response: {e}")
```