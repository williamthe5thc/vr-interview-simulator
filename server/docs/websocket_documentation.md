# VR Interview System: WebSocket Documentation

## Title and Overview

The WebSocket component of the VR Interview System provides the real-time communication channel between the VR client application and the server. It handles bi-directional, full-duplex communication, enabling the exchange of audio data, text, and control messages. The WebSocket server is optimized for handling both long-running operations (like LLM generation) and high-frequency updates without blocking or disconnecting the client. This implementation features improved task tracking, granular processing states, and enhanced error recovery mechanisms.

## Architecture

The WebSocket implementation follows an enhanced asynchronous architecture designed to prevent blocking during long-running operations. It consists of several key components:

1. **WebSocketServer Class**: The main server class managing client connections, message routing, and lifecycle
2. **EnhancedStreamProcessor**: Specialized handler for streaming audio processing pipeline
3. **Protocol Module**: Handles message encoding, decoding, and validation
4. **Session Management**: Tracks active connections and associated session data
5. **Task Management System**: Ensures proper tracking and cleanup of asyncio tasks
6. **Heartbeat Service**: Keeps connections alive during long-running operations

### Where This Component Fits

The WebSocket server acts as the central communication hub of the VR Interview System:

```
                               ┌─────────────────┐
                               │   Client (VR)   │
                               └────────┬────────┘
                                        │
                                        ▼
┌───────────────────────────────────────────────────────────────────────┐
│                        WebSocket Connection                           │
└───────────────────────────────┬───────────────────────────────────────┘
                                │
                                ▼
┌───────────────────────────────────────────────────────────────────────┐
│                     WebSocket Server (Enhanced)                       │
└─────┬────────────────────┬────────────────────┬──────────────────┬────┘
      │                    │                    │                  │
      ▼                    ▼                    ▼                  ▼
┌───────────┐     ┌────────────────┐    ┌─────────────┐    ┌────────────┐
│State      │     │Enhanced Stream │    │STT/TTS      │    │LLM         │
│Manager    │◄───►│Processor       │◄───►Services     │◄───►Client      │
└─────┬─────┘     └────────────────┘    └─────────────┘    └────────────┘
      │                                                           ▲
      │                                                           │
      ▼                                                           │
┌───────────┐                                              ┌────────────┐
│Error      │◄─────────────────────────────────────────────┤Heartbeat   │
│Handler    │                                              │Service     │
└───────────┘                                              └────────────┘
```

## Key Classes/Functions

### WebSocketServer

```python
class WebSocketServer:
    """
    Enhanced WebSocket server with improved error handling and task management.
    
    This server ensures that long-running operations like LLM processing don't
    block WebSocket communication and state updates.
    """
```

#### Core Methods

- **`__init__`**: Initializes the WebSocket server with references to all system components
- **`start()`**: Starts the WebSocket server and begins accepting connections
- **`shutdown()`**: Gracefully shuts down the server and cleans up resources
- **`handle_connection()`**: Handles new WebSocket connections and session creation
- **`process_message()`**: Processes incoming WebSocket messages
- **`process_audio()`**: Handles audio data messages from clients
- **`process_audio_pipeline()`**: Orchestrates the full audio processing workflow with granular states
- **`_track_task()`**: Adds a task to tracking system for proper lifecycle management
- **`_remove_task()`**: Removes a completed task from the tracking system
- **`_cleanup_session()`**: Performs comprehensive session cleanup
- **`send_audio_response()`**: Sends audio responses back to clients
- **`handle_client_capabilities()`**: Processes client capability information
- **`_send_heartbeat_during_llm()`**: Provides progress updates during long processes

### EnhancedStreamProcessor

This improved class manages the audio processing pipeline with better parallel processing:

```python
class EnhancedStreamProcessor:
    """
    Enhanced stream processor with optimized processing pipeline.
    
    Features:
    - Multi-stage parallel processing
    - Optimized direct audio generation
    - Intelligent caching for frequently used responses
    - Advanced error handling and recovery
    """
```

#### Key Methods

- **`process_streaming_audio_pipeline()`**: Main processing pipeline with granular states
- **`_generate_standard_tts()`**: Generates speech using direct TTS
- **`_prewarm_tts()`**: Preloads TTS engine to reduce response latency
- **`_handle_delayed_llm_response()`**: Handles responses that arrive after timeout
- **`_send_progressive_updates()`**: Sends incremental updates during LLM processing

