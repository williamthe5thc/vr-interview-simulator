# Updated VR Interview System Configuration Guide

This document describes the configuration options and management system for the VR Interview System.

## Configuration Architecture

The VR Interview System implements a sophisticated configuration management system based on a singleton pattern with the `Config` class. The system provides:

- Platform-specific configuration detection and adaptation
- GPU detection and automatic configuration
- Hierarchical configuration with intelligent defaults
- Environment variable overrides with support for nested keys
- Configuration validation with helpful error messages

```
┌────────────────┐   Load   ┌───────────────┐   Override  ┌─────────────────┐
│ Default Config │────────► │ File Config   │─────────────►Environment Config│
└────────────────┘          └───────────────┘             └────────┬─────────┘
                                                                   │
┌─────────────────────────────────────────────────────────────────▼───────────┐
│                      Platform & GPU Detection                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                               Validation                                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Application Config                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Configuration Files

The system uses JSON configuration files to control its behavior. Several configuration files are provided:

- `config.json` - The main configuration file used by default
- `config_example.json` - An example configuration file with comments explaining each option
- `config_minimal.json` - Minimal configuration for systems with limited resources
- `config_development.json` - Configuration optimized for development with extra debugging
- `config_production.json` - Configuration optimized for production use

## Loading Configuration

The configuration system follows a predictable path to locate and load the configuration:

1. Check for a configuration path in the `VR_INTERVIEW_CONFIG` environment variable
2. If not set, use the platform-specific default location:
   - Windows: `%APPDATA%\VRInterviewSystem\config\config.json`
   - macOS: `~/Library/Application Support/VRInterviewSystem/config/config.json`
   - Linux: `~/.vr_interview_system/config/config.json`
3. If the configuration file doesn't exist, create a default one with platform-specific optimizations

You can specify a custom configuration file path when starting the server:

```bash
# Using environment variable
export VR_INTERVIEW_CONFIG="/path/to/custom/config.json"
python server.py

# Using the run script
./run_server.sh /path/to/custom/config.json
```

## Configuration Options

### Server Settings

```json
"server": {
  "host": "0.0.0.0",  // Listen on all interfaces
  "port": 8765,       // WebSocket port
  "log_level": "INFO" // Logging level (DEBUG, INFO, WARNING, ERROR)
}
```

### Audio Settings

```json
"audio": {
  "stt_model": "medium", // Whisper model size: tiny, base, small, medium, large
  "tts_model": "en",     // Text-to-speech model
  "sample_rate": 16000,  // Audio sample rate
  "channels": 1,         // Audio channels (mono = 1)
  "device": "cuda"       // Device to use: cuda, mps, rocm, cpu (auto-detected)
}
```

### Storage Settings

```json
"storage": {
  "audio_dir": "/path/to/audio",         // Audio storage directory
  "conversation_dir": "/path/to/conversations", // Conversation history storage
  "retention_days": 30                   // Data retention period
}
```

### AllTalk Integration

The system supports multiple TTS providers, with AllTalk as the primary option and automatic fallbacks:

```json
"alltalk": {
  "url": "http://127.0.0.1:7851",     // AllTalk server URL
  "voice": "female_06.wav",           // Voice to use
  "retries": 3,                       // Retry attempts on failure
  "timeout": 60,                      // Request timeout in seconds
  "alltalk_dir": "/path/to/alltalk",  // AllTalk installation directory
  "default_language": "en",           // Default language
  "endpoints": ["tts-generate", "synthesize", "tts"], // API endpoints to try
  "use_fallback": true                // Use gTTS fallback if AllTalk fails
}
```

### Cache Settings

```json
"cache": {
  "enabled": true,                     // Enable response caching
  "dir": "/path/to/cache/tts",         // Cache directory  
  "max_entries": 1000                  // Maximum cache entries
}
```

### Ollama LLM Settings

```json
"ollama": {
  "url": "http://localhost:11434",   // Ollama server URL
  "model": "mistral:latest",         // LLM model to use
  "context_length": 8192,            // Maximum context length
  "system_prompt": "You are a job interviewer...", // Initial system prompt
  "use_streaming": false,            // Use streaming mode
  "precompute_enabled": true,        // Enable precomputation of common responses
  "scenario_type": "interview",      // Default scenario type
  "max_cache_entries": 500,          // Maximum cache entries for LLM
  "options": {                       // Model generation parameters
    "temperature": 0.7,              // Randomness (higher = more creative)
    "top_p": 0.85,                   // Nucleus sampling probability 
    "top_k": 30,                     // Top tokens to consider
    "repeat_penalty": 1.2,           // Penalty for repeating tokens
    "num_predict": 120,              // Maximum tokens to generate
    "seed": 42                       // Random seed for reproducibility
  }
}
```

### Heartbeat Settings

```json
"heartbeat": {
  "enabled": true,  // Enable connection heartbeat
  "interval": 5.0   // Base heartbeat interval in seconds
}
```

### EmotiVoice TTS Provider (Optional)

```json
"emotivoice": {
  "url": "http://localhost:8501",   // EmotiVoice server URL
  "voice": "default",               // Voice ID to use
  "language": "en",                 // Language code
  "emotion": "neutral",             // Default emotion
  "timeout": 20,                    // Request timeout in seconds
  "cache_dir": "data/tts_cache/emotivoice" // Cache directory
}
```

### Piper TTS Provider (Optional)

```json
"piper": {
  "voice": "en_US-lessac-medium",   // Piper voice to use
  "model_dir": "./models/piper"     // Directory containing Piper models
}
```

## Enhanced GPU Detection and Configuration

The system now features improved GPU detection and automatic configuration for different hardware:

### Automatic Hardware Detection

The system detects available GPU hardware and configures itself appropriately:

```python
# In Config._apply_platform_overrides()
gpu_type, gpu_name, gpu_available = self.gpu_info

