# VR Interview System: System Overview

## Title and Overview

The VR Interview System is a real-time interview simulation platform that uses WebSockets, speech-to-text (STT), large language models (LLM), and text-to-speech (TTS) technologies to create an interactive interview experience in a virtual reality environment. The system processes audio from users, transcribes it, generates appropriate responses via an LLM, converts those responses to speech, and delivers them back to the client.

## Architecture

The VR Interview System follows a modular client-server architecture with asynchronous processing to handle real-time interactions without blocking. The system's primary components include:

1. **Server Core**: The central component that orchestrates all other modules and manages the WebSocket server.
2. **WebSocket Server**: Handles client connections, message parsing, and the communication protocol.
3. **Enhanced Stream Processor**: Optimizes the audio processing pipeline with parallel processing stages.
4. **State Management System**: Manages session states and ensures valid state transitions.
5. **Speech Recognition (STT)**: Converts user audio input to text using CUDA-optimized models.
6. **Language Model Integration (LLM)**: Processes transcribed text and generates contextually relevant responses.
7. **Text-to-Speech (TTS)**: Converts generated text responses to audio with multiple provider support.
8. **Error Handling System**: Manages error recovery and graceful degradation.
9. **Heartbeat Mechanism**: Ensures connections remain active during long-running operations.
10. **GPU Monitoring**: Tracks GPU memory usage and optimizes performance for CUDA operations.

### Architecture Diagram (ASCII)

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
│                            Server Core                                │
│                         (EnhancedServer)                              │
└─┬─────────────┬───────────────┬────────────────┬──────────────────────┘
  │             │               │                │
  ▼             ▼               ▼                ▼
┌──────────┐ ┌───────┐  ┌───────────────┐ ┌─────────────┐
│WebSocket │ │ State │  │  STT Service  │ │ TTS Service │
│ Server   │ │Manager│  │(CUDA-Whisper) │ │             │
└────┬─────┘ └───────┘  └───────────────┘ └────────┬────┘
     │                                             │
     ▼                                             ▼
┌──────────────────┐                      ┌────────────────────┐
│Enhanced Stream   │                      │ TTS Providers      │
│Processor         │                      │ (AllTalk, gTTS)    │
└──────┬───────────┘                      └──────────┬─────────┘
       │                                             │
       ▼                                             │
┌──────────────────┐                                 │
│ LLM Client       │◄────────────────────────────────┘
│ (Ollama)         │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│Interview Scenario│
│Framework         │
└──────────────────┘
```

### Data Flow

1. **Client Connection**: 
   - VR client connects via WebSocket
   - Server assigns session ID
   - Client and server exchange capabilities
   - System initializes in IDLE state

2. **Audio Input Processing**:
   - Client sends audio data to the server
   - EnhancedStreamProcessor handles audio routing
   - StateManager transitions to LISTENING state
   - Audio data is sent to STT service
   - STT transcribes audio to text using CUDA acceleration when available
   - Transcript is displayed in VR interface

3. **LLM Processing**:
   - StateManager transitions to PROCESSING state
   - OllamaClient formats prompt with context and stage guidance
   - Intelligent context pruning maintains important information
   - LLM generates response with optimized parameters
   - Progressive updates sent during generation
   - Response is cached for future reuse

4. **Speech Synthesis**:
   - TTSService handles text-to-speech conversion
   - AllTalk with gTTS fallback ensures robust operation
   - Generated audio is processed and optimized
   - StateManager transitions to RESPONDING state
   - Audio is sent to client

5. **Client Playback**:
   - Client plays audio through avatar
   - Avatar animations synchronize with speech
   - Client notifies server when playback completes
   - StateManager transitions to WAITING state
   - System awaits next user input

### State Machine

The conversation follows a sophisticated state machine pattern with flexible transitions:

```
┌─────┐                 ┌───────────┐                 ┌─────────────┐
│     │◄───────────────┤           │◄────────────────┤             │
│ IDLE│────────────────►│ LISTENING │────────────────►│ PROCESSING  │
│     │                 │           │                 │             │
└──┬──┘                 └───────────┘                 └──────┬──────┘
   │                                                         │
   │                                                         │
   │                                                         │
   │                                                         ▼