### Message Types

The WebSocket server handles an expanded set of message types:

1. **`audio_data`**: Contains raw audio data from the client
2. **`ping`/`pong`**: Connection health checks
3. **`control`**: Client control messages (reset, stop)
4. **`state_update`**: Server state change notifications with granular states
5. **`playback_complete`**: Client notification of audio playback completion
6. **`client_capabilities`**: Client feature and format support information
7. **`system_message`**: System notifications and status updates
8. **`error`**: Error messages and codes
9. **`text_response`**: Text responses (when audio unavailable)
10. **`audio_response`**: Audio response data
11. **`audio_file_url`**: URLs for direct audio file access
12. **`heartbeat`**: Connection keep-alive with progress information
13. **`progress_update`**: Detailed progress information during processing
14. **`transcript_update`**: Updates for delayed transcripts
15. **`streaming_status`**: Status updates for streaming operations
16. **`capabilities_ack`**: Acknowledgment of client capabilities

## Usage Patterns

### Connection Lifecycle

1. **Connection Establishment**:
   ```python
   # Server side
   async def handle_connection(self, websocket, path):
       session_id = str(uuid.uuid4())
       session = Session(session_id, websocket)
       self.active_connections[session_id] = websocket
       self.session_tasks[session_id] = set()  # Track tasks per session
       
       # Send initial session ID
       await websocket.send(json.dumps({
           "type": "session_init",
           "session_id": session_id,
           "timestamp": time.time()
       }))
   ```

2. **Client Capability Exchange**:
   ```python
   # Client sends capabilities
   {
     "type": "client_capabilities",
     "capabilities": {
       "audio_formats": ["wav", "mp3"],
       "browser": {"name": "unity", "version": "2022.3"},
       "features": ["direct_audio", "progressive_updates"]
     }
   }
   
   # Server acknowledges and provides supported features
   {
     "type": "state_update",
     "current": "IDLE",
     "metadata": {
       "supported_features": {
         "direct_audio": true,
         "streaming": false,
         "progressive_updates": true
       }
     }
   }
   ```

3. **Audio Processing with Granular State Updates**:
   ```python
   # Client sends audio
   {
     "type": "audio_data",
     "data": "base64-encoded-audio-data",
     "format": "wav"
   }
   
   # Server sends state updates for each phase
   {
     "type": "state_update",
     "previous": "LISTENING",
     "current": "PROCESSING_STT",
     "metadata": {
       "message": "Transcribing your speech to text",
       "progress": 0.0
     }
   }
   
   # Progressive updates during LLM processing
   {
     "type": "state_update",
     "current": "PROCESSING_LLM",
     "metadata": {
       "message": "Still thinking about your question...",
       "progress": 0.6
     }
   }
   
   # Server responds with audio
   {
     "type": "audio_response",
     "data": "base64-encoded-audio-data",
     "format": "wav",
     "text": "Fallback text version"
   }
   ```

4. **Playback Completion**:
   ```python
   # Client notifies when audio playback completes
   {
     "type": "playback_complete",
     "session_id": "unique-session-id"
   }
   
   # Server acknowledges
   {
     "type": "playback_ack",
     "session_id": "unique-session-id",
     "message": "Playback completion acknowledged"
   }
   ```

5. **Connection Termination with Enhanced Cleanup**:
   ```python
   # Server performs comprehensive cleanup
   async def _cleanup_session(self, session_id):
       # 1. Cancel all session-specific tasks
       # 2. Stop heartbeat service for this session
       # 3. Remove from active connections
       # 4. Remove client capabilities
       # 5. End session in state manager
   ```

### Task Tracking System

The WebSocket server now features a sophisticated task tracking system for proper lifecycle management:

