"""
GTTS-only TTS service for VR Interview System.

This module provides a simplified TTS service that uses gTTS directly,
avoiding the timeouts and reliability issues with AllTalk.
"""

import logging
import time
import os
import io
import traceback
from typing import Optional

class GTTSOnlyService:
    """
    Simple TTS service that uses gTTS directly for better reliability
    """
    
    def __init__(self, language="en", voice=None):
        self.logger = logging.getLogger("gtts_service")
        self.language = language
        self.voice = voice  # Not used by gTTS but kept for compatibility
        
        self.logger.info(f"Initializing GTTS-only service with language: {language}")
    
    def is_available(self) -> bool:
        """Always available"""
        return True
    
    def synthesize(self, text: str, session_id: Optional[str] = None) -> bytes:
        """
        Synthesize speech from text using gTTS
        
        Args:
            text: The text to convert to speech
            session_id: Optional session ID (not used, for compatibility)
            
        Returns:
            WAV audio data as bytes
        """
        if not text:
            self.logger.warning("Empty text provided to synthesize")
            return self._generate_silence()
            
        try:
            from gtts import gTTS
            from pydub import AudioSegment
            
            start_time = time.time()
            
            # Use gTTS to generate MP3
            self.logger.info(f"Generating speech with gTTS: {len(text)} characters")
            tts = gTTS(text=text, lang=self.language)
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
            output_file = f"vr_interview_gtts_{int(time.time())}"
            
            try:
                os.makedirs("audio_out", exist_ok=True)
                with open(f"audio_out/{output_file}.wav", "wb") as f:
                    f.write(audio_data)
            except Exception as save_error:
                self.logger.warning(f"Failed to save gTTS audio file: {save_error}")
                
            return audio_data
            
        except Exception as e:
            self.logger.error(f"Error in gTTS synthesis: {e}\n{traceback.format_exc()}")
            self.logger.warning("Using silent audio as fallback")
            return self._generate_silence()
    
    def _generate_silence(self, duration_ms: int = 1000) -> bytes:
        """
        Generate silent audio as a last resort fallback.
        
        Args:
            duration_ms: Duration of silence in milliseconds
            
        Returns:
            WAV audio data as bytes
        """
        try:
            from pydub import AudioSegment
            import io
            
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
