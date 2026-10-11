"""
 TTS Service for VR Interview System

This module provides a consolidated TTS service that primarily uses the AllTalk direct API
with fallback to gTTS when needed. It includes caching, error handling, and supports
multiple API endpoints for improved reliability.
"""

import requests
import json
import logging
import time
import uuid
import os
import io
import hashlib
import traceback
from typing import Dict, Any, Optional, List, Union
import tempfile
from gtts import gTTS
from pydub import AudioSegment


class TTSService:
    """
    TTS service with AllTalk direct API and gTTS fallback.
    
    Features:
    - Primary use of AllTalk direct API for high-quality speech
    - Multiple API endpoint attempts for reliable operation
    - Automatic fallback to gTTS when AllTalk is unavailable
    - Response caching to improve performance
    - Robust error handling with graceful degradation
    """
    
    def __init__(self, config=None):
        self.logger = logging.getLogger("tts")
        
        # Default configuration
        self.default_config = {
            "alltalk": {
                "url": "http://127.0.0.1:7851",
                "voice": "female_06.wav",
                "retries": 3,
                "timeout": 40,
                "endpoints": ["tts-generate", "synthesize", "tts"],
                "alltalk_dir": "PATH_TO_ALLTALK/alltalk_tts"
            },
            # "engine": "alltalk" (XTTS voices, default) or "kokoro" (tools/tts_worker.py on port 8771, about 4x faster).
            # With "kokoro" any failure falls back to AllTalk, so the interview never goes silent.
            "engine": "alltalk",
            "kokoro": {
                "url": "http://127.0.0.1:8771",
                "timeout": 20,
                # by interviewer name (the headset's cast sends it in "begin"), so no headset change is needed
                "voices": {
                    "Dana Whitfield": "af_heart", "Margaret Ellis": "bf_emma", "Linda Foster": "af_nicole", "Rachel Grant": "af_bella",
                    "Daniel Hayes": "am_michael", "Marcus Reed": "am_onyx", "Eric Carter": "am_eric", "Victor Brooks": "bm_george",
                    "Samuel Hughes": "am_adam", "Thomas Irwin": "bm_lewis", "Gregory Jensen": "bm_daniel"
                },
                "default_female": "af_heart",
                "default_male": "am_adam"
            },
            "gtts": {
                "language": "en",
                "tld": "com"  # Top-level domain for gTTS server
            },
            "cache": {
                "enabled": True,
                "dir": "data/cache/tts",
                "max_entries": 1000
            }
        }
        
        # Merge with provided config
        self.config = self.default_config.copy()
        if config:
            self._deep_update(self.config, config)
        
        # Initialize logger
        self.logger.info("Initializing TTS Service")
        
        # Extract config values for convenience
        self.base_url = self.config["alltalk"]["url"].rstrip('/')
        self.voice = self.config["alltalk"]["voice"]
        self.timeout = self.config["alltalk"]["timeout"]
        self.alltalk_dir = self.config["alltalk"]["alltalk_dir"]
        self.outputs_dir = os.path.join(self.alltalk_dir, "outputs")
        
        # Check if directories exist
        if not os.path.exists(self.alltalk_dir):
            self.logger.warning(f"AllTalk directory does not exist: {self.alltalk_dir}")
        if not os.path.exists(self.outputs_dir):
            self.logger.warning(f"AllTalk outputs directory does not exist: {self.outputs_dir}")
        
        # Initialize caching system
        if self.config["cache"]["enabled"]:
            self.cache_dir = self.config["cache"]["dir"]
            os.makedirs(self.cache_dir, exist_ok=True)
            self.cache = {}
            self.max_cache_entries = self.config["cache"]["max_entries"]
            self._load_cache_index()
        
        # Check if AllTalk is available
        self.alltalk_available = self._check_alltalk_server()
        
        if self.alltalk_available:
            self.logger.info(f"AllTalk TTS service available at {self.base_url}")
            # Get available voices
            self.available_voices = self._get_available_voices()
            if self.available_voices:
                self.logger.info(f"Found {len(self.available_voices)} voices")
                # Check if selected voice is available
                if self.voice not in self.available_voices and self.available_voices:
                    self.logger.warning(f"Voice {self.voice} not found, using {self.available_voices[0]}")
                    self.voice = self.available_voices[0]
        else:
            self.logger.warning("AllTalk TTS service not available, will use gTTS fallback")
        
        # Create temporary directory for fallbacks
        os.makedirs("audio_out", exist_ok=True)

    def set_interviewer(self, name):
        """The interviewer's name (from the headset's cast); with engine "kokoro" it picks that interviewer's voice."""
        self.interviewer = (name or "").strip()
        self._pick_kokoro_voice()

    def _pick_kokoro_voice(self):
        cfg = self.config.get("kokoro", {})
        voice = (cfg.get("voices") or {}).get(getattr(self, "interviewer", ""))
        if not voice:
            male = "male" in (self.voice or "").lower()
            voice = cfg.get("default_male" if male else "default_female", "af_heart")
        if voice != getattr(self, "kokoro_voice", None):
            self.logger.info(f"Kokoro voice set to {voice} for {getattr(self, 'interviewer', '') or 'default interviewer'}")
        self.kokoro_voice = voice

    def _synthesize_kokoro(self, text: str) -> Optional[bytes]:
        """WAV from the Kokoro worker, or None when it is down (checked at most every 30 s) so the caller can fall back to AllTalk."""
        if time.time() < getattr(self, "_kokoro_retry_at", 0):
            return None
        cfg = self.config.get("kokoro", {})
        if not getattr(self, "kokoro_voice", None):
            self._pick_kokoro_voice()
        try:
            response = requests.post(f"{cfg.get('url', 'http://127.0.0.1:8771')}/synthesize",
                                     json={"text": text, "voice": self.kokoro_voice}, timeout=cfg.get("timeout", 20))
            if response.status_code == 200 and len(response.content) > 1000:
                return response.content
            raise RuntimeError(f"HTTP {response.status_code}: {response.text[:100]}")
        except Exception as e:
            self.logger.warning(f"Kokoro worker unavailable ({e}); using AllTalk for the next 30 s")
            self._kokoro_retry_at = time.time() + 30
            return None

    def set_voice(self, voice):
        """Switch the AllTalk voice (e.g. 'male_02.wav') for the following replies; unknown names are ignored."""
        if not voice:
            return
        self.voice_file_requested = voice
        if self.config.get("engine") == "kokoro":
            # the Kokoro voice is chosen by interviewer name; the voice file only decides male/female when the name is unknown
            self.voice = voice if voice.lower().endswith(".wav") else voice + ".wav"
            self._pick_kokoro_voice()
        if not voice.lower().endswith(".wav"):
            voice += ".wav"
        known = getattr(self, "available_voices", None)
        if known and voice not in known:
            self.logger.warning(f"Voice {voice} is not available; keeping {self.voice}")
            return
        if voice != self.voice:
            self.voice = voice
            self.logger.info(f"TTS voice set to {voice}")
    
    def _deep_update(self, base_dict: Dict, update_dict: Dict) -> None:
        """Recursively update a nested dictionary."""
        for key, value in update_dict.items():
            if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                self._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value
    
    def _check_alltalk_server(self) -> bool:
        """Check if AllTalk server is available."""
        endpoints_to_try = [
            "/status",
            "/api/ready",
            "/api/status"
        ]
        
        for endpoint in endpoints_to_try:
            try:
                response = requests.get(f"{self.base_url}{endpoint}", timeout=5)
                if response.status_code == 200:
                    self.logger.info(f"AllTalk available via {endpoint}")
                    return True
            except Exception as e:
                self.logger.debug(f"Endpoint {endpoint} check failed: {e}")
                continue
        
        return False
    
    def _get_available_voices(self) -> List[str]:
        """Get available voices from AllTalk server."""
        endpoints_to_try = [
            "/voices",
            "/api/voices"
        ]
        
        for endpoint in endpoints_to_try:
            try:
                response = requests.get(f"{self.base_url}{endpoint}", timeout=5)
                if response.status_code == 200:
                    try:
                        data = response.json()
                        if isinstance(data, list):
                            # Direct list of voices
                            return [v.get('name', v) if isinstance(v, dict) else v for v in data]
                        elif isinstance(data, dict) and "voices" in data:
                            # Dict with voices key
                            voices = data["voices"]
                            return [v.get('name', v) if isinstance(v, dict) else v for v in voices]
                    except Exception as e:
                        self.logger.warning(f"Error parsing voices response: {e}")
            except Exception as e:
                self.logger.debug(f"Endpoint {endpoint} check failed: {e}")
                continue
        
        return []
    
    def synthesize(self, text: str, session_id: Optional[str] = None) -> bytes:
        """
        Convert text to speech using AllTalk with gTTS fallback.
        
        Args:
            text: Text to convert to speech
            session_id: Optional session ID for tracking (not used internally)
            
        Returns:
            WAV audio data as bytes
        """
        if not text:
            self.logger.warning("Empty text provided to synthesize")
            return self._generate_silence()
        
        # Check cache first if enabled
        if self.config["cache"]["enabled"]:
            cache_key = self._create_cache_key(text)
            cached_audio = self._get_from_cache(cache_key)
            if cached_audio:
                self.logger.info(f"Using cached TTS response for text: {text[:30]}...")
                return cached_audio
        
        # Kokoro engine (config tts engine = "kokoro"): fast path, AllTalk below is the fallback
        if self.config.get("engine") == "kokoro":
            audio_data = self._synthesize_kokoro(text)
            if audio_data:
                if self.config["cache"]["enabled"]:
                    self._add_to_cache(self._create_cache_key(text), audio_data)
                return audio_data

        # Check if AllTalk is available
        # We only do this periodically to avoid slowing down when AllTalk is down
        if not hasattr(self, '_last_check_time') or time.time() - self._last_check_time > 60:
            self.alltalk_available = self._check_alltalk_server()
            self._last_check_time = time.time()
        
        # If AllTalk is available, try to use it first
        if self.alltalk_available:
            try:
                self.logger.info(f"Synthesizing with AllTalk: {len(text)} characters")
                
                # Try multiple AllTalk API methods in sequence for best reliability
                audio_data = self._try_alltalk_api_methods(text)
                
                # If successful, cache and return the audio
                if audio_data and len(audio_data) > 1000:
                    if self.config["cache"]["enabled"]:
                        self._add_to_cache(self._create_cache_key(text), audio_data)
                    return audio_data
                
                # If we get here, AllTalk methods failed
                self.logger.warning("All AllTalk methods failed, falling back to gTTS")
            except Exception as e:
                self.logger.error(f"Error in AllTalk synthesis: {e}")
                self.logger.warning("Falling back to gTTS after AllTalk error")
        
        # If we get here, use gTTS as fallback
        try:
            audio_data = self._synthesize_gtts(text)
            
            # Cache the result if enabled
            if audio_data and len(audio_data) > 1000 and self.config["cache"]["enabled"]:
                self._add_to_cache(self._create_cache_key(text), audio_data)
                
            return audio_data
        except Exception as e:
            self.logger.error(f"Error in gTTS synthesis: {e}")
            return self._generate_silence()
    
    def _try_alltalk_api_methods(self, text: str) -> Optional[bytes]:
        """Try multiple AllTalk API methods in sequence."""
        # Try each API endpoint in the configured order
        for endpoint in self.config["alltalk"]["endpoints"]:
            method_name = f"_try_{endpoint.replace('-', '_')}_api"
            method = getattr(self, method_name, None)
            
            if method:
                try:
                    self.logger.debug(f"Trying AllTalk method: {method_name}")
                    audio_data = method(text)
                    if audio_data and len(audio_data) > 1000:
                        self.logger.info(f"Successfully generated audio using {method_name}: {len(audio_data)} bytes")
                        return audio_data
                except Exception as e:
                    self.logger.warning(f"Method {method_name} failed: {e}")
            else:
                self.logger.warning(f"Method {method_name} not implemented")
        
        # Look for recently generated files in case the API returned success but no content
        try:
            timestamp = int(time.time())
            filename_pattern = f"vr_interview_{timestamp - 5}"  # Look for files from the last 5 seconds
            audio_data = self._try_load_output_file(filename_pattern)
            if audio_data:
                self.logger.info(f"Found recently generated audio file: {len(audio_data)} bytes")
                return audio_data
        except Exception as e:
            self.logger.warning(f"Error looking for recent files: {e}")
        
        return None
    
    def _try_tts_generate_api(self, text: str) -> Optional[bytes]:
        """Try generating speech using tts-generate API."""
        # Create a safe output filename without special characters
        timestamp = int(time.time())
        output_file = f"vr_interview_{timestamp}_{uuid.uuid4().hex[:6]}"   # unique: streamed chunks can be synthesized in the same second

        try:
            # First try with form data
            response = requests.post(
                f"{self.base_url}/api/tts-generate",
                data={
                    "text_input": text,
                    "character_voice_gen": self.voice,
                    "format": "wav",
                    "output_file_name": output_file
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=self.timeout
            )
            
            # Check for success
            if response.status_code == 200:
                # Check if response has content
                if len(response.content) > 1000:
                    # Save to local file for caching
                    try:
                        os.makedirs("audio_out", exist_ok=True)
                        with open(f"audio_out/{output_file}.wav", "wb") as f:
                            f.write(response.content)
                    except Exception as e:
                        self.logger.warning(f"Could not save audio file: {e}")
                    
                    return response.content
                else:
                    # Try to find the file that may have been generated
                    audio_data = self._try_load_output_file(output_file)
                    if audio_data:
                        return audio_data
            
            # If form data failed, try with JSON
            response = requests.post(
                f"{self.base_url}/api/tts-generate",
                json={
                    "text": text,
                    "voice": self.voice,
                    "output_file": f"{output_file}.wav",
                    "format": "wav"
                },
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                if len(response.content) > 1000:
                    return response.content
                else:
                    # Try to find the file that may have been generated
                    audio_data = self._try_load_output_file(output_file)
                    if audio_data:
                        return audio_data
        except Exception as e:
            self.logger.warning(f"Error using tts-generate API: {e}")
        
        return None
    
    def _try_synthesize_api(self, text: str) -> Optional[bytes]:
        """Try generating speech using synthesize API."""
        try:
            # Try form data first
            response = requests.post(
                f"{self.base_url}/api/synthesize",
                data={
                    "text": text,
                    "voice": self.voice,
                    "format": "wav"
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=self.timeout
            )
            
            if response.status_code == 200 and len(response.content) > 1000:
                # Save to local file for caching
                timestamp = int(time.time())
                output_file = f"vr_interview_synth_{timestamp}"
                try:
                    with open(f"audio_out/{output_file}.wav", "wb") as f:
                        f.write(response.content)
                except Exception as e:
                    self.logger.warning(f"Could not save audio file: {e}")
                
                return response.content
            
            # Try JSON if form data failed
            response = requests.post(
                f"{self.base_url}/api/synthesize",
                json={
                    "text": text,
                    "voice": self.voice,
                    "format": "wav"
                },
                timeout=self.timeout
            )
            
            if response.status_code == 200 and len(response.content) > 1000:
                return response.content
            
            # Try without /api prefix as a last resort
            response = requests.post(
                f"{self.base_url}/synthesize",
                json={
                    "text": text,
                    "voice": self.voice,
                    "format": "wav"
                },
                timeout=self.timeout
            )
            
            if response.status_code == 200 and len(response.content) > 1000:
                return response.content
        except Exception as e:
            self.logger.warning(f"Error using synthesize API: {e}")
        
        return None
    
    def _try_tts_api(self, text: str) -> Optional[bytes]:
        """Try generating speech using tts API."""
        try:
            # Try JSON format first
            response = requests.post(
                f"{self.base_url}/api/tts",
                json={
                    "text": text,
                    "voice": self.voice
                },
                timeout=self.timeout
            )
            
            if response.status_code == 200 and len(response.content) > 1000:
                # Save to local file for caching
                timestamp = int(time.time())
                output_file = f"vr_interview_tts_{timestamp}"
                try:
                    with open(f"audio_out/{output_file}.wav", "wb") as f:
                        f.write(response.content)
                except Exception as e:
                    self.logger.warning(f"Could not save audio file: {e}")
                
                return response.content
            
            # Try without /api prefix as a last resort
            response = requests.post(
                f"{self.base_url}/tts",
                json={
                    "text": text,
                    "voice": self.voice
                },
                timeout=self.timeout
            )
            
            if response.status_code == 200 and len(response.content) > 1000:
                return response.content
        except Exception as e:
            self.logger.warning(f"Error using tts API: {e}")
        
        return None
    
    def _try_load_output_file(self, filename_base: str) -> Optional[bytes]:
        """
        Try to find and load AllTalk output file from possible locations.
        
        Args:
            filename_base: Base filename without extension
            
        Returns:
            Audio data as bytes if found, None otherwise
        """
        # First look for exact matches
        possible_paths = [
            os.path.join(self.outputs_dir, f"{filename_base}.wav"),
            os.path.join(self.outputs_dir, f"{filename_base}_gen.wav"),
            os.path.join(self.alltalk_dir, "outputs", f"{filename_base}.wav"),
            os.path.join(self.alltalk_dir, "outputs", f"{filename_base}_gen.wav"),
            f"audio_out/{filename_base}.wav",
        ]
        
        for path in possible_paths:
            try:
                if os.path.exists(path):
                    self.logger.info(f"Found generated audio file: {path}")
                    with open(path, "rb") as f:
                        data = f.read()
                        if len(data) > 1000:
                            return data
            except Exception as e:
                self.logger.warning(f"Error reading potential file {path}: {e}")
        
        # If no exact matches, look for files containing the base name
        try:
            if os.path.exists(self.outputs_dir):
                files = os.listdir(self.outputs_dir)
                matching_files = [f for f in files if filename_base in f and f.endswith('.wav')]
                if matching_files:
                    # Sort by modification time (most recent first)
                    matching_files.sort(key=lambda f: os.path.getmtime(os.path.join(self.outputs_dir, f)), reverse=True)
                    most_recent = matching_files[0]
                    full_path = os.path.join(self.outputs_dir, most_recent)
                    self.logger.info(f"Found matching audio file: {full_path}")
                    with open(full_path, "rb") as f:
                        data = f.read()
                        if len(data) > 1000:
                            return data
        except Exception as e:
            self.logger.warning(f"Error searching for matching files: {e}")
            
        # Finally, try the most recent file in the outputs directory
        try:
            most_recent_file = self._find_most_recent_wav(self.outputs_dir)
            if most_recent_file:
                # Check if it's recent enough (created in the last 10 seconds)
                file_time = os.path.getmtime(most_recent_file)
                if time.time() - file_time < 10:
                    self.logger.info(f"Using most recent WAV file: {most_recent_file}")
                    with open(most_recent_file, "rb") as f:
                        data = f.read()
                        if len(data) > 1000:
                            return data
        except Exception as e:
            self.logger.warning(f"Error finding most recent WAV file: {e}")
        
        return None
    
    def _find_most_recent_wav(self, directory: str) -> Optional[str]:
        """Find the most recently modified WAV file in a directory."""
        try:
            if not os.path.exists(directory):
                return None
                
            wav_files = [f for f in os.listdir(directory) if f.endswith('.wav')]
            if not wav_files:
                return None
                
            wav_files.sort(key=lambda f: os.path.getmtime(os.path.join(directory, f)), reverse=True)
            return os.path.join(directory, wav_files[0])
        except Exception as e:
            self.logger.warning(f"Error finding most recent WAV file: {e}")
            return None
    
    def _synthesize_gtts(self, text: str) -> bytes:
        """
        Fallback synthesis using gTTS.
        
        Args:
            text: The text to convert to speech
            
        Returns:
            WAV audio data as bytes
        """
        try:
            start_time = time.time()
            
            # Use gTTS to generate MP3
            tts = gTTS(
                text=text, 
                lang=self.config["gtts"]["language"],
                tld=self.config["gtts"]["tld"]
            )
            
            mp3_fp = io.BytesIO()
            tts.write_to_fp(mp3_fp)
            mp3_fp.seek(0)
            
            # Convert MP3 to WAV
            audio = AudioSegment.from_mp3(mp3_fp)
            wav_fp = io.BytesIO()
            audio.export(wav_fp, format="wav")
            wav_fp.seek(0)
            audio_data = wav_fp.read()
            
            duration = time.time() - start_time
            self.logger.info(f"gTTS synthesis complete: {len(audio_data)} bytes in {duration:.2f}s")
            
            # Save to file for possible retrieval later
            timestamp = int(time.time())
            output_file = f"vr_interview_gtts_{timestamp}"
            
            try:
                with open(f"audio_out/{output_file}.wav", "wb") as f:
                    f.write(audio_data)
            except Exception as save_error:
                self.logger.warning(f"Failed to save gTTS audio file: {save_error}")
                
            return audio_data
            
        except Exception as e:
            self.logger.error(f"Error in gTTS synthesis: {e}\n{traceback.format_exc()}")
            return self._generate_silence()
    
    def _create_cache_key(self, text: str) -> str:
        """Create a unique cache key based on the text and voice."""
        engine_voice = f"kokoro:{getattr(self, 'kokoro_voice', '')}" if self.config.get("engine") == "kokoro" else self.voice
        key_string = f"{engine_voice}_{text}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _get_from_cache(self, key: str) -> Optional[bytes]:
        """Get audio data from cache if available."""
        if not self.config["cache"]["enabled"] or key not in self.cache:
            return None
            
        cache_path = self.cache[key]
        try:
            if os.path.exists(cache_path):
                with open(cache_path, 'rb') as f:
                    return f.read()
        except Exception as e:
            self.logger.warning(f"Failed to read from cache: {e}")
        
        return None
    
    def _add_to_cache(self, key: str, audio_data: bytes) -> None:
        """Add audio data to cache."""
        if not self.config["cache"]["enabled"]:
            return
            
        # Limit cache size by removing old entries if needed
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
        cache_path = os.path.join(self.cache_dir, f"{key}.wav")
        try:
            with open(cache_path, 'wb') as f:
                f.write(audio_data)
            self.cache[key] = cache_path
            self._save_cache_index()
        except Exception as e:
            self.logger.error(f"Failed to cache audio: {e}")
    
    def _load_cache_index(self) -> None:
        """Load cache index from disk."""
        if not self.config["cache"]["enabled"]:
            return
            
        index_path = os.path.join(self.cache_dir, "cache_index.json")
        if os.path.exists(index_path):
            try:
                with open(index_path, 'r') as f:
                    self.cache = json.load(f)
                self.logger.info(f"Loaded {len(self.cache)} TTS cache entries")
            except Exception as e:
                self.logger.warning(f"Failed to load cache index: {e}")
                self.cache = {}
        else:
            self.cache = {}
    
    def _save_cache_index(self) -> None:
        """Save cache index to disk."""
        if not self.config["cache"]["enabled"]:
            return
            
        index_path = os.path.join(self.cache_dir, "cache_index.json")
        try:
            with open(index_path, 'w') as f:
                json.dump(self.cache, f)
        except Exception as e:
            self.logger.warning(f"Failed to save cache index: {e}")
    
    def _generate_silence(self, duration_ms: int = 1000) -> bytes:
        """
        Generate silent audio as a last resort fallback.
        
        Args:
            duration_ms: Duration of silence in milliseconds
            
        Returns:
            WAV audio data as bytes
        """
        try:
            silence = AudioSegment.silent(duration=duration_ms)
            wav_fp = io.BytesIO()
            silence.export(wav_fp, format="wav")
            wav_fp.seek(0)
            return wav_fp.read()
        except Exception as e:
            self.logger.error(f"Failed to generate silent audio: {e}")
            # Return an empty WAV file (44-byte header)
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
        """Check if any TTS service is available."""
        # gTTS is always available as fallback
        return True
    
    def get_available_voices(self) -> List[str]:
        """Get a list of available voices."""
        if self.alltalk_available:
            return self.available_voices
        return ["default"]  # gTTS fallback
    
    def cleanup_old_files(self, max_age_hours: int = 24) -> None:
        """
        Clean up old audio files to prevent disk space issues.
        
        Args:
            max_age_hours: Maximum age of files to keep in hours
        """
        try:
            # Create list of common directories to check
            dirs_to_check = [
                "audio_out",
                os.path.join(self.cache_dir),
                os.path.join(self.outputs_dir)
            ]
            
            now = time.time()
            max_age_seconds = max_age_hours * 3600
            
            # Check each directory
            for directory in dirs_to_check:
                if not os.path.exists(directory):
                    continue
                    
                try:
                    for filename in os.listdir(directory):
                        if filename.startswith("vr_interview_") and (filename.endswith(".wav") or filename.endswith(".mp3")):
                            file_path = os.path.join(directory, filename)
                            file_age = now - os.path.getmtime(file_path)
                            
                            if file_age > max_age_seconds:
                                try:
                                    os.remove(file_path)
                                    self.logger.info(f"Removed old audio file: {file_path}")
                                except Exception as remove_error:
                                    self.logger.warning(f"Failed to remove old file {file_path}: {remove_error}")
                except Exception as dir_error:
                    self.logger.warning(f"Error checking directory {directory}: {dir_error}")
                    
        except Exception as e:
            self.logger.error(f"Error cleaning up old files: {e}")