```python
def _track_task(self, task: asyncio.Task, session_id: Optional[str] = None):
    """Track a task for proper cleanup"""
    self.tasks.add(task)
    
    # Add to session-specific tasks if session_id provided
    if session_id and session_id in self.session_tasks:
        self.session_tasks[session_id].add(task)
        
    # Set up callback to remove task when done
    task.add_done_callback(lambda t: self._remove_task(t, session_id))

def _remove_task(self, task: asyncio.Task, session_id: Optional[str] = None):
    """Remove a completed task from tracking sets"""
    if task in self.tasks:
        self.tasks.remove(task)
        
    if session_id and session_id in self.session_tasks:
        if task in self.session_tasks[session_id]:
            self.session_tasks[session_id].remove(task)
```

### Error Handling with Specific Recovery Strategies

The WebSocket server now works with the error handler for specialized recovery based on error type:

```python
# LLM error handling
if self.error_handler:
    await self.error_handler.handle_error(
        ErrorHandler.LLM_ERROR,
        session_id,
        llm_error,
        {
            "websocket": websocket,
            "transcript": transcript
        }
    )

# TTS error handling with text fallback
if self.error_handler:
    await self.error_handler.handle_error(
        ErrorHandler.TTS_ERROR,
        session_id,
        tts_error,
        {
            "websocket": websocket,
            "text_response": response
        }
    )
```

## Implementation Details

### Enhanced Session Cleanup

The session cleanup process is now more thorough to prevent resource leaks:

```python
async def _cleanup_session(self, session_id: str):
    """Clean up a session's resources"""
    self.logger.info(f"Starting cleanup for session: {session_id}")
    
    # Cancel session-specific tasks
    if session_id in self.session_tasks:
        task_count = len(self.session_tasks[session_id])
        self.logger.info(f"Cancelling {task_count} tasks for session {session_id}")
        for task in list(self.session_tasks[session_id]):
            if not task.done():
                task.cancel()
                
        # Wait for tasks to cancel
        if self.session_tasks[session_id]:
            await asyncio.gather(
                *self.session_tasks[session_id], 
                return_exceptions=True
            )
        
        del self.session_tasks[session_id]
    
    # Stop heartbeat if active
    if self.heartbeat_service:
        self.logger.info(f"Stopping heartbeat for session {session_id}")
        await self.heartbeat_service.stop_heartbeat(session_id)
        
    # Remove from active connections
    if session_id in self.active_connections:
        self.logger.info(f"Removing session {session_id} from active_connections")
        del self.active_connections[session_id]
        
    # Remove client capabilities
    if session_id in self.client_capabilities:
        self.logger.info(f"Removing session {session_id} from client_capabilities")
        del self.client_capabilities[session_id]
        
    # End session in state manager
    if asyncio.iscoroutinefunction(getattr(self.state_manager, 'end_session', None)):
        self.logger.info(f"Ending session {session_id} in state manager (async)")
        await self.state_manager.end_session(session_id)
    else:
        self.logger.info(f"Ending session {session_id} in state manager (sync)")
        self.state_manager.end_session(session_id)
    
    self.logger.info(f"Completed cleanup for session: {session_id}")
```

### Progressive Updates During LLM Processing

The system now provides incremental updates during long-running LLM operations:

```python
async def _send_progressive_updates(self, session_id, websocket):
    """
    Send progressive updates to client during long LLM operations
    """
    update_messages = [
        "I'm thinking about your question...",
        "Still processing your question...",
        "This is a complex question, giving it some thought...",
        "Almost ready with a response...",
        "Finalizing my thoughts on this..."
    ]
    
    progress_values = [0.2, 0.4, 0.6, 0.8, 0.9]
    
    try:
        # Send updates every 5 seconds
        for i in range(len(update_messages)):
            await asyncio.sleep(5.0)
            
            # Update the LLM processing state with progress
            await self.state_manager.transition_state(session_id, "PROCESSING_LLM", {
                "message": update_messages[i % len(update_messages)],
                "progress": progress_values[i % len(progress_values)]
            })
            
            # Also send a direct system message
            await self._send_progress_update(websocket, update_messages[i % len(update_messages)])
            
    except asyncio.CancelledError:
        # Task was cancelled (normal when LLM completes)
        pass
    except Exception as e:
        self.logger.error(f"Error in progressive updates: {e}")
```

### Improved Client Capability Handling

The system now has more comprehensive client capability detection and storage:

