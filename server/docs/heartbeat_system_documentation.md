# VR Interview System: Heartbeat System Documentation

## Title and Overview

The Heartbeat System in the VR Interview System prevents WebSocket timeouts during long-running operations like LLM generation and speech synthesis. It sends periodic messages to clients to keep the connection alive and provide progress updates. This is crucial for maintaining the illusion of continuous conversation and avoiding disconnections during processing-intensive operations. The system features dynamic interval adjustment based on the current processing stage and provides detailed progress information to improve user experience.

## Architecture

The Heartbeat System is implemented through the `HeartbeatService` class, which manages periodic message sending for each active session. It works in coordination with the WebSocket server and has sophisticated stage awareness to adjust message frequency based on the current processing activity.

```
┌───────────────────┐      Sends      ┌───────────────────┐
│ WebSocket Server  │◄───Heartbeats───┤ HeartbeatService  │
└─────────┬─────────┘                 └─────────┬─────────┘
          │                                     │
          │                                     │
┌─────────▼─────────┐     Request     ┌─────────▼─────────┐
│  Client Connection │───Heartbeats───►│ Processing Stage  │
└───────────────────┘                 │ - STT             │
                                      │ - LLM             │
                                      │ - TTS             │
                                      └───────────────────┘
```

The system also provides fallback mechanisms within the WebSocket server to ensure heartbeats continue even if the main HeartbeatService is unavailable.

## Key Classes/Functions

### HeartbeatService

The central class responsible for managing heartbeat messages:

```python
class HeartbeatService:
    """
    Service for sending periodic heartbeat messages to clients.
    
    This helps prevent WebSocket timeouts during long operations like
    LLM processing or speech synthesis.
    """
```

#### Core Methods

- **`__init__(heartbeat_interval)`**: Initializes the service with specified interval
- **`start_heartbeat(session_id, send_func, metadata)`**: Starts sending heartbeats for a session
- **`stop_heartbeat(session_id)`**: Stops heartbeats for a specific session
- **`stop_all()`**: Stops all active heartbeats
- **`_heartbeat_loop(session_id, send_func, metadata)`**: Internal loop that sends messages

### WebSocket Server Internal Heartbeat Methods

The WebSocket server also implements its own heartbeat mechanism as a fallback:

- **`_send_heartbeat_during_llm(session_id, websocket)`**: Sends periodic updates during LLM processing
- **`_send_progressive_updates(session_id, websocket)`**: Sends incremental updates with meaningful progress messages

## Usage Patterns

### Starting a Heartbeat with Processing Stage Awareness

```python
# Create a heartbeat when beginning LLM processing with specific stage metadata
if self.heartbeat_service and websocket:
    heartbeat_task = asyncio.create_task(
        self.heartbeat_service.start_heartbeat(
            session_id,
            lambda msg: websocket.send(json.dumps(msg)),
            {"processing_stage": "generating_response"}
        )
    )
```

### Starting Heartbeats for Different Processing Stages

```python
# For STT processing
heartbeat_task = asyncio.create_task(
    self.heartbeat_service.start_heartbeat(
        session_id,
        lambda msg: websocket.send(json.dumps(msg)),
        {"processing_stage": "transcribing"}
    )
)

# For TTS processing
heartbeat_task = asyncio.create_task(
    self.heartbeat_service.start_heartbeat(
        session_id,
        lambda msg: websocket.send(json.dumps(msg)),
        {"processing_stage": "generating_speech"}
    )
)
```

### Stopping a Heartbeat

```python
# Stop the heartbeat when processing completes
if heartbeat_task and not heartbeat_task.done():
    heartbeat_task.cancel()
    try:
        await heartbeat_task
    except asyncio.CancelledError:
        pass
        
# Start a new heartbeat with different metadata if needed
if self.heartbeat_service and websocket:
    heartbeat_task = asyncio.create_task(
        self.heartbeat_service.start_heartbeat(
            session_id,
            lambda msg: websocket.send(json.dumps(msg)),
            {"processing_stage": "generating_speech"}
        )
    )
```

### Session Cleanup with Heartbeat Termination

```python
async def _cleanup_session(self, session_id: str):
    """Clean up a session's resources"""
    self.logger.info(f"Starting cleanup for session: {session_id}")
    
    # Cancel session-specific tasks
    if session_id in self.session_tasks:
        # [...task cancellation code...]
    
    # Stop heartbeat if active
    if self.heartbeat_service:
        self.logger.info(f"Stopping heartbeat for session {session_id}")
        await self.heartbeat_service.stop_heartbeat(session_id)
        
    # [...other cleanup code...]
```

### Heartbeat During Server Shutdown

```python
async def shutdown(self):
    """Gracefully shutdown the WebSocket server"""
    if self.server:
        self.logger.info("Shutting down WebSocket server...")
        self.server.close()
        await self.server.wait_closed()
        
        # Stop heartbeats if available
        if self.heartbeat_service:
            await self.heartbeat_service.stop_all()
            
        # Cleanup other resources
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        [task.cancel() for task in tasks]
        await asyncio.gather(*tasks, return_exceptions=True)
```

