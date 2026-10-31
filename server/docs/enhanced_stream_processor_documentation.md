# VR Interview System: Enhanced Stream Processor Documentation (Updated)

## Title and Overview

The Enhanced Stream Processor provides optimized handling for audio processing in the VR Interview System. It implements a sophisticated parallel processing pipeline that improves response times and user experience by overlapping operations, prewarming components, and handling delayed responses. This component specifically addresses the challenge of managing long-running operations in a real-time, interactive system while providing detailed progress updates through granular state transitions and recovering gracefully from various types of errors.

## Architecture

The Enhanced Stream Processor follows a multi-stage parallel processing architecture that decouples the sequential steps of audio processing, allowing them to run concurrently where possible, while maintaining detailed state tracking:

```
┌───────────────────┐
│ Audio Data Input  │
└─────────┬─────────┘
          │
          ▼
┌─────────────────────┐      ┌─────────────────┐
│ PROCESSING_STT      │◄─────┤  TTS Prewarming │
│ (Transcription)     │      └─────────────────┘
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐      ┌─────────────────┐
│ PROCESSING_LLM      │◄─────┤  Progressive    │
│ (Response Gen)      │      │  Updates        │
└─────────┬───────────┘      └─────────────────┘
          │
          ▼
┌─────────────────────┐
│ PROCESSING_TTS      │
│ (Speech Synthesis)  │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ RESPONDING          │
│ (Audio Playback)    │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ WAITING             │
│ (Ready for Input)   │
└─────────────────────┘
```

This architecture includes parallel tasks for optimization:
- TTS prewarming runs during STT processing to reduce cold-start latency
- Progressive updates run during LLM processing to keep the client informed
- Delayed response handling ensures outputs are delivered even after timeouts

## Key Classes/Functions

### EnhancedStreamProcessor

The main class implementing the optimized processing pipeline:

```python
class EnhancedStreamProcessor:
    """
    Enhanced stream processor with optimized processing pipeline.
    
    Features:
    - Multi-stage parallel processing with granular state transitions
    - Optimized direct audio generation
    - Intelligent caching for frequently used responses
    - Advanced error handling and recovery
    - Progressive updates during long-running operations
    - Delayed response handling for LLM and TTS
    """
```

#### Core Methods

- **`__init__(state_manager, stt_service, tts_service, llm_client, error_handler)`**: Initializes with system components
- **`process_streaming_audio_pipeline(session_id, audio_data, websocket)`**: Processes audio with parallel optimization and granular state tracking
- **`_generate_standard_tts(session_id, text, websocket)`**: Generates TTS response using direct API with enhanced error handling
- **`_prewarm_tts()`**: Prewarms TTS engine to reduce cold-start latency
- **`_handle_delayed_llm_response(session_id, llm_future, websocket)`**: Handles LLM responses that complete after timeout
- **`_check_delayed_tts_response(session_id, text_response, context)`**: Checks for delayed TTS responses that complete after timeout
- **`_send_progressive_updates(session_id, websocket)`**: Sends periodic updates during LLM processing with meaningful messages
- **`_send_progress_update(websocket, message)`**: Sends individual progress updates to client

## Usage Patterns

### Streaming Audio Pipeline with Granular States

The Enhanced Stream Processor is used by the WebSocket server to process audio with optimized performance:

```python
# In WebSocketServer.process_audio()
if use_streaming:
    # Use optimized streaming pipeline for faster responses
    task = asyncio.create_task(
        self.stream_processor.process_streaming_audio_pipeline(
            session_id, 
            audio_data,
            self.active_connections.get(session_id)
        )
    )
    self._track_task(task, session_id)
```

The pipeline uses granular state transitions for better progress tracking:

```python
# Transition to PROCESSING_STT
await self.state_manager.transition_state(session_id, "PROCESSING_STT", {
    "message": "Transcribing your speech to text",
    "progress": 0.0
})

# Transcribe audio and update progress to complete
await self.state_manager.transition_state(session_id, "PROCESSING_STT", {
    "message": "Speech transcribed successfully",
    "progress": 1.0
})

# Move to LLM processing
await self.state_manager.transition_state(session_id, "PROCESSING_LLM", {
    "message": "Generating response to your question",
    "transcript": transcript,
    "progress": 0.0
})
```

### Parallel Processing and Progress Updates

Multiple operations are started in parallel to reduce end-to-end latency:

