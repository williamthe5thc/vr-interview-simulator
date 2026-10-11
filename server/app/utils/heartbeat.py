"""
Heartbeat mechanism for keeping WebSocket connections alive during long operations.

This module provides a heartbeat service that sends periodic messages to clients
to prevent timeouts and keep the connection alive during long-running operations.
"""

import asyncio
import logging
from typing import Dict, Any, Callable, Awaitable, Optional

logger = logging.getLogger("heartbeat")

class HeartbeatService:
    """
    Service for sending periodic heartbeat messages to clients.
    
    This helps prevent WebSocket timeouts during long operations like
    LLM processing or speech synthesis.
    """
    
    def __init__(self, heartbeat_interval: float = 5.0):
        """
        Initialize the heartbeat service.
        
        Args:
            heartbeat_interval: Time between heartbeats in seconds
        """
        self.heartbeat_interval = heartbeat_interval
        self.active_tasks: Dict[str, asyncio.Task] = {}
        logger.info(f"Heartbeat service initialized with interval: {heartbeat_interval}s")
        
    async def start_heartbeat(
        self, 
        session_id: str, 
        send_func: Callable[[Dict[str, Any]], Awaitable[None]],
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Start sending heartbeat messages for a session.
        
        Args:
            session_id: Unique identifier for the session
            send_func: Function to call to send the heartbeat
            metadata: Additional data to include in heartbeat
        """
        # Stop any existing heartbeat for this session
        await self.stop_heartbeat(session_id)
        
        # Create a new heartbeat task
        task = asyncio.create_task(
            self._heartbeat_loop(session_id, send_func, metadata or {})
        )
        self.active_tasks[session_id] = task
        logger.debug(f"Started heartbeat for session {session_id}")
        
    async def stop_heartbeat(self, session_id: str):
        """
        Stop sending heartbeat messages for a session.
        
        Args:
            session_id: Unique identifier for the session
        """
        task = self.active_tasks.pop(session_id, None)
        if task:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            logger.debug(f"Stopped heartbeat for session {session_id}")
            
    async def stop_all(self):
        """Stop all active heartbeats."""
        session_ids = list(self.active_tasks.keys())
        for session_id in session_ids:
            await self.stop_heartbeat(session_id)
        logger.info("All heartbeats stopped")
        
    async def _heartbeat_loop(
        self, 
        session_id: str, 
        send_func: Callable[[Dict[str, Any]], Awaitable[None]],
        metadata: Dict[str, Any]
    ):
        """
        Internal loop that sends periodic heartbeat messages.
        
        Args:
            session_id: Unique identifier for the session
            send_func: Function to call to send the heartbeat
            metadata: Additional data to include in heartbeat
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
                    break
                    
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
                
                # Wait for next heartbeat
                await asyncio.sleep(interval)
                
        except asyncio.CancelledError:
            logger.debug(f"Heartbeat task cancelled for session {session_id}")
        except Exception as e:
            logger.error(f"Error in heartbeat loop for {session_id}: {e}")
