import logging
import os
import sys
import time
import importlib
import torch
from typing import Union, Optional
import numpy as np

class STTService:
    """
    A wrapper for different Speech-to-Text services with CUDA optimization support.
    This will try to use the OpenAI Whisper model first, then fall back to other implementations.
    """
    
    def __init__(self, model_name: str = "base"):
        self.model_name = model_name
        self.logger = logging.getLogger("stt_wrapper")
        self.logger.info(f"Initializing STT wrapper with model: {model_name}")
        
        # Log CUDA availability
        self.cuda_available = torch.cuda.is_available()
        if self.cuda_available:
            self.logger.info(f"CUDA available: {torch.cuda.get_device_name(0)}")
            self.logger.info(f"CUDA version: {torch.version.cuda}")
            self.logger.info(f"PyTorch CUDA: {torch.version.cuda}")
        else:
            self.logger.warning("CUDA not available, using CPU for speech recognition")
        
        # First try to load the original STT module
        self.original_stt = None
        try:
            # Directly try to use the original STT class but with safe import
            safe_whisper_import = False
            try:
                # Try to import whisper first to see if it works
                import whisper
                if hasattr(whisper, 'load_model'):
                    safe_whisper_import = True
                    self.logger.info("Detected proper OpenAI Whisper installation")
            except (ImportError, TypeError, AttributeError) as e:
                self.logger.warning(f"Whisper import error: {e}")
                
            if safe_whisper_import:
                # Original STT should now work since whisper import worked
                from .stt import STTService as OriginalSTT
                self.original_stt = OriginalSTT(model_name)
                self.logger.info("Successfully loaded CUDA-optimized STT service")
        except Exception as e:
            self.logger.warning(f"Could not load original STT: {e}")
        
        # If original fails, try the simple STT
        if self.original_stt is None:
            try:
                from .simple_stt import SimpleSTTService
                self.original_stt = SimpleSTTService(model_name)
                self.logger.info("Using SimpleSTTService as fallback")
            except Exception as e:
                self.logger.warning(f"Could not load SimpleSTTService: {e}")
        
        # Set availability based on whether we found an implementation
        self.is_available = (self.original_stt is not None)
        if not self.is_available:
            self.logger.error("No STT implementation available!")
        else:
            self.logger.info("STT service initialized successfully")
        
        # Additional periodic GPU memory cleanup
        if self.cuda_available:
            torch.cuda.empty_cache()
            self.logger.info("Performed initial CUDA cache cleanup")
        
    remote_url: Optional[str] = None   # set by the server from config audio.stt_remote_url

    def remote_ready(self) -> bool:
        import requests
        try:
            return bool(requests.get(f"{self.remote_url}/health", timeout=2).json().get("ok"))
        except Exception:
            return False

    def _remote_transcribe(self, audio_data: bytes) -> Optional[str]:
        """Text from the faster-whisper worker, or None when it is down or cannot read this audio (the caller then uses the local Whisper)."""
        import requests
        try:
            start = time.time()
            response = requests.post(f"{self.remote_url}/transcribe", data=audio_data, timeout=30)
            if response.status_code != 200:
                raise RuntimeError(f"HTTP {response.status_code}: {response.text[:120]}")
            body = response.json()
            self.logger.info(f"Transcribed by faster-whisper worker: {body.get('audio_seconds')}s of audio in "
                             f"{body.get('seconds')}s (round trip {time.time() - start:.2f}s)")
            return body.get("text", "").strip()
        except Exception as e:
            now = time.time()
            if now - getattr(self, "_remote_warned", 0) > 60:
                self.logger.warning(f"faster-whisper worker unavailable ({e}); using the built-in Whisper")
                self._remote_warned = now
            return None

    def transcribe(self, audio_data: Union[bytes, np.ndarray, str]) -> str:
        """
        Transcribe audio data to text using available STT implementation with CUDA optimizations
        """
        # Fast path: the faster-whisper worker (tools/stt_worker.py), when audio.stt_remote_url is set and it answers
        if isinstance(audio_data, bytes) and getattr(self, "remote_url", None):
            text = self._remote_transcribe(audio_data)
            if text is not None:
                return text

        if not self.is_available or self.original_stt is None:
            self.logger.error("No STT service available for transcription")
            return "I couldn't process your audio. Please check the server logs."
            
        try:
            self.logger.info(f"Transcribing using {type(self.original_stt).__name__}")
            
            # Free up GPU memory before transcription if possible
            if self.cuda_available:
                torch.cuda.empty_cache()
            
            # Perform transcription
            result = self.original_stt.transcribe(audio_data)
            
            self.logger.info(f"Transcription complete: {len(result)} characters")
            
            # Clean up GPU memory after transcription
            if self.cuda_available:
                torch.cuda.empty_cache()
                
            return result
        except Exception as e:
            self.logger.error(f"Transcription error: {e}")
            return "I encountered an error while transcribing. Please try again."
            
    def get_model_info(self) -> dict:
        """
        Get information about the loaded model
        """
        if not self.is_available or self.original_stt is None:
            return {
                "name": self.model_name,
                "language": "unknown",
                "dimensions": {"width": 0, "height": 0},
                "cuda_available": self.cuda_available
            }
            
        try:
            info = self.original_stt.get_model_info()
            # Add CUDA information if not present
            if "cuda_available" not in info:
                info["cuda_available"] = self.cuda_available
            if self.cuda_available and "cuda_device" not in info:
                info["cuda_device"] = torch.cuda.get_device_name(0)
            return info
        except Exception as e:
            self.logger.error(f"Error getting model info: {e}")
            return {
                "name": self.model_name,
                "language": "error",
                "dimensions": {"width": 0, "height": 0},
                "cuda_available": self.cuda_available
            }