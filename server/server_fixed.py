#!/usr/bin/env python3
"""
Fixed VR Interview System Server
This version addresses the 3 critical issues:
1. AI Personality Confusion - Uses enhanced Ollama client with proper role anchoring
2. Invalid State Transitions - Uses fixed state manager that prevents loops
3. Session ID Mismatch - Implements proper session synchronization
"""

import asyncio
import logging
import signal
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.utils.logging import setup_logging
from app.utils.config import load_config
from app.utils.error_handler import ErrorHandler
from app.utils.heartbeat import HeartbeatService

# Import FIXED components
from app.state.manager_fixed import StateManager
from services.llm.Ollama_client_fixed import OllamaClient

# Import other components (not fixed)
from app.websocket.server_enhanced_fixed import WebSocketServer
from services.audio.stt_wrapper import STTService
from services.audio.tts import TTSService


class EnhancedServer:
    """
    Enhanced VR Interview System Server with fixes for critical issues.
    
    Key fixes:
    1. AI Personality - Enhanced Ollama client with proper role reinforcement
    2. State Transitions - Fixed state manager prevents invalid loops
    3. Session Sync - Improved session ID handling and synchronization
    """
    
    def __init__(self):
        self.config = None
        self.logger = None
        self.state_manager = None
        self.stt_service = None
        self.tts_service = None
        self.llm_client = None
        self.error_handler = None
        self.heartbeat_service = None
        self.websocket_server = None
        self.running = False
        
    async def initialize(self):
        """Initialize all server components with fixes"""
        try:
            # Load configuration with error handling
            try:
                self.config = load_config()
                print("[OK] Configuration loaded successfully")
            except Exception as e:
                print(f"[ERROR] Failed to load configuration: {e}")
                raise
            
            # Set up logging with error handling
            try:
                log_level = self.config.get("server", {}).get("log_level", "INFO")
                setup_logging(log_level)
                self.logger = logging.getLogger("server")
                print("[OK] Logging initialized successfully")
            except Exception as e:
                print(f"[ERROR] Failed to initialize logging: {e}")
                # Create a basic logger as fallback
                logging.basicConfig(level=logging.INFO)
                self.logger = logging.getLogger("server")
                self.logger.error(f"Logging initialization failed: {e}")
            
            self.logger.info("=" * 60)
            self.logger.info("STARTING VR INTERVIEW SYSTEM - FIXED VERSION")
            self.logger.info("=" * 60)
            self.logger.info("Fixes applied:")
            self.logger.info("[OK] AI Personality Confusion - Enhanced role anchoring")
            self.logger.info("[OK] Invalid State Transitions - Prevents PROCESSING loops")
            self.logger.info("[OK] Session ID Mismatch - Improved synchronization")
            self.logger.info("=" * 60)
            
            # Initialize FIXED state manager
            self.logger.info("Initializing FIXED state manager...")
            self.state_manager = StateManager()
            self.logger.info("[OK] Fixed state manager initialized")
            
            # Initialize services
            await self._initialize_audio_services()
            await self._initialize_llm_service()
            await self._initialize_support_services()
            await self._initialize_websocket_server()
            
            self.logger.info("[OK] All components initialized successfully!")
            return True
            
        except Exception as e:
            error_msg = f"[ERROR] Failed to initialize server: {e}"
            if hasattr(self, 'logger') and self.logger:
                self.logger.error(error_msg)
            else:
                print(error_msg)
                import traceback
                print(f"Traceback: {traceback.format_exc()}")
            return False
    
    async def _initialize_audio_services(self):
        """Initialize audio processing services"""
        self.logger.info("Initializing audio services...")
        
        # Initialize STT service with wrapper for error handling
        stt_config = self.config.get("audio", {})
        self.stt_service = STTService(stt_config.get("stt_model", "base"))
        self.logger.info("[OK] STT service initialized")
        
        # Initialize TTS service  
        tts_config = self.config.get("alltalk", {})
        self.tts_service = TTSService(tts_config)
        self.logger.info("[OK] TTS service initialized")
        
    async def _initialize_llm_service(self):
        """Initialize FIXED LLM service"""
        self.logger.info("Initializing FIXED LLM service...")
        
        llm_config = self.config.get("ollama", {})
        
        # Create FIXED Ollama client with enhanced role management
        self.llm_client = OllamaClient(
            url=llm_config.get("url", "http://localhost:11434"),
            model=llm_config.get("model", "mistral:latest"),
            context_length=llm_config.get("context_length", 8192),
            config=llm_config
        )
        
        self.logger.info("[OK] FIXED LLM client initialized with enhanced personality anchoring")
        
    async def _initialize_support_services(self):
        """Initialize support services"""
        self.logger.info("Initializing support services...")
        
        # Initialize error handler
        self.error_handler = ErrorHandler()
        self.logger.info("[OK] Error handler initialized")
        
        # Initialize heartbeat service
        heartbeat_config = self.config.get("heartbeat", {})
        if heartbeat_config.get("enabled", True):
            self.heartbeat_service = HeartbeatService(
                heartbeat_interval=heartbeat_config.get("interval", 5.0)
            )
            self.logger.info("[OK] Heartbeat service initialized")
        else:
            self.logger.info("[WARN] Heartbeat service disabled")
            
    async def _initialize_websocket_server(self):
        """Initialize WebSocket server with fixed components"""
        self.logger.info("Initializing WebSocket server...")
        
        server_config = self.config.get("server", {})
        
        self.websocket_server = WebSocketServer(
            host=server_config.get("host", "0.0.0.0"),
            port=server_config.get("port", 8765),
            state_manager=self.state_manager,
            stt_service=self.stt_service,
            tts_service=self.tts_service,
            llm_client=self.llm_client,
            error_handler=self.error_handler,
            heartbeat_service=self.heartbeat_service
        )
        
        self.logger.info("[OK] WebSocket server initialized")
        
    async def start(self):
        """Start the server"""
        if not await self.initialize():
            return False
            
        try:
            self.running = True
            
            # Start the WebSocket server
            await self.websocket_server.start()
            
            self.logger.info("VR Interview System Server is running!")
            self.logger.info("Key improvements active:")
            self.logger.info("  • AI acts as interviewer, not candidate")
            self.logger.info("  • State machine prevents infinite loops")  
            self.logger.info("  • Session IDs properly synchronized")
            self.logger.info("Ready for VR connections!")
            
            # Keep the server running
            while self.running:
                await asyncio.sleep(1)
                
                # Optional: Check for stuck sessions every 30 seconds
                if hasattr(self.state_manager, 'recover_stuck_sessions'):
                    try:
                        recovered = await self.state_manager.recover_stuck_sessions(30)
                        if recovered > 0:
                            self.logger.info(f"[RECOVERY] Auto-recovered {recovered} stuck sessions")
                    except Exception as e:
                        self.logger.error(f"Error in session recovery: {e}")
                        
                await asyncio.sleep(29)  # Total 30 second cycle
                    
        except Exception as e:
            self.logger.error(f"❌ Server error: {e}")
            return False
            
        return True
        
    async def shutdown(self):
        """Gracefully shutdown the server"""
        self.logger.info("[SHUTDOWN] Shutting down VR Interview System Server...")
        
        self.running = False
        
        # Shutdown components in reverse order
        if self.websocket_server:
            await self.websocket_server.shutdown()
            
        if self.heartbeat_service:
            await self.heartbeat_service.stop_all()
            
        if self.llm_client and hasattr(self.llm_client, 'cleanup'):
            self.llm_client.cleanup()
            
        self.logger.info("[OK] Server shutdown complete")
        
    def setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown"""
        def signal_handler(sig, frame):
            print(f"\n[SHUTDOWN] Received signal {sig}, shutting down...")
            asyncio.create_task(self.shutdown())
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)


async def main():
    """Main server entry point"""
    server = EnhancedServer()
    server.setup_signal_handlers()
    
    try:
        success = await server.start()
        if not success:
            print("[ERROR] Failed to start server")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Server interrupted by user")
    except Exception as e:
        error_msg = f"[ERROR] Unexpected error: {e}"
        print(error_msg)
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)
    finally:
        await server.shutdown()


if __name__ == "__main__":
    # Run the server
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[EXIT] Goodbye!")
    except Exception as e:
        print(f"[ERROR] Fatal error: {e}")
        sys.exit(1)
