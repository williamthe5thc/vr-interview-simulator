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
    Manages the state machine for conversation sessions.
    
    This class handles state transitions and ensures they follow the defined flow:
    IDLE → LISTENING → PROCESSING_STT → PROCESSING_LLM → PROCESSING_TTS → RESPONDING → WAITING → (repeat)
    
    It also handles broadcasting state changes to connected clients.
    """
    
    def __init__(self):
        self.sessions = {}
        self.logger = logging.getLogger("state_manager")
        self._state_locks = {}  # Locks to prevent race conditions in state transitions
        self._deadlock_timeouts = {}  # Timeouts to prevent deadlocks
        
    def create_session(self, session_id, session):
        """Initialize a new session with IDLE state"""
        self.sessions[session_id] = session
        self._state_locks[session_id] = asyncio.Lock()
        self.logger.info(f"Created new session: {session_id}")
        
        # Set initial state
        asyncio.create_task(
            self.transition_state(session_id, "IDLE")
        )
        
    async def end_session(self, session_id):
        """Clean up session resources"""
        # Cancel any deadlock timeouts
        if session_id in self._deadlock_timeouts:
            self._deadlock_timeouts[session_id].cancel()
            
        if session_id in self.sessions:
            # Log the session ending
            self.logger.info(f"Ended session: {session_id}")
            del self.sessions[session_id]
            
        if session_id in self._state_locks:
            del self._state_locks[session_id]
            
    async def force_transition(self, session_id, new_state, metadata=None):
        """
        Force a state transition without waiting for locks.
        For emergency recovery only.
        
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
            
            # Force the state change directly
            session.state = new_state
            session.last_updated = time.time()
            
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
                f"Forced state transition: {session_id}: {previous_state} to {new_state}"
            )
            
            # Try to broadcast the change
            try:
                await self._broadcast_state_change(session_id, previous_state, new_state, metadata)
            except Exception as e:
                self.logger.error(f"Error broadcasting forced state change: {e}")
                # Even if broadcast fails, we still made the change
                
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
        
    async def transition_state(self, session_id, new_state, metadata=None, timeout=5.0):
        """
        Transition session to a new state and broadcast the change.
        
        Uses locks with shorter timeouts to prevent blocking and improved deadlock prevention.
        
        Args:
            session_id: The session to update
            new_state: The new state to transition to
            metadata: Optional metadata for the state update
            timeout: Maximum time to wait for lock acquisition
        
        Returns:
            True if the transition was successful, False otherwise
        """
        if session_id not in self.sessions:
            # More helpful log message with the session ID to make it easier to debug
            self.logger.error(f"Cannot transition state for unknown session: {session_id} (to state {new_state})")
            return False
        
        # Set up a task to handle deadlock timeout if needed
        if session_id in self._deadlock_timeouts:
            self._deadlock_timeouts[session_id].cancel()
            
        deadlock_task = asyncio.create_task(
            self._handle_deadlock(session_id, new_state, timeout)
        )
        self._deadlock_timeouts[session_id] = deadlock_task
            
        try:
            # Acquire lock with timeout to prevent blocking indefinitely
            lock_acquired = False
            try:
                # Use wait_for with a timeout to avoid deadlocks
                await asyncio.wait_for(
                    self._state_locks[session_id].acquire(),
                    timeout=timeout
                )
                lock_acquired = True
            except asyncio.TimeoutError:
                self.logger.warning(
                    f"Timed out waiting for state lock on {session_id}. "
                    f"Forcing transition to {new_state}."
                )
                # Force the transition by creating a new lock
                self._state_locks[session_id] = asyncio.Lock()
                # We'll proceed without the lock - this is dangerous but better than deadlocking
            
            try:
                session = self.sessions.get(session_id)
                if not session:
                    self.logger.warning(f"Session {session_id} no longer exists during transition")
                    return False
                    
                previous_state = session.state
                
                # Detect redundant processing state updates
                if previous_state == new_state:
                    # For processing states, limit updates to be less frequent
                    if new_state.startswith("PROCESSING"):
                        # Track updates per processing type to avoid redundancy
                        last_update_key = f"last_{new_state.lower()}_update"
                        last_update_time = getattr(session, last_update_key, 0)
                        current_time = time.time()
                        
                        # Only allow updates every 3 seconds unless they contain progress info
                        if (current_time - last_update_time < 3.0 and 
                            (not metadata or "progress" not in metadata)):
                            self.logger.debug(
                                f"Limiting {new_state} state updates for {session_id}, "
                                f"last update was {current_time - last_update_time:.1f}s ago"
                            )
                            return True
                        
                        # Update the last processing update time
                        setattr(session, last_update_key, current_time)
                    # For other states, check if metadata has meaningful changes
                    elif metadata and "progress" not in metadata:
                        # For progress updates, we still want to show them
                        # But avoid redundant state broadcasts that have no meaningful changes
                        redundant = True
                        
                        # Check if there's any meaningful difference in metadata
                        if metadata and session.metadata:
                            for key, value in metadata.items():
                                if key not in session.metadata or session.metadata[key] != value:
                                    redundant = False
                                    break
                        
                        if redundant:
                            self.logger.debug(f"Skipping redundant state update for {session_id}: {new_state}")
                            return True
                
                # Validate the state transition
                if not self._is_valid_transition(previous_state, new_state):
                    self.logger.warning(
                        f"Invalid state transition: {previous_state} to {new_state}"
                    )
                    # Allow the transition in production to prevent deadlocks
                    # Just log the warning
                
                # Update the session state
                session.state = new_state
                session.last_updated = time.time()
                
                # Add metadata if provided
                if metadata:
                    session.metadata.update(metadata)
                    
                self.logger.info(f"State transition: {session_id}: {previous_state} to {new_state}")
                
                # Cancel the deadlock timeout task
                if deadlock_task and not deadlock_task.done():
                    deadlock_task.cancel()
                
                # Broadcast state change
                await self._broadcast_state_change(session_id, previous_state, new_state, metadata)
                
                return True
            finally:
                # Only release the lock if we acquired it
                if lock_acquired:
                    self._state_locks[session_id].release()
                
        except Exception as e:
            self.logger.error(f"Error during state transition: {e}")
            return False
    
    # Updated valid transitions to handle new granular processing states
    def _is_valid_transition(self, current, next_state):
        """
        Validate that a state transition follows the allowed flow.
        
        Modified with more flexible transitions to prevent deadlocks:
        - Any state can transition to ERROR state
        - Any state can transition to WAITING (helps recover from errors)
        - PROCESSING states can go to each other or to the next logical state
        - PROCESSING* states are compatible with older PROCESSING state for backward compatibility
        """
        # Allow these universal transitions
        if next_state in ["IDLE", "ERROR", "WAITING"]:
            return True
            
        # Handle the normal flow with refined processing states
        valid_transitions = {
            "IDLE": ["LISTENING", "WAITING", "PROCESSING", "PROCESSING_STT", "RESPONDING"],
            "LISTENING": ["PROCESSING", "PROCESSING_STT", "WAITING", "IDLE", "RESPONDING"],
            
            # Generic PROCESSING can go to any state (for backward compatibility)
            "PROCESSING": ["RESPONDING", "PROCESSING", "PROCESSING_STT", "PROCESSING_LLM", 
                          "PROCESSING_TTS", "WAITING", "IDLE", "LISTENING", "ERROR"],
            
            # Granular processing states
            "PROCESSING_STT": ["PROCESSING_LLM", "PROCESSING", "RESPONDING", "WAITING", "ERROR"],
            "PROCESSING_LLM": ["PROCESSING_TTS", "PROCESSING", "RESPONDING", "WAITING", "ERROR"],
            "PROCESSING_TTS": ["RESPONDING", "PROCESSING", "WAITING", "ERROR"],
            
            "RESPONDING": ["WAITING", "IDLE", "ERROR"],
            "WAITING": ["LISTENING", "IDLE", "PROCESSING", "PROCESSING_STT", "RESPONDING"],
            "ERROR": ["IDLE", "WAITING", "PROCESSING", "PROCESSING_STT", "LISTENING", "RESPONDING"]
        }
        
        return next_state in valid_transitions.get(current, [])
        
    async def _handle_deadlock(self, session_id, new_state, timeout):
        """
        Improved deadlock detection and resolution.
        Ensures conversations can continue even after state transition problems.
        
        Args:
            session_id: The session ID experiencing potential deadlock
            new_state: The state we're attempting to transition to
            timeout: The lock acquisition timeout
        """
        try:
            # Wait for the timeout period plus a buffer
            await asyncio.sleep(timeout + 0.5)
            
            # If we get here, the transition may be deadlocked
            self.logger.warning(
                f"Possible deadlock detected for session {session_id} "
                f"transitioning to {new_state}. Forcing resolution."
            )
            
            # Force a new lock to be created
            if session_id in self._state_locks:
                self._state_locks[session_id] = asyncio.Lock()
                
            # Force transition if the session still exists
            if session_id in self.sessions:
                session = self.sessions[session_id]
                previous_state = session.state
                
                # Update the state directly without lock
                session.state = new_state
                session.last_updated = time.time()
                
                self.logger.warning(
                    f"Forced state transition after deadlock: {session_id}: {previous_state} to {new_state}"
                )
                
                # Try to broadcast the state change
                try:
                    await self._broadcast_state_change(
                        session_id, previous_state, new_state, {"forced": True}
                    )
                except Exception as broadcast_error:
                    self.logger.error(f"Error broadcasting forced state change: {broadcast_error}")
                
                # If we've been stuck in a processing state for too long, force to WAITING
                if previous_state.startswith("PROCESSING") and new_state.startswith("PROCESSING"):
                    self.logger.warning(f"Detected potential hang in processing state for {session_id}")
                    try:
                        session.state = "WAITING"
                        await self._broadcast_state_change(
                            session_id, previous_state, "WAITING", 
                            {"message": "Ready for next question", "forced_recovery": True}
                        )
                        self.logger.info(f"Forced recovery to WAITING state for {session_id}")
                    except Exception as recovery_error:
                        self.logger.error(f"Error during forced recovery: {recovery_error}")
                    
        except asyncio.CancelledError:
            # Task was cancelled normally
            pass
        except Exception as e:
            self.logger.error(f"Error in deadlock handler: {e}")
            
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