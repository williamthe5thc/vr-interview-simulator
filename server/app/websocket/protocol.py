import json
import logging

logger = logging.getLogger("protocol")

def encode_message(message):
    """
    Encode a message dictionary to a JSON string for sending over WebSocket
    
    Args:
        message (dict): The message to encode
        
    Returns:
        str: JSON encoded message
    """
    try:
        return json.dumps(message)
    except Exception as e:
        logger.error(f"Error encoding message: {e}")
        return json.dumps({
            "type": "error",
            "message": "Error encoding message"
        })

def decode_message(raw_message):
    """
    Decode a raw WebSocket message to a dictionary
    
    Args:
        raw_message (str): The raw message from WebSocket
        
    Returns:
        dict: Decoded message as dictionary
        
    Raises:
        ValueError: If message cannot be decoded as JSON
    """
    try:
        if isinstance(raw_message, bytes):
            # Binary message, likely raw audio
            return {
                "type": "audio_data",
                "data": raw_message
            }
        else:
            # Text message, should be JSON
            decoded = json.loads(raw_message)
            
            # Log message type for debugging
            logger.debug(f"Decoded message of type: {decoded.get('type', 'unknown')}")
            
            # Log and validate client capabilities message specifically
            if decoded.get('type') == 'client_capabilities':
                logger.info(f"Received client capabilities: {decoded.get('capabilities', {})}")
                
                # Log session ID for debugging
                logger.debug(f"Client capabilities message session ID: {decoded.get('session_id', 'not provided')}")
                
            return decoded
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding message: {e}")
        logger.debug(f"Bad message: {raw_message[:100]}...")
        raise ValueError(f"Invalid JSON message: {e}")

def validate_message(message):
    """
    Validate that a message has the required fields and structure
    
    Args:
        message (dict): The message to validate
        
    Returns:
        bool: True if message is valid, False otherwise
    """
    if not isinstance(message, dict):
        logger.error(f"Message is not a dictionary: {type(message)}")
        return False
        
    # All messages must have a type
    if "type" not in message:
        logger.error("Message missing required 'type' field")
        return False
        
    # Validate different message types
    msg_type = message.get("type")
    
    # For messages that should have session_id
    if msg_type not in ["ping", "connection_request"]:
        if "session_id" not in message:
            logger.warning(f"Message of type '{msg_type}' missing 'session_id' field")
            # Not all messages need session_id, so don't fail validation for this
            # But log it for debugging purposes
        else:
            # Log the session ID for debugging
            logger.debug(f"Message session ID: {message['session_id']}")
    
    if msg_type == "audio_data":
        # Audio data must have data field
        if "data" not in message:
            logger.error("Audio message missing 'data' field")
            return False
    elif msg_type == "ping":
        # Ping is always valid
        # Extract the client's session ID if available
        if "session_id" in message:
            logger.debug(f"Received ping with client session ID: {message['session_id']}")
        pass
    elif msg_type == "control":
        # Control messages must have an action
        if "action" not in message:
            logger.error("Control message missing 'action' field")
            return False
        if message["action"] not in ["start", "stop", "reset", "begin", "timeout", "coach", "say"]:
            logger.error(f"Invalid control action: {message['action']}")
            return False
    elif msg_type == "playback_complete":
        # Playback complete notification from client
        # This is valid as long as it has a session_id
        if "session_id" not in message:
            logger.error("Playback complete message missing 'session_id' field")
            return False
        logger.info(f"Received playback complete notification for session {message.get('session_id')}")
        return True
    elif msg_type == "client_capabilities":
        # Client capabilities message
        # This is valid as long as it has capabilities
        if "capabilities" not in message:
            logger.error("Client capabilities message missing 'capabilities' field")
            return False
        logger.info(f"Received client capabilities: {message.get('capabilities')}")
        return True
    elif msg_type == "streaming_status":
        # Streaming status message
        # This is valid as long as it has status
        if "status" not in message:
            logger.error("Streaming status message missing 'status' field")
            return False
        if message["status"] not in ["started", "failed", "completed"]:
            logger.warning(f"Unexpected streaming status: {message['status']}")
        logger.info(f"Received streaming status: {message.get('status')}")
        return True
    elif msg_type in ["state_update", "audio_response", "text_response", "audio_stream_url", "audio_file_url", "pong", "error", "heartbeat", "system_message", "audio_chunk", "audio_chunk_ack", "capabilities_ack"]:
        # These are typically sent by the server, but we'll accept them from clients too
        return True
    else:
        # Unknown message type
        logger.warning(f"Unknown message type: {msg_type}")
        return False
        
    return True