┌──▼──┐                 ┌───────────┐                 ┌─────────────┐
│     │◄───────────────┤           │◄────────────────┤             │
│ERROR│────────────────►│  WAITING  │────────────────►│ RESPONDING  │
│     │                 │           │                 │             │
└─────┘                 └───────────┘                 └─────────────┘
```

The state machine has been enhanced with:
- Flexible transitions for error recovery
- Deadlock prevention and detection
- Forced transitions for system recovery
- Granular state updates with detailed metadata

## Key Classes/Functions

### Server Core
- `EnhancedServer`: Main server class that initializes and orchestrates all components
- `start()`: Starts the WebSocket server and initializes services
- `_shutdown()`: Gracefully shuts down the server and cleans up resources
- `_setup_signal_handlers()`: Sets up handlers for graceful termination
- `_register_error_handlers()`: Configures specialized error recovery strategies

### WebSocket Server
- `WebSocketServer`: Manages WebSocket connections and message routing
- `handle_connection()`: Processes new client connections
- `process_message()`: Routes incoming messages to appropriate handlers
- `process_audio()`: Initiates the audio processing pipeline
- `process_audio_pipeline()`: Orchestrates the full audio-to-response flow

### Enhanced Stream Processor
- `EnhancedStreamProcessor`: Optimizes audio processing with parallel stages
- `process_streaming_audio_pipeline()`: Implements optimized pipeline
- `_generate_standard_tts()`: Handles non-streaming TTS generation
- `_send_progressive_updates()`: Provides real-time updates during processing
- `_prewarm_tts()`: Prepares TTS engine to reduce cold-start latency

### State Manager
- `StateManager`: Manages conversation states and session data
- `transition_state()`: Handles state transitions with validation and deadlock prevention
- `force_transition()`: Forces state change for emergency recovery
- `_is_valid_transition()`: Validates state transitions against defined rules
- `_handle_deadlock()`: Detects and resolves potential deadlocks
- `_broadcast_state_change()`: Communicates state changes to clients

### LLM Integration
- `OllamaClient`: Client for the Ollama API with context management and response caching
- `generate_response()`: Produces text responses based on conversation context
- `_format_prompt()`: Formats prompts with context and stage guidance
- `_prune_context()`: Intelligently reduces context size while preserving key information
- `_precompute_responses()`: Generates responses for common questions in background
- `_prune_cache()`: Manages cache size with weighted priority algorithm

### Interview Scenarios
- `JOB_INTERVIEW_SCENARIO`: Comprehensive template for job interviews
- `get_interview_prompt()`: Generates formatted prompts for specific scenarios
- `get_stage_questions()`: Provides appropriate questions for interview stages
- `generate_interview_context()`: Creates context summaries from conversation history

### Audio Processing
- `STTService`: Speech-to-text service using CUDA-optimized Whisper models
- `TTSService`: Primary TTS provider using AllTalk with gTTS fallback
- `GTTSOnlyService`: Fallback TTS provider using Google's service

### GPU Monitoring
- `GPUMonitor`: Utility class for monitoring GPU resource usage
- `log_memory_usage()`: Tracks GPU memory allocation and usage
- `clear_cache()`: Frees GPU memory by clearing CUDA cache
- `time_function()`: Decorator for timing GPU operations
- `optimize_for_inference()`: Configures PyTorch for optimal inference performance

### Error Handling
- `ErrorHandler`: Manages error recovery strategies
- `handle_error()`: Routes errors to appropriate recovery mechanisms
- `_handle_exceeded_recovery_attempts()`: Implements aggressive recovery for persistent errors
- `_handle_cooldown_recovery()`: Provides lightweight recovery during cooldown periods
- `reset_session_errors()`: Clears error tracking for specific sessions

## Usage Patterns

### Typical Interaction Flow
1. Client establishes WebSocket connection
2. Server creates session and assigns unique ID
3. Client and server exchange capabilities information
4. Client sends audio data when user speaks
5. EnhancedStreamProcessor manages the processing pipeline
6. Server responds with audio or text response
7. Client plays audio response
8. Client notifies server of playback completion
9. Flow repeats for continued conversation

### Error Recovery Flow
1. Error is detected in any component
2. ErrorHandler categorizes error type and context
3. Specialized recovery handler attempts resolution
4. If recovery fails, system uses more aggressive strategies
5. Cooldown periods prevent cascading failures
6. Session is reset to a known good state
7. Client is notified of the recovery action

## Implementation Details

### Asynchronous Architecture
The system uses asyncio for non-blocking I/O operations, allowing multiple sessions to be processed simultaneously. Long-running operations (like LLM processing) are offloaded to thread pools to prevent blocking the event loop. Key features include:

- Thread pools for CPU-intensive operations
- Task tracking for proper resource management
- Safety timeouts to prevent hanging
- Progress updates during long operations

### GPU Acceleration
The system leverages GPU acceleration for performance-critical components:

- CUDA-optimized Whisper models for STT
- Memory management for efficient GPU utilization
- Performance monitoring and optimization
- Automatic fallback to CPU when GPU unavailable

### Multiple TTS Providers
The system incorporates multiple TTS providers with intelligent fallbacks:

```
┌────────────┐
│ TTS Service│
└─────┬──────┘
      │
      ▼
