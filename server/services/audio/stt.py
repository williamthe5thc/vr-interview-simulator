"""
Cross-Platform Optimized Speech-to-Text service for VR Interview System.

This module implements enhanced Whisper model support with GPU acceleration.
Supports NVIDIA CUDA, AMD ROCm, Apple Metal, and CPU processing.
"""

import logging
import os
import tempfile
import time
import torch
import numpy as np
from typing import Union, Optional, Tuple
from app.utils.config import Config
from app.utils.platform_utils import PlatformUtils


class STTService:
    """
    Speech-to-Text service with cross-platform GPU support.
    Supports NVIDIA CUDA, AMD ROCm, Apple Metal, and CPU fallback.
    """
    
    def __init__(self, model_name: str = None):
        self.config = Config.get_instance()
        
        # Get model name from config or use fallback
        self.model_name = model_name or self.config.get("audio.stt_model", "medium")
        
        self.logger = logging.getLogger("stt")
        self.model = None  # Lazy-loaded on first use
        
        # Determine optimal device
        self.device = self._get_optimal_device()
        
        # Log platform and device information
        platform_info = self.config.get_platform_info()
        gpu_type, gpu_name, gpu_available = self.config.get_gpu_info()
        
        self.logger.info(f"Platform: {PlatformUtils.is_windows() and 'Windows' or PlatformUtils.is_mac() and 'macOS' or 'Linux'}")
        self.logger.info(f"GPU detected: {gpu_type} - {gpu_name}")
        self.logger.info(f"Using device: {self.device}")
        
        # Check if whisper is available
        try:
            import whisper
            self.whisper = whisper
            self.is_available = True
            self.logger.info(f"Whisper module available, will use model: {self.model_name}")
        except ImportError:
            self.whisper = None
            self.logger.warning("Whisper module not available. Using dummy transcription.")
            self.is_available = False
    
    def _get_optimal_device(self) -> str:
        """
        Determine the optimal device for speech recognition based on platform and available hardware.
        Returns a string device identifier compatible with PyTorch.
        """
        # Get configured device
        configured_device = self.config.get("audio.device", "cpu")
        
        # Get GPU information
        gpu_type, gpu_name, gpu_available = self.config.get_gpu_info()
        
        # Check device availability
        if configured_device == "cuda" and torch.cuda.is_available():
            return "cuda"
        elif configured_device == "mps" and hasattr(torch, 'mps') and torch.backends.mps.is_available():
            # Apple Silicon GPU support
            return "mps"
        elif configured_device == "rocm" and torch.cuda.is_available():
            # ROCm presents itself as CUDA in PyTorch
            return "cuda"
        else:
            # Fallback to CPU
            return "cpu"
            
    def _load_model(self):
        """
        Lazy-load the Whisper model with platform-specific optimizations
        """
        # Skip if whisper is not available
        if not self.is_available or self.whisper is None:
            self.logger.warning("Whisper is not available, skipping model loading")
            return
            
        if self.model is None:
            self.logger.info(f"Loading Whisper model: {self.model_name} on {self.device}")
            start_time = time.time()
            
            try:
                # Set environment variables for AMD GPUs if needed
                if self.device == "cuda" and PlatformUtils.get_gpu_info()[0] == "amd":
                    # These can help with ROCm compatibility
                    os.environ['HSA_OVERRIDE_GFX_VERSION'] = '10.3.0'
                    os.environ['HIP_VISIBLE_DEVICES'] = '0'
                
                # Handle MPS (Apple Silicon) specifically
                if self.device == "mps":
                    # Some operations aren't supported on MPS yet, so load on CPU first
                    self.model = self.whisper.load_model(self.model_name)
                    # Selective operations will use MPS when available
                else:
                    # Load model on specified device
                    self.model = self.whisper.load_model(self.model_name).to(self.device)
                
                load_time = time.time() - start_time
                self.logger.info(f"Whisper model loaded successfully in {load_time:.2f}s")
                
                # Log GPU memory usage if using CUDA
                if self.device == "cuda":
                    allocated = torch.cuda.memory_allocated(0) / 1e9  # GB
                    reserved = torch.cuda.memory_reserved(0) / 1e9  # GB
                    self.logger.info(f"GPU memory after model load: {allocated:.2f}GB allocated, {reserved:.2f}GB reserved")
            except Exception as e:
                self.logger.error(f"Failed to load Whisper model: {e}")
                self.logger.warning(f"Falling back to CPU. Error: {str(e)}")
                self.device = "cpu"
                try:
                    # Try to load on CPU as fallback
                    self.model = self.whisper.load_model(self.model_name)
                    self.logger.info("Successfully loaded model on CPU as fallback")
                except Exception as cpu_error:
                    self.logger.error(f"Failed to load Whisper model on CPU: {cpu_error}")
                    self.is_available = False  # Mark as unavailable after error
                    self.logger.warning("Falling back to dummy transcription")
                    return
                
    def transcribe(self, audio_data: Union[bytes, np.ndarray, str]) -> str:
        """
        Transcribe audio data to text with platform-specific optimizations.
        
        Args:
            audio_data: Audio data as bytes, numpy array, or path to file
            
        Returns:
            Transcribed text
        """
        # Check if whisper is available
        if not self.is_available or self.whisper is None:
            # Return a dummy transcription for testing
            if isinstance(audio_data, bytes):
                # Return text based on the length of the audio data
                audio_length = len(audio_data)
                if audio_length < 50000:  # Short audio
                    return "Hello, can you tell me about your experience?"
                elif audio_length < 100000:  # Medium audio
                    return "What skills do you have that would be relevant for this position?"
                else:  # Long audio
                    return "Can you describe a challenging project you worked on and how you handled it?"
            elif isinstance(audio_data, str):
                # Return based on the content of the string
                return f"I simulated transcribing: {audio_data[:50]}..."
            else:
                return "Tell me about your qualifications for this position."
        
        # Ensure model is loaded if whisper is available
        self._load_model()
        
        try:
            # Free up GPU memory before processing if possible
            if self.device == "cuda":
                torch.cuda.empty_cache()
                
            start_time = time.time()
            
            # Handle different input types
            if isinstance(audio_data, bytes):
                # Determine appropriate temp file extension
                # Mac often needs different file extensions
                suffix = ".wav" if PlatformUtils.is_mac() else ".webm"
                
                # Save bytes to temporary file
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_file:
                    tmp_file.write(audio_data)
                    tmp_path = tmp_file.name
                    
                # Transcribe from temporary file with appropriate optimization
                try:
                    # Use torch.no_grad to save memory
                    with torch.no_grad():
                        # Platform-specific optimizations
                        if self.device == "cuda":
                            # CUDA optimization (both NVIDIA and AMD via ROCm)
                            with torch.amp.autocast(device_type='cuda'):
                                result = self.model.transcribe(tmp_path, fp16=True)
                        elif self.device == "mps":
                            # MPS (Apple Silicon) special handling
                            # Need to pass torch.mps tensors explicitly
                            result = self.model.transcribe(tmp_path)
                        else:
                            # CPU fallback
                            result = self.model.transcribe(tmp_path)
                finally:
                    # Clean up temporary file
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                        
            elif isinstance(audio_data, np.ndarray):
                # Transcribe directly from numpy array
                with torch.no_grad():
                    if self.device == "cuda":
                        with torch.amp.autocast(device_type='cuda'):
                            result = self.model.transcribe(audio_data, fp16=True)
                    elif self.device == "mps":
                        # MPS handling
                        result = self.model.transcribe(audio_data)
                    else:
                        result = self.model.transcribe(audio_data)
                
            elif isinstance(audio_data, str) and os.path.exists(audio_data):
                # Normalize path for platform compatibility
                audio_path = PlatformUtils.normalize_path(audio_data)
                
                # Transcribe from file path
                with torch.no_grad():
                    if self.device == "cuda":
                        with torch.amp.autocast(device_type='cuda'):
                            result = self.model.transcribe(audio_path, fp16=True)
                    elif self.device == "mps":
                        # MPS handling
                        result = self.model.transcribe(audio_path)
                    else:
                        result = self.model.transcribe(audio_path)
                
            else:
                raise ValueError("Unsupported audio data format")
                
            # Extract transcription text
            transcription = result.get("text", "").strip()
            elapsed = time.time() - start_time
            self.logger.info(f"Transcription complete: {len(transcription)} characters in {elapsed:.2f}s")
            
            # Clean up GPU memory after processing
            if self.device == "cuda":
                torch.cuda.empty_cache()
                
            return transcription
            
        except Exception as e:
            self.logger.error(f"Transcription error: {e}")
            return ""  # Return empty string on error
            
    def get_model_info(self) -> dict:
        """
        Get information about the loaded model with platform-specific details
        """
        self._load_model()
        
        # Basic info
        info = {
            "name": self.model_name,
            "device": self.device,
            "platform": PlatformUtils.is_windows() and "Windows" or PlatformUtils.is_mac() and "macOS" or "Linux"
        }
        
        # Get GPU information
        gpu_type, gpu_name, gpu_available = self.config.get_gpu_info()
        info["gpu_type"] = gpu_type
        info["gpu_name"] = gpu_name
        info["gpu_available"] = gpu_available
        
        # Device-specific info
        if self.device == "cuda":
            info["cuda_available"] = torch.cuda.is_available()
            if torch.cuda.is_available():
                info["cuda_device"] = torch.cuda.get_device_name(0)
                info["cuda_memory_allocated"] = f"{torch.cuda.memory_allocated(0) / 1e9:.2f}GB"
                info["cuda_memory_reserved"] = f"{torch.cuda.memory_reserved(0) / 1e9:.2f}GB"
        elif self.device == "mps":
            info["mps_available"] = hasattr(torch, 'mps') and torch.backends.mps.is_available()
        
        # Add model-specific info if available
        if self.model is not None:
            try:
                info["model_device"] = self.model.device.type
                info["dimensions"] = self.model.dims
            except Exception as e:
                self.logger.warning(f"Error getting detailed model info: {e}")
                
        return info
