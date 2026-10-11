"""
AllTalk Endpoint Mapper - Provides correct endpoint mappings for AllTalk TTS service.

This module fixes endpoint issues with the AllTalk TTS API by providing correct mappings
between the expected endpoints and the actual endpoints.
"""

import os
import logging
import requests
import time
from typing import Dict, List, Optional, Tuple

class AllTalkEndpointMapper:
    """
    Maps between expected and actual AllTalk endpoints.
    
    This is a non-invasive way to fix API endpoint issues without modifying the
    original AllTalk integration code.
    """
    
    def __init__(self, base_url: str = None):
        """Initialize the endpoint mapper with the base URL."""
        self.logger = logging.getLogger("alltalk_mapper")
        self.base_url = base_url or "http://127.0.0.1:7851"
        
        # Mapping from expected to actual endpoints
        self.endpoint_mapping = {
            "/api/ready": "/status",
            "/api/voices": "/voices",
            "/api/tts-generate": "/tts-generate",
            "/api/synthesize": "/synthesize",
            "/api/tts": "/tts"
        }
        
        # Cache for available voices
        self.available_voices = []
        self.last_check_time = 0
        
        # Check connections on startup
        self._check_connection()
        self.logger.info("AllTalk Endpoint Mapper initialized")
    
    def _check_connection(self) -> bool:
        """Check connection to AllTalk and cache available voices."""
        try:
            # Check if AllTalk is available
            response = requests.get(f"{self.base_url}/status", timeout=5)
            if response.status_code != 200:
                self.logger.warning(f"AllTalk returned status code {response.status_code}")
                return False
                
            # Get available voices
            try:
                voices_response = requests.get(f"{self.base_url}/voices", timeout=5)
                if voices_response.status_code == 200:
                    voices = voices_response.json()
                    if isinstance(voices, list):
                        self.available_voices = [v.get('name', v) if isinstance(v, dict) else v for v in voices]
                    self.logger.info(f"Found {len(self.available_voices)} voices")
                    self.last_check_time = time.time()
                else:
                    self.logger.warning(f"Failed to get voices: {voices_response.status_code}")
            except Exception as e:
                self.logger.warning(f"Error getting voices: {e}")
                
            return True
        except Exception as e:
            self.logger.warning(f"Error checking AllTalk connection: {e}")
            return False
    
    def map_endpoint(self, original_endpoint: str) -> str:
        """Map the original endpoint to the correct endpoint."""
        if original_endpoint in self.endpoint_mapping:
            return self.endpoint_mapping[original_endpoint]
        return original_endpoint
    
    def get_full_url(self, endpoint: str) -> str:
        """Get the full URL for an endpoint."""
        # Remove /api/ prefix if present
        if endpoint.startswith("/api/"):
            endpoint = endpoint[4:]
            
        # Remove leading slash if needed
        if endpoint.startswith("/"):
            endpoint = endpoint[1:]
            
        return f"{self.base_url}/{endpoint}"
    
    def get_available_voices(self, force_refresh: bool = False) -> List[str]:
        """Get the available voices, optionally refreshing the cache."""
        # Refresh if requested or cache is older than 5 minutes
        if force_refresh or (time.time() - self.last_check_time) > 300:
            self._check_connection()
        return self.available_voices
    
    def find_best_voice(self, requested_voice: str) -> str:
        """Find the best matching voice from available voices."""
        # Refresh if cache is older than 5 minutes
        if (time.time() - self.last_check_time) > 300:
            self._check_connection()
            
        # If the requested voice is available, use it
        if requested_voice in self.available_voices:
            return requested_voice
            
        # If not, try to find a similar voice
        if self.available_voices:
            # If the name contains a known voice prefix, try to find a match
            for prefix in ["en_", "alan", "english", "en-"]:
                if requested_voice.lower().startswith(prefix):
                    for voice in self.available_voices:
                        if voice.lower().startswith(prefix):
                            self.logger.info(f"Using similar voice: {voice} instead of {requested_voice}")
                            return voice
            
            # Otherwise, just use the first available voice
            self.logger.info(f"Using first available voice: {self.available_voices[0]} instead of {requested_voice}")
            return self.available_voices[0]
            
        # If no voices available, return the requested voice (will fail gracefully)
        return requested_voice
    
    def submit_tts_request(self, endpoint: str, text: str, voice: str, 
                          output_file: Optional[str] = None, timeout: int = 30) -> Tuple[bool, Optional[bytes]]:
        """
        Submit a TTS request to the correct endpoint.
        
        Args:
            endpoint: The endpoint to use
            text: The text to synthesize
            voice: The voice to use
            output_file: Optional output file name
            timeout: Request timeout in seconds
            
        Returns:
            Tuple of (success, response_data)
        """
        # Map the endpoint
        mapped_endpoint = self.map_endpoint(endpoint)
        full_url = self.get_full_url(mapped_endpoint)
        
        # Find the best voice
        best_voice = self.find_best_voice(voice)
        
        # Prepare the payload
        if mapped_endpoint in ["/tts-generate", "tts-generate"]:
            payload = {
                "text": text,
                "voice": best_voice
            }
            if output_file:
                payload["output_file"] = output_file
        else:
            payload = {
                "text": text,
                "voice": best_voice
            }
            
        try:
            response = requests.post(full_url, json=payload, timeout=timeout)
            if response.status_code == 200:
                return True, response.content
            else:
                self.logger.warning(f"TTS request failed: {response.status_code}")
                return False, None
        except Exception as e:
            self.logger.error(f"Error in TTS request: {e}")
            return False, None
