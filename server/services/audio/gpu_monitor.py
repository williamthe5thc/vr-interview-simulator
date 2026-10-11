"""
GPU monitoring and optimization utilities for VR Interview System.

This module provides utilities for monitoring GPU usage, optimizing performance,
and timing operations on CUDA devices.
"""

import torch
import logging
import time
import psutil
import subprocess
from functools import wraps
from typing import Dict, Any, Optional, Callable, Union


class GPUMonitor:
    """
    Utility class for monitoring GPU usage and performance throughout the application.
    """
    def __init__(self):
        self.logger = logging.getLogger("gpu_monitor")
        self.cuda_available = torch.cuda.is_available()
        
        if self.cuda_available:
            self.device_name = torch.cuda.get_device_name(0)
            self.device_count = torch.cuda.device_count()
            self.logger.info(f"GPU monitoring initialized for: {self.device_name}")
            self.logger.info(f"CUDA version: {torch.version.cuda}")
            self.logger.info(f"PyTorch version: {torch.__version__}")
            self.logger.info(f"Total devices: {self.device_count}")
            
            # Initial memory stats
            self.log_memory_usage("Initialization")
        else:
            self.logger.warning("CUDA not available, GPU monitoring disabled")
    
    def log_memory_usage(self, label=""):
        """Log current GPU memory usage"""
        if not self.cuda_available:
            return
            
        try:
            allocated = torch.cuda.memory_allocated(0) / 1e9  # Convert to GB
            reserved = torch.cuda.memory_reserved(0) / 1e9
            max_memory = torch.cuda.max_memory_allocated(0) / 1e9
            
            # Get CPU memory usage as well
            cpu_percent = psutil.cpu_percent()
            ram = psutil.virtual_memory()
            ram_used_gb = ram.used / (1024**3)
            ram_total_gb = ram.total / (1024**3)
            
            self.logger.info(f"Memory {label}: "
                           f"GPU: {allocated:.2f}GB allocated, {reserved:.2f}GB reserved, {max_memory:.2f}GB peak | "
                           f"CPU: {cpu_percent}% | RAM: {ram_used_gb:.2f}/{ram_total_gb:.2f}GB")
        except Exception as e:
            self.logger.error(f"Error logging GPU memory: {e}")
    
    def clear_cache(self):
        """Clear CUDA cache to free memory"""
        if self.cuda_available:
            try:
                before = torch.cuda.memory_allocated(0) / 1e9
                torch.cuda.empty_cache()
                after = torch.cuda.memory_allocated(0) / 1e9
                self.logger.info(f"Cleared CUDA cache: {before:.2f}GB → {after:.2f}GB")
            except Exception as e:
                self.logger.error(f"Error clearing CUDA cache: {e}")
    
    def reset_peak_memory(self):
        """Reset peak memory stats"""
        if self.cuda_available:
            try:
                torch.cuda.reset_peak_memory_stats()
                self.logger.info("Reset peak memory statistics")
            except Exception as e:
                self.logger.error(f"Error resetting peak memory: {e}")
    
    def time_function(self, func_name=""):
        """Decorator to time function execution with CUDA events"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                if not self.cuda_available:
                    start_time = time.time()
                    result = func(*args, **kwargs)
                    elapsed = time.time() - start_time
                    self.logger.info(f"{func_name or func.__name__} took {elapsed:.4f}s (CPU)")
                    return result
                
                # Use CUDA events for accurate GPU timing
                try:
                    # Log memory before execution
                    self.log_memory_usage(f"Before {func_name or func.__name__}")
                    
                    start = torch.cuda.Event(enable_timing=True)
                    end = torch.cuda.Event(enable_timing=True)
                    
                    # Ensure all CUDA operations are complete
                    torch.cuda.synchronize()
                    
                    # Record start event
                    start.record()
                    
                    # Execute function
                    result = func(*args, **kwargs)
                    
                    # Record end event
                    end.record()
                    
                    # Wait for all operations to complete
                    torch.cuda.synchronize()
                    
                    # Calculate elapsed time in milliseconds
                    elapsed_ms = start.elapsed_time(end)
                    self.logger.info(f"{func_name or func.__name__} took {elapsed_ms:.2f}ms (GPU)")
                    
                    # Log memory after execution
                    self.log_memory_usage(f"After {func_name or func.__name__}")
                    
                    return result
                except Exception as e:
                    self.logger.error(f"Error in GPU timing: {e}")
                    # Fall back to CPU timing
                    start_time = time.time()
                    result = func(*args, **kwargs)
                    elapsed = time.time() - start_time
                    self.logger.info(f"{func_name or func.__name__} took {elapsed:.4f}s (CPU fallback)")
                    return result
                    
            return wrapper
        return decorator
    
    def get_gpu_utilization(self):
        """Get current GPU utilization if available"""
        if not self.cuda_available:
            return {"error": "CUDA not available"}
            
        try:
            # Try to use nvidia-smi through subprocess
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=utilization.gpu,utilization.memory,memory.used,memory.total', '--format=csv,noheader,nounits'],
                stdout=subprocess.PIPE,
                universal_newlines=True
            )
            
            if result.returncode == 0:
                # Parse the output
                values = result.stdout.strip().split(',')
                if len(values) >= 4:
                    return {
                        "gpu_utilization": float(values[0].strip()),
                        "memory_utilization": float(values[1].strip()),
                        "memory_used_mb": float(values[2].strip()),
                        "memory_total_mb": float(values[3].strip()),
                    }
            
            # If nvidia-smi fails, return basic torch information
            return {
                "memory_allocated_gb": torch.cuda.memory_allocated(0) / 1e9,
                "memory_reserved_gb": torch.cuda.memory_reserved(0) / 1e9
            }
        except Exception as e:
            self.logger.error(f"Error getting GPU utilization: {e}")
            return {"error": str(e)}
            
    def optimize_for_inference(self):
        """Configure PyTorch for optimal inference performance"""
        if self.cuda_available:
            try:
                # Disable gradient calculation for inference
                torch.set_grad_enabled(False)
                
                # Enable cuDNN benchmark mode for better performance with fixed input sizes
                torch.backends.cudnn.benchmark = True
                
                # Disable cuDNN determinism for better performance
                torch.backends.cudnn.deterministic = False
                
                self.logger.info("PyTorch optimized for inference performance")
                return True
            except Exception as e:
                self.logger.error(f"Error optimizing for inference: {e}")
                return False
        return False
        
    def validate_gpu_available_for_model_size(self, model_name: str) -> bool:
        """
        Check if GPU has sufficient memory for the specified model size
        
        Args:
            model_name: Model name (e.g., "base", "small", "medium", "large")
            
        Returns:
            True if GPU has sufficient memory, False otherwise
        """
        if not self.cuda_available:
            return False
            
        # Approximate VRAM requirements for Whisper models (in GB)
        model_sizes = {
            "tiny": 1.0,
            "base": 1.5,
            "small": 2.5, 
            "medium": 5.0,
            "large": 10.0
        }
        
        # Get available GPU memory
        try:
            # Get total memory in GB
            total_memory = torch.cuda.get_device_properties(0).total_memory / 1e9
            # Get current free memory
            allocated = torch.cuda.memory_allocated(0) / 1e9
            reserved = torch.cuda.memory_reserved(0) / 1e9
            free_memory = total_memory - reserved
            
            # Check if model fits
            required = model_sizes.get(model_name.lower(), 2.0)  # Default to 2GB if unknown
            has_enough_memory = free_memory >= required * 1.2  # Add 20% buffer
            
            self.logger.info(f"GPU memory check for {model_name} model: " +
                          f"Required: {required:.1f}GB, Available: {free_memory:.1f}GB, " +
                          f"Result: {'Sufficient' if has_enough_memory else 'Insufficient'}")
            
            return has_enough_memory
        except Exception as e:
            self.logger.error(f"Error checking GPU memory: {e}")
            return False  # Be conservative