# Update STT settings based on GPU availability
if "audio" in Config._config:
    if gpu_type == "nvidia" and gpu_available:
        # NVIDIA acceleration for STT
        Config._config["audio"]["device"] = "cuda"
    elif gpu_type == "amd" and gpu_available:
        # AMD acceleration for STT - will work on Linux with ROCm or Mac with MPS
        if PlatformUtils.is_mac():
            Config._config["audio"]["device"] = "mps"
        elif PlatformUtils.is_linux():
            Config._config["audio"]["device"] = "rocm"
        else:
            # Probably Windows with AMD GPU - no direct PyTorch ROCm support
            Config._config["audio"]["device"] = "cpu"
    elif gpu_type == "apple" and gpu_available:
        # Apple Silicon acceleration
        Config._config["audio"]["device"] = "mps"
    else:
        # Default to CPU
        Config._config["audio"]["device"] = "cpu"
```

### NVIDIA GPU Support

For systems with NVIDIA GPUs:
- System automatically detects NVIDIA GPUs using `nvidia-smi`
- Configures CUDA acceleration for optimal performance
- Sets appropriate flags for TensorFloat32 (TF32) on supported GPUs

### AMD GPU Support

For systems with AMD GPUs:
- Linux: Detects and configures ROCm when available
- macOS: Uses Metal Performance Shaders (MPS) for GPU acceleration
- Windows: Falls back to CPU processing (no ROCm support)

### Apple Silicon Support

For Apple Silicon Macs (M1/M2/M3):
- Automatically detects Apple Silicon 
- Configures Metal Performance Shaders (MPS) for GPU acceleration
- Handles MPS-specific optimizations and limitations
- Falls back to CPU for unsupported operations

### Device Configuration

The `device` setting in the audio configuration is automatically set based on hardware detection:

```json
"audio": {
  "device": "cuda"  // auto: NVIDIA GPUs via CUDA
  "device": "mps"   // auto: Apple Silicon via Metal Performance Shaders
  "device": "rocm"  // auto: AMD GPUs on Linux via ROCm
  "device": "cpu"   // auto: Fallback when no GPU support available
}
```

## Improved Caching System

The system includes enhanced caching mechanisms for better performance:

### TTS Caching

An intelligent caching system stores TTS audio to avoid regenerating the same speech:

- **Cache Keys**: MD5 hashes based on text content and voice
- **Cache Directory**: Configurable storage location
- **Max Entries**: Configurable maximum cache size
- **Cache Pruning**: Intelligent removal of least-used entries when full
- **Usage Analytics**: Tracks cache hits and miss rates

### LLM Response Caching

The LLM client implements advanced caching:

- **Contextual Cache Keys**: Keys based on prompt, conversation context, and interaction stage
- **Intelligent Cache Pruning**: Weighs recency, usage count, and age for pruning decisions
- **Metadata Storage**: Tracks creation time, usage, and generation performance
- **Background Precomputation**: Common questions are precomputed during idle time
- **Disk Persistence**: Cache survives restarts for improved cold-start performance

## Using the Config Class

The `Config` class implements a singleton pattern for consistent access to configuration:

```python
from app.utils.config import Config

# Get the singleton instance
config = Config.get_instance()

# Get a configuration value with fallback
log_level = config.get("server.log_level", "INFO")

# Get GPU information
gpu_type, gpu_name, gpu_available = config.get_gpu_info()