```python
async def handle_client_capabilities(self, websocket, session_id: str, message: Dict[str, Any]):
    """Process client capability information"""
    try:
        # Log reception of message
        self.logger.info(f"Received client capabilities message for session {session_id}")
        
        # Extract capabilities from message
        capabilities = message.get("capabilities", {})
        
        # Format validation check and correction
        if not isinstance(capabilities, dict):
            self.logger.error(f"Invalid capabilities format: {type(capabilities)}, value: {capabilities}")
            # Try to extract from root level if JSON structure is different
            if isinstance(message, dict) and "audio_formats" in message:
                self.logger.info("Found capabilities at root level of message, fixing...")
                capabilities = message
            # Try to extract from a string if the value might be JSON encoded
            elif isinstance(capabilities, str):
                try:
                    capabilities = json.loads(capabilities)
                    self.logger.info(f"Parsed capabilities from string: {capabilities}")
                except:
                    # Last resort - create default capabilities
                    self.logger.warning("Creating default capabilities as fallback")
                    capabilities = {
                        "audio_formats": ["wav", "mp3"],
                        "browser": {"name": "unity"}
                    }
        
        # Store capabilities in the server's dictionary
        self.client_capabilities[session_id] = capabilities
            
        # Extract key capabilities for logging
        audio_formats = capabilities.get('audio_formats', [])
        browser_info = capabilities.get('browser', {})
        
        # Store capabilities in session metadata
        session = self.state_manager.get_session(session_id)
        if session and hasattr(session, "metadata"):
            if not session.metadata:
                session.metadata = {}
            # Store the capabilities object
            session.metadata["client_capabilities"] = capabilities
        
        # Send acknowledgment with supported features
        ack_message = {
            "type": "state_update",
            "session_id": session_id,
            "previous": "IDLE",
            "current": "IDLE",
            "timestamp": time.time(),
            "metadata": {
                "message": "Client capabilities acknowledged",
                "supported_features": {
                    "direct_audio": True,
                    "streaming": False,  # Explicitly mark streaming as not supported
                    "progressive_updates": True
                }
            }
        }
        if websocket:
            await websocket.send(encode_message(ack_message))
        else:
            self.logger.warning(f"Could not send capabilities acknowledgment: no websocket")
    except Exception as e:
        self.logger.error(f"Error handling client capabilities: {e}")
```

### Delayed Response Handling

The system now has sophisticated handling for responses that arrive after timeouts:

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

## Configuration

The WebSocket server's configuration is controlled via the main system config:

```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 8765,
    "log_level": "INFO"
  },
  "heartbeat": {
    "enabled": true,
    "interval": 5.0
  }
}
```

Key configuration options:
- **Host**: The network interface to bind to (0.0.0.0 = all interfaces)
- **Port**: The WebSocket port to listen on
- **Log Level**: Logging verbosity (DEBUG, INFO, WARNING, ERROR)
- **Heartbeat Enabled**: Whether to enable the heartbeat mechanism
- **Heartbeat Interval**: Time between heartbeat messages in seconds

The WebSocket server also supports these advanced settings:
- **ping_interval**: WebSocket ping interval in seconds (default: 30)
- **ping_timeout**: WebSocket ping timeout in seconds (default: 10)
- **max_size**: Maximum message size in bytes (default: 10MB)

## Common Issues

### Connection Handling Issues

1. **Connection Timeout During Long Operations**: 
   - **Cause**: Long-running operations (like LLM processing) exceed client timeout thresholds.
   - **Solution**: The heartbeat service sends stage-appropriate updates at varying intervals.
   
   ```python
   # In the HeartbeatService class
   interval = self.heartbeat_interval
   if metadata and "processing_stage" in metadata:
       stage = metadata["processing_stage"]
       if stage == "generating_response":
           # More frequent updates during LLM processing - critical for client responsiveness
           interval = 1.5  # Send more frequent updates during LLM processing
       elif stage == "transcribing":
           interval = 3.0  # Less frequent during STT
       elif stage == "generating_speech":
           interval = 2.0  # Medium frequency during TTS
   ```