┌─────┴──────┐  Failure  ┌────────────┐
│ AllTalk    │──────────►│ Google TTS │
│ (Primary)  │           │ (Fallback) │
└────────────┘           └────────────┘
```

### Comprehensive Error Handling
The system implements a sophisticated error recovery system:

- Error categorization by type and source
- Progressive recovery strategies
- Cooldown periods to prevent cascading failures
- Pattern detection for recurring issues
- Specialized handlers for different error types
- Graceful degradation paths for all services

## Configuration

The system configuration is managed through a JSON file (`config/config.json`) with the following key sections:

### Server Configuration
```json
"server": {
  "host": "0.0.0.0",
  "port": 8765,
  "log_level": "INFO"
}
```

### Audio Configuration
```json
"audio": {
  "stt_model": "medium",
  "sample_rate": 16000,
  "channels": 1
}
```

### Storage Configuration
```json
"storage": {
  "audio_dir": "data/audio",
  "conversation_dir": "data/conversations",
  "retention_days": 30
}
```

### LLM Configuration
```json
"ollama": {
  "url": "http://localhost:11434",
  "model": "mistral:latest",
  "context_length": 8192,
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

### TTS Configuration
```json
"alltalk": {
  "url": "http://127.0.0.1:7851",
  "voice": "female_06.wav",
  "format": "wav",
  "retries": 3,
  "timeout": 60,
  "direct_api_timeout": 60,
  "alltalk_dir": "D:/AllTalk/alltalk_tts",
  "default_language": "en"
}

"tts": {
  "primary_engine": "alltalk",
  "fallback": "gtts",
  "cache_enabled": true
}
```

### Heartbeat Configuration
```json
"heartbeat": {
  "enabled": true,
  "interval": 5.0
}
```

Configuration can also be overridden through environment variables using the `VR_INTERVIEW_` prefix and double underscores for nested keys. For example:

```
VR_INTERVIEW_SERVER__PORT=8080
VR_INTERVIEW_OLLAMA__URL=http://ollama:11434
```

## Common Issues

### WebSocket Connection Issues

1. **Timeouts During Long Operations**
   - **Symptoms**: Client disconnects during LLM processing
   - **Cause**: Default WebSocket timeout reached
   - **Solution**: Heartbeat mechanism sends periodic messages
   - **Implementation**: Enhanced heartbeat service with dynamic intervals

2. **Session ID Mismatch**
   - **Symptoms**: Conversation history lost after reconnection
   - **Cause**: Client and server using different session IDs
   - **Solution**: Session ID mapping system with synchronization
   - **Implementation**: Improved WebSocket server with session tracking

### Speech Processing Issues

1. **GPU Memory Management**
   - **Symptoms**: Out of memory errors during STT processing
   - **Cause**: Insufficient CUDA memory
   - **Solution**: GPU monitoring and memory optimization
   - **Implementation**: GPUMonitor class with automatic cache clearing

2. **TTS Provider Failures**
   - **Symptoms**: Missing audio responses
   - **Cause**: Primary TTS service unavailable
   - **Solution**: Simple fallback chain for robust operation
   - **Implementation**: TTSService with gTTS fallback

3. **AllTalk API Issues**
   - **Symptoms**: API endpoint failures
   - **Cause**: AllTalk API changes or configuration issues
   - **Solution**: Multiple API attempt strategies
   - **Implementation**: Multiple API attempt methods in TTSService

### LLM Processing Issues

1. **Context Management**
   - **Symptoms**: Lost conversation context, irrelevant responses
   - **Cause**: Context window overflow
   - **Solution**: Intelligent context pruning
   - **Implementation**: Sophisticated pruning with importance heuristics

2. **Response Caching**
   - **Symptoms**: Cache overflow, low hit rates
   - **Cause**: Inefficient cache management
   - **Solution**: Weighted prioritization for cache pruning
   - **Implementation**: Advanced cache system with usage analytics

3. **Long Processing Times**
   - **Symptoms**: User waiting for responses
   - **Cause**: Complex LLM processing
   - **Solution**: Progressive updates during generation
   - **Implementation**: Async processing with progress callbacks

## System Startup and Shutdown

### Startup Process
1. Load configuration from `config/config.json`
2. Setup logging based on configured level
3. Create necessary directories for data storage
4. Initialize error handler and register specialized handlers
5. Initialize heartbeat service (if enabled)
6. Initialize state manager
7. Initialize STT service with model preloading
8. Initialize TTS service with provider chain
9. Initialize LLM client with precomputation if enabled
10. Initialize WebSocket server with component references
11. Setup signal handlers for graceful shutdown
12. Start WebSocket server and begin accepting connections
13. Start GPU monitoring if CUDA is available

### Shutdown Process
1. Capture termination signals (SIGINT, SIGTERM)
2. Close WebSocket server to stop accepting new connections
3. Stop heartbeat service if running
4. Cancel all running tasks and wait for completion
5. Save LLM cache to disk
6. Clean up temporary files
7. Release GPU resources
8. Stop event loop

## Code Examples

### Starting the Enhanced Server
```python
# Create and run the enhanced server
server = EnhancedServer()
try:
    loop = asyncio.get_event_loop()
    loop.run_until_complete(server.start())
    loop.run_forever()
except KeyboardInterrupt:
    pass
finally:
    loop.close()
```

### Enhanced Audio Processing Pipeline
```python
async def process_streaming_audio_pipeline(self, session_id, audio_data, websocket):
    """
    Process audio with optimized streaming pipeline.
    """
    # Track active tasks for proper cleanup
    tasks = []
    
    try:
        # 1. Start multiple stages in parallel
        # First transcribe audio and notify state change
        await self.state_manager.transition_state(session_id, "LISTENING", {
            "message": "Receiving audio"
        })
        
        # Transcribe audio in a separate thread
        transcript_future = asyncio.create_task(
            asyncio.to_thread(self.stt_service.transcribe, audio_data)
        )
        tasks.append(transcript_future)
        
        # Add a timeout to prevent hanging
        transcript = await asyncio.wait_for(transcript_future, timeout=10.0)
        
        # 2. Update state and prepare for LLM processing
        await self.state_manager.transition_state(session_id, "PROCESSING", {
            "message": "Generating response",
            "transcript": transcript
        })
        
        # 3. Start TTS prewarming in parallel with LLM generation
        tts_prewarm_task = asyncio.create_task(self._prewarm_tts())
        tasks.append(tts_prewarm_task)
        
        # Start heartbeat task to send updates during LLM processing
        heartbeat_task = asyncio.create_task(
            self._send_progressive_updates(session_id, websocket)
        )
        tasks.append(heartbeat_task)
        
        # 4. Generate LLM response with progress updates and timeout
        progress_callback = lambda msg: self._send_progress_update(websocket, msg)
        
        # Generate response asynchronously
        response = await self.llm_client.generate_response_async(
            transcript,
            session.get_context(),
            None,
            None,
            progress_callback,
            interaction_stage
        )
        
        # 5. Generate speech using direct API
        await self.state_manager.transition_state(session_id, "PROCESSING", {
            "message": "Converting response to speech"
        })
        
        # Use direct TTS processing
        await self._generate_standard_tts(session_id, response, websocket)
        
    except Exception as e:
        # Error handling and recovery
        self.logger.error(f"Error in streaming pipeline: {e}")
        
        # Cancel all running tasks
        for task in tasks:
            if not task.done():
                task.cancel()
                
        # Use error handler for recovery
        if self.error_handler:
            await self.error_handler.handle_error(
                "SYSTEM_ERROR",
                session_id,
                e,
                {"websocket": websocket}
            )
```

### GPU Memory Monitoring
```python
# In server.py
# Import GPU monitoring utilities
try:
    import torch
    from app.utils.gpu_monitor import GPUMonitor
    
    # Initialize GPU monitoring
    gpu_monitor = GPUMonitor()
    gpu_monitor.log_memory_usage("Server startup")
    gpu_monitor.reset_peak_memory()
    
    # Optimize PyTorch for inference
    gpu_monitor.optimize_for_inference()
    
    # Add periodic monitoring
    async def monitor_gpu_periodically():
        while True:
            gpu_monitor.log_memory_usage("Periodic check")
            # Clean up caches periodically
            if hasattr(torch.cuda, 'empty_cache'):
                torch.cuda.empty_cache()
            await asyncio.sleep(300)  # 5 minutes
    
    # Start GPU monitoring task if CUDA is available
    if torch.cuda.is_available():
        logging.info("Starting periodic GPU monitoring")
        asyncio.create_task(monitor_gpu_periodically())
except ImportError:
    logging.warning("GPU monitoring not available (missing dependencies)")
    gpu_monitor = None
```

## Unity Client Integration

The Unity client integrates with the server using the WebSocket protocol. Key integration points include:

1. **WebSocket Connection**
   - Establishes connection to server
   - Handles reconnection and session recovery
   - Sends and receives structured messages

2. **Audio Processing**
   - Captures audio from VR headset microphone
   - Detects voice activity and encodes audio
   - Receives and plays audio responses
   - Synchronizes avatar lip movements with audio

3. **UI Updates**
   - Displays transcripts of user and system speech
   - Shows progress indicators during processing
   - Presents error messages and recovery information
   - Updates avatar animations based on conversation state

4. **State Synchronization**
   - Processes state updates from server
   - Updates UI elements based on conversation state
   - Manages appropriate avatar animations per state
   - Provides visual feedback for state transitions

Please refer to the Unity documentation for detailed information about the client implementation.

## Conclusion

The VR Interview System provides a sophisticated, robust platform for realistic interview practice in virtual reality. Through its modular architecture, comprehensive error handling, and multiple fallback paths, it delivers a responsive and engaging experience while gracefully handling the complex challenges of real-time speech processing and natural language generation.