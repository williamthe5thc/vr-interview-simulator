#!/usr/bin/env python3
"""
Enhanced VR Interview Server

This version includes improved error handling, heartbeat mechanism,
and optimized async architecture to prevent blocking during LLM processing.
"""

# Configure logging first thing
import logging
import os
import sys
import traceback

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("server_diagnostic.log"),
    ]
)

logger = logging.getLogger("server")
logger.info("==== VR INTERVIEW SERVER STARTING ====")
logger.info(f"Python version: {sys.version}")
logger.info(f"Current working directory: {os.getcwd()}")
logger.info(f"Server script location: {os.path.abspath(__file__)}")

import asyncio
import base64
import json
import logging
import signal
import sys
import os
import time
from pathlib import Path

# Import core components
from app.websocket.server_enhanced_fixed import WebSocketServer
from app.state.manager import StateManager
from services.audio.stt_wrapper import STTService  # Fixed import
from services.audio.tts import TTSService
from services.llm.Ollama_client import OllamaClient
from app.utils.logging import setup_logging
from app.utils.config import load_config
from app.utils.error_handler import ErrorHandler
from app.utils.heartbeat import HeartbeatService

class EnhancedServer:
    """
    Enhanced server with improved async architecture and error handling.
    
    This server uses the enhanced WebSocket implementation that prevents
    blocking during LLM operations and provides better error recovery.
    """
    
    def __init__(self, config_path="config/config.json"):
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Setup logging
        setup_logging(self.config["server"].get("log_level", "INFO"))
        self.logger = logging.getLogger("enhanced_server")
        
        # Create directories if they don't exist
        self._setup_directories()
        
        # Initialize support services first
        self.error_handler = ErrorHandler()
        
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
            
        # Register error recovery handlers
        self._register_error_handlers()
        
        # Initialize core components
        self.state_manager = StateManager()
        self.stt_service = STTService(self.config["audio"]["stt_model"])
        # optional faster-whisper worker (tools/stt_worker.py); the built-in Whisper stays as the fallback
        self.stt_service.remote_url = (self.config["audio"].get("stt_remote_url") or "").rstrip("/") or None

        try:
            # First try to initialize AllTalk Direct
            from services.audio.tts import TTSService
            self.logger.info("Attempting to use AllTalk Direct for TTS")
            
            # Pass ONLY the config parameter
            self.tts_service = TTSService(config=self.config)
            
            # Test if AllTalk is actually available
            if self.config.get("engine") == "kokoro":
                # Kokoro worker mode: AllTalk may be deliberately not running (it would use several GB of GPU memory).
                # The TTS service keeps working: Kokoro first, then AllTalk if it happens to be up, then gTTS.
                self.logger.info("Voice engine: Kokoro worker (tools/tts_worker.py)")
            elif hasattr(self.tts_service, 'is_available') and self.tts_service.is_available():
                self.logger.info("Successfully connected to AllTalk TTS service")
            else:
                self.logger.warning("AllTalk not available, falling back to gTTS")
                from services.audio.gtts_only_service import GTTSOnlyService
                self.tts_service = GTTSOnlyService(language='en')
        except Exception as e:
            self.logger.warning(f"Error initializing AllTalk Direct: {e}, falling back to gTTS")
            from services.audio.gtts_only_service import GTTSOnlyService
            self.tts_service = GTTSOnlyService(language='en')
        # Initialize LLM client with improved configuration
        ollama_config = self.config["ollama"]
        self.llm_client = OllamaClient(
            ollama_config["url"],
            ollama_config["model"],
            ollama_config.get("context_length", 4096),
            config=ollama_config  # Pass complete config
        )
        
        # Initialize WebSocket server with references to all components
        self.websocket_server = WebSocketServer(
            self.config["server"]["host"],
            self.config["server"]["port"],
            self.state_manager,
            self.stt_service,
            self.tts_service,
            self.llm_client,
            self.error_handler,
            self.heartbeat_service
        )
        
        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()
        
        self.logger.info("Enhanced server initialized")
        
        # GPU monitoring disabled
        logging.info("GPU monitoring disabled")
        gpu_monitor = None

    def _load_config(self, config_path):
        """Load configuration from file with fallback to default"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading config from {config_path}: {e}")
            self.logger.info("Falling back to default config/config.json")
            try:
                with open("config/config.json", 'r') as f:
                    return json.load(f)
            except Exception as e2:
                self.logger.critical(f"Error loading fallback config: {e2}")
                sys.exit(1)

    def _setup_directories(self):
        """Create necessary directories for data storage"""
        Path(self.config["storage"]["audio_dir"]).mkdir(parents=True, exist_ok=True)
        Path(self.config["storage"]["conversation_dir"]).mkdir(parents=True, exist_ok=True)
        Path(f"{self.config['storage']['audio_dir']}/uploads").mkdir(parents=True, exist_ok=True)
        Path(f"{self.config['storage']['audio_dir']}/responses").mkdir(parents=True, exist_ok=True)

    def _setup_signal_handlers(self):
        """Setup handlers for graceful shutdown"""
        # Simple signal handling that works on both Windows and Unix
        try:
            # Register for SIGINT (Ctrl+C)
            signal.signal(signal.SIGINT, self._signal_handler)
            # Register for SIGTERM if available
            if hasattr(signal, 'SIGTERM'):
                signal.signal(signal.SIGTERM, self._signal_handler)
            self.logger.info("Signal handlers registered")
        except Exception as e:
            self.logger.warning(f"Could not set up signal handlers: {e}")
            
    def _register_error_handlers(self):
        """Register handlers for different error types"""
        # Register LLM error handler
        self.error_handler.register_recovery_handler(
            ErrorHandler.LLM_ERROR,
            self._handle_llm_error
        )
        
        # Register STT error handler
        self.error_handler.register_recovery_handler(
            ErrorHandler.STT_ERROR,
            self._handle_stt_error
        )
        
        # Register TTS error handler
        self.error_handler.register_recovery_handler(
            ErrorHandler.TTS_ERROR,
            self._handle_tts_error
        )
        
        # Register WebSocket error handler
        self.error_handler.register_recovery_handler(
            ErrorHandler.WEBSOCKET_ERROR,
            self._handle_websocket_error
        )
        
        # Register system error handler
        self.error_handler.register_recovery_handler(
            ErrorHandler.SYSTEM_ERROR,
            self._handle_system_error
        )
    
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
            
    async def _handle_stt_error(self, session_id, exception, context):
        """Handle errors in speech-to-text processing with improved recovery"""
        try:
            # Always transition to WAITING state for next input
            await self.state_manager.transition_state(session_id, "WAITING", {
                "message": "Speech recognition error, please try again"
            })
            
            # Send error notification if possible
            if "websocket" in context:
                websocket = context["websocket"]
                message = {
                    "type": "system_message",
                    "message": "I couldn't understand that clearly. Could you please try again?"
                }
                await websocket.send(json.dumps(message))
                
            return True  # Indicate successful recovery
        except Exception as e:
            self.logger.error(f"Error during STT error recovery: {e}")
            # Final fallback - always try to get back to WAITING state
            try:
                await self.state_manager.transition_state(session_id, "WAITING", {})
            except:
                pass
            return False
            
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

            
    async def _handle_websocket_error(self, session_id, exception, context):
        """Handle WebSocket connection errors with improved cleanup"""
        try:
            self.logger.warning(f"WebSocket error for {session_id}. Scheduling cleanup.")
            
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
            
            # Schedule session cleanup after a delay - reduce from 30s to 10s
            asyncio.get_event_loop().call_later(
                10, 
                lambda: asyncio.create_task(self.state_manager.end_session(session_id))
            )
            
            return True  # Indicate successful recovery
        except Exception as e:
            self.logger.error(f"Error during WebSocket error recovery: {e}")
            return False
            
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
            
    def _signal_handler(self, sig, frame):
        """Handle termination signals"""
        self.logger.info(f"Received signal {sig}, initiating shutdown...")
        # Just exit cleanly - we can't do much else in a signal handler on Windows
        self.logger.info("Exiting...")
        os._exit(0)
        
    async def _shutdown(self):
        """Gracefully shutdown the server - used by internal logic, not signals"""
        self.logger.info("Shutting down...")
        
        # Stop heartbeat service if enabled
        if self.heartbeat_service:
            await self.heartbeat_service.stop_all()
            
        # Close WebSocket server
        await self.websocket_server.shutdown()
        
        # Cleanup other resources
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        [task.cancel() for task in tasks]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        asyncio.get_event_loop().stop()
        self.logger.info("Shutdown complete")

    async def start(self):
        """Start the server and all components with proper initialization"""
        # Preload the STT model before accepting connections
        self.logger.info("Preloading STT model (this may take a moment)...")
        try:
            # Run in thread pool to avoid blocking startup
            # Access the actual STT implementation through the wrapper
            start_time = time.time()
            # Use the original_stt instance which has the _load_model method
            if self.stt_service.remote_url and await asyncio.to_thread(self.stt_service.remote_ready):
                self.logger.info(f"faster-whisper worker is up at {self.stt_service.remote_url}; "
                                 "the built-in Whisper will only load if the worker fails (saves ~1 GB of GPU memory)")
            elif hasattr(self.stt_service, 'original_stt') and hasattr(self.stt_service.original_stt, '_load_model'):
                await asyncio.to_thread(self.stt_service.original_stt._load_model)
                load_time = time.time() - start_time
                self.logger.info(f"STT model preloaded successfully in {load_time:.2f} seconds")
        except Exception as e:
            self.logger.error(f"Error preloading STT model: {e}")
            self.logger.warning("Will use lazy loading instead, expect delay on first transcription")
            
        # Preload the LLM model by making a simple request
        self.logger.info("Preloading LLM model (this may take a moment)...")
        try:
            # Make a simple request to ensure model is loaded
            start_time = time.time()
            # Use a simple prompt to initialize the model
            test_prompt = "Hello"
            await asyncio.to_thread(
                self.llm_client.generate_response,
                test_prompt,
                [],  # Empty context
                None,  # Default timeout
                None,  # Default retries
                "greeting"  # Use greeting stage
            )
            load_time = time.time() - start_time
            self.logger.info(f"LLM model preloaded successfully in {load_time:.2f} seconds")
        except Exception as e:
            self.logger.error(f"Error preloading LLM model: {e}")
            self.logger.warning("Will use lazy loading instead, expect delay on first response")
            
        # Now start the server
        self.logger.info(f"Starting server on {self.config['server']['host']}:{self.config['server']['port']}")
        try:
            await self.websocket_server.start()
        except Exception as e:
            self.logger.error(f"Failed to start server: {e}")
            await self._shutdown()


if __name__ == "__main__":
    # Create and run the enhanced server
    server = EnhancedServer()
    
    # Different approach based on platform
    if sys.platform == 'win32':
        # On Windows, we need a slightly different approach
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(server.start())
            loop.run_forever()
        except KeyboardInterrupt:
            pass
        finally:
            loop.close()
    else:
        # On Unix platforms, asyncio.run works fine
        asyncio.run(server.start())