2. **Session ID Mismatch Issues**:
   - **Cause**: Client reconnects with different session ID than server expects.
   - **Solution**: Improved session ID reconciliation in message handling.
   
   ```python
   # Extract client's session ID from the message if available
   client_session_id = msg_data.get("session_id", session_id)
   
   # Handle session ID mismatch (common with reconnections)
   if client_session_id != session_id and client_session_id:
       self.logger.info(f"Session ID mismatch: Message uses {client_session_id}, server using {session_id}")
       # For capabilities, we'll use the server's session ID but log the client's
       if msg_type == "client_capabilities":
           self.logger.info(f"Using server session ID {session_id} for client capabilities")
       else:
           # For other message types, consider using the client's session ID
           if msg_type != "audio_data":
               self.logger.info(f"Using client-provided session ID {client_session_id}")
               session_id = client_session_id
   ```

3. **Task Leakage**:
   - **Cause**: Tasks not properly tracked or cleaned up during disconnection.
   - **Solution**: Comprehensive task tracking and session cleanup.

### Audio Processing Issues

1. **TTS Timeout with Eventual Completion**:
   - **Cause**: TTS takes longer than the timeout but eventually completes.
   - **Solution**: Delayed TTS response checking to deliver audio when ready.
   
   ```python
   async def _check_delayed_tts_response(self, session_id, text_response, context):
       """Check if a delayed TTS response becomes available"""
       # Wait a bit to allow TTS to finish
       await asyncio.sleep(10)
       
       # Look for recently generated audio files
       # If found, send to client even after timeout
   ```

2. **Streaming API Deprecation**:
   - **Cause**: Legacy clients still using streaming endpoints.
   - **Solution**: Graceful handling with client notification.
   
   ```python
   async def handle_streaming_status(self, session_id: str, message: Dict[str, Any]):
       """Handle streaming status updates from client (deprecated)"""
       # Inform the client that streaming is not supported
       await websocket.send(encode_message({
           "type": "system_message",
           "message": "Streaming audio is not supported in this version"
       }))
   ```

## Code Examples

### Granular Audio Processing with Progress Tracking