```python
# Start multiple stages in parallel
# 1. Transcribe audio and notify state change
await self.state_manager.transition_state(session_id, "PROCESSING_STT", {
    "message": "Transcribing your speech to text",
    "progress": 0.0
})

# 2. Start TTS prewarming in parallel with LLM generation
tts_prewarm_task = asyncio.create_task(self._prewarm_tts())
tasks.append(tts_prewarm_task)

# 3. Start heartbeat task to send updates during LLM processing
heartbeat_task = asyncio.create_task(
    self._send_progressive_updates(session_id, websocket)
)
tasks.append(heartbeat_task)

# 4. Generate LLM response with progress callback
async def progress_callback(msg, progress=None):
    # Update state with progress information
    progress_metadata = {"message": msg}
    if progress is not None:
        progress_metadata["progress"] = progress
    await self.state_manager.transition_state(
        session_id, "PROCESSING_LLM", progress_metadata
    )
    await self._send_progress_update(websocket, msg)

llm_future = asyncio.create_task(
    self.llm_client.generate_response_async(
        transcript,
        context,
        None,  # default timeout
        None,  # default retries
        progress_callback,
        interaction_stage
    )
)
```

### Enhanced Delayed Response Handling

The processor handles both delayed LLM and TTS responses that complete after timeout:

```python
# For LLM timeouts - continue processing in background
asyncio.create_task(
    self._handle_delayed_llm_response(session_id, llm_future, websocket)
)

# For TTS timeouts - check for delayed completion
asyncio.create_task(
    self._check_delayed_tts_response(
        session_id, 
        text_response, 
        context
    )
)
```

## Implementation Details

### TTS Prewarming

To reduce cold-start latency, the TTS engine is prewarmed in parallel with STT processing:

```python
async def _prewarm_tts(self) -> bool:
    """
    Prewarm TTS engine to reduce cold-start latency.
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Send a simple request to make sure the TTS engine is ready
        await asyncio.to_thread(
            self.tts_service.synthesize,
            "Prewarming the text to speech system."
        )
        return True
    except Exception as e:
        self.logger.warning(f"TTS prewarm failed: {e}")
        return False
```

### Enhanced Progressive Updates

To keep the user engaged during LLM processing, progressive updates are sent with detailed progress tracking and meaningful natural language messages:

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

### Improved Delayed LLM Response Handling

The system can recover and utilize LLM responses that complete after the timeout:

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

### New Delayed TTS Response Check

The system now checks for TTS responses that complete after timeout, providing a better user experience by delivering speech even after initial timeouts:

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
            }
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

### Enhanced Task Management

The system carefully tracks tasks to ensure proper cleanup and prevent resource leaks:

```python
# Track active tasks for proper cleanup
tasks = []

try:
    # Start multiple stages in parallel
    # 1. Transcribe audio and notify state change
    await self.state_manager.transition_state(session_id, "LISTENING", {
        "message": "Receiving audio"
    })
    
    # Transcribe audio (CPU intensive) in a separate thread
    transcript_future = asyncio.create_task(
        asyncio.to_thread(self.stt_service.transcribe, audio_data)
    )
    tasks.append(transcript_future)
    
    # Remove completed task when done
    if transcript_future in tasks:
        tasks.remove(transcript_future)
    
    # Additional tasks and processing...
    
except asyncio.CancelledError:
    # Handle cancellation
    self.logger.info(f"Streaming pipeline cancelled for {session_id}")
    
    # Cancel all running tasks
    for task in tasks:
        if not task.done():
            task.cancel()
    
    # Always try to return to WAITING state
    try:
        await self.state_manager.transition_state(session_id, "WAITING", {
            "message": "Processing cancelled"
        })
    except Exception:
        pass
```

## Configuration

The Enhanced Stream Processor is configured through the main system configuration with improved settings for timeouts and error handling:

```json
"ollama": {
  "url": "http://localhost:11434",
  "model": "mistral:latest",
  "context_length": 8192,
  "system_prompt": "You are an AI interviewer conducting a job interview.",
  "timeout": 45,
  "max_retries": 2,
  "options": {
    "temperature": 0.7,
    "top_p": 0.9
  }
},
"alltalk": {
  "url": "http://127.0.0.1:7851",
  "voice": "female_06.wav",
  "retries": 3,
  "timeout": 15,
  "endpoints": ["tts-generate", "synthesize", "tts"]
},
"heartbeat": {
  "enabled": true,
  "interval": 5.0
}
```

Key configuration options:
- **LLM timeout**: Extended to 45 seconds for complex requests (previously 20s)
- **TTS timeout**: Extended to 15 seconds for better completion rates (previously 8s)
- **Multiple TTS endpoints**: Attempting different endpoints for better reliability
- **Heartbeat interval**: Configurable interval with processing stage awareness

## Common Issues

### Processing Pipeline Issues

1. **LLM Timeout Handling**:
   - **Symptoms**: Long LLM processing times exceeding timeouts
   - **Causes**: Large context, complex prompts, slow LLM server
   - **Solution**: Delayed response handling with both transcript updates and subsequent TTS generation
   - **Recovery Mechanism**: Continue LLM processing in background and check for eventual completion

