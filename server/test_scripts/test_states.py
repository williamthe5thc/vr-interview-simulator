"""
Test script for the new granular state system.

This script creates a mock session and tests various state transitions
to verify that the new granular processing states work correctly.
"""

import asyncio
import logging
import sys
import os
import json
import time
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import required components
from app.state.manager import StateManager, States
from app.state.session import Session


# Set up basic logging for testing
def setup_test_logging():
    """Configure logging for tests."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )


# Mock WebSocket class for testing
class MockWebSocket:
    """Mock WebSocket class for testing state transitions."""
    
    def __init__(self):
        self.sent_messages = []
        self.closed = False
        
    async def send(self, message):
        """Record sent messages."""
        self.sent_messages.append(message)
        print(f"WebSocket sent: {message}")
        
    async def close(self):
        """Mark as closed."""
        self.closed = True
        
    def get_state_updates(self):
        """Extract state updates from sent messages."""
        updates = []
        for msg in self.sent_messages:
            try:
                data = json.loads(msg)
                if data.get("type") == "state_update":
                    updates.append(data)
            except json.JSONDecodeError:
                pass
        return updates


async def test_state_transitions():
    """Test the state transition flow with the new granular states."""
    # Set up logging
    setup_test_logging()
    logger = logging.getLogger("test")
    
    # Create state manager
    state_manager = StateManager()
    
    # Create mock websocket
    websocket = MockWebSocket()
    
    # Create test session
    session_id = f"test_{int(time.time())}"
    session = Session(session_id, websocket)
    
    # Register session with state manager
    state_manager.create_session(session_id, session)
    
    # Wait for initial state
    await asyncio.sleep(0.5)
    
    # Print current state
    print(f"Initial state: {state_manager.get_session_state(session_id)}")
    
    # Test normal conversation flow
    print("\n=== Testing normal conversation flow ===")
    
    # 1. Transition to LISTENING
    print("\nTransitioning to LISTENING...")
    await state_manager.transition_state(session_id, "LISTENING", {
        "message": "Receiving audio"
    })
    
    print(f"Current state: {state_manager.get_session_state(session_id)}")
    
    # 2. Transition to PROCESSING_STT
    print("\nTransitioning to PROCESSING_STT...")
    await state_manager.transition_state(session_id, "PROCESSING_STT", {
        "message": "Transcribing your speech to text",
        "progress": 0.0
    })
    
    print(f"Current state: {state_manager.get_session_state(session_id)}")
    
    # Update progress
    await asyncio.sleep(0.5)
    await state_manager.transition_state(session_id, "PROCESSING_STT", {
        "message": "Transcribing your speech to text",
        "progress": 0.5
    })
    
    # Complete STT
    await asyncio.sleep(0.5)
    await state_manager.transition_state(session_id, "PROCESSING_STT", {
        "message": "Speech transcribed successfully",
        "progress": 1.0,
        "transcript": "Tell me about your experience with project management."
    })
    
    print(f"Current state: {state_manager.get_session_state(session_id)}")
    
    # 3. Transition to PROCESSING_LLM
    print("\nTransitioning to PROCESSING_LLM...")
    await state_manager.transition_state(session_id, "PROCESSING_LLM", {
        "message": "Generating response to your question",
        "progress": 0.0
    })
    
    print(f"Current state: {state_manager.get_session_state(session_id)}")
    
    # Update LLM progress
    await asyncio.sleep(0.5)
    await state_manager.transition_state(session_id, "PROCESSING_LLM", {
        "message": "I'm thinking about your question...",
        "progress": 0.3
    })
    
    await asyncio.sleep(0.5)
    await state_manager.transition_state(session_id, "PROCESSING_LLM", {
        "message": "Almost ready with a response...",
        "progress": 0.8
    })
    
    # Complete LLM
    await asyncio.sleep(0.5)
    await state_manager.transition_state(session_id, "PROCESSING_LLM", {
        "message": "Response generated successfully",
        "progress": 1.0
    })
    
    print(f"Current state: {state_manager.get_session_state(session_id)}")
    
    # 4. Transition to PROCESSING_TTS
    print("\nTransitioning to PROCESSING_TTS...")
    await state_manager.transition_state(session_id, "PROCESSING_TTS", {
        "message": "Converting response to speech",
        "progress": 0.0
    })
    
    print(f"Current state: {state_manager.get_session_state(session_id)}")
    
    # Update TTS progress
    await asyncio.sleep(0.5)
    await state_manager.transition_state(session_id, "PROCESSING_TTS", {
        "message": "Generating audio from text",
        "progress": 0.5
    })
    
    # Complete TTS
    await asyncio.sleep(0.5)
    await state_manager.transition_state(session_id, "PROCESSING_TTS", {
        "message": "Audio generation complete",
        "progress": 1.0
    })
    
    print(f"Current state: {state_manager.get_session_state(session_id)}")
    
    # 5. Transition to RESPONDING
    print("\nTransitioning to RESPONDING...")
    await state_manager.transition_state(session_id, "RESPONDING", {
        "message": "Playing response"
    })
    
    print(f"Current state: {state_manager.get_session_state(session_id)}")
    
    # 6. Transition to WAITING
    print("\nTransitioning to WAITING...")
    await state_manager.transition_state(session_id, "WAITING", {
        "message": "Waiting for user input"
    })
    
    print(f"Current state: {state_manager.get_session_state(session_id)}")
    
    # Test error handling
    print("\n=== Testing error handling ===")
    
    # 1. Start normal flow again
    await state_manager.transition_state(session_id, "LISTENING", {
        "message": "Receiving audio"
    })
    
    await state_manager.transition_state(session_id, "PROCESSING_STT", {
        "message": "Transcribing your speech to text",
        "progress": 0.0
    })
    
    # 2. Simulate STT error
    print("\nSimulating STT error...")
    await state_manager.transition_state(session_id, "ERROR", {
        "message": "Failed to understand your speech",
        "error_type": "STT_ERROR"
    })
    
    print(f"Current state: {state_manager.get_session_state(session_id)}")
    
    # 3. Recover from error
    print("\nRecovering from error...")
    await state_manager.transition_state(session_id, "WAITING", {
        "message": "Ready for your next question"
    })
    
    print(f"Current state: {state_manager.get_session_state(session_id)}")
    
    # Test backward compatibility
    print("\n=== Testing backward compatibility ===")
    
    # 1. Use generic PROCESSING state
    print("\nUsing generic PROCESSING state...")
    await state_manager.transition_state(session_id, "LISTENING", {
        "message": "Receiving audio"
    })
    
    await state_manager.transition_state(session_id, "PROCESSING", {
        "message": "Processing your request"
    })
    
    print(f"Current state: {state_manager.get_session_state(session_id)}")
    
    # 2. Transition from generic PROCESSING to specific state
    print("\nTransitioning from PROCESSING to PROCESSING_TTS...")
    await state_manager.transition_state(session_id, "PROCESSING_TTS", {
        "message": "Converting response to speech"
    })
    
    print(f"Current state: {state_manager.get_session_state(session_id)}")
    
    # Print state transition history
    print("\n=== State Transition History ===")
    state_updates = websocket.get_state_updates()
    for i, update in enumerate(state_updates):
        print(f"{i+1}. {update['previous']} → {update['current']}: {update.get('metadata', {}).get('message', '')}")
    
    # End session
    await state_manager.end_session(session_id)
    print("\nSession ended")
    
    return state_updates


if __name__ == "__main__":
    # Run the test
    asyncio.run(test_state_transitions())