# VR Interview System: CUDA Optimization Documentation

## Overview

The VR Interview System leverages GPU acceleration through CUDA to improve performance for computationally intensive tasks such as speech recognition and language model inference. This document provides comprehensive guidance on configuring, optimizing, and troubleshooting GPU usage within the system.

## GPU-Accelerated Components

The following system components can benefit from GPU acceleration:

1. **Speech-to-Text (STT)**: OpenAI Whisper models running on CUDA for faster transcription
2. **Text-to-Speech (TTS)**: GPU-accelerated AllTalk XTTS models for improved speech synthesis
3. **Language Model Inference**: Ollama models utilizing GPU for faster response generation

## GPU Monitoring System

The system includes a dedicated `GPUMonitor` class that provides real-time monitoring and optimization of GPU resources:

```python
class GPUMonitor:
    """
    Utility class for monitoring GPU resource usage.
    Provides memory tracking and optimization functions.
    """
    
    def __init__(self):
        self.logger = logging.getLogger("gpu_monitor")
        self.has_cuda = False
        
        try:
            import torch
            self.has_cuda = torch.cuda.is_available()
            if self.has_cuda:
                self.device_count = torch.cuda.device_count()
                self.current_device = torch.cuda.current_device()
                self.device_name = torch.cuda.get_device_name(self.current_device)
                self.logger.info(f"CUDA available: {self.device_count} device(s)")
                self.logger.info(f"Using device: {self.device_name}")
                self.peak_memory = 0
                
                # Record initial memory usage
                self.log_memory_usage("Initialization")
        except ImportError:
            self.logger.warning("PyTorch not available, GPU monitoring disabled")
        except Exception as e:
            self.logger.error(f"Error initializing GPU monitor: {e}")
            self.has_cuda = False
```

Key monitoring features include:

### Memory Usage Tracking

```python
def log_memory_usage(self, tag=""):
    """
    Log current GPU memory usage with optional tag for identification.
    
    Args:
        tag: Optional identifier for the logging point
    """
    if not self.has_cuda:
        return
        
    try:
        import torch
        
        # Get current memory allocation
        allocated = torch.cuda.memory_allocated(self.current_device)
        reserved = torch.cuda.memory_reserved(self.current_device)
        
        # Convert to MB for readability
        allocated_mb = allocated / (1024 * 1024)
        reserved_mb = reserved / (1024 * 1024)
        
        # Update peak memory
        if allocated > self.peak_memory:
            self.peak_memory = allocated
            peak_mb = self.peak_memory / (1024 * 1024)
            self.logger.info(f"New peak memory: {peak_mb:.2f} MB")
        
        # Log with tag if provided
        if tag:
            self.logger.info(f"GPU Memory [{tag}] - Allocated: {allocated_mb:.2f} MB, Reserved: {reserved_mb:.2f} MB")
        else:
            self.logger.info(f"GPU Memory - Allocated: {allocated_mb:.2f} MB, Reserved: {reserved_mb:.2f} MB")
    except Exception as e:
        self.logger.error(f"Error logging GPU memory: {e}")
```

### Cache Management

```python
def clear_cache(self):
    """
    Clear CUDA cache to free GPU memory.
    Call this after large operations to prevent memory fragmentation.
    """
    if not self.has_cuda:
        return
        
    try:
        import torch
        
        # Log memory before clearing
        self.log_memory_usage("Before cache clear")
        
        # Empty cache
        torch.cuda.empty_cache()
        
        # Log memory after clearing
        self.log_memory_usage("After cache clear")
    except Exception as e:
        self.logger.error(f"Error clearing GPU cache: {e}")
```

### Function Performance Timing

```python
def time_function(self, func, *args, tag="", **kwargs):
    """
    Time the execution of a function and log GPU memory usage.
    
    Args:
        func: Function to time
        *args: Arguments to pass to function
        tag: Identifier for logging
        **kwargs: Keyword arguments to pass to function
        
    Returns:
        Result of the function
    """
    if not tag:
        tag = func.__name__
        
    # Log before execution
    self.log_memory_usage(f"{tag} (start)")
    
    # Time execution
    start_time = time.time()
    result = func(*args, **kwargs)
    execution_time = time.time() - start_time
    
    # Log after execution
    self.log_memory_usage(f"{tag} (end)")
    
    self.logger.info(f"Function {tag} took {execution_time:.2f} seconds")
    
    return result
```

### Inference Optimization

