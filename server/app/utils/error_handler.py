"""
Enhanced error handler with improved recovery mechanisms and diagnostics for VR Interview System.

This module provides a more robust error handling system with:
- Better error tracking and pattern detection
- Improved recovery strategies
- More detailed diagnostics
- Graceful degradation for different error types
"""

import logging
import json
import time
import traceback
import asyncio
from typing import Dict, Any, Optional, Tuple, List, Callable, Set

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
    
    def __init__(self):
        self.logger = logging.getLogger("enhanced_error_handler")
        self.recovery_handlers = {}  # Type: Dict[str, Callable]
        self.error_counts = {}  # Track error counts per session
        self.error_types = {}   # Track error types per session
        self.recent_errors = [] # Track recent errors for pattern detection
        self.session_recovery_attempts = {}  # Track recovery attempts per session
        
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
        
        # Track last recovery attempt times
        self.last_recovery_times = {}  # Type: Dict[str, Dict[str, float]]
    
    def register_recovery_handler(self, error_type: str, handler: Callable):
        """Register a handler for a specific error type"""
        self.recovery_handlers[error_type] = handler
        self.logger.info(f"Registered recovery handler for {error_type}")
    
    async def handle_error(self, error_type: str, session_id: str, 
                          exception: Exception, context: Optional[Dict[str, Any]] = None) -> Tuple[bool, Dict[str, Any]]:
        """
        Enhanced error handler with improved tracking and recovery
        
        Args:
            error_type: Type of error (use class constants)
            session_id: Session identifier
            exception: The exception that occurred
            context: Additional context information for recovery
            
        Returns:
            Tuple: (success, metadata)
        """
        try:
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
            
            # Track recovery timestamp
            current_time = time.time()
            self.last_recovery_times[session_id][error_name] = current_time
            
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
            
            # Check for recurring errors
            recurring = False
            if self.error_counts[session_id] >= 3:
                # Check if same error type is recurring
                for err_type, count in self.error_types[session_id].items():
                    if count >= 2:
                        recurring = True
                        break
            
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
            
            # Try to reset state to WAITING
            try:
                # Import here to avoid circular imports
                from app.state.manager import StateManager
                state_manager = None
                
                # Try to get the StateManager instance
                if hasattr(StateManager, 'get_instance'):
                    state_manager = StateManager.get_instance()
                else:
                    # If no get_instance method, try to get instance from context
                    state_manager = context.get('state_manager') if context else None
                
                if state_manager:
                    # Check current state
                    current_state = state_manager.get_session_state(session_id)
                    
                    # Only transition if not already in WAITING/IDLE
                    if current_state not in ["WAITING", "IDLE"]:
                        await state_manager.transition_state(session_id, "WAITING", {
                            "message": "Ready for next question after error recovery",
                            "error_recovered": True,
                            "error_type": error_name
                        })
                        self.logger.info(f"Transitioned session {session_id} to WAITING state after error")
            except Exception as state_error:
                self.logger.error(f"Error transitioning state after error: {state_error}")
                # Last resort - try to send a direct message
                if websocket:
                    try:
                        await websocket.send(json.dumps({
                            "type": "state_update",
                            "session_id": session_id,
                            "previous": "ERROR",
                            "current": "WAITING",
                            "timestamp": time.time(),
                            "metadata": {
                                "message": "Please continue with your next question"
                            }
                        }))
                    except Exception as ws_error:
                        self.logger.error(f"Final error recovery attempt failed: {ws_error}")
            
            # Return False as we used fallback
            return False, {}
            
        except Exception as e:
            # Meta-error: error in error handler
            self.logger.critical(f"Critical error in error handler: {e}")
            self.logger.critical(traceback.format_exc())
            return False, {}
    
    async def _handle_exceeded_recovery_attempts(self, error_type: str, session_id: str, 
                                              exception: Exception, context: Optional[Dict[str, Any]] = None) -> Tuple[bool, Dict[str, Any]]:
        """
        Handle the case where we've exceeded maximum recovery attempts for an error type
        
        This uses more aggressive recovery strategies:
        - Resets session state completely
        - Suggests client restart if applicable
        - Uses simpler fallback mechanisms
        
        Args:
            error_type: Type of error 
            session_id: Session identifier
            exception: The exception that occurred
            context: Additional context information for recovery
            
        Returns:
            Tuple: (success, metadata)
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
    
    async def _handle_cooldown_recovery(self, error_type: str, session_id: str,
                                     exception: Exception, context: Optional[Dict[str, Any]] = None) -> Tuple[bool, Dict[str, Any]]:
        """
        Handle the case where we're in a cooldown period for an error type
        
        This uses lighter recovery strategies to avoid spamming the client with messages
        
        Args:
            error_type: Type of error 
            session_id: Session identifier
            exception: The exception that occurred
            context: Additional context information for recovery
            
        Returns:
            Tuple: (success, metadata)
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
                if current_state in ["PROCESSING", "RESPONDING", "ERROR"]:
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
    
    def get_error_statistics(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get error statistics for debugging and monitoring
        
        Args:
            session_id: Optional session ID to get stats for a specific session
            
        Returns:
            Dictionary with error statistics
        """
        if session_id:
            # Return stats for a specific session
            return {
                "error_count": self.error_counts.get(session_id, 0),
                "error_types": self.error_types.get(session_id, {}),
                "recovery_attempts": self.session_recovery_attempts.get(session_id, {})
            }
        else:
            # Return global stats
            return {
                "total_sessions_with_errors": len(self.error_counts),
                "total_errors": sum(self.error_counts.values()) if self.error_counts else 0,
                "error_type_counts": self._aggregate_error_types(),
                "recent_errors": self.recent_errors
            }
    
    def _aggregate_error_types(self) -> Dict[str, int]:
        """
        Aggregate error types across all sessions
        
        Returns:
            Dictionary mapping error types to counts
        """
        result = {}
        for session_id, error_types in self.error_types.items():
            for error_type, count in error_types.items():
                if error_type not in result:
                    result[error_type] = 0
                result[error_type] += count
        return result
    
    def reset_session_errors(self, session_id: str):
        """
        Reset error tracking for a specific session
        
        Args:
            session_id: Session identifier to reset
        """
        if session_id in self.error_counts:
            self.error_counts[session_id] = 0
        if session_id in self.error_types:
            self.error_types[session_id] = {}
        if session_id in self.session_recovery_attempts:
            self.session_recovery_attempts[session_id] = {}
        if session_id in self.last_recovery_times:
            self.last_recovery_times[session_id] = {}
            
        self.logger.info(f"Reset error tracking for session {session_id}")
    
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