```python
async def process_audio_pipeline(self, session_id: str, audio_data: bytes):
    """
    Full audio processing pipeline with granular states for better progress tracking.
    """
    websocket = self.active_connections.get(session_id)
    progress_task = None
    heartbeat_task = None
    safety_timer = None
    
    try:
        # Create a separate task for heartbeat
        if self.heartbeat_service and websocket:
            heartbeat_task = asyncio.create_task(
                self.heartbeat_service.start_heartbeat(
                    session_id,
                    lambda msg: websocket.send(json.dumps(msg)),
                    {"processing_stage": "transcribing"}
                )
            )
        
        # Start a safety timer that will force transition to WAITING if processing takes too long
        safety_timer = asyncio.create_task(
            self._safety_timeout(session_id, 25.0)  # 25 second timeout
        )
        
        # Transition to PROCESSING_STT state
        await self.state_manager.transition_state(session_id, "PROCESSING_STT", {
            "message": "Transcribing your speech to text",
            "progress": 0.0
        })
        
        # Transcribe audio (CPU intensive) in a separate thread
        try:
            transcript_future = asyncio.create_task(
                asyncio.to_thread(self.stt_service.transcribe, audio_data)
            )
            
            # Add a timeout to prevent hanging
            transcript = await asyncio.wait_for(transcript_future, timeout=15.0)
            
            # Update STT progress to complete
            await self.state_manager.transition_state(session_id, "PROCESSING_STT", {
                "message": "Speech transcribed successfully",
                "progress": 1.0
            })
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
            
            # Transition to ERROR state
            await self.state_manager.transition_state(session_id, "ERROR", {
                "message": "Speech transcription timed out",
                "error_type": "STT_ERROR"
            })
            
            # Cancel safety timer
            if safety_timer and not safety_timer.done():
                safety_timer.cancel()
            
            return
        
        # Get the current session and its conversation history
        session = self.state_manager.get_session(session_id)
        if not session:
            self.logger.error(f"Session {session_id} not found")
            return
        
        # Transition to PROCESSING_LLM
        await self.state_manager.transition_state(session_id, "PROCESSING_LLM", {
            "message": "Generating response to your question",
            "transcript": transcript,
            "stage": interaction_stage,
            "progress": 0.0
        })
        
        # Cancel previous heartbeat task
        if heartbeat_task and not heartbeat_task.done():
            heartbeat_task.cancel()
        
        # Start a new heartbeat for LLM processing
        if self.heartbeat_service and websocket:
            heartbeat_task = asyncio.create_task(
                self.heartbeat_service.start_heartbeat(
                    session_id,
                    lambda msg: websocket.send(json.dumps(msg)),
                    {"processing_stage": "generating_response"}
                )
            )
        
        # Generate LLM response with a timeout
        try:
            llm_future = asyncio.create_task(
                asyncio.to_thread(
                    self.llm_client.generate_response,
                    transcript,
                    session.get_context(),
                    None,  # default timeout
                    None,  # default retries
                    interaction_stage
                )
            )
            
            # Add a timeout for LLM processing
            response = await asyncio.wait_for(llm_future, timeout=20.0)
            
            # Update LLM progress to complete
            await self.state_manager.transition_state(session_id, "PROCESSING_LLM", {
                "message": "Response generated successfully",
                "progress": 1.0
            })
        except asyncio.TimeoutError:
            # Handle LLM timeout
            self.logger.warning(f"LLM timeout for session {session_id}")
            
            # Create a background task to handle delayed response
            asyncio.create_task(
                self._handle_delayed_llm_response(session_id, llm_future, websocket)
            )
            
            # Tell the user about the delay
            await websocket.send(json.dumps({
                "type": "system_message",
                "message": "I'm still thinking about your question. This might take a moment..."
            }))
            
            # Transition to ERROR state
            await self.state_manager.transition_state(session_id, "ERROR", {
                "message": "LLM response generation timed out, still working in background",
                "error_type": "LLM_TIMEOUT"
            })
            
            return
        
        # Add the exchange to session history
        session.add_interaction(transcript, response)
        
        # Transition to PROCESSING_TTS 
        await self.state_manager.transition_state(session_id, "PROCESSING_TTS", {
            "message": "Converting response to speech",
            "progress": 0.0
        })
        
        # Start a new heartbeat for TTS processing
        if heartbeat_task and not heartbeat_task.done():
            heartbeat_task.cancel()
            
        if self.heartbeat_service and websocket:
            heartbeat_task = asyncio.create_task(
                self.heartbeat_service.start_heartbeat(
                    session_id,
                    lambda msg: websocket.send(json.dumps(msg)),
                    {"processing_stage": "generating_speech"}
                )
            )
        
        # Generate speech from text with timeout
        tts_future = None
        try:
            tts_future = asyncio.create_task(
                asyncio.to_thread(self.tts_service.synthesize, response)
            )
            
            # Add a timeout for TTS processing
            audio_response = await asyncio.wait_for(tts_future, timeout=15.0)
            
            # Update TTS progress to complete
            await self.state_manager.transition_state(session_id, "PROCESSING_TTS", {
                "message": "Audio generation complete",
                "progress": 1.0
            })
        except asyncio.TimeoutError:
            self.logger.warning(f"TTS timeout for session {session_id}")
            
            # Store the task for potential delayed completion
            if session_id in self.state_manager.sessions:
                session = self.state_manager.sessions[session_id]
                if not hasattr(session, 'pending_tts_tasks'):
                    session.pending_tts_tasks = []
                # Store task for potential completion later
                if tts_future and not tts_future.done():
                    self.logger.info(f"Storing pending TTS task for session {session_id}")
                    session.pending_tts_tasks.append(tts_future)
            
            if self.error_handler:
                await self.error_handler.handle_error(
                    ErrorHandler.TTS_ERROR,
                    session_id,
                    Exception("Speech synthesis timed out"),
                    {"websocket": websocket, "text_response": response}
                )
            
            # Send text-only response as fallback
            fallback_message = {
                "type": "text_response",
                "session_id": session_id,
                "timestamp": time.time(),
                "text": response,
                "message": "Audio conversion timed out, showing text instead"
            }
            await websocket.send(json.dumps(fallback_message))
            
            # Transition to WAITING state
            await self.state_manager.transition_state(session_id, "WAITING", {
                "message": "Waiting for user input after fallback"
            })
            
            return
        
        # Stop all background tasks
        if heartbeat_task and not heartbeat_task.done():
            heartbeat_task.cancel()
        
        if safety_timer and not safety_timer.done():
            safety_timer.cancel()
        
        # Transition to RESPONDING state
        await self.state_manager.transition_state(session_id, "RESPONDING", {
            "message": "Playing response"
        })
        
        # Send audio response to client
        await self.send_audio_response(session_id, audio_response, response)
        
        # Transition to WAITING state
        await self.state_manager.transition_state(session_id, "WAITING", {
            "message": "Waiting for user input"
        })
        
    except asyncio.CancelledError:
        # Task was cancelled, clean up
        self.logger.info(f"Audio pipeline cancelled for {session_id}")
        
        # Cancel all running subtasks
        for task in [heartbeat_task, safety_timer]:
            if task and not task.done():
                task.cancel()
        
        # Reset to WAITING state if connection still active
        if session_id in self.active_connections:
            await self.state_manager.transition_state(session_id, "WAITING", {
                "message": "Processing cancelled"
            })
    
    except Exception as e:
        # Stop all background tasks
        for task in [heartbeat_task, safety_timer]:
            if task and not task.done():
                task.cancel()
        
        self.logger.error(f"Error in audio pipeline: {e}\n{traceback.format_exc()}")
        
        # Try to use error handler
        if self.error_handler:
            try:
                success, _ = await self.error_handler.handle_error(
                    ErrorHandler.SYSTEM_ERROR,
                    session_id,
                    e,
                    {"websocket": websocket}
                )
                if success:
                    return
            except Exception as handler_error:
                self.logger.error(f"Error handler failed: {handler_error}")
        
        # Always try to transition back to WAITING to prevent client hang
        try:
            await asyncio.sleep(1)  # Give a moment for the error to be displayed
            await self.state_manager.transition_state(session_id, "WAITING", {
                "message": "Ready for next input after error"
            })
        except Exception as transition_error:
            self.logger.error(f"Failed to transition to WAITING after error: {transition_error}")
```