```python
def optimize_for_inference(self):
    """Configure PyTorch for optimal inference performance."""
    if not self.has_cuda:
        return
        
    try:
        import torch
        
        # Set inference mode
        torch.set_grad_enabled(False)
        
        # Set cudnn benchmark
        torch.backends.cudnn.benchmark = True
        torch.backends.cudnn.deterministic = False
        
        self.logger.info("PyTorch optimized for inference")
    except Exception as e:
        self.logger.error(f"Error optimizing for inference: {e}")
```

## Periodic Monitoring

The system implements periodic GPU monitoring to ensure optimal performance over time:

```python
async def monitor_gpu_periodically():
    """Periodically monitor GPU and optimize memory usage"""
    while True:
        await asyncio.sleep(300)  # Every 5 minutes
        
        gpu_monitor.log_memory_usage("Periodic check")
        
        # Clear CUDA cache if memory usage is high
        if torch.cuda.memory_allocated() > 0.8 * torch.cuda.get_device_properties(0).total_memory:
            gpu_monitor.clear_cache()
```

## Configuration Options

GPU usage can be configured through the `config/config.json` file:

```json
{
  "gpu": {
    "enabled": true,
    "memory_limit": 0.8,  // Use up to 80% of available VRAM
    "cache_cleanup_interval": 300,  // Clear cache every 5 minutes
    "optimize_for_inference": true
  },
  "whisper": {
    "model": "medium",
    "device": "cuda",  // Use GPU for STT
    "compute_type": "float16"  // Use mixed precision
  },
  "alltalk": {
    "use_gpu": true,
    "half_precision": true  // Use float16 for faster inference
  },
  "ollama": {
    "num_gpu": 1,     // Number of GPUs to use
    "gpu_layers": 50  // Number of layers to offload to GPU
  }
}
```

## Model Size Recommendations

### For Speech-to-Text (Whisper)

| Model | VRAM Required | Accuracy | Speed | Recommendation |
|-------|---------------|----------|-------|----------------|
| tiny  | 1GB           | Low      | Fast  | Low-end systems |
| base  | 1.5GB         | Medium   | Good  | Balanced systems |
| small | 2GB           | Good     | Medium| Standard choice |
| medium| 4GB           | Very Good| Slower| Recommended if available |
| large | 8GB+          | Excellent| Slow  | Only for high-end systems |

### For Text-to-Speech (AllTalk)

| Model Type | VRAM Required | Quality | Speed | Recommendation |
|------------|---------------|---------|-------|----------------|
| XTTS       | 6GB+          | Excellent| Slow | High quality needs |
| Piper      | 2GB           | Good    | Fast  | Real-time needs |

### For Language Models (Ollama)

| Model       | VRAM Required | Quality | Speed | Recommendation |
|-------------|---------------|---------|-------|----------------|
| phi:2b      | 2GB           | Good    | Fast  | Low-end systems |
| gemma-2b    | 4GB           | Good    | Fast  | Balanced systems |
| mistral     | 8GB+          | Excellent| Medium| Recommended if available |
| llama3:8b   | 8GB+          | Excellent| Medium| Standard choice |
| larger models | 12GB+       | Superior| Slow  | Only for high-end systems |

## Memory Management Strategies

### 1. Component Isolation

The system separates GPU-intensive tasks to prevent memory contention:

```python
# Example of component isolation in server.py
async def start_server():
    # Initialize components with staggered GPU usage
    
    # First STT (holds models in memory)
    stt_service = STTService(config)
    
    # Then TTS (loads/unloads as needed)
    tts_service = TTSService(config)
    
    # Finally LLM (dynamic memory usage)
    llm_service = OllamaClient(config)
```

### 2. Prioritized Model Loading

For systems with limited VRAM, the system prioritizes critical models:

```python
# Preload the STT model before accepting connections
self.logger.info("Preloading STT model (this may take a moment)...")
try:
    # Run in thread pool to avoid blocking startup
    start_time = time.time()
    if hasattr(self.stt_service, 'original_stt') and hasattr(self.stt_service.original_stt, '_load_model'):
        await asyncio.to_thread(self.stt_service.original_stt._load_model)
        load_time = time.time() - start_time
        self.logger.info(f"STT model preloaded successfully in {load_time:.2f} seconds")
except Exception as e:
    self.logger.error(f"Error preloading STT model: {e}")
    self.logger.warning("Will use lazy loading instead, expect delay on first transcription")
```