2. **TTS Timeout Handling**:
   - **Symptoms**: TTS takes longer than the allocated time but eventually completes
   - **Causes**: TTS service overload, complex text, network issues
   - **Solution**: New `_check_delayed_tts_response` method that monitors for delayed completions
   - **Recovery Mechanism**: Send text fallback immediately, but continue checking for audio

3. **Task Lifecycle Management**:
   - **Symptoms**: Hanging tasks, resource leaks, memory consumption
   - **Causes**: Tasks not properly tracked or cancelled during cleanup
   - **Solution**: Comprehensive task tracking and explicit cancellation in both normal and error cases

### Performance Optimizations

1. **Parallel Processing with Granular States**:
   - Multiple stages run concurrently to reduce end-to-end latency
   - Granular state transitions (PROCESSING_STT, PROCESSING_LLM, PROCESSING_TTS) for better tracking
   - Progress percentage updates for each processing stage
   - TTS prewarming runs during transcription and LLM processing

2. **Enhanced User Experience**:
   - Detailed progress messages during each processing stage
   - Progress percentage indicators for UI progress bars
   - Multiple fallback mechanisms for different error types
   - Graceful degradation from audio to text when needed
   - Recovery of delayed responses when they eventually complete

3. **Error Recovery Strategies**:
   - Integration with the `ErrorHandler` for specialized recovery approaches
   - Different error handling strategies for STT, LLM, and TTS errors
   - Fallback to text responses when audio generation fails
   - Session state recovery to ensure responsiveness after errors

## Code Examples

### Full Streaming Pipeline

```python
async def process_streaming_audio_pipeline(
    self,
    session_id: str,
    audio_data: bytes,
    websocket
):
    """
    Process audio with optimized streaming pipeline.
    
    Args:
        session_id: Session identifier
        audio_data: Raw audio data
        websocket: WebSocket connection for sending responses
    """
    # Track active tasks for proper cleanup
    tasks = []
    
    try:
        # Start multiple stages in parallel
        # 1. Transcribe audio and notify state change
        await self.state_manager.transition_state(session_id, "LISTENING", {
            "message": "Receiving audio"
        })
        
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
            tasks.append(transcript_future)
            
            # Add a timeout to prevent hanging
            transcript = await asyncio.wait_for(transcript_future, timeout=10.0)
            
            # Remove completed task
            if transcript_future in tasks:
                tasks.remove(transcript_future)
                
            # Send progress update for completed transcription
            await self.state_manager.transition_state(session_id, "PROCESSING_STT", {
                "message": "Speech transcribed successfully",
                "progress": 1.0
            })
        except asyncio.TimeoutError:
            self.logger.warning(f"STT timeout for session {session_id}")
            if self.error_handler:
                await self.error_handler.handle_error(
                    "STT_ERROR",
                    session_id,
                    Exception("Speech transcription timed out"),
                    {"websocket": websocket}
                )
            # Transition to ERROR state
            await self.state_manager.transition_state(session_id, "ERROR", {
                "message": "Speech transcription timed out",
                "error_type": "STT_ERROR"
            })
            return
        except Exception as e:
            self.logger.error(f"STT error: {e}")
            # Error handling for STT
            # ...
            return
        
        # Check transcript result
        self.logger.info(f"Transcription: {transcript}")
        if not transcript.strip():
            await self.state_manager.transition_state(session_id, "WAITING", {
                "message": "No speech detected, please try again"
            })
            return
        
        # 2. Update state and prepare for LLM processing
        await self.state_manager.transition_state(session_id, "PROCESSING_LLM", {
            "message": "Generating response to your question",
            "transcript": transcript,
            "progress": 0.0
        })
        
        # Get session context
        session = self.state_manager.get_session(session_id)
        if not session:
            self.logger.error(f"Session {session_id} not found")
            return
            
        context = session.get_context()
        
        # 3. Start TTS prewarming in parallel with LLM generation
        tts_prewarm_task = asyncio.create_task(self._prewarm_tts())
        tasks.append(tts_prewarm_task)
        
        # Start heartbeat task to send updates during LLM processing
        heartbeat_task = asyncio.create_task(
            self._send_progressive_updates(session_id, websocket)
        )
        tasks.append(heartbeat_task)
        
        # 4. Generate LLM response with progress updates and timeout
        try:
            # Create progress callback that will update the state
            async def progress_callback(msg, progress=None):
                # Update state with progress information
                progress_metadata = {
                    "message": msg
                }
                
                # Add progress value if provided
                if progress is not None:
                    progress_metadata["progress"] = progress
                    
                await self.state_manager.transition_state(session_id, "PROCESSING_LLM", 
                                                         progress_metadata)
                
                # Also send direct progress update
                await self._send_progress_update(websocket, msg)
            
            llm_future = asyncio.create_task(
                self.llm_client.generate_response_async(
                    transcript,
                    context,
                    None,  # default timeout
                    None,  # default retries
                    progress_callback,
                    interaction_stage
                )
            )
            tasks.append(llm_future)
            
            # Add a timeout for LLM processing (extended to 45 seconds)
            response = await asyncio.wait_for(llm_future, timeout=45.0)
            
            # Remove completed task
            if llm_future in tasks:
                tasks.remove(llm_future)
                
            # Send final LLM progress update
            await self.state_manager.transition_state(session_id, "PROCESSING_LLM", {
                "message": "Response generated successfully",
                "progress": 1.0
            })
            
            # Cancel heartbeat task once we have the response
            if heartbeat_task and not heartbeat_task.done():
                heartbeat_task.cancel()
        except asyncio.TimeoutError:
            self.logger.warning(f"LLM timeout for session {session_id}")
            
            # Create a background task to handle it when it completes
            asyncio.create_task(
                self._handle_delayed_llm_response(session_id, llm_future, websocket)
            )
            
            # Tell the user about the delay
            await websocket.send(json.dumps({
                "type": "system_message",
                "session_id": session_id,
                "timestamp": time.time(),
                "message": "I'm still thinking about your question. This might take a moment..."
            }))
            
            # Transition to ERROR state
            await self.state_manager.transition_state(session_id, "ERROR", {
                "message": "LLM response generation timed out, but still working in background",
                "error_type": "LLM_TIMEOUT"
            })
            
            return
        except Exception as e:
            self.logger.error(f"LLM error: {e}")
            # Error handling for LLM
            # ...
            return
        
        # Add the exchange to session history
        session.add_interaction(transcript, response)
        
        # 5. Generate speech using TTS
        await self.state_manager.transition_state(session_id, "PROCESSING_TTS", {
            "message": "Converting response to speech",
            "progress": 0.0
        })
        
        # Use direct TTS processing
        await self._generate_standard_tts(session_id, response, websocket)
            
    except asyncio.CancelledError:
        # Handle cancellation
        self.logger.info(f"Streaming pipeline cancelled for {session_id}")
        
        # Cancel all running tasks
        for task in tasks:
            if not task.done():
                task.cancel()
                
        # Always try to return to WAITING state
        try:
            await self.state_manager.transition_state(session_id, "WAITING", {
                "message": "Processing cancelled"
            })
        except Exception:
            pass
            
    except Exception as e:
        self.logger.error(f"Error in streaming pipeline: {e}")
        
        # Cancel all running tasks
        for task in tasks:
            if not task.done():
                task.cancel()
                
        # Use error handler
        if self.error_handler:
            await self.error_handler.handle_error(
                "SYSTEM_ERROR",
                session_id,
                e,
                {"websocket": websocket}
            )
```

