"""
EmotiVoice TTS implementation for emotional speech synthesis.
This module provides integration with the EmotiVoice TTS system,
which specializes in generating emotionally expressive speech.
"""

import logging
import requests
import json
import time
import os
import io
import hashlib
from typing import Optional, Dict, Any, List


class EmotiVoiceTTSService:
    """
    Text-to-speech service using EmotiVoice for emotional speech synthesis.
    """
    
    def __init__(self, config=None):
        self.logger = logging.getLogger("emotivoice_tts")
        
        # Set default configuration
        self.config = {
            "url": "http://localhost:8501",  # Default URL for EmotiVoice service
            "voice": "default",              # Default voice ID
            "language": "en",                # Default language (en or zh)
            "emotion": "neutral",            # Default emotion
            "timeout": 20,                   # Default timeout in seconds
            "cache_dir": "data/tts_cache/emotivoice"  # Cache directory
        }
        
        # Update with provided config
        if config:
            self.config.update(config)
        
        # Ensure cache directory exists
        os.makedirs(self.config["cache_dir"], exist_ok=True)
        
        # Initialize cache
        self.cache = {}
        self.max_cache_entries = 1000
        self._load_cache_index()
        
        # Check if the service is available
        self.server_available = self._check_server()
        
        self.logger.info(f"Initialized EmotiVoice TTS service with URL: {self.config['url']}, availability: {self.server_available}")
    
    def _check_server(self) -> bool:
        """Check if the EmotiVoice server is available."""
        try:
            response = requests.get(
                f"{self.config['url']}/health",
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            self.logger.warning(f"EmotiVoice server not available: {e}")
            return False
    
    def synthesize(self, text: str, emotion: str = None) -> bytes:
        """
        Synthesize speech from text with emotion.
        
        Args:
            text: The text to convert to speech
            emotion: Optional emotion override (happy, sad, angry, etc.)
            
        Returns:
            WAV audio data as bytes
        """
        if not text or not text.strip():
            self.logger.warning("Empty text provided to EmotiVoice TTS")
            return self._generate_silence()
        
        if not self.server_available:
            self.logger.warning("EmotiVoice server not available, returning silence")
            return self._generate_silence()
        
        # Use specified emotion or default
        emotion_to_use = emotion or self.config["emotion"]
        
        # Check cache first
        cache_key = self._create_cache_key(text, emotion_to_use)
        cached_audio = self._get_from_cache(cache_key)
        if cached_audio:
            self.logger.info(f"Using cached EmotiVoice audio for: {text[:30]}... (emotion: {emotion_to_use})")
            return cached_audio
        
        try:
            self.logger.info(f"Synthesizing with EmotiVoice: {len(text)} chars, emotion: {emotion_to_use}")
            start_time = time.time()
            
            # Call EmotiVoice API
            response = requests.post(
                f"{self.config['url']}/api/tts",
                json={
                    "text": text,
                    "voice": self.config["voice"],
                    "language": self.config["language"],
                    "emotion": emotion_to_use
                },
                timeout=self.config["timeout"]
            )
            
            if response.status_code != 200:
                self.logger.error(f"EmotiVoice API error: {response.status_code} {response.text}")
                return self._generate_silence()
            
            # Extract audio data from response
            audio_data = response.content
            
            # Track timing
            elapsed = time.time() - start_time
            self.logger.info(f"EmotiVoice synthesis complete: {len(audio_data)} bytes in {elapsed:.2f}s")
            
            # Add to cache
            self._add_to_cache(cache_key, audio_data)
            
            return audio_data
            
        except Exception as e:
            self.logger.error(f"Error in EmotiVoice synthesis: {e}")
            return self._generate_silence()
    
    def _create_cache_key(self, text: str, emotion: str) -> str:
        """Create a unique cache key for the text and emotion."""
        key_parts = f"{self.config['voice']}_{self.config['language']}_{emotion}_{text}"
        return hashlib.md5(key_parts.encode()).hexdigest()
    
    def _get_from_cache(self, key: str) -> Optional[bytes]:
        """Get audio data from cache if available."""
        if key in self.cache:
            cache_path = self.cache[key]
            try:
                with open(cache_path, 'rb') as f:
                    return f.read()
            except Exception as e:
                self.logger.warning(f"Failed to read cached audio: {e}")
        return None
    
    def _add_to_cache(self, key: str, audio_data: bytes) -> None:
        """Add audio data to cache."""
        if len(self.cache) >= self.max_cache_entries:
            # Remove oldest entries (10%)
            entries = list(self.cache.items())
            entries.sort(key=lambda x: os.path.getmtime(x[1]) if os.path.exists(x[1]) else 0)
            for old_key, old_path in entries[:max(1, len(entries) // 10)]:
                try:
                    if os.path.exists(old_path):
                        os.unlink(old_path)
                    del self.cache[old_key]
                except Exception as e:
                    self.logger.warning(f"Failed to remove cache entry: {e}")
        
        # Save new cache entry
        cache_path = os.path.join(self.config["cache_dir"], f"{key}.wav")
        try:
            with open(cache_path, 'wb') as f:
                f.write(audio_data)
            self.cache[key] = cache_path
            self._save_cache_index()
        except Exception as e:
            self.logger.error(f"Failed to cache audio: {e}")
    
    def _load_cache_index(self) -> None:
        """Load cache index from disk."""
        index_path = os.path.join(self.config["cache_dir"], "cache_index.json")
        if os.path.exists(index_path):
            try:
                with open(index_path, 'r') as f:
                    self.cache = json.load(f)
                self.logger.info(f"Loaded {len(self.cache)} EmotiVoice cache entries")
            except Exception as e:
                self.logger.warning(f"Failed to load EmotiVoice cache index: {e}")
                self.cache = {}
    
    def _save_cache_index(self) -> None:
        """Save cache index to disk."""
        index_path = os.path.join(self.config["cache_dir"], "cache_index.json")
        try:
            with open(index_path, 'w') as f:
                json.dump(self.cache, f)
        except Exception as e:
            self.logger.warning(f"Failed to save EmotiVoice cache index: {e}")
    
    def _generate_silence(self, duration_ms: int = 1000) -> bytes:
        """Generate silent audio as a fallback."""
        try:
            from pydub import AudioSegment
            
            silence = AudioSegment.silent(duration=duration_ms)
            output = io.BytesIO()
            silence.export(output, format="wav")
            output.seek(0)
            return output.read()
            
        except Exception as e:
            self.logger.error(f"Failed to generate silent audio: {e}")
            # Return minimal WAV header
            return bytes.fromhex(
                "52494646" +  # "RIFF"
                "2C000000" +  # Chunk size (44 bytes)
                "57415645" +  # "WAVE"
                "666D7420" +  # "fmt "
                "10000000" +  # Subchunk1 size (16 bytes)
                "0100" +      # Audio format (1 = PCM)
                "0100" +      # Num channels (1)
                "44AC0000" +  # Sample rate (44100)
                "88580100" +  # Byte rate (44100*2)
                "0200" +      # Block align (2)
                "1000" +      # Bits per sample (16)
                "64617461" +  # "data"
                "00000000"    # Subchunk2 size (0 bytes of data)
            )
    
    def is_available(self) -> bool:
        """Check if EmotiVoice is available."""
        return self.server_available
    
    def get_available_voices(self) -> List[str]:
        """Get a list of available EmotiVoice voices."""
        if not self.server_available:
            return []
            
        try:
            response = requests.get(
                f"{self.config['url']}/api/voices",
                timeout=5
            )
            if response.status_code == 200:
                return response.json().get("voices", [])
            return []
        except Exception as e:
            self.logger.warning(f"Failed to get EmotiVoice voices: {e}")
            return []
    
    def get_available_emotions(self) -> List[str]:
        """Get a list of available emotions."""
        # Static list of common emotions supported by EmotiVoice
        return [
            "neutral", 
            "happy", 
            "sad", 
            "angry", 
            "fear", 
            "surprise",
            "disgust"
        ]