## Implementation Details

### Dynamic Interval Adjustment

The heartbeat system intelligently adjusts its interval based on the current processing stage for optimal user experience:

```python
# Determine interval based on processing stage
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

This dynamic adjustment balances responsiveness with server load:
- **LLM Processing**: More frequent updates (1.5s) since this is typically the longest operation and users need frequent feedback
- **Speech Synthesis**: Medium frequency updates (2.0s) as this operation usually completes faster
- **Speech Recognition**: Less frequent updates (3.0s) as this is typically the quickest operation

### Progressive Update Messages

The EnhancedStreamProcessor provides more meaningful progress updates during LLM processing:

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
```

These natural language messages provide a better user experience than generic "processing" messages.

### Heartbeat Message Format

Heartbeat messages include progress information and are formatted as JSON:

```json
{
  "type": "heartbeat",
  "session_id": "unique-session-id",
  "counter": 3,
  "timestamp": 1635789012.345,
  "metadata": {
    "processing_stage": "generating_response",
    "progress": 45,
    "message": "Still thinking about your question..."
  }
}
```

### Task Management and Error Handling

The heartbeat service implements robust error handling and task management:

```python
async def _heartbeat_loop(
    self, 
    session_id: str, 
    send_func: Callable[[Dict[str, Any]], Awaitable[None]],
    metadata: Dict[str, Any]
):
    """
    Internal loop that sends periodic heartbeat messages.
    """
    try:
        counter = 0
        while True:
            counter += 1
            
            # Prepare heartbeat message
            message = {
                "type": "heartbeat",
                "session_id": session_id,
                "counter": counter,
                "timestamp": asyncio.get_event_loop().time(),
            }
            
            # Add metadata if provided
            if metadata:
                message["metadata"] = metadata
                
            # Send the heartbeat
            try:
                await send_func(message)
                logger.debug(f"Sent heartbeat #{counter} to session {session_id}")
            except Exception as e:
                logger.error(f"Error sending heartbeat to {session_id}: {e}")
                break  # Break the loop if sending fails
                
            # Determine interval based on processing stage
            interval = self.heartbeat_interval
            if metadata and "processing_stage" in metadata:
                stage = metadata["processing_stage"]
                if stage == "generating_response":
                    interval = 1.5  # Send more frequent updates during LLM processing
                elif stage == "transcribing":
                    interval = 3.0  # Less frequent during STT
                elif stage == "generating_speech":
                    interval = 2.0  # Medium frequency during TTS
            
            # Wait for next heartbeat
            await asyncio.sleep(interval)
                
        except asyncio.CancelledError:
            logger.debug(f"Heartbeat task cancelled for session {session_id}")
        except Exception as e:
            logger.error(f"Error in heartbeat loop for {session_id}: {e}")
```

## Alternative Implementations

### WebSocket Server Integrated Heartbeat

When the dedicated HeartbeatService is not available, the WebSocket server provides its own implementation:

```python
async def _send_heartbeat_during_llm(self, session_id, websocket):
    """Send periodic heartbeat messages during LLM processing"""
    count = 0
    try:
        while True:
            # Send a heartbeat every 2 seconds
            await asyncio.sleep(2)
            count += 1
            
            try:
                message = {
                    "type": "heartbeat",
                    "session_id": session_id,
                    "timestamp": time.time(),
                    "progress": min(99, count * 5),  # Simulate progress
                    "message": f"Processing your response... ({count*2}s)"
                }
                await websocket.send(json.dumps(message))
            except Exception as e:
                self.logger.error(f"Error sending heartbeat: {e}")
                break
                
            # Stop after 45 seconds to prevent infinite loop
            if count >= 22:  # 22 * 2s = 44 seconds
                break
                
    except asyncio.CancelledError:
        # Task was cancelled normally
        pass
    except Exception as e:
        self.logger.error(f"Error in heartbeat task: {e}")
```

This internal implementation ensures that clients receive progress updates even without the dedicated HeartbeatService.

## Configuration

The heartbeat system is configured through the main system configuration:

```json
"heartbeat": {
  "enabled": true,
  "interval": 5.0
}
```

Key configuration options:
- **enabled**: Whether the heartbeat system is active (default: true)
- **interval**: Default time between heartbeats in seconds (default: 5.0)

The system also supports runtime configuration through metadata:
- **processing_stage**: The current stage of processing ("transcribing", "generating_response", "generating_speech")
- **progress**: Numeric progress value (0-100) if available
- **message**: Text message describing the current status

## Common Issues

### Connection Issues

1. **Browser Timeouts**:
   - **Symptoms**: Client disconnects during long LLM processing
   - **Causes**: Browser WebSocket connection timeouts (typically 30-60 seconds)
   - **Solution**: Heartbeat messages keep the connection alive with stage-appropriate frequency

