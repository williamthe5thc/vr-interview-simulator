"""
Enhanced WebSocket server for VR Interview System.

This implementation provides improved error handling, heartbeat functionality,
and better async task management to prevent blocking during LLM operations.
"""

import asyncio
import json
import os
import re
import logging
import time
import threading
import uuid
import base64
import traceback
from typing import Dict, Any, Optional, Set
from websockets import serve, ConnectionClosed

from app.websocket.enhanced_stream_processor import EnhancedStreamProcessor
from app.websocket.protocol import encode_message, decode_message, validate_message
from app.state.session import Session
from app.utils.error_handler import ErrorHandler


class WebSocketServer:
    """
    Enhanced WebSocket server with improved error handling and task management.
    
    This server ensures that long-running operations like LLM processing don't
    block WebSocket communication and state updates.
    """
    
    def __init__(
        self, 
        host: str, 
        port: int, 
        state_manager, 
        stt_service, 
        tts_service, 
        llm_client,
        error_handler=None, 
        heartbeat_service=None
    ):
        self.host = host
        self.port = port
        self.state_manager = state_manager
        self.stt_service = stt_service
        self.tts_service = tts_service
        self.llm_client = llm_client
        self.error_handler = error_handler
        self.heartbeat_service = heartbeat_service
        self.server = None
        self.active_connections: Dict[str, Any] = {}
        self.logger = logging.getLogger("websocket")
        
        # Initialize client capabilities tracking
        self.client_capabilities = {}
        
        # Initialize stream processor
        self.stream_processor = EnhancedStreamProcessor(
            state_manager,
            stt_service,
            tts_service,
            llm_client,
            error_handler
        )
        self.logger.info("Enhanced Stream Processor initialized")
        
        # Task tracking for proper management
        self.tasks: Set[asyncio.Task] = set()
        self.session_tasks: Dict[str, Set[asyncio.Task]] = {}
        
        # health checks and self-healing of Ollama / AllTalk (see app/supervisor.py)
        from app.supervisor import Supervisor
        self.supervisor = Supervisor(tts_service=tts_service, llm_client=llm_client)
        self._health_task = None
        self._last_status_text = ""

        self.logger.info("Enhanced WebSocket server initialized")

    async def start(self):
        """Start the WebSocket server"""
        self.server = await serve(
            self.handle_connection,
            self.host,
            self.port,
            ping_interval=30,
            ping_timeout=10,
            max_size=10485760  # Increase to 10MB (default is ~1MB)
        )
        self.logger.info(f"WebSocket server started on {self.host}:{self.port}")
        self._health_task = asyncio.create_task(self._health_loop())
        print(f"\nVR Interview Server running at ws://{self.host}:{self.port}")
        print("Press Ctrl+C to stop the server\n")

    async def shutdown(self):
        """Gracefully shutdown the WebSocket server"""
        if self._health_task:
            self._health_task.cancel()
        if self.server:
            self.logger.info("Shutting down WebSocket server...")
            self.server.close()
            await self.server.wait_closed()
            
            # Stop heartbeats if available
            if self.heartbeat_service:
                await self.heartbeat_service.stop_all()
            
            # Cancel all running tasks
            for task in self.tasks:
                if not task.done():
                    task.cancel()
            
            # Wait for tasks to cancel
            if self.tasks:
                await asyncio.gather(*self.tasks, return_exceptions=True)
            
            self.logger.info("WebSocket server shut down")

    async def _broadcast_status(self):
        """Tell every connected headset what is wrong (or that it is fine again); text is empty when all is well."""
        text = self.supervisor.status_text()
        self._last_status_text = text
        for sid in list(self.active_connections):
            await self._send_json(sid, {"type": "server_status", "text": text,
                                        "llm": self.supervisor.llm_ok, "voice": self.supervisor.voice_ok,
                                        "restarting": self.supervisor.restarting})

    async def _health_loop(self):
        """Every 20 s: probe Ollama and AllTalk, log changes, notify the headsets, restart a dead voice engine."""
        await asyncio.sleep(5)
        while True:
            try:
                before = (self.supervisor.llm_ok, self.supervisor.voice_ok)
                await self.supervisor.check()
                after = (self.supervisor.llm_ok, self.supervisor.voice_ok)
                if after != before:
                    self.logger.warning(f"Dependency state changed: language model ok={after[0]}, voice ok={after[1]}")
                if self.supervisor.status_text() != self._last_status_text:
                    await self._broadcast_status()
                if self.supervisor.voice_ok and not before[1]:
                    self.supervisor.tts_failures = 0   # just came (back) up: forget failures from while it was down
                elif (not self.supervisor.voice_ok and self.supervisor.voice_seen_ok
                      and self.supervisor.auto_restart_voice and not self.supervisor.restarting):
                    self.supervisor.tts_failures = max(self.supervisor.tts_failures, 2)   # was up, now not answering: no need to wait for replies to fail
                if self.supervisor.voice_needs_restart():
                    asyncio.create_task(self.supervisor.restart_voice(self._broadcast_status))
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger.error(f"Health check error: {e}", exc_info=True)
            await asyncio.sleep(20)

    def _note_tts(self, ok: bool):
        """Count real synthesis results; two failures in a row restart the voice engine."""
        try:
            self.supervisor.note_tts(ok)
            if self.supervisor.voice_needs_restart():
                asyncio.create_task(self.supervisor.restart_voice(self._broadcast_status))
        except Exception as e:
            self.logger.error(f"TTS bookkeeping failed: {e}")

    async def handle_connection(self, websocket, path):
        """Handle a new WebSocket connection"""
        session_id = str(uuid.uuid4())
        self.logger.info(f"New connection established: {session_id}")
        
        # Create a new session
        session = Session(session_id, websocket)
        self.active_connections[session_id] = websocket
        self.session_tasks[session_id] = set()
        
        # Register session with state manager
        self.state_manager.create_session(session_id, session)
        
        # Send initial message with session ID to synchronize client and server IDs
        await websocket.send(json.dumps({
            "type": "session_init",
            "session_id": session_id,
            "timestamp": time.time()
        }))
        
        # Send initial IDLE state
        await self.state_manager.transition_state(session_id, "IDLE", {
            "message": "Ready for conversation"
        })
        if self._last_status_text:
            await self._send_json(session_id, {"type": "server_status", "text": self._last_status_text,
                                               "llm": self.supervisor.llm_ok, "voice": self.supervisor.voice_ok,
                                               "restarting": self.supervisor.restarting})
        
        try:
            async for message in websocket:
                # Process the incoming message in a separate task
                task = asyncio.create_task(
                    self.process_message(session_id, message)
                )
                # Track the task
                self._track_task(task, session_id)
                
        except ConnectionClosed:
            self.logger.info(f"Connection closed: {session_id}")
        except Exception as e:
            self.logger.error(f"Error in connection handler: {e}")
            if self.error_handler:
                await self.error_handler.handle_error(
                    ErrorHandler.WEBSOCKET_ERROR,
                    session_id,
                    e,
                    {"websocket": websocket}
                )
        finally:
            # Clean up session
            await self._cleanup_session(session_id)

    def _track_task(self, task: asyncio.Task, session_id: Optional[str] = None):
        """Track a task for proper cleanup"""
        self.tasks.add(task)
        
        # Add to session-specific tasks if session_id provided
        if session_id and session_id in self.session_tasks:
            self.session_tasks[session_id].add(task)
            
        # Set up callback to remove task when done
        task.add_done_callback(lambda t: self._remove_task(t, session_id))
    
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
            
    async def _safety_timeout(self, session_id: str, timeout_seconds: float):
        """Force transition to WAITING state if processing takes too long"""
        try:
            await asyncio.sleep(timeout_seconds)
            
            # Check current state
            current_state = self.state_manager.get_session_state(session_id)
            
            # If still in PROCESSING state after timeout, force transition to WAITING
            if current_state == "PROCESSING":
                self.logger.warning(f"Safety timeout triggered for session {session_id}")
                await self.state_manager.transition_state(session_id, "WAITING", {
                    "message": "Ready for next question (timeout recovery)"
                })
                
        except asyncio.CancelledError:
            # Task was cancelled normally
            pass
        except Exception as e:
            self.logger.error(f"Error in safety timeout: {e}")
    
    def _remove_task(self, task: asyncio.Task, session_id: Optional[str] = None):
        """Remove a completed task from tracking sets"""
        if task in self.tasks:
            self.tasks.remove(task)
            
        if session_id and session_id in self.session_tasks:
            if task in self.session_tasks[session_id]:
                self.session_tasks[session_id].remove(task)
    
    async def _cleanup_session(self, session_id: str):
        """Clean up a session's resources"""
        self.logger.info(f"Starting cleanup for session: {session_id}")
        
        # Clean up stream processor tracking if available
        if hasattr(self, 'stream_processor') and self.stream_processor is not None:
            # Log cleanup action
            self.logger.info(f"Cleaning up session {session_id} from stream processor")
        
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

    async def process_message(self, session_id: str, message: str):
        """Process an incoming WebSocket message"""
        try:
            # Decode and validate the message
            msg_data = decode_message(message)
            if not validate_message(msg_data):
                await self.send_error(session_id, 400, "Invalid message format")
                return
                
            msg_type = msg_data.get("type")
            
            # Extract client's session ID from the message if available
            client_session_id = msg_data.get("session_id", session_id)
            
            # Handle session ID mismatch (common with reconnections)
            if client_session_id != session_id and client_session_id:
                self.logger.info(f"Session ID mismatch: Message uses {client_session_id}, server using {session_id}")
                # For capabilities, we'll use the server's session ID but log the client's
                if msg_type == "client_capabilities":
                    self.logger.info(f"Using server session ID {session_id} for client capabilities")
                    # No change needed, we'll use the server's session ID
                else:
                    # For other message types, consider using the client's session ID
                    # This is usually safe for control messages, playback_complete, etc.
                    # But we'll keep using server's for audio data
                    if msg_type != "audio_data":
                        self.logger.info(f"Using client-provided session ID {client_session_id} for {msg_type} message")
                        session_id = client_session_id
                        # Also store this session_id in our tracking sets if not already present
                        if msg_type == "streaming_status" and session_id not in self.streaming_sessions and "started" in msg_data.get("status", ""):
                            self.logger.info(f"Adding missing session {session_id} to streaming_sessions from streaming_status message")
                            self.streaming_sessions.add(session_id)
            
            self.logger.debug(f"Processing message type: {msg_type} for session {session_id}")
            
            # Route message based on type
            if msg_type == "audio_data":
                await self.process_audio(session_id, msg_data)
            elif msg_type == "ping":
                await self.send_pong(session_id)
            elif msg_type == "control":
                await self.process_control(session_id, msg_data)
            elif msg_type == "playback_complete":
                await self.handle_playback_complete(session_id, msg_data)
            elif msg_type == "client_capabilities":
                await self.handle_client_capabilities(websocket=self.active_connections.get(session_id), 
                                                    session_id=session_id, 
                                                    message=msg_data)
            elif msg_type == "streaming_status":
                await self.handle_streaming_status(session_id, msg_data)
                
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
            
            # Use error handler if available
            if self.error_handler:
                await self.error_handler.handle_error(
                    ErrorHandler.SYSTEM_ERROR,
                    session_id,
                    e,
                    {"websocket": self.active_connections.get(session_id)}
                )
            else:
                # Basic error handling fallback
                await self.send_error(session_id, 500, "Internal server error")
                await self.state_manager.transition_state(session_id, "ERROR", {
                    "error": str(e)
                })

    async def process_audio(self, session_id: str, message: Dict[str, Any]):
        """
        Process incoming audio data.
        This is where we need to carefully manage async operations to prevent blocking.
        """
        try:
            # Check current state
            current_state = self.state_manager.get_session_state(session_id)
            if str(current_state) == "ERROR":
                # an earlier failure (e.g. a speech-to-text timeout) must not leave the session deaf: speaking again or starting over is the retry
                self.logger.info(f"Recovering session {session_id} from ERROR")
                await self.state_manager.transition_state(session_id, "WAITING", {"message": "Recovered, listening again"})
                current_state = self.state_manager.get_session_state(session_id)
            if current_state not in ["IDLE", "WAITING"]:
                self.logger.warning(
                    f"Received audio when in {current_state} state. Ignoring."
                )
                return
                
            # Transition to LISTENING
            await self.state_manager.transition_state(session_id, "LISTENING", {
                "message": "Receiving audio"
            })
            
            # Decode audio data
            audio_data = base64.b64decode(message.get("data", ""))
            if not audio_data:
                await self.send_error(session_id, 400, "Empty audio data")
                return
                
            # Determine whether to use streaming or standard pipeline
            config = getattr(self.llm_client, 'config', {}) or {}
            use_streaming = config.get('use_streaming', True)
            
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
            else:
                # Use standard pipeline
                task = asyncio.create_task(
                    self.process_audio_pipeline(session_id, audio_data)
                )
                self._track_task(task, session_id)
            
        except Exception as e:
            self.logger.error(f"Error processing audio: {e}")
            
            # Try to use error handler if available
            if self.error_handler:
                await self.error_handler.handle_error(
                    ErrorHandler.SYSTEM_ERROR,
                    session_id,
                    e,
                    {"websocket": self.active_connections.get(session_id)}
                )
            else:
                # Fallback error handling
                await self.send_error(session_id, 500, "Error processing audio")
                await self.state_manager.transition_state(session_id, "ERROR", {
                    "error": str(e)
                })

    async def process_audio_pipeline(self, session_id: str, audio_data: bytes, forced_transcript: Optional[str] = None):
        """
        Full audio processing pipeline - runs asynchronously to avoid blocking the WebSocket.
        This improved version uses granular processing states for better progress tracking.
        """
        websocket = self.active_connections.get(session_id)
        progress_task = None
        heartbeat_task = None
        safety_timer = None
        turn_t0 = time.time()   # the candidate's audio has just arrived (the end of their speech is a moment before this)

        try:
            # Create a separate task for heartbeat if available
            if self.heartbeat_service and websocket:
                heartbeat_task = asyncio.create_task(
                    self.heartbeat_service.start_heartbeat(
                        session_id,
                        lambda msg: websocket.send(json.dumps(msg)),
                        {"processing_stage": "transcribing"}
                    )
                )
            else:
                # Use our internal heartbeat implementation
                heartbeat_task = asyncio.create_task(
                    self._send_heartbeat_during_llm(session_id, websocket)
                )
            
            # Start a safety timer that will force transition to WAITING if processing takes too long
            safety_timer = asyncio.create_task(
                self._safety_timeout(session_id, 25.0)  # 25 second timeout
            )
            
            # Transition to PROCESSING_STT (new granular state)
            await self.state_manager.transition_state(session_id, "PROCESSING_STT", {
                "message": "Transcribing your speech to text",
                "progress": 0.0
            })
            
            # Transcribe audio (CPU intensive) in a separate thread
            try:
                if forced_transcript is not None:
                    # Interviewer-initiated turn (control action "begin"): there is no audio to transcribe
                    transcript = forced_transcript
                else:
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
            except Exception as stt_error:
                # Transition to ERROR state
                await self.state_manager.transition_state(session_id, "ERROR", {
                    "message": f"Speech transcription error: {str(stt_error)}",
                    "error_type": "STT_ERROR"
                })
                
                if self.error_handler:
                    # Handle STT errors with error handler
                    success, _ = await self.error_handler.handle_error(
                        ErrorHandler.STT_ERROR,
                        session_id,
                        stt_error,
                        {"websocket": websocket}
                    )
                    if success:
                        # Cancel safety timer
                        if safety_timer and not safety_timer.done():
                            safety_timer.cancel()
                        # If handled successfully, stop here
                        return
                
                # Re-raise the error if not handled
                raise
            
            # Log the transcript
            self.logger.info(f"Transcription: {transcript}")
            stt_s = time.time() - turn_t0
            if not transcript.strip():
                await self.state_manager.transition_state(session_id, "WAITING", {
                    "message": "No speech detected, please try again"
                })
                # Cancel all background tasks
                if heartbeat_task and not heartbeat_task.done():
                    heartbeat_task.cancel()
                if safety_timer and not safety_timer.done():
                    safety_timer.cancel()
                return
            
            # Get the current session and its conversation history
            session = self.state_manager.get_session(session_id)
            if not session:
                self.logger.error(f"Session {session_id} not found")
                # Cancel all background tasks
                if heartbeat_task and not heartbeat_task.done():
                    heartbeat_task.cancel()
                if safety_timer and not safety_timer.done():
                    safety_timer.cancel()
                return
            
            # Get the current state info for metadata
            metadata = {}
            if hasattr(session, "metadata"):
                metadata = session.metadata.copy() if session.metadata else {}
            
            # Determine interaction stage based on context and metadata
            interaction_stage = metadata.get("stage", None)
            
            # If no explicit stage, try to infer it
            if not interaction_stage:
                context = session.get_context()
                # First message is greeting
                if not context or len(context) <= 1:
                    interaction_stage = "greeting"
                # Later stages inferred by counting turns
                elif len(context) > 10:
                    interaction_stage = "wrap_up"
            
            # Transition to PROCESSING_LLM (new granular state)
            await self.state_manager.transition_state(session_id, "PROCESSING_LLM", {
                "message": "Generating response to your question",
                "transcript": transcript,
                "stage": interaction_stage,
                "progress": 0.0
            })
            
            # Cancel previous heartbeat task if it exists
            if heartbeat_task and not heartbeat_task.done():
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
            
            # Start a new heartbeat for LLM processing
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
            
            # Streamed reply: speak sentence 1 while the model is still writing the rest (config ollama.stream_reply).
            # It returns False when it failed before anything was sent, and the normal path below then runs.
            if self.llm_client.config.get("stream_reply", False) and hasattr(self.llm_client, "stream_response"):
                if await self._streamed_turn(session_id, transcript, session, interaction_stage, heartbeat_task, safety_timer,
                                             turn_t0=turn_t0, stt_s=stt_s):
                    return

            # Generate LLM response with a timeout to prevent hanging
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
                
                # Transition to ERROR state
                await self.state_manager.transition_state(session_id, "ERROR", {
                    "message": "LLM response generation timed out, but still working in background",
                    "error_type": "LLM_TIMEOUT"
                })
                
                if self.error_handler:
                    await self.error_handler.handle_error(
                        ErrorHandler.LLM_ERROR,
                        session_id,
                        Exception("LLM response generation timed out"),
                        {"websocket": websocket, "transcript": transcript}
                    )
                
                # Cancel all background tasks
                if heartbeat_task and not heartbeat_task.done():
                    heartbeat_task.cancel()
                if safety_timer and not safety_timer.done():
                    safety_timer.cancel()
                return
            except Exception as llm_error:
                # Transition to ERROR state
                await self.state_manager.transition_state(session_id, "ERROR", {
                    "message": f"LLM response generation error: {str(llm_error)}",
                    "error_type": "LLM_ERROR"
                })
                
                # Cancel heartbeat task
                if heartbeat_task and not heartbeat_task.done():
                    heartbeat_task.cancel()
                
                if self.error_handler:
                    # Handle LLM errors with error handler
                    success, _ = await self.error_handler.handle_error(
                        ErrorHandler.LLM_ERROR,
                        session_id,
                        llm_error,
                        {
                            "websocket": websocket,
                            "transcript": transcript
                        }
                    )
                    if success:
                        # Cancel safety timer
                        if safety_timer and not safety_timer.done():
                            safety_timer.cancel()
                        return
                
                # Re-raise if not handled
                raise
            
            # Cancel heartbeat task
            if heartbeat_task and not heartbeat_task.done():
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
            
            # Add the exchange to session history
            session.add_interaction(transcript, response)
            
            self.logger.info(f"LLM Response: {response}")
            
            # Transition to PROCESSING_TTS (new granular state)
            await self.state_manager.transition_state(session_id, "PROCESSING_TTS", {
                "message": "Converting response to speech",
                "progress": 0.0
            })
            
            # Start a new heartbeat for TTS processing
            if self.heartbeat_service and websocket:
                heartbeat_task = asyncio.create_task(
                    self.heartbeat_service.start_heartbeat(
                        session_id,
                        lambda msg: websocket.send(json.dumps(msg)),
                        {"processing_stage": "generating_speech"}
                    )
                )
            else:
                # Use our internal heartbeat implementation
                heartbeat_task = asyncio.create_task(
                    self._send_heartbeat_during_llm(session_id, websocket)
                )
            
            # Generate speech from text with timeout
            tts_future = None
            tts_first, tts_rest = self._split_for_speech(response)
            rest_future = None
            try:
                tts_future = asyncio.create_task(
                    asyncio.to_thread(self.tts_service.synthesize, tts_first)
                )
                
                # Add a timeout for TTS processing but let the task continue
                try:
                    audio_response = await asyncio.wait_for(asyncio.shield(tts_future), timeout=15.0)
                except asyncio.TimeoutError:
                    # a busy machine can make the voice slow; keep waiting for the same synthesis instead of dropping it
                    self.logger.warning(f"TTS slow for session {session_id}, waiting longer")
                    audio_response = await asyncio.wait_for(asyncio.shield(tts_future), timeout=30.0)
                
                self._note_tts(True)

                # Update TTS progress to complete
                await self.state_manager.transition_state(session_id, "PROCESSING_TTS", {
                    "message": "Audio generation complete",
                    "progress": 1.0
                })
            except asyncio.TimeoutError:
                self.logger.warning(f"TTS timeout for session {session_id}")
                self._note_tts(False)
                
                # Transition to ERROR state
                await self.state_manager.transition_state(session_id, "ERROR", {
                    "message": "Audio generation timed out",
                    "error_type": "TTS_TIMEOUT"
                })
                
                # Don't cancel the TTS future - let it continue in the background
                # Instead, keep a reference to it for later retrieval
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
                
                # Cancel only heartbeat task but keep safety timer
                if heartbeat_task and not heartbeat_task.done():
                    heartbeat_task.cancel()
                    
                # Don't return yet - let the server transition to WAITING state normally
                audio_response = None
            except Exception as tts_error:
                # Transition to ERROR state
                await self.state_manager.transition_state(session_id, "ERROR", {
                    "message": f"Audio generation error: {str(tts_error)}",
                    "error_type": "TTS_ERROR"
                })
                
                if self.error_handler:
                    # Handle TTS errors with error handler
                    success, _ = await self.error_handler.handle_error(
                        ErrorHandler.TTS_ERROR,
                        session_id,
                        tts_error,
                        {
                            "websocket": websocket,
                            "text_response": response
                        }
                    )
                    if success:
                        # Cancel safety timer
                        if safety_timer and not safety_timer.done():
                            safety_timer.cancel()
                        return
                
                # Re-raise if not handled
                raise
            
            # Stop all background tasks
            if heartbeat_task and not heartbeat_task.done():
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
            
            if safety_timer and not safety_timer.done():
                safety_timer.cancel()
                try:
                    await safety_timer
                except asyncio.CancelledError:
                    pass
            
            # Transition to RESPONDING state
            await self.state_manager.transition_state(session_id, "RESPONDING", {
                "message": "Playing response"
            })
            
            # Start the voice for the remainder while the first part is already on its way to the headset
            if tts_rest and audio_response:
                rest_future = asyncio.create_task(
                    asyncio.to_thread(self.tts_service.synthesize, tts_rest)
                )

            # Send audio response to client
            await self.send_audio_response(session_id, audio_response, tts_first if rest_future else response,
                                           more=rest_future is not None)

            if rest_future is not None:
                try:
                    rest_audio = await asyncio.wait_for(rest_future, timeout=15.0)
                    await self.send_audio_response(session_id, rest_audio, response)
                except Exception as rest_error:
                    self.logger.warning(f"Second speech chunk failed for {session_id}: {rest_error}")
                    await self.send_audio_response(session_id, None, response, more=False)
            
            # Wait a moment to ensure audio is received
            await asyncio.sleep(0.5)
            
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
            
            # Transition to ERROR state
            await self.state_manager.transition_state(session_id, "ERROR", {
                "message": f"System error: {str(e)}",
                "error_type": "SYSTEM_ERROR"
            })
            
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
                    self.logger.error(
                        f"Error handler failed: {handler_error}\n"
                        f"{traceback.format_exc()}"
                    )
            
            # Fallback error handling
            await self.state_manager.transition_state(session_id, "ERROR", {
                "error": str(e)
            })
            await self.send_error(session_id, 500, "Error processing request")
            
            # Always try to transition back to WAITING to prevent client hang
            try:
                await asyncio.sleep(1)  # Give a moment for the error to be displayed
                await self.state_manager.transition_state(session_id, "WAITING", {
                    "message": "Ready for next input after error"
                })
            except Exception as transition_error:
                self.logger.error(f"Failed to transition to WAITING after error: {transition_error}")

    FIRST_SPLIT_FROM = 60      # opening sentences longer than this are cut at a comma / clause
    FIRST_SPLIT_MIN = 25       # but never leaving a clip shorter than this

    def _split_first_chunk(self, sentence: str) -> list:
        """[first clause, rest] when the opening sentence is long and has a comma, semicolon, colon or dash that leaves both halves a
        reasonable size; otherwise [sentence]. The first clip is synthesised and sent while the rest is still being voiced."""
        if len(sentence) <= self.FIRST_SPLIT_FROM:
            return [sentence]
        for m in re.finditer(r"[,;:]\s|\s[-–—]+\s", sentence):
            cut = m.start() + (1 if sentence[m.start()] in ",;:" else 0)
            head, rest = sentence[:cut].strip(), sentence[m.end():].strip()
            if len(head) > 110:
                break
            if len(head) >= self.FIRST_SPLIT_MIN and len(rest) >= 15:
                return [head, rest]
        return [sentence]

    def _warm_up(self):
        """Runs in a thread when an interview begins: a speech clip through the STT worker, and the local model loaded for 24 h when the
        hosted model is switched on (it answers a turn itself when the API is slow)."""
        try:
            url = getattr(self.stt_service, "remote_url", None)
            if url:
                import requests
                took = requests.post(f"{url}/warm", data=b"", timeout=30).json().get("seconds")
                self.logger.info(f"STT warmed in {took}s")
            from services.llm import anthropic_backend
            if anthropic_backend.wanted() and hasattr(self.llm_client, "warm_local"):
                if hasattr(self.llm_client, "_anth"):
                    self.llm_client._anth.preconnect()      # opens the connection only: no key sent, no tokens, no cost
                self.llm_client.warm_local()
        except Exception as e:
            self.logger.warning(f"Warm-up skipped: {e}")

    def _tts_engine(self) -> str:
        return ((getattr(self.tts_service, "config", None) or {}).get("engine") or "alltalk").lower()

    STREAM_MIN_CHUNK_CHARS = 30   # shorter sentences are joined with the next one (a tiny clip sounds choppy and leaves a gap)

    async def _streamed_turn(self, session_id, transcript, session, interaction_stage, heartbeat_task, safety_timer,
                             turn_t0=None, stt_s=0.0) -> bool:
        """
        One reply with the model's sentences going to the voice as they are written.

        Chunks leave in order with the same contract as the normal path (`more` is only true when a further chunk really
        follows, the last chunk carries the full reply text). Returns True when the turn was handled, False when streaming
        failed before anything was sent (the caller then uses the normal path).
        """
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()
        started = time.time()
        context = session.get_context()

        def produce():
            try:
                for sentence in self.llm_client.stream_response(transcript, context, interaction_stage):
                    loop.call_soon_threadsafe(queue.put_nowait, sentence)
            except Exception as e:  # reported to the consumer below
                loop.call_soon_threadsafe(queue.put_nowait, e)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        # A short first sentence ("Got it.") is joined with the next one only when the voice is slow (XTTS needs ~2 s per
        # sentence, so a tiny first clip would leave a gap before the next one). The fast Kokoro voice sends it at once.
        min_chunk = 8 if self._tts_engine() == "kokoro" else self.STREAM_MIN_CHUNK_CHARS
        first_sentence_at = [0.0]
        chunks: list = []            # {"text", "task"}
        sentences: list = []
        state = {"done": False, "error": None}
        progress = asyncio.Event()

        def add_chunk(text):
            chunks.append({"text": text, "task": asyncio.create_task(asyncio.to_thread(self.tts_service.synthesize, text))})
            progress.set()

        async def feeder():
            buf = ""
            try:
                while True:
                    item = await queue.get()
                    if item is None:
                        break
                    if isinstance(item, Exception):
                        state["error"] = item
                        continue
                    sentences.append(item)
                    if len(sentences) == 1:
                        first_sentence_at[0] = time.time() - started
                        self.logger.info(f"Streamed reply: first sentence ready after {first_sentence_at[0]:.2f}s")
                    pieces = [item]
                    if len(sentences) == 1 and self._tts_engine() == "kokoro":
                        pieces = self._split_first_chunk(item)     # a long opening sentence leaves in two clips so the voice starts sooner
                    for piece in pieces:
                        buf = f"{buf} {piece}".strip()
                        if len(buf) >= min_chunk:
                            add_chunk(buf)
                            buf = ""
                if buf:
                    add_chunk(buf)
            finally:
                state["done"] = True
                progress.set()

        async def wait_for(condition):
            while not condition():
                progress.clear()
                if condition():
                    break
                await progress.wait()

        producer = asyncio.create_task(asyncio.to_thread(produce))
        feeder_task = asyncio.create_task(feeder())
        sent = 0
        try:
            await wait_for(lambda: len(chunks) > 0 or state["done"])
            if not chunks:   # the model gave nothing usable: let the normal path try
                self.logger.warning("Streamed reply produced no sentence; falling back")
                return False

            await self.state_manager.transition_state(session_id, "PROCESSING_TTS", {"message": "Converting response to speech", "progress": 0.0})
            index = 0
            while True:
                await wait_for(lambda: len(chunks) > index or state["done"])
                if len(chunks) <= index:
                    break
                try:
                    audio = await asyncio.wait_for(asyncio.shield(chunks[index]["task"]), timeout=45.0)
                    self._note_tts(True)
                except Exception as tts_error:
                    self.logger.warning(f"Streamed chunk {index} failed to synthesize: {tts_error}")
                    self._note_tts(False)
                    audio = None
                if index == 0:
                    for task in (heartbeat_task, safety_timer):
                        if task and not task.done():
                            task.cancel()
                    await self.state_manager.transition_state(session_id, "RESPONDING", {"message": "Playing response"})
                    self.logger.info(f"Streamed reply: first audio ready after {time.time() - started:.2f}s")
                # is there a later chunk? (only the end of the stream or the next chunk can tell)
                await wait_for(lambda: len(chunks) > index + 1 or state["done"])
                more = len(chunks) > index + 1
                text = chunks[index]["text"] if more else " ".join(sentences)
                await self.send_audio_response(session_id, audio, text, more=more)
                if index == 0 and turn_t0:
                    # what the candidate actually waits for (from the moment their audio arrived), and where the time went
                    self.logger.info(
                        f"LIVE LATENCY: first audio chunk sent {time.time() - turn_t0:.2f}s after the candidate's audio arrived "
                        f"(speech-to-text {stt_s:.2f}s, LLM first sentence at +{first_sentence_at[0]:.2f}s, "
                        f"first chunk {len(chunks[0]['text'])} chars, voice {self._tts_engine()}, "
                        f"{len(chunks[0]['text'].split())} words in chunk 1)")
                sent += 1
                index += 1
                if not more:
                    break

            await feeder_task
            response = " ".join(sentences)
            session.add_interaction(transcript, response)
            self.logger.info(f"LLM Response: {response}")
            self.logger.info(f"Streamed reply finished: {sent} chunk(s), {time.time() - started:.2f}s total")
            await asyncio.sleep(0.5)
            await self.state_manager.transition_state(session_id, "WAITING", {"message": "Waiting for user input"})
            return True
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger.error(f"Streamed reply failed after {sent} chunk(s): {e}\n{traceback.format_exc()}")
            if sent == 0:
                return False
            try:
                session.add_interaction(transcript, " ".join(sentences))
                await self.state_manager.transition_state(session_id, "WAITING", {"message": "Ready for next input after error"})
            except Exception:
                pass
            return True

    async def process_control(self, session_id: str, message: Dict[str, Any]):
        """Process control messages from client"""
        action = message.get("action")
        
        if action == "reset":
            # Reset the conversation (an interview that actually happened is saved to exports/ first)
            session = self.state_manager.get_session(session_id)
            if session:
                await self._finish_interview(session_id, session)
                session.reset()
                await self.state_manager.transition_state(session_id, "IDLE", {
                    "message": "Conversation reset"
                })
                
        elif action == "stop":
            # Stop the current response
            current_state = self.state_manager.get_session_state(session_id)
            if current_state in ["RESPONDING", "PROCESSING"]:
                # Cancel any ongoing tasks for this session
                if session_id in self.session_tasks:
                    for task in list(self.session_tasks[session_id]):
                        if not task.done():
                            task.cancel()
                
                # Transition to WAITING state
                await self.state_manager.transition_state(session_id, "WAITING", {
                    "message": "Response stopped"
                })
                
        elif action == "coach":
            # Job-coach review of the last finished interview
            task = asyncio.create_task(self._run_coach(session_id))
            self._track_task(task, session_id)

        elif action == "timeout":
            # Idle timeout reported by the client: nothing to do on the server
            self.logger.info(f"Client idle timeout for session {session_id}")

        elif action == "begin":
            # The interviewer speaks first: run the normal pipeline with a canned candidate greeting instead of audio
            threading.Thread(target=self._warm_up, daemon=True).start()   # keep speech-to-text (and the local fallback model) warm
            job_id = message.get("job")
            if job_id and hasattr(self.llm_client, "set_job"):
                self.llm_client.set_job(job_id)
            # the headset chooses which interviewer (character) is sitting there: use her/his name and a matching voice
            interviewer_name = message.get("interviewer")
            if interviewer_name:
                self.llm_client.interviewer_name = interviewer_name
                if hasattr(self.tts_service, "set_interviewer"):
                    self.tts_service.set_interviewer(interviewer_name)   # picks that interviewer's voice when engine = kokoro
            voice = message.get("voice")
            if voice and hasattr(self.tts_service, "set_voice"):
                self.tts_service.set_voice(voice)
            current_state = self.state_manager.get_session_state(session_id)
            if str(current_state) == "ERROR":
                # an earlier failure (e.g. a speech-to-text timeout) must not leave the session deaf: speaking again or starting over is the retry
                self.logger.info(f"Recovering session {session_id} from ERROR")
                await self.state_manager.transition_state(session_id, "WAITING", {"message": "Recovered, listening again"})
                current_state = self.state_manager.get_session_state(session_id)
            if current_state not in ["IDLE", "WAITING"]:
                self.logger.warning(f"Ignoring 'begin' while in state {current_state}")
            else:
                await self.state_manager.transition_state(session_id, "LISTENING", {
                    "message": "Starting interview"
                })
                task = asyncio.create_task(
                    self.process_audio_pipeline(session_id, b"", forced_transcript="Hello.")
                )
                self._track_task(task, session_id)

        elif action == "say":
            # Test/dev only (the headset never sends this): run one candidate turn from typed text instead of audio,
            # so a scripted interview can be replayed through the real LLM, voice, lip-sync and export path
            text = (message.get("text") or "").strip()
            current_state = self.state_manager.get_session_state(session_id)
            if str(current_state) == "ERROR":
                await self.state_manager.transition_state(session_id, "WAITING", {"message": "Recovered, listening again"})
                current_state = self.state_manager.get_session_state(session_id)
            if text and current_state in ["IDLE", "WAITING"]:
                await self.state_manager.transition_state(session_id, "LISTENING", {"message": "Typed turn"})
                task = asyncio.create_task(self.process_audio_pipeline(session_id, b"", forced_transcript=text))
                self._track_task(task, session_id)
            else:
                self.logger.warning(f"Ignoring 'say' (state {current_state}, text {'present' if text else 'empty'})")

        elif action == "ping":
            # Simple ping to keep connection alive
            await self.send_pong(session_id)

    # ---- interview export and job-coach review ----------------------------------------------------------------

    async def _send_json(self, session_id: str, payload: Dict[str, Any]):
        websocket = self.active_connections.get(session_id)
        if not websocket:
            return
        payload.setdefault("session_id", session_id)
        payload.setdefault("timestamp", time.time())
        try:
            await websocket.send(encode_message(payload))
        except Exception as e:
            self.logger.warning(f"Could not send {payload.get('type')} to {session_id}: {e}")

    async def _send_visemes(self, session_id: str, audio_data: bytes, seq: int):
        """Analyse a voice chunk with Rhubarb and send its mouth-shape timeline (the headset has already started playing it)."""
        try:
            from app import lipsync
            cues = await asyncio.to_thread(lipsync.analyze_wav, audio_data)
            if cues:
                await self._send_json(session_id, {"type": "visemes", "seq": seq, "cues": cues})
        except Exception as e:
            self.logger.warning(f"Mouth cues failed for chunk {seq}: {e}")

    async def _finish_interview(self, session_id: str, session):
        """Save the interview that just ended (if there was one) and remember it for the coach."""
        try:
            from app import interview_review as review
            from services.llm.scenarios import job_interview
            history = list(getattr(session, "history", []) or [])
            exchanges = review.build_exchanges(history)
            if len(exchanges) < 2:
                return
            persona = getattr(self.llm_client, "persona", {}) or {}
            job_id = persona.get("job_id") or "software_engineer"
            job = job_interview.JOB_CATALOG.get(job_id, {})
            record = {
                "session_id": session_id,
                "job_id": job_id,
                "job_label": job.get("label", job_id),
                "company": job.get("company", ""),
                "interviewer": getattr(self.llm_client, "interviewer_name", "") or "",
                "started": history[0].get("timestamp", ""),
                "exchanges": exchanges,
                "closing": (history[-1].get("system_response") or "") if history else "",
            }
            base = await asyncio.to_thread(review.export_interview, record)
            self.last_interviews = getattr(self, "last_interviews", {})
            self.last_interviews[session_id] = {"record": record, "base": base}
            await self._send_json(session_id, {"type": "export_saved", "filename": os.path.basename(base) + ".md",
                                               "questions": len(exchanges)})
        except Exception as e:
            self.logger.error(f"Could not export interview for {session_id}: {e}", exc_info=True)

    async def _run_coach(self, session_id: str):
        try:
            from app import interview_review as review
            from services.llm.scenarios import job_interview
            saved = getattr(self, "last_interviews", {}).get(session_id)
            if not saved:
                await self._send_json(session_id, {"type": "coach_report", "error": "No finished interview to review yet.",
                                                   "summary": "", "strengths": [], "focus": [], "items": []})
                return
            record = saved["record"]
            loop = asyncio.get_running_loop()

            def progress(n, total):
                asyncio.run_coroutine_threadsafe(
                    self._send_json(session_id, {"type": "coach_progress", "done": n, "total": total}), loop)

            self.logger.info(f"Coach review started for {session_id} ({len(record['exchanges'])} answers)")
            started = time.time()
            report = await asyncio.to_thread(review.generate_coach_report, self.llm_client, record,
                                             job_interview.get_job_info(record["job_id"]), progress)
            self.logger.info(f"Coach review finished in {time.time() - started:.1f}s")
            await asyncio.to_thread(review.export_interview, record, report)   # same file name, now with the coach notes
            report["type"] = "coach_report"
            report["filename"] = os.path.basename(saved["base"]) + ".md"
            await self._send_json(session_id, report)
        except Exception as e:
            self.logger.error(f"Coach review failed for {session_id}: {e}", exc_info=True)
            await self._send_json(session_id, {"type": "coach_report", "error": "The coach could not finish the review.",
                                               "summary": "", "strengths": [], "focus": [], "items": []})

    @staticmethod
    def _split_for_speech(text: str, min_first: int = 18):
        """Split a reply after a sentence so the voice can start sooner. Returns (first, rest or '').

        The remainder is synthesized while the first part plays, so the first part must last longer than that takes:
        speech runs about 67 ms per character, synthesis about 0.2 s + 28 ms per character, which needs
        len(first) >= 2 + 0.3 * len(total). Otherwise the whole reply is spoken in one piece (no mid-reply gap).
        """
        text = (text or "").strip()
        need = max(min_first, 2 + 0.3 * len(text))
        for m in re.finditer(r'[.!?]["\')]*\s+', text):
            first, rest = text[:m.end()].strip(), text[m.end():].strip()
            if len(first) >= need and len(rest) >= 15:
                return first, rest
        return text, ""

    async def send_audio_response(
        self, 
        session_id: str, 
        audio_data: bytes,
        text_response: Optional[str] = None,
        more: bool = False
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
                if more:
                    message["more"] = True   # another audio chunk for this reply follows
                self._chunk_seq = getattr(self, "_chunk_seq", 0) + 1
                seq = self._chunk_seq
                message["seq"] = seq         # the mouth cues for this chunk follow in a "visemes" message with the same seq

                # Flag the interviewer's closing reply so the client can run its ending sequence
                if getattr(self.llm_client, "last_stage", None) == "conclusion":
                    message["interview_complete"] = True
                
                # Include text response as a fallback
                if text_response:
                    message["text"] = text_response
                    
                await websocket.send(encode_message(message))
                self.logger.debug(f"Sent audio response to {session_id}, size: {len(audio_data)} bytes")
                task = asyncio.create_task(self._send_visemes(session_id, audio_data, seq))
                self._viseme_tasks = getattr(self, "_viseme_tasks", set())
                self._viseme_tasks.add(task)
                task.add_done_callback(self._viseme_tasks.discard)
                
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

    def _validate_wav_format(self, audio_data: bytes) -> bool:
        """
        Perform basic validation on WAV format to ensure it's playable by the client
        
        Args:
            audio_data: The WAV audio data bytes
            
        Returns:
            True if valid WAV format, False otherwise
        """
        try:
            # Check minimum WAV header size
            if len(audio_data) < 44:
                return False
                
            # Check for RIFF header
            if audio_data[:4] != b'RIFF':
                return False
                
            # Check for WAVE format
            if audio_data[8:12] != b'WAVE':
                return False
                
            # Check for fmt chunk
            if audio_data[12:16] != b'fmt ':
                return False
                
            # Check for data chunk (anywhere in the file after fmt)
            data_chunk_found = b'data' in audio_data[20:1024]
            if not data_chunk_found:
                return False
                
            return True
        except Exception as e:
            self.logger.error(f"Error validating WAV format: {e}")
            return False

    async def handle_playback_complete(self, session_id: str, message: Dict[str, Any]):
        """Handle playback completion notification from client"""
        # Extract client's session ID from the message if available
        client_session_id = message.get("session_id", session_id)
        
        # Log using the appropriate ID
        if client_session_id != session_id:
            self.logger.info(f"Received playback completion from client session {client_session_id}, server session {session_id}")
            # Use the client's session ID if it differs from server's
            session_id = client_session_id
        else:
            self.logger.info(f"Received playback completion for session {session_id}")
        
        # This is just an informational message from the client, no action needed
        # You could optionally use this to trigger follow-up prompts or actions
        
        # Send acknowledgment
        websocket = self.active_connections.get(session_id)
        if not websocket:
            return
            
        try:
            # Send a simple acknowledgment
            ack_message = {
                "type": "playback_ack",
                "session_id": session_id,
                "timestamp": time.time(),
                "message": "Playback completion acknowledged"
            }
            await websocket.send(json.dumps(ack_message))
        except Exception as e:
            self.logger.error(f"Error sending playback acknowledgment: {e}")
    
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
            
            # Get client session ID if provided
            client_session_id = message.get("session_id", "")
            
            # Store capabilities in the server's dictionary
            self.client_capabilities[session_id] = capabilities
            if client_session_id and client_session_id != session_id:
                self.client_capabilities[client_session_id] = capabilities
                
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
            elif session and not hasattr(session, "metadata"):
                # Create metadata if needed
                try:
                    session.metadata = {"client_capabilities": capabilities}
                except Exception as attr_err:
                    self.logger.error(f"Error adding metadata attribute: {attr_err}")
            
            # Send acknowledgment
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
                        "streaming": False  # Explicitly mark streaming as not supported
                    }
                }
            }
            if websocket:
                await websocket.send(encode_message(ack_message))
            else:
                self.logger.warning(f"Could not send capabilities acknowledgment: no websocket")
        except Exception as e:
            self.logger.error(f"Error handling client capabilities: {e}")
            self.logger.debug("Exception details:", exc_info=True)

    async def send_alltalk_file_url(self, session_id, output_file):
        """Send URL for the client to directly download the audio file from AllTalk server"""
        websocket = self.active_connections.get(session_id)
        if not websocket:
            return
            
        alltalk_url = self.tts_service.base_url
        file_url = f"{alltalk_url}/outputs/{output_file}"
        
        message = {
            "type": "audio_file_url",
            "session_id": session_id,
            "timestamp": time.time(),
            "url": file_url,
            "format": "wav",
            "message": "Direct file URL for audio playback"
        }
        await websocket.send(encode_message(message))
        self.logger.info(f"Sent direct file URL: {file_url}")

    async def handle_streaming_status(self, session_id: str, message: Dict[str, Any]):
        """Handle streaming status updates from client (deprecated but kept for compatibility)"""
        # This is a deprecated endpoint but we keep it for compatibility
        self.logger.info(f"Received streaming status message (deprecated): {json.dumps(message)}")
        
        # Inform the client that streaming is not supported
        websocket = self.active_connections.get(session_id)
        if websocket:
            try:
                await websocket.send(encode_message({
                    "type": "system_message",
                    "session_id": session_id,
                    "timestamp": time.time(),
                    "message": "Streaming audio is not supported in this version"
                }))
            except Exception as e:
                self.logger.error(f"Error sending streaming deprecation message: {e}")
    
    # Streaming fallback timer removed - not needed with direct API only
    
    async def send_pong(self, session_id: str):
        """Send pong response to client"""
        websocket = self.active_connections.get(session_id)
        if not websocket:
            return
            
        try:
            message = {
                "type": "pong",
                "session_id": session_id,
                "timestamp": time.time()
            }
            await websocket.send(encode_message(message))
        except Exception as e:
            self.logger.error(f"Error sending pong: {e}")

    async def send_error(self, session_id: str, code: int, message: str):
        """Send error message to client"""
        websocket = self.active_connections.get(session_id)
        if not websocket:
            return
            
        try:
            error_message = {
                "type": "error",
                "session_id": session_id,
                "code": code,
                "message": message,
                "timestamp": time.time()
            }
            await websocket.send(encode_message(error_message))
        except Exception as e:
            self.logger.error(f"Error sending error message: {e}")
    
    async def send_text_message(self, session_id: str, text: str, message_type: str = "system_message"):
        """Send a text message to the client"""
        websocket = self.active_connections.get(session_id)
        if not websocket:
            return
            
        try:
            message = {
                "type": message_type,
                "session_id": session_id,
                "timestamp": time.time(),
                "text": text
            }
            await websocket.send(encode_message(message))
        except Exception as e:
            self.logger.error(f"Error sending text message: {e}")
