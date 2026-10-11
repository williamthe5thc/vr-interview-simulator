"""
Enhanced Stream Processor for VR Interview System.

This module provides optimized processing of audio data with improved
streaming capabilities for faster responses and better user experience.
"""

import asyncio
import json
import logging
import time
from typing import Dict, Any, Optional, List, Callable
import base64
import os
import hashlib
import io

from app.state.manager import StateManager


class EnhancedStreamProcessor:
    """
    Enhanced stream processor with optimized processing pipeline.
    
    Features:
    - Multi-stage parallel processing
    - Optimized direct audio generation
    - Intelligent caching for frequently used responses
    - Advanced error handling and recovery
    """
    
    def __init__(
        self,
        state_manager,
        stt_service,
        tts_service,
        llm_client,
        error_handler=None
    ):
        self.state_manager = state_manager
        self.stt_service = stt_service
        self.tts_service = tts_service
        self.llm_client = llm_client
        self.error_handler = error_handler
        self.logger = logging.getLogger("enhanced_stream")
        
        # Initialize cache
        self.cache_dir = "data/cache/stream"
        os.makedirs(self.cache_dir, exist_ok=True)
        self.audio_chunks_cache = {}
        
        self.logger.info("Enhanced Stream Processor initialized")
    
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
                # Transition to ERROR state
                await self.state_manager.transition_state(session_id, "ERROR", {
                    "message": f"Speech transcription error: {str(e)}",
                    "error_type": "STT_ERROR"
                })
                if self.error_handler:
                    await self.error_handler.handle_error(
                        "STT_ERROR",
                        session_id,
                        e,
                        {"websocket": websocket}
                    )
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
            
            # Determine interaction stage from metadata
            metadata = {}
            if hasattr(session, "metadata"):
                metadata = session.metadata.copy() if session.metadata else {}
                
            interaction_stage = metadata.get("stage", None)
            
            # If no explicit stage, try to infer it
            if not interaction_stage:
                if not context or len(context) <= 1:
                    interaction_stage = "introduction"
                elif len(context) > 10:
                    interaction_stage = "conclusion"
                else:
                    interaction_stage = "behavioral_assessment"
            
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
                
                # Cancel the LLM task (but let it continue in background)
                if llm_future and not llm_future.done():
                    # Instead of canceling it, let it run in background
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
                
                # Let the error handler know too
                if self.error_handler:
                    await self.error_handler.handle_error(
                        "LLM_ERROR",
                        session_id,
                        Exception("LLM response generation timed out"),
                        {"websocket": websocket, "transcript": transcript}
                    )
                return
            except Exception as e:
                self.logger.error(f"LLM error: {e}")
                # Transition to ERROR state
                await self.state_manager.transition_state(session_id, "ERROR", {
                    "message": f"LLM response generation error: {str(e)}",
                    "error_type": "LLM_ERROR"
                })
                if self.error_handler:
                    await self.error_handler.handle_error(
                        "LLM_ERROR",
                        session_id,
                        e,
                        {"websocket": websocket, "transcript": transcript}
                    )
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
                    
            # Transition to ERROR state
            await self.state_manager.transition_state(session_id, "ERROR", {
                "message": f"System error: {str(e)}",
                "error_type": "SYSTEM_ERROR"
            })
            
            # Try to use error handler
            if self.error_handler:
                await self.error_handler.handle_error(
                    "SYSTEM_ERROR",
                    session_id,
                    e,
                    {"websocket": websocket}
                )
            
            # Always try to get back to WAITING state
            try:
                await self.state_manager.transition_state(session_id, "WAITING", {
                    "message": "Ready for next input after error"
                })
            except Exception:
                pass
    
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
                
                # Transition to ERROR state for TTS failure
                await self.state_manager.transition_state(session_id, "ERROR", {
                    "message": f"Delayed audio generation error: {str(e)}",
                    "error_type": "DELAYED_TTS_ERROR"
                })
                
                # Try to return to WAITING state
                await self.state_manager.transition_state(session_id, "WAITING", {
                    "message": "Waiting for user input after error"
                })
                
        except Exception as e:
            self.logger.error(f"Error handling delayed LLM response: {e}")
            
            # Transition to ERROR state
            await self.state_manager.transition_state(session_id, "ERROR", {
                "message": f"Error processing delayed response: {str(e)}",
                "error_type": "DELAYED_LLM_ERROR"
            })
            
            # Try to return to WAITING state
            await self.state_manager.transition_state(session_id, "WAITING", {
                "message": "Waiting for user input after error"
            })
    
    async def _send_progress_update(self, websocket, message: str) -> None:
        """
        Send progress update message to client.
        
        Args:
            websocket: WebSocket connection
            message: Progress message
        """
        try:
            update = {
                "type": "progress_update",
                "timestamp": time.time(),
                "message": message
            }
            
            await websocket.send(json.dumps(update))
        except Exception as e:
            self.logger.warning(f"Failed to send progress update: {e}")
            
    async def _send_progressive_updates(self, session_id, websocket):
        """
        Send progressive updates to client during long LLM operations
        
        Args:
            session_id: Session identifier
            websocket: WebSocket connection
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