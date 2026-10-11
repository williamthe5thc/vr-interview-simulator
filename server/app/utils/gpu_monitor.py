"""
GPU monitoring utility for VR Interview System.

This module provides utilities for monitoring GPU memory usage
and optimizing PyTorch for inference.
"""

import logging
import time
from typing import Optional


class GPUMonitor:
    """
    Monitors GPU memory usage and provides optimization utilities.
    
    Requires PyTorch with CUDA support.
    """
    
    def __init__(self):
        self.logger = logging.getLogger("gpu_monitor")
        
        try:
            import torch
            self.torch = torch
            
            if not torch.cuda.is_available():
                self.logger.warning("CUDA is not available - GPU monitoring disabled")
                self.available = False
            else:
                self.available = True
                self.device_count = torch.cuda.device_count()
                self.logger.info(f"GPU monitoring enabled: {self.device_count} device(s) available")
                
                # Log initial device info
                for i in range(self.device_count):
                    device_name = torch.cuda.get_device_name(i)
                    self.logger.info(f"Device {i}: {device_name}")
                
                # Track peak memory per device
                self.peak_memory = [0] * self.device_count
                
        except ImportError:
            self.logger.warning("PyTorch not available - GPU monitoring disabled")
            self.available = False
            
    def log_memory_usage(self, tag: str = ""):
        """
        Log current GPU memory usage for all devices.
        
        Args:
            tag: Optional tag to identify this logging point
        """
        if not self.available:
            return
            
        try:
            for i in range(self.device_count):
                # Get current memory usage in bytes
                memory_allocated = self.torch.cuda.memory_allocated(i)
                memory_reserved = self.torch.cuda.memory_reserved(i)
                
                # Convert to MB for logging
                memory_allocated_mb = memory_allocated / (1024 * 1024)
                memory_reserved_mb = memory_reserved / (1024 * 1024)
                
                # Update peak tracking
                if memory_allocated > self.peak_memory[i]:
                    self.peak_memory[i] = memory_allocated
                
                # Log current usage
                if tag:
                    log_prefix = f"[{tag}] "
                else:
                    log_prefix = ""
                    
                self.logger.info(
                    f"{log_prefix}Device {i} memory: "
                    f"{memory_allocated_mb:.2f}MB allocated, "
                    f"{memory_reserved_mb:.2f}MB reserved"
                )
                
        except Exception as e:
            self.logger.error(f"Error logging GPU memory: {e}")
    
    def reset_peak_memory(self):
        """Reset peak memory tracking for all devices."""
        if not self.available:
            return
            
        try:
            self.torch.cuda.reset_peak_memory_stats()
            self.peak_memory = [0] * self.device_count
            self.logger.info("Reset peak memory tracking")
        except Exception as e:
            self.logger.error(f"Error resetting peak memory: {e}")
    
    def log_peak_memory(self, tag: str = ""):
        """
        Log peak GPU memory usage for all devices.
        
        Args:
            tag: Optional tag to identify this logging point
        """
        if not self.available:
            return
            
        try:
            for i in range(self.device_count):
                # Get peak memory in bytes
                peak_memory = self.torch.cuda.max_memory_allocated(i)
                
                # Convert to MB for logging
                peak_memory_mb = peak_memory / (1024 * 1024)
                
                # Log peak usage
                if tag:
                    log_prefix = f"[{tag}] "
                else:
                    log_prefix = ""
                    
                self.logger.info(
                    f"{log_prefix}Device {i} peak memory: {peak_memory_mb:.2f}MB"
                )
                
        except Exception as e:
            self.logger.error(f"Error logging peak GPU memory: {e}")
    
    def optimize_for_inference(self):
        """
        Apply optimizations for inference workloads.
        """
        if not self.available:
            return
            
        try:
            # Set PyTorch to inference mode
            self.torch.set_grad_enabled(False)
            
            # Enable TF32 precision if available (NVIDIA Ampere+ GPUs)
            if hasattr(self.torch.cuda, 'matmul') and hasattr(self.torch.cuda.matmul, 'allow_tf32'):
                self.torch.cuda.matmul.allow_tf32 = True
                self.logger.info("TF32 precision enabled for matrix multiplications")
                
            if hasattr(self.torch.backends, 'cudnn') and hasattr(self.torch.backends.cudnn, 'allow_tf32'):
                self.torch.backends.cudnn.allow_tf32 = True
                self.logger.info("TF32 precision enabled for cuDNN")
            
            # Enable cuDNN benchmarking for optimized convolutions
            if hasattr(self.torch.backends, 'cudnn'):
                self.torch.backends.cudnn.benchmark = True
                self.logger.info("cuDNN benchmark enabled")
                
            # Clear cache
            self.torch.cuda.empty_cache()
            
            self.logger.info("Applied optimizations for inference")
            
        except Exception as e:
            self.logger.error(f"Error applying optimizations: {e}")
    
    def is_cuda_available(self) -> bool:
        """Check if CUDA is available."""
        return self.available if hasattr(self, 'available') else False
