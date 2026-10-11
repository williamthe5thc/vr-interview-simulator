"""
Piper TTS implementation for faster speech synthesis.
This module provides integration with the Piper TTS system, optimized for
low-latency response generation.
"""

import subprocess
import os
import logging
import tempfile
import time
import io
from typing import Optional, Dict, Any, List
import json
import hashlib


class PiperTTSService:
    """
    Text-to-speech service using Piper TTS for fast response times.
    """
    
    def __init__(self, voice="en_US-lessac-medium", model_dir="./models/piper"):
        self.logger = logging.getLogger("piper_tts")
        self.voice = voice
        self.model_dir = model_dir
        
        # Ensure model directory exists
        os.makedirs(model_dir, exist_ok=True)
        
        # Initialize cache
        self.cache_dir = os.path.join(model_dir, "cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.cache = {}
        self.max_cache_entries = 1000
        self._load_cache_index()
        
        # Set flag for availability
        self.is_piper_available = self._check_piper_available()
        
        # Only try to download model if Piper is available
        if self.is_piper_available:
            self._ensure_model_available()
            self.logger.info(f"Initialized Piper TTS with voice: {voice}")
        else:
            self.logger.info("Piper TTS not available, will use fallback TTS")
    
    def _check_piper_available(self) -> bool:
        """Check if Piper is available on the system."""
        try:
            subprocess.run(
                ["piper", "--help"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                check=False
            )
            return True
        except Exception:
            return False
    
    def _ensure_model_available(self) -> None:
        """Check if the voice model is available, don't attempt download."""
        model_path = os.path.join(self.model_dir, f"{self.voice}.onnx")
        if not os.path.exists(model_path):
            self.logger.info(f"Piper model not available: {self.voice}")
            self.logger.info(f"Skipping download as Piper model download requires manual installation")
    
    def synthesize(self, text: str) -> bytes:
        """
        Synthesize speech from text using Piper TTS.
        
        Args:
            text: The text to convert to speech
            
        Returns:
            WAV audio data as bytes
        """
        if not text or not text.strip():
            self.logger.warning("Empty text provided to Piper TTS")
            return self._generate_silence()
            
        # If Piper is not available, return silence immediately
        if not self.is_piper_available:
            return self._generate_silence()
            
        try:
            # Check cache first
            cache_key = self._create_cache_key(text)
            cached_audio = self._get_from_cache(cache_key)
            if cached_audio:
                self.logger.info(f"Using cached Piper audio for: {text[:30]}...")
                return cached_audio
            
            self.logger.info(f"Synthesizing with Piper: {len(text)} characters")
            
            # For sentences longer than 100 characters, break into chunks for faster processing
            if len(text) > 100:
                return self._synthesize_long_text(text, cache_key)
            
            # Process single sentence/short text
            return self._synthesize_text(text, cache_key)
            
        except Exception as e:
            self.logger.error(f"Error in Piper synthesis: {e}")
            return self._generate_silence()
    
    def _synthesize_text(self, text: str, cache_key: str) -> bytes:
        """Synthesize a single piece of text."""
        start_time = time.time()
        
        # Create temporary files for input text and output audio
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as text_file:
            text_file.write(text)
            text_path = text_file.name
        
        output_path = text_path.replace('.txt', '.wav')
        
        try:
            # Check if model exists - if not, return silence
            model_path = os.path.join(self.model_dir, f"{self.voice}.onnx")
            if not os.path.exists(model_path):
                self.logger.warning(f"Piper model not found: {model_path}")
                return self._generate_silence()
            
            # Run Piper TTS
            subprocess.run(
                [
                    "piper",
                    "--model", model_path,
                    "--output_file", output_path,
                    "--input_file", text_path
                ],
                check=True,
                timeout=10  # Add timeout to prevent hanging
            )
            
            # Read the output audio file
            with open(output_path, 'rb') as audio_file:
                audio_data = audio_file.read()
            
            # Clean up temporary files
            os.unlink(text_path)
            os.unlink(output_path)
            
            elapsed = time.time() - start_time
            self.logger.info(f"Piper synthesis complete: {len(audio_data)} bytes in {elapsed:.2f}s")
            
            # Add to cache
            self._add_to_cache(cache_key, audio_data)
            
            return audio_data
            
        except Exception as e:
            self.logger.error(f"Error in Piper synthesis: {e}")
            # Clean up temporary files
            if os.path.exists(text_path):
                os.unlink(text_path)
            if os.path.exists(output_path):
                os.unlink(output_path)
            return self._generate_silence()
    
    def _synthesize_long_text(self, text: str, cache_key: str) -> bytes:
        """Synthesize longer text by breaking it into sentences for faster processing."""
        sentences = self._split_into_sentences(text)
        audio_chunks = []
        
        for sentence in sentences:
            if not sentence.strip():
                continue
            
            # Generate audio for each sentence
            sentence_cache_key = self._create_cache_key(sentence)
            sentence_audio = self._get_from_cache(sentence_cache_key) or self._synthesize_text(sentence, sentence_cache_key)
            audio_chunks.append(sentence_audio)
        
        # Combine audio chunks
        combined_audio = self._combine_audio_chunks(audio_chunks)
        
        # Cache the combined result
        self._add_to_cache(cache_key, combined_audio)
        
        return combined_audio
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences for chunked processing."""
        import re
        # Split on common sentence terminators
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return sentences
    
    def _combine_audio_chunks(self, chunks: List[bytes]) -> bytes:
        """Combine multiple audio chunks into one audio file."""
        if not chunks:
            return self._generate_silence()
        
        try:
            from pydub import AudioSegment
            
            combined = AudioSegment.empty()
            for chunk in chunks:
                segment = AudioSegment.from_wav(io.BytesIO(chunk))
                combined += segment
            
            # Export to WAV
            output = io.BytesIO()
            combined.export(output, format="wav")
            output.seek(0)
            return output.read()
            
        except Exception as e:
            self.logger.error(f"Error combining audio chunks: {e}")
            # Return the first chunk as fallback
            return chunks[0] if chunks else self._generate_silence()
    
    def _create_cache_key(self, text: str) -> str:
        """Create a unique cache key for the text."""
        voice_text = f"{self.voice}_{text}"
        return hashlib.md5(voice_text.encode()).hexdigest()
    
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
        index_path = os.path.join(self.cache_dir, "cache_index.json")
        if os.path.exists(index_path):
            try:
                with open(index_path, 'r') as f:
                    self.cache = json.load(f)
                self.logger.info(f"Loaded {len(self.cache)} cache entries")
            except Exception as e:
                self.logger.warning(f"Failed to load cache index: {e}")
                self.cache = {}
    
    def _save_cache_index(self) -> None:
        """Save cache index to disk."""
        index_path = os.path.join(self.cache_dir, "cache_index.json")
        try:
            with open(index_path, 'w') as f:
                json.dump(self.cache, f)
        except Exception as e:
            self.logger.warning(f"Failed to save cache index: {e}")
    
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
        """Check if Piper TTS is available."""
        return self.is_piper_available

    def get_available_voices(self) -> List[str]:
        """Get a list of available Piper voices."""
        # Just return the default voice since we're not fully installed
        return [self.voice]
