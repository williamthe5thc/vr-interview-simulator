import asyncio
import logging
import time
import json
from enum import Enum, auto


class States(Enum):
    """Enumeration of possible states for the conversation"""
    IDLE = auto()
    LISTENING = auto()
    # Granular processing states
    PROCESSING = auto()          # Generic processing state (for backward compatibility)
    PROCESSING_STT = auto()      # Specifically transcribing speech to text
    PROCESSING_LLM = auto()      # Generating response with the language model 
    PROCESSING_TTS = auto()      # Converting text response to audio
    RESPONDING = auto()
    WAITING = auto()
    ERROR = auto()


class StateManager:
    """
    Fixed state manager that prevents invalid state transitions and loops.
    
    This class handles state transitions and ensures they follow the defined flow:
    IDLE → LISTENING → PROCESSING_STT → PROCESSING_LLM → PROCESSING_TTS → RESPONDING → WAITING → (repeat)
    
    Key fixes:
    - Prevents same-state transitions that cause loops
    - Enforces proper state flow to avoid confusion
    - Improved deadlock prevention without forced transitions
    """
    
    def __init__(self):
        self.sessions = {}
        self.logger = logging.getLogger("state_manager")
        self._state_locks = {}  # Locks to prevent race conditions in state transitions
        self._last_state_change = {}  # Track when states actually changed
        
    def create_session(self, session_id, session):
        """Initialize a new session with IDLE state"""
        self.sessions[session_id] = session
        self._state_locks[session_id] = asyncio.Lock()
        self._last_state_change[session_id] = time.time()
        self.logger.info(f"Created new session: {session_id}")
        
        # Set initial state
        asyncio.create_task(
            self.transition_state(session_id, "IDLE")
        )
        
    async def end_session(self, session_id):
        """Clean up session resources"""
        if session_id in self.sessions:
            self.logger.info(f"Ended session: {session_id}")
            del self.sessions[session_id]
            
        if session_id in self._state_locks:
            del self._state_locks[session_id]
            
        if session_id in self._last_state_change:
            del self._last_state_change[session_id]
            
    async def force_transition(self, session_id, new_state, metadata=None):
        """
        Force a state transition for emergency recovery only.
        
        Args:
            session_id: The session to update
            new_state: The new state to transition to
            metadata: Optional metadata for the state update
            
        Returns:
            True if the transition was successful, False otherwise
        """
        if session_id not in self.sessions:
            self.logger.error(f"Cannot force transition for unknown session: {session_id}")
            return False
            
        try:
            session = self.sessions[session_id]
            previous_state = session.state
            
            # Only force if really necessary (avoid abuse)
            if previous_state == new_state:
                self.logger.debug(f"Skipping forced transition to same state: {session_id}: {new_state}")
                return True
            
            # Force the state change directly
            session.state = new_state
            session.last_updated = time.time()
            self._last_state_change[session_id] = time.time()
            
            # Update metadata if provided
            if metadata:
                session.metadata.update(metadata)
            else:
                metadata = {}
                
            # Add forced flag to metadata
            metadata["forced"] = True
            metadata["recovery"] = True
            metadata["message"] = metadata.get("message", "Forced state transition for recovery")
            
            self.logger.warning(
                f"Forced state transition: {session_id}: {previous_state} → {new_state}"
            )
            
            # Try to broadcast the change
            try:
                await self._broadcast_state_change(session_id, previous_state, new_state, metadata)
            except Exception as e:
                self.logger.error(f"Error broadcasting forced state change: {e}")
                
            return True
        except Exception as e:
            self.logger.error(f"Error during forced state transition: {e}")
            return False
        
    def get_session(self, session_id):
        """Get the session object for a session ID"""
        return self.sessions.get(session_id)
        
    def get_session_state(self, session_id):
        """Get the current state name for a session"""
        session = self.sessions.get(session_id)
        if not session:
            return None
        return session.state
        
    async def transition_state(self, session_id, new_state, metadata=None, timeout=3.0):
        """
        Transition session to a new state and broadcast the change.
        
        Key improvements:
        - Prevents same-state transitions that cause loops
        - Enforces valid state flow
        - Shorter timeouts to prevent blocking
        - Better handling of redundant updates
        
        Args:
            session_id: The session to update
            new_state: The new state to transition to
            metadata: Optional metadata for the state update
            timeout: Maximum time to wait for lock acquisition
        
        Returns:
            True if the transition was successful, False otherwise
        """
        if session_id not in self.sessions:
            self.logger.error(f"Cannot transition state for unknown session: {session_id} (to state {new_state})")
            return False
        
        session = self.sessions.get(session_id)
        if not session:
            self.logger.warning(f"Session {session_id} no longer exists")
            return False
            
        current_state = session.state
        
        # CRITICAL FIX: Prevent same-state transitions that cause loops
        if current_state == new_state:
            # Allow progress updates for the same state, but limit frequency
            if metadata and ("progress" in metadata or "message" in metadata):
                # Check if enough time has passed since last update
                last_change = self._last_state_change.get(session_id, 0)
                if time.time() - last_change < 1.0:  # Limit to once per second
                    self.logger.debug(f"Rate limiting same-state update: {session_id}: {new_state}")
                    return True
                    
                # Allow progress update but don't change state
                try:
                    if metadata:
                        session.metadata.update(metadata)
                    await self._broadcast_state_change(session_id, current_state, new_state, metadata)
                    self._last_state_change[session_id] = time.time()
                    return True
                except Exception as e:
                    self.logger.error(f"Error broadcasting progress update: {e}")
                    return False
            else:
                # Block redundant same-state transitions without progress info
                self.logger.debug(f"Blocking redundant state transition: {session_id}: {current_state} → {new_state}")
                return True
        
        # Validate the state transition
        if not self._is_valid_transition(current_state, new_state):
            self.logger.error(f"INVALID state transition blocked: {session_id}: {current_state} → {new_state}")
            return False
            
        try:
            # Use asyncio.wait_for with timeout for lock acquisition
            try:
                await asyncio.wait_for(self._state_locks[session_id].acquire(), timeout=timeout)
            except asyncio.TimeoutError:
                self.logger.warning(f"State transition timeout: {session_id}: {current_state} → {new_state}")
                return False
            
            try:
                # Double-check session still exists after acquiring lock
                session = self.sessions.get(session_id)
                if not session:
                    self.logger.warning(f"Session {session_id} disappeared during transition")
                    return False
                
                # Double-check the transition is still valid (state might have changed)
                actual_current = session.state
                if actual_current != current_state:
                    self.logger.info(f"State changed during lock wait: {session_id}: {current_state} → {actual_current}")
                    current_state = actual_current
                    
                    # Re-validate with actual current state
                    if not self._is_valid_transition(current_state, new_state):
                        self.logger.error(f"INVALID transition after lock: {session_id}: {current_state} → {new_state}")
                        return False
                
                # Skip if we're trying to transition to the same state again
                if current_state == new_state:
                    self.logger.debug(f"Skipping same-state transition after lock: {session_id}: {new_state}")
                    return True
                
                # Update the session state
                session.state = new_state
                session.last_updated = time.time()
                self._last_state_change[session_id] = time.time()
                
                # Add metadata if provided
                if metadata:
                    session.metadata.update(metadata)
                    
                self.logger.info(f"State transition: {session_id}: {current_state} -> {new_state}")
                
                # Broadcast state change
                await self._broadcast_state_change(session_id, current_state, new_state, metadata)
                
                return True
            finally:
                # Always release the lock
                self._state_locks[session_id].release()
                    
        except Exception as e:
            self.logger.error(f"Error during state transition: {e}")
            return False
    
    def _is_valid_transition(self, current, next_state):
        """
        Validate that a state transition follows the allowed flow.
        
        CRITICAL FIX: Removed self-transitions that were causing loops.
        Each processing state can only move forward or to recovery states.
        """
        # Allow universal recovery transitions
        if next_state in ["IDLE", "ERROR", "WAITING"]:
            return True
            
        # FIXED: Strict state flow without loops
        valid_transitions = {
            "IDLE": ["LISTENING", "PROCESSING_STT"],
            "LISTENING": ["PROCESSING_STT", "PROCESSING", "IDLE"],
            
            # CRITICAL FIX: Processing states can't loop back to themselves
            "PROCESSING": ["PROCESSING_STT", "PROCESSING_LLM", "PROCESSING_TTS", "RESPONDING"],
            "PROCESSING_STT": ["PROCESSING_LLM", "PROCESSING", "RESPONDING"],  # No self-loop!
            "PROCESSING_LLM": ["PROCESSING_TTS", "PROCESSING", "RESPONDING"],  # No self-loop!
            "PROCESSING_TTS": ["RESPONDING", "PROCESSING"],  # No self-loop!
            
            "RESPONDING": ["WAITING", "IDLE"],
            "WAITING": ["LISTENING", "IDLE", "PROCESSING_STT"],
            "ERROR": ["IDLE", "WAITING"]
        }
        
        allowed = valid_transitions.get(current, [])
        is_valid = next_state in allowed
        
        if not is_valid:
            self.logger.warning(f"Invalid transition attempted: {current} → {next_state} (allowed: {allowed})")
            
        return is_valid
        
    async def _broadcast_state_change(self, session_id, previous, current, metadata):
        """Broadcast state change to the client"""
        session = self.sessions.get(session_id)
        if not session or not hasattr(session, 'websocket') or session.websocket is None:
            return
            
        try:
            # Create state update message
            message = {
                "type": "state_update",
                "session_id": session_id,
                "previous": previous,
                "current": current,
                "timestamp": time.time(),
                "metadata": metadata or {}
            }
            
            # Send message to client
            await session.websocket.send(json.dumps(message))
            
        except Exception as e:
            self.logger.error(f"Error broadcasting state change: {e}")
    
    async def get_stuck_sessions(self, timeout_seconds=30):
        """
        Identify sessions that may be stuck in processing states.
        
        Args:
            timeout_seconds: How long a session can stay in a processing state
            
        Returns:
            List of session IDs that appear to be stuck
        """
        stuck_sessions = []
        current_time = time.time()
        
        for session_id, session in self.sessions.items():
            if session.state.startswith("PROCESSING"):
                last_change = self._last_state_change.get(session_id, current_time)
                if current_time - last_change > timeout_seconds:
                    stuck_sessions.append(session_id)
                    self.logger.warning(f"Session {session_id} stuck in {session.state} for {current_time - last_change:.1f}s")
        
        return stuck_sessions
    
    async def recover_stuck_sessions(self, timeout_seconds=30):
        """
        Automatically recover sessions that are stuck in processing states.
        
        Args:
            timeout_seconds: How long to wait before considering a session stuck
            
        Returns:
            Number of sessions recovered
        """
        stuck_sessions = await self.get_stuck_sessions(timeout_seconds)
        recovered = 0
        
        for session_id in stuck_sessions:
            try:
                success = await self.force_transition(
                    session_id, 
                    "WAITING", 
                    {
                        "message": "Ready for next question",
                        "recovery_reason": "stuck_in_processing",
                        "auto_recovery": True
                    }
                )
                if success:
                    recovered += 1
                    self.logger.info(f"Auto-recovered stuck session: {session_id}")
            except Exception as e:
                self.logger.error(f"Failed to recover stuck session {session_id}: {e}")
        
        return recovered
