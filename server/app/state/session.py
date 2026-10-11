import time
import json
from datetime import datetime


class Session:
    """
    Represents a conversation session with a client.
    
    Stores session-specific data including:
    - Connection information
    - Conversation history
    - State information
    - Session metadata
    """
    
    def __init__(self, session_id, websocket):
        self.session_id = session_id
        self.websocket = websocket
        self.state = "IDLE"
        self.history = []
        self.metadata = {}
        self.created_at = time.time()
        self.last_updated = time.time()
        
    def add_interaction(self, user_input, system_response):
        """
        Record a user-system interaction in the conversation history
        """
        interaction = {
            "timestamp": datetime.now().isoformat(),
            "user_input": user_input,
            "system_response": system_response
        }
        self.history.append(interaction)
        self.last_updated = time.time()
        
    def get_context(self):
        """
        Get formatted conversation context for the LLM
        
        Returns a list of conversation turns formatted for the LLM context
        """
        context = []
        for interaction in self.history:
            context.append({
                "role": "user",
                "content": interaction["user_input"]
            })
            context.append({
                "role": "assistant",
                "content": interaction["system_response"]
            })
        return context
        
    def reset(self):
        """
        Reset the conversation history
        """
        self.history = []
        self.last_updated = time.time()
        
    def is_expired(self, timeout_seconds=1800):  # 30 minutes default
        """
        Check if the session has expired due to inactivity
        """
        return (time.time() - self.last_updated) > timeout_seconds
        
    def to_dict(self):
        """
        Convert session to a dictionary for storage or serialization
        """
        return {
            "session_id": self.session_id,
            "state": self.state,
            "history": self.history,
            "metadata": self.metadata,
            "created_at": datetime.fromtimestamp(self.created_at).isoformat(),
            "last_updated": datetime.fromtimestamp(self.last_updated).isoformat(),
            "duration_seconds": time.time() - self.created_at
        }
        
    def save_to_file(self, file_path):
        """
        Save the session data to a JSON file
        """
        try:
            with open(file_path, 'w') as f:
                json.dump(self.to_dict(), f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving session: {e}")
            return False