### Enhanced Audio Response with Format Validation

```python
async def send_audio_response(
    self, 
    session_id: str, 
    audio_data: bytes,
    text_response: Optional[str] = None
):
    """
    Send audio response to client using direct audio data
    
    This simplified version only uses direct audio delivery with text fallback.
    
    Args:
        session_id: The session identifier
        audio_data: The audio data as bytes
        text_response: Optional text version of the response for fallback
    """
    websocket = self.active_connections.get(session_id)
    if not websocket:
        self.logger.error(f"No active connection for {session_id}")
        return
        
    try:
        # Check if we have valid audio data
        has_valid_audio = (audio_data is not None and 
                         len(audio_data) > 1000 and 
                         self._validate_wav_format(audio_data))
        
        if has_valid_audio:
            # We have valid audio data - send it directly
            self.logger.info(f"Using direct audio data for {session_id}")
            
            # Create the audio response message
            message = {
                "type": "audio_response",
                "session_id": session_id,
                "timestamp": time.time(),
                "format": "wav",  # Explicitly specify format
                "data": base64.b64encode(audio_data).decode('utf-8')
            }
            
            # Include text response as a fallback
            if text_response:
                message["text"] = text_response
                
            await websocket.send(encode_message(message))
            self.logger.debug(f"Sent audio response to {session_id}, size: {len(audio_data)} bytes")
            
        else:
            # No valid audio or streaming available - use text fallback
            self.logger.warning(f"No valid audio available for {session_id}, using text fallback")
            
            if text_response:
                text_message = {
                    "type": "text_response",
                    "session_id": session_id,
                    "timestamp": time.time(),
                    "text": text_response,
                    "message": "Audio unavailable, showing text instead"
                }
                await websocket.send(encode_message(text_message))
            else:
                # No text either - send generic error
                await self.send_error(session_id, 500, "Audio synthesis failed")
            
    except Exception as e:
        self.logger.error(f"Error sending audio response: {e}")
        
        # Try to send a text-only response if audio fails
        if text_response:
            try:
                text_message = {
                    "type": "text_response",
                    "session_id": session_id,
                    "timestamp": time.time(),
                    "text": text_response,
                    "message": "Audio playback failed, showing text instead"
                }
                await websocket.send(encode_message(text_message))
            except Exception as text_error:
                self.logger.error(f"Failed to send text fallback: {text_error}")
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
        if current_state and current_state.startswith("PROCESSING"):
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