### 3. Mixed Precision Inference

The system uses half-precision (float16) where appropriate to reduce memory usage:

```python
# In stt_service.py
def load_model(self):
    import torch
    
    # Enable mixed precision
    if self.config.get("compute_type") == "float16" and torch.cuda.is_available():
        self.model = whisper.load_model(
            self.model_size,
            device=self.device,
            download_root=self.download_root
        ).half()  # Convert to half precision
        
        self.logger.info(f"Loaded {self.model_size} model in half precision")
    else:
        self.model = whisper.load_model(
            self.model_size,
            device=self.device,
            download_root=self.download_root
        )
```

### 4. Automatic Cache Clearing

The system automatically clears the CUDA cache to prevent memory fragmentation:

```python
# Clear cache after unloading models
gpu_monitor.clear_cache()

# Periodic cache clearing
if torch.cuda.memory_allocated() > 0.8 * torch.cuda.get_device_properties(0).total_memory:
    gpu_monitor.clear_cache()
```

## Hardware Requirements

### Minimum Requirements
- NVIDIA GPU with 4GB VRAM
- CUDA 11.7 or later
- Current NVIDIA drivers

### Recommended Specifications
- NVIDIA GPU with 8GB+ VRAM (RTX 2060 or better)
- CUDA 12.0+
- 16GB+ system RAM
- SSD storage for models

## Common Issues and Solutions

### 1. Out of Memory Errors

**Symptoms**: 
- CUDA out of memory errors
- System crashes during processing
- STT or TTS operations failing

**Solutions**:
- Reduce model sizes (use smaller models)
- Enable mixed precision (float16)
- Increase cache clearing frequency
- Disable GPU for one component (e.g., run STT on CPU)

**Example Fix**:
```python
# Switch to a smaller model
config["whisper"]["model"] = "small"

# Enable mixed precision
config["whisper"]["compute_type"] = "float16"

# Increase cache clearing frequency
config["gpu"]["cache_cleanup_interval"] = 120  # Clear every 2 minutes
```

### 2. Slow First-Time Operations

**Symptoms**:
- First STT operation takes much longer than subsequent ones
- TTS initializes slowly on first use

**Solutions**:
- Preload models at startup
- Use model prewarming
- Implement progressive loading

**Example Fix**:
```python
# In EnhancedServer.start()
# Preload models in background
async def preload_models():
    self.logger.info("Preloading models...")
    
    # STT model preloading
    await asyncio.to_thread(self.stt_service.load_model)
    
    # TTS prewarm
    await asyncio.to_thread(self.tts_service.synthesize, "Prewarming the TTS system")
    
    self.logger.info("Models preloaded successfully")

asyncio.create_task(preload_models())
```

### 3. Memory Leaks

**Symptoms**:
- Increasing memory usage over time
- Performance degradation after extended use
- Eventually running out of memory

**Solutions**:
- Regular cache clearing
- Session cleanup
- Proper reference management

**Example Fix**:
```python
# Setup periodic memory monitoring and cleanup
async def monitor_memory():
    while True:
        await asyncio.sleep(300)  # Every 5 minutes
        
        # Log current memory usage
        gpu_monitor.log_memory_usage("Periodic check")
        
        # Clear CUDA cache
        gpu_monitor.clear_cache()
        
        # Force garbage collection
        import gc
        gc.collect()
        
        # Clear any old sessions
        state_manager.cleanup_old_sessions(max_age=3600)  # 1 hour

asyncio.create_task(monitor_memory())
```

## Best Practices

1. **Right-Size Your Models**
   - Use the smallest model that meets your quality requirements
   - Consider quality/performance tradeoffs for your specific use case

2. **Monitor GPU Usage**
   - Implement regular logging of GPU memory usage
   - Set up alerts for high memory conditions

3. **Implement Fallbacks**
   - Always have CPU fallbacks for critical components
   - Degrade gracefully when GPU resources are constrained

4. **Progressive Enhancement**
   - Start with smaller models and scale up if resources permit
   - Add GPU-accelerated components incrementally

5. **Memory Management**
   - Clear CUDA cache after large operations
   - Unload unused models when not needed
   - Use mixed precision where appropriate

## Conclusion

Proper CUDA optimization is essential for the VR Interview System's performance, especially for real-time conversation. By following these guidelines and implementing appropriate monitoring and optimization strategies, you can achieve the best possible performance for your specific hardware configuration.