2. **Proxy Timeouts**:
   - **Symptoms**: Intermittent disconnections in specific network environments
   - **Causes**: Intermediate proxies closing idle connections
   - **Solution**: Increase heartbeat frequency (can be configured in heartbeat.interval setting)

3. **Mobile Client Disconnections**:
   - **Symptoms**: Mobile clients lose connection more frequently
   - **Causes**: Mobile OS aggressive background connection management
   - **Solution**: Set mobile_optimized=True in metadata to use shorter intervals (not yet implemented)

### Resource Management

1. **Task Leaks**:
   - **Symptoms**: Increasing memory usage over time
   - **Causes**: Uncancelled heartbeat tasks
   - **Solution**: Comprehensive session cleanup in _cleanup_session method

2. **CPU Spikes**:
   - **Symptoms**: Regular CPU spikes with many clients
   - **Causes**: Too many simultaneous heartbeats
   - **Solution**: Staggered heartbeat timings (not yet implemented)

3. **Heartbeat Congestion with Many Users**:
   - **Symptoms**: Network traffic spikes
   - **Causes**: Many clients receiving simultaneous heartbeats
   - **Solution**: Adaptive heartbeat rate based on system load (future enhancement)

## Code Examples

### Initializing the Heartbeat Service

```python
# Initialize heartbeat service if enabled
heartbeat_config = self.config.get("heartbeat", {})
if heartbeat_config.get("enabled", True):
    self.heartbeat_service = HeartbeatService(
        heartbeat_interval=heartbeat_config.get("interval", 5.0)
    )
    self.logger.info(
        f"Heartbeat service enabled with interval: "
        f"{heartbeat_config.get('interval', 5.0)}s"
    )
else:
    self.heartbeat_service = None
    self.logger.info("Heartbeat service disabled")
```

### Using the Heartbeat During Audio Processing

```python
async def process_audio_pipeline(self, session_id, audio_data):
    """Full audio processing pipeline with heartbeat integration"""
    websocket = self.active_connections.get(session_id)
    heartbeat_task = None
    
    try:
        # Start heartbeat for STT processing
        if self.heartbeat_service:
            heartbeat_task = asyncio.create_task(
                self.heartbeat_service.start_heartbeat(
                    session_id,
                    lambda msg: websocket.send(json.dumps(msg)),
                    {"processing_stage": "transcribing"}
                )
            )
        
        # Transcribe audio...
        # [STT processing code]
        
        # Cancel STT heartbeat and start LLM heartbeat
        if heartbeat_task and not heartbeat_task.done():
            heartbeat_task.cancel()
            
        # Start heartbeat for LLM processing
        if self.heartbeat_service:
            heartbeat_task = asyncio.create_task(
                self.heartbeat_service.start_heartbeat(
                    session_id,
                    lambda msg: websocket.send(json.dumps(msg)),
                    {"processing_stage": "generating_response"}
                )
            )
            
        # Generate LLM response...
        # [LLM processing code]
        
        # Cancel LLM heartbeat and start TTS heartbeat
        if heartbeat_task and not heartbeat_task.done():
            heartbeat_task.cancel()
            
        # Start heartbeat for TTS processing
        if self.heartbeat_service:
            heartbeat_task = asyncio.create_task(
                self.heartbeat_service.start_heartbeat(
                    session_id,
                    lambda msg: websocket.send(json.dumps(msg)),
                    {"processing_stage": "generating_speech"}
                )
            )
            
        # Generate TTS...
        # [TTS processing code]
        
        # Cancel TTS heartbeat
        if heartbeat_task and not heartbeat_task.done():
            heartbeat_task.cancel()
            
    except Exception as e:
        # Error handling
        if heartbeat_task and not heartbeat_task.done():
            heartbeat_task.cancel()
```

### Alternative Fallback Implementation

```python
# Choose appropriate heartbeat implementation
if self.heartbeat_service and websocket:
    heartbeat_task = asyncio.create_task(
        self.heartbeat_service.start_heartbeat(
            session_id,
            lambda msg: websocket.send(json.dumps(msg)),
            {"processing_stage": "generating_response"}
        )
    )
else:
    # Use our internal heartbeat implementation
    heartbeat_task = asyncio.create_task(
        self._send_heartbeat_during_llm(session_id, websocket)
    )
```

### Safe Heartbeat Shutdown

```python
# For graceful shutdown, ensure all heartbeats are cancelled
async def shutdown(self):
    """Gracefully shutdown all components"""
    try:
        # Stop heartbeat service
        if self.heartbeat_service:
            self.logger.info("Stopping heartbeat service")
            await self.heartbeat_service.stop_all()
            
        # Continue with other shutdown tasks
    except Exception as e:
        self.logger.error(f"Error during shutdown: {e}")
```