### Enhanced TTS Generation with Error Handling

```python
async def _generate_standard_tts(self, session_id: str, text: str, websocket) -> None:
    """
    Generate TTS response using standard (non-streaming) approach.
    
    Args:
        session_id: Session identifier
        text: Text to synthesize
        websocket: WebSocket connection
    """
    try:
        # Update TTS progress
        await self.state_manager.transition_state(session_id, "PROCESSING_TTS", {
            "message": "Generating audio from text",
            "progress": 0.5
        })
        
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
        
        # Transition to RESPONDING state
        await self.state_manager.transition_state(session_id, "RESPONDING", {
            "message": "Playing response"
        })
        
        # Send audio response to client
        message = {
            "type": "audio_response",
            "session_id": session_id,
            "timestamp": time.time(),
            "format": "wav",
            "data": base64.b64encode(audio_response).decode('utf-8'),
            "text": text
        }
        
        await websocket.send(json.dumps(message))
        
        # Wait a moment to ensure audio is received
        await asyncio.sleep(0.5)
        
        # Transition to WAITING state
        await self.state_manager.transition_state(session_id, "WAITING", {
            "message": "Waiting for user input"
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
            
        # Check for delayed TTS response
        asyncio.create_task(
            self._check_delayed_tts_response(session_id, text, {"websocket": websocket})
        )
        
    except Exception as e:
        self.logger.error(f"Error in standard TTS: {e}")
        
        # Transition to ERROR state
        await self.state_manager.transition_state(session_id, "ERROR", {
            "message": f"Audio generation error: {str(e)}",
            "error_type": "TTS_ERROR"
        })
        
        # Try to send text-only response
        try:
            text_message = {
                "type": "text_response",
                "session_id": session_id,
                "timestamp": time.time(),
                "text": text,
                "message": "Audio generation failed, showing text instead"
            }
            
            await websocket.send(json.dumps(text_message))
            
            # Update state
            await self.state_manager.transition_state(session_id, "WAITING", {
                "message": "Waiting for user input after error"
            })
        except Exception as text_error:
            self.logger.error(f"Failed to send text fallback: {text_error}")
```