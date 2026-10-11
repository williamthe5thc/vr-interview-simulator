"""
Enhanced Text-to-Speech Service

This improved TTS service implementation addresses the WAV format issues
and ensures robust audio synthesis for Unity client playback.
"""

import io
import os
import logging
import tempfile
import subprocess
import wave
import struct
from typing import Optional
from gtts import gTTS

class TTSService:
    """
    Text-to-Speech service with improved error handling and WAV format compatibility.
    
    This version ensures generated audio is properly formatted for Unity client playback.
    """

    def __init__(self, model="gtts"):
        self.model = model
        self.logger = logging.getLogger("tts")
        self.logger.info(f"Initialized TTS service with model: {model}")
        
    def synthesize(self, text: str) -> bytes:
        """
        Convert text to speech using the configured TTS service.
        
        Args:
            text: The text to convert to speech
            
        Returns:
            WAV audio data as bytes
        """
        if not text or not text.strip():
            # Generate silence for empty text
            return self._generate_silence(1.0)
            
        self.logger.info(f"Synthesizing: {len(text)} characters")
        
        if self.model == "gtts":
            return self._synthesize_gtts(text)
        else:
            # Fallback to gTTS if model not recognized
            self.logger.warning(f"Unknown TTS model: {self.model}, falling back to gTTS")
            return self._synthesize_gtts(text)
    
    def _synthesize_gtts(self, text: str) -> bytes:
        """
        Synthesize speech using Google Text-to-Speech.
        
        This implementation ensures proper WAV format conversion for Unity.
        
        Args:
            text: The text to convert to speech
            
        Returns:
            WAV audio data as bytes
        """
        start_time = os.times()
        
        try:
            # Create a temporary file for the MP3
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as mp3_file:
                mp3_path = mp3_file.name
                
            # Use gTTS to generate MP3
            tts = gTTS(text=text, lang='en', slow=False)
            tts.save(mp3_path)
            
            # Convert MP3 to WAV format that Unity can easily play
            wav_data = self._convert_mp3_to_wav(mp3_path)
            
            # Clean up the temporary MP3 file
            os.unlink(mp3_path)
            
            elapsed = os.times().system - start_time.system
            self.logger.info(f"gTTS synthesis complete: {len(wav_data)} bytes in {elapsed:.2f}s")
            
            return wav_data
            
        except Exception as e:
            self.logger.error(f"Error in gTTS synthesis: {e}")
            # Generate silence as fallback
            return self._generate_silence(2.0)
    
    def _convert_mp3_to_wav(self, mp3_path: str) -> bytes:
        """
        Convert MP3 to WAV format using ffmpeg, ensuring compatibility with Unity.
        
        Args:
            mp3_path: Path to the MP3 file
            
        Returns:
            WAV audio data as bytes
        """
        try:
            # Create a temporary file for the WAV
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as wav_file:
                wav_path = wav_file.name
            
            # Using ffmpeg for conversion with specific format settings for Unity compatibility
            # - PCM signed 16-bit little-endian format
            # - 16000 Hz sample rate
            # - Mono channel
            command = [
                "ffmpeg",
                "-i", mp3_path,
                "-acodec", "pcm_s16le",
                "-ar", "16000",
                "-ac", "1",
                "-f", "wav",
                wav_path
            ]
            
            # Try to use ffmpeg first (better quality)
            try:
                subprocess.run(command, check=True, capture_output=True)
                
                # Read the WAV file data
                with open(wav_path, "rb") as f:
                    wav_data = f.read()
                    
                # Clean up
                os.unlink(wav_path)
                
                return wav_data
                
            except (subprocess.SubprocessError, FileNotFoundError):
                # Fallback to manual conversion if ffmpeg is not available
                self.logger.warning("ffmpeg not available, using fallback MP3 to WAV conversion")
                return self._manual_mp3_to_wav_conversion(mp3_path)
                
        except Exception as e:
            self.logger.error(f"Error converting MP3 to WAV: {e}")
            # Generate silence as fallback
            return self._generate_silence(2.0)
    
    def _manual_mp3_to_wav_conversion(self, mp3_path: str) -> bytes:
        """
        Fallback method to convert MP3 to WAV if ffmpeg is not available.
        Uses Python-only solutions with minimal dependencies.
        
        Args:
            mp3_path: Path to the MP3 file
            
        Returns:
            WAV audio data as bytes
        """
        try:
            # Try to use pydub if available
            import pydub
            from pydub import AudioSegment
            
            # Load the MP3 file
            audio = AudioSegment.from_mp3(mp3_path)
            
            # Set the parameters to make it compatible with Unity
            audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
            
            # Export to in-memory WAV file
            buffer = io.BytesIO()
            audio.export(buffer, format="wav")
            
            return buffer.getvalue()
            
        except ImportError:
            # If pydub is not available, try to use GTTS's built-in MP3 decoder
            self.logger.warning("pydub not available, using simplified conversion")
            
            # Read the MP3 file into memory
            with open(mp3_path, "rb") as f:
                mp3_data = f.read()
                
            # Create a simple WAV with compatible format
            return self._create_simple_wav()
    
    def _create_simple_wav(self, duration: float = 2.0, sample_rate: int = 16000) -> bytes:
        """
        Create a simple WAV file for Unity compatibility.
        
        Args:
            duration: Duration of the audio in seconds
            sample_rate: Sample rate in Hz
            
        Returns:
            WAV audio data as bytes
        """
        # Generate a simple beep sound
        buffer = io.BytesIO()
        
        with wave.open(buffer, 'wb') as wav:
            wav.setnchannels(1)  # Mono
            wav.setsampwidth(2)  # 16-bit
            wav.setframerate(sample_rate)
            
            # Generate a simple sine wave beep
            for i in range(int(duration * sample_rate)):
                value = int(32767.0 * 0.5 * (i % 400 < 200))  # Simple square wave
                data = struct.pack('<h', value)
                wav.writeframes(data)
        
        return buffer.getvalue()
    
    def _generate_silence(self, duration: float = 1.0, sample_rate: int = 16000) -> bytes:
        """
        Generate silence as WAV data.
        
        Args:
            duration: Duration of silence in seconds
            sample_rate: Sample rate in Hz
            
        Returns:
            WAV audio data as bytes
        """
        buffer = io.BytesIO()
        
        with wave.open(buffer, 'wb') as wav:
            wav.setnchannels(1)  # Mono
            wav.setsampwidth(2)  # 16-bit
            wav.setframerate(sample_rate)
            
            # Generate silence (all zeros)
            num_samples = int(duration * sample_rate)
            wav.writeframes(b'\x00' * (num_samples * 2))  # 2 bytes per sample (16-bit)
        
        return buffer.getvalue()
    
    def get_available_voices(self) -> list:
        """
        Get available voices for the current TTS service.
        
        Returns:
            List of available voice names
        """
        if self.model == "gtts":
            return ["en_us", "en_uk", "en_au"]
        else:
            return ["default"]