# Get platform information
platform_info = config.get_platform_info()
```

### Key Methods

- **`get(key, default=None)`**: Get a configuration value with fallback
- **`get_all()`**: Get the entire configuration dictionary
- **`get_platform_info()`**: Get information about the current platform
- **`get_gpu_info()`**: Get information about available GPUs

## Environment Variables

Configuration values can be overridden using environment variables prefixed with `VR_INTERVIEW_` and using double underscore as separator for nested keys:

```bash
# Override server port
export VR_INTERVIEW_SERVER__PORT=8080

# Override Ollama URL
export VR_INTERVIEW_OLLAMA__URL=http://ollama:11434

# Override AllTalk voice
export VR_INTERVIEW_ALLTALK__VOICE=female_07.wav

# Override device type
export VR_INTERVIEW_AUDIO__DEVICE=cpu
```

Type conversion is automatically handled:
- Numeric strings are converted to integers or floats
- "true"/"false", "yes"/"no", "1"/"0" are converted to booleans
- Other values remain as strings

## Platform-Specific Configurations

The configuration system uses the `PlatformUtils` class to detect platform information and apply appropriate configurations:

### Windows-Specific Configuration

```json
// Default AllTalk path on Windows
"alltalk": {
  "alltalk_dir": "D:/AllTalk/alltalk_tts"
}
```

### macOS-Specific Configuration

```json
// Default AllTalk path on macOS
"alltalk": {
  "alltalk_dir": "~/Applications/AllTalk"
}

// For Apple Silicon Macs
"audio": {
  "device": "mps"  // Use Metal Performance Shaders
}
```

### Linux-Specific Configuration

```json
// Default AllTalk path on Linux
"alltalk": {
  "alltalk_dir": "~/alltalk_tts"
}

// For AMD GPUs on Linux
"audio": {
  "device": "rocm"  // Use ROCm
}
```

## TTS Service Configuration

The TTS service uses a sophisticated provider system with multiple endpoints and fallbacks:

### AllTalk API Endpoints

The system tries multiple API endpoints to maximize compatibility:

```json
"alltalk": {
  "endpoints": ["tts-generate", "synthesize", "tts"]
}
```

For each endpoint, the system will attempt different request formats:
1. Form data submission
2. JSON body
3. Alternative API paths

### Fallback Strategies

The TTS service incorporates multiple fallback strategies:

1. Try each AllTalk API endpoint in sequence
2. Look for recently generated files if API doesn't return content
3. Fall back to gTTS if AllTalk is unavailable
4. Generate silence as a last resort

## Common Issues

### Device Selection Issues

1. **CUDA Unavailable**:
   - **Symptoms**: Warnings about CUDA not available, falling back to CPU
   - **Causes**: Missing CUDA drivers or PyTorch not built with CUDA support
   - **Solution**: Install CUDA drivers or configure PyTorch properly

2. **MPS Issues on Apple Silicon**:
   - **Symptoms**: Errors about MPS operations not supported
   - **Causes**: Some operations aren't supported on MPS backend
   - **Solution**: System will selectively use CPU for unsupported operations

3. **ROCm Compatibility**:
   - **Symptoms**: Errors with AMD GPU on Linux
   - **Causes**: ROCm installation or compatibility issues
   - **Solution**: Add environment variables for compatibility: `HSA_OVERRIDE_GFX_VERSION=10.3.0`

### AllTalk Integration Issues

1. **Connection Errors**:
   - **Symptoms**: Warnings about AllTalk not available
   - **Causes**: AllTalk server not running or wrong URL
   - **Solution**: System will automatically fall back to gTTS

2. **Voice Not Found**:
   - **Symptoms**: Voice substitution messages
   - **Causes**: Requested voice not available in AllTalk
   - **Solution**: System will substitute with an available voice

3. **AllTalk Directory Issues**:
   - **Symptoms**: Warnings about directory not found
   - **Causes**: Incorrect path in configuration
   - **Solution**: Update alltalk_dir in configuration to correct path

## Configuration Tips

1. **Model Size**: Start with a smaller STT model (`tiny` or `base`) if you experience performance issues, then gradually increase.

2. **GPU Acceleration**: Let the system auto-detect your GPU capabilities or manually set the device type if needed.

3. **AllTalk Integration**: Configure all available AllTalk endpoints for maximum compatibility with different AllTalk versions.

4. **Caching**: Enable caching for improved performance in production environments.

5. **Environment Variables**: Use environment variables for deployment-specific settings to keep configuration files consistent.

6. **Platform-Specific Paths**: The system handles platform-specific paths automatically, but you can override them if needed.

7. **Temperature**: Lower values (0.5-0.7) keep the interviewer more focused, while higher values (0.7-0.9) create more varied responses.

8. **Disk Safety**: The system includes intelligent caching with automatic pruning to prevent disk space issues.