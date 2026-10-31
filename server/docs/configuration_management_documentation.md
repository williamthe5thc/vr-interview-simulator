# VR Interview System: Configuration Management Documentation (Updated)

## Title and Overview

The Configuration Management component of the VR Interview System provides a flexible, hierarchical approach to configuring all aspects of the system. It implements a singleton pattern through the `Config` class for consistent configuration access throughout the application. The system loads settings from JSON files, detects platform-specific capabilities, automatically configures GPU acceleration based on available hardware, and supports overrides through environment variables. This ensures deployability across different environments while providing optimal performance for each platform.

## Architecture

The Configuration Management is implemented as a singleton utility class with methods for loading, validating, and applying environment overrides to the system configuration. It includes platform detection and GPU capability discovery to optimize performance on different hardware.

```
┌────────────────┐   Load   ┌───────────────┐   Override  ┌─────────────────┐
│ Default Config │────────► │ File Config   │─────────────►Environment Config│
└────────────────┘          └───────────────┘             └────────┬─────────┘
                                                                   │
┌─────────────────────────────────────────────────────────────────▼───────────┐
│                  Platform & GPU Detection and Configuration                 │
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

## Key Classes/Functions

### Config Class

```python
class Config:
    """Configuration manager with platform-aware path handling."""
    
    _instance = None
    _config: Dict[str, Any] = {}
    
    @classmethod
    def get_instance(cls) -> 'Config':
        """Get singleton instance of Config."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
```

#### Core Methods

- **`__init__(self)`**: Initializes configuration with platform detection
- **`load_config(self, config_path=None)`**: Loads configuration from file with platform-specific defaults
- **`get(self, key, default=None)`**: Gets configuration value by key with dot notation support
- **`get_all(self)`**: Gets entire configuration
- **`get_platform_info(self)`**: Gets platform information
- **`get_gpu_info(self)`**: Gets GPU information and capabilities

### Helper Functions

- **`_deep_update(self, base_dict, update_dict)`**: Recursively updates a nested dictionary
- **`_apply_platform_overrides(self)`**: Applies platform-specific configuration adjustments
- **`_apply_env_overrides(self)`**: Applies environment variable overrides
- **`_validate_config(self)`**: Validates that configuration has all required fields
- **`_create_default_config(self, config_path)`**: Creates a default configuration file
- **`_set_nested_value(self, d, keys, value)`**: Sets a nested configuration value

### Backward Compatibility Function

```python
def load_config(config_path: str = "config/config.json") -> Dict[str, Any]:
    """
    Load configuration with backward compatibility.
    This function is maintained for compatibility with existing code.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Configuration dictionary
    """
    config_instance = Config.get_instance()
    if config_path != "config/config.json":
        # If a specific path was provided, reload with that path
        config_instance.load_config(config_path)
    
    return config_instance.get_all()
```

## Usage Patterns

### Singleton Pattern

The new configuration system uses a singleton pattern to ensure consistent configuration access:

```python
# Get the singleton configuration instance
from app.utils.config import Config
config = Config.get_instance()

# Access configuration values with dot notation
log_level = config.get("server.log_level", "INFO")
port = config.get("server.port", 8765)

# Get platform information
platform_info = config.get_platform_info()
if platform_info["is_mac"]:
    # Handle Mac-specific logic
    
# Get GPU information
gpu_type, gpu_name, gpu_available = config.get_gpu_info()
if gpu_available and gpu_type == "nvidia":
    # Use CUDA acceleration
```

### Loading Custom Configuration

```python
# Load a custom configuration file
config = Config.get_instance()
config.load_config("/path/to/custom/config.json")

# Access the updated configuration
new_value = config.get("custom.setting")

# For backward compatibility
from app.utils.config import load_config
config_dict = load_config("/path/to/custom/config.json")
```

### Accessing Configuration Values

```python
# Get a simple value with a default
host = config.get("server.host", "0.0.0.0")

# Get a nested value
ollama_url = config.get("ollama.url", "http://localhost:11434")

# Get a deeply nested value
temperature = config.get("ollama.options.temperature", 0.7)

# Get entire configuration
full_config = config.get_all()
```

### Environment Overrides

```bash
# Override server port
export VR_INTERVIEW_SERVER__PORT=8080

# Override Ollama URL
export VR_INTERVIEW_OLLAMA__URL=http://ollama:11434

# Override a nested option (temperature)
export VR_INTERVIEW_OLLAMA__OPTIONS__TEMPERATURE=0.8

# Override boolean value
export VR_INTERVIEW_HEARTBEAT__ENABLED=false

# Override device type
export VR_INTERVIEW_AUDIO__DEVICE=cpu
```

## Implementation Details

### Singleton Configuration Instance

The configuration system uses a singleton pattern to ensure a single consistent configuration throughout the application:

```python
@classmethod
def get_instance(cls) -> 'Config':
    """Get singleton instance of Config."""
    if cls._instance is None:
        cls._instance = cls()
    return cls._instance

def __init__(self):
    """Initialize configuration with platform detection."""
    if Config._instance is not None:
        raise RuntimeError("Config is a singleton. Use get_instance() instead.")
    
    self.logger = logging.getLogger("config")
    
    self.platform_info = {
        "is_windows": PlatformUtils.is_windows(),
        "is_mac": PlatformUtils.is_mac(),
        "is_linux": PlatformUtils.is_linux(),
    }
    
    # Get GPU information
    self.gpu_info = PlatformUtils.get_gpu_info()
    
    # Ensure platform directories exist
    PlatformUtils.create_platform_dirs()
    
    # Load configuration
    self.load_config()
```

### Platform and GPU Detection

The system now automatically detects platform and GPU information for optimal configuration:

```python
def _get_gpu_info(self):
    """
    Get available GPU information.
    Returns a tuple of (gpu_type, gpu_name, available) where:
    - gpu_type: 'nvidia', 'amd', 'apple', or 'none'
    - gpu_name: Name of the GPU or 'none'
    - available: Boolean indicating if GPU acceleration can be used
    """
    gpu_type = "none"
    gpu_name = "none"
    available = False
    
    try:
        if PlatformUtils.is_windows():
            # Check for NVIDIA GPU on Windows
            # [GPU detection code for Windows...]
        
        elif PlatformUtils.is_mac():
            # Check for Metal-compatible GPU on Mac
            # [GPU detection code for macOS...]
            
            # Check for Apple Silicon
            if "apple" in output and "m1" in output or "m2" in output or "m3" in output:
                gpu_type = "apple"
                gpu_name = "Apple Silicon"
                available = True
        
        elif PlatformUtils.is_linux():
            # Try to detect GPU on Linux
            # [GPU detection code for Linux...]
    
    except Exception as e:
        print(f"Error detecting GPU: {str(e)}")
    
    return (gpu_type, gpu_name, available)
```

### Platform-Specific Configuration

The system applies platform-specific overrides automatically:

```python
def _apply_platform_overrides(self) -> None:
    """Apply platform-specific configuration overrides."""
    
    # Apply GPU-specific settings
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
    
    # Mac-specific adjustments
    if PlatformUtils.is_mac():
        if "alltalk" in Config._config:
            # Update AllTalk paths for Mac
            alltalk_dir = PlatformUtils.get_alltalk_default_path()
            Config._config["alltalk"]["alltalk_dir"] = alltalk_dir
```

### Environment Variable Overrides

The system supports overriding configuration with environment variables using a structured approach:

```python
def _apply_env_overrides(self) -> None:
    """Apply configuration overrides from environment variables."""
    prefix = "VR_INTERVIEW_"
    
    for key, value in os.environ.items():
        if key.startswith(prefix):
            # Remove prefix and split by double underscore for nested keys
            config_path = key[len(prefix):].lower().split("__")
            
            # Apply to config dict
            self._set_nested_value(Config._config, config_path, value)

def _set_nested_value(self, d: Dict[str, Any], keys: list, value: str) -> None:
    """Set a nested dictionary value from a list of keys."""
    if not keys:
        return
    
    # Process value based on existing type if present
    if len(keys) == 1:
        key = keys[0]
        if key in d:
            existing_value = d[key]
            if isinstance(existing_value, bool):
                d[key] = value.lower() in ('true', 'yes', '1')
            elif isinstance(existing_value, int):
                d[key] = int(value)
            elif isinstance(existing_value, float):
                d[key] = float(value)
            else:
                d[key] = value
        else:
            # If key doesn't exist, add it as string
            d[key] = value
    else:
        # Navigate to nested dict
        key = keys[0]
        if key not in d:
            d[key] = {}
        elif not isinstance(d[key], dict):
            d[key] = {}
        
        # Recursively set nested value
        self._set_nested_value(d[key], keys[1:], value)
```

### Enhanced Configuration Validation

The system validates configuration to ensure all required components are present:

```python
def _validate_config(self) -> None:
    """Validate that configuration has all required fields."""
    # Check required sections
    required_sections = ["server", "audio", "ollama"]
    for section in required_sections:
        if section not in Config._config:
            self.logger.error(f"Missing required configuration section: {section}")
            raise ValueError(f"Missing required configuration section: {section}")
            
    # Validate server config
    if "host" not in Config._config["server"]:
        self.logger.error("Missing server.host configuration")
        raise ValueError("Missing server.host configuration")
        
    if "port" not in Config._config["server"]:
        self.logger.error("Missing server.port configuration")
        raise ValueError("Missing server.port configuration")
        
    # Validate Ollama config
    if "url" not in Config._config["ollama"]:
        self.logger.error("Missing ollama.url configuration")
        raise ValueError("Missing ollama.url configuration")
        
    if "model" not in Config._config["ollama"]:
        self.logger.error("Missing ollama.model configuration")
        raise ValueError("Missing ollama.model configuration")
```

### Default Configuration Creation

The system can create a default configuration file with platform-specific settings:

```python
def _create_default_config(self, config_path: str) -> None:
    """Create a default configuration file."""
    default_config = self._get_minimal_config()
    
    # Add platform-specific paths
    default_config["storage"] = {
        "audio_dir": os.path.join(PlatformUtils.get_app_data_path(), "audio"),
        "conversation_dir": os.path.join(PlatformUtils.get_app_data_path(), "conversations"),
        "retention_days": 30
    }
    
    default_config["alltalk"] = {
        "url": "http://127.0.0.1:7851",
        "voice": "female_06.wav",
        "format": "wav",
        "retries": 3,
        "timeout": 60,
        "alltalk_dir": PlatformUtils.get_alltalk_default_path(),
        "default_language": "en",
        "endpoints": ["tts-generate", "synthesize", "tts"]
    }
    
    default_config["cache"] = {
        "enabled": True,
        "dir": os.path.join(PlatformUtils.get_app_data_path(), "cache", "tts"),
        "max_entries": 1000
    }
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    
    # Write config file
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(default_config, f, indent=2)
    
    Config._config = default_config
```

## Configuration

The VR Interview System configuration is stored in a JSON file with the following structure:

### Server Configuration
```json
"server": {
  "host": "0.0.0.0",
  "port": 8765,
  "log_level": "INFO"
}
```

### Audio Configuration with Automatic Device Selection
```json
"audio": {
  "stt_model": "medium",
  "tts_model": "en",
  "sample_rate": 16000,
  "channels": 1,
  "device": "cuda"  // Auto-configured based on GPU detection
}
```

### Storage Configuration with Platform-Specific Paths
```json
"storage": {
  "audio_dir": "~/Library/Application Support/VRInterviewSystem/audio",  // Platform-specific
  "conversation_dir": "~/Library/Application Support/VRInterviewSystem/conversations",
  "retention_days": 30
}
```

### LLM Configuration
```json
"ollama": {
  "url": "http://localhost:11434",
  "model": "mistral:latest",
  "context_length": 8192,
  "system_prompt": "You are a job interviewer conducting an interview with the candidate...",
  "options": {
    "temperature": 0.7,
    "top_p": 0.9,
    "top_k": 40,
    "repeat_penalty": 1.1,
    "num_predict": 100,
    "seed": 42,
    "timeout": 60
  }
}
```

### TTS Configuration with Platform-Specific Paths
```json
"alltalk": {
  "url": "http://127.0.0.1:7851",
  "voice": "female_06.wav",
  "format": "wav",
  "retries": 3,
  "timeout": 60,
  "alltalk_dir": "~/Applications/AllTalk",  // Platform-specific
  "default_language": "en",
  "endpoints": ["tts-generate", "synthesize", "tts"]
}
```

### Caching Configuration
```json
"cache": {
  "enabled": true,
  "dir": "~/Library/Application Support/VRInterviewSystem/cache/tts",  // Platform-specific
  "max_entries": 1000
}
```

### Heartbeat Configuration
```json
"heartbeat": {
  "enabled": true,
  "interval": 5.0
}
```

## Common Issues

### Configuration Loading Issues

1. **Missing Configuration File**:
   - **Symptoms**: Warnings about file not found, using defaults
   - **Causes**: Incorrect file path or missing config file
   - **Solution**: System now creates a default configuration file with platform-specific settings

2. **Invalid JSON**:
   - **Symptoms**: Error loading configuration, JSON parsing errors
   - **Causes**: Syntax errors in the config file
   - **Solution**: Validate JSON format before deployment

3. **Missing Required Sections**:
   - **Symptoms**: Validation errors at startup
   - **Causes**: Incomplete configuration
   - **Solution**: Validation ensures all required fields are present

### Environment Variable Issues

1. **Case Sensitivity**:
   - **Symptoms**: Environment variables not being applied
   - **Causes**: Incorrect casing in variable names
   - **Solution**: Variables are converted to lowercase during processing

2. **Type Conversion**:
   - **Symptoms**: Unexpected configuration behavior
   - **Causes**: Incorrect type conversion from string
   - **Solution**: The `_set_nested_value` function handles common types

3. **Naming Conventions**:
   - **Symptoms**: Nested configuration not applied
   - **Causes**: Incorrect variable naming
   - **Solution**: Use double underscore as separator for nested keys

### GPU Configuration Issues

1. **Incorrect Device Selection**:
   - **Symptoms**: System using CPU despite available GPU
   - **Causes**: Misconfigured GPU settings or detection issue
   - **Solution**: Improved automatic GPU detection and manual override option

2. **Apple Silicon Compatibility**:
   - **Symptoms**: Issues with MPS backend on Apple Silicon
   - **Causes**: Certain operations not yet supported on MPS backend
   - **Solution**: Selective operation fallback to CPU

3. **AMD GPU Support**:
   - **Symptoms**: AMD GPU not being utilized on Windows
   - **Causes**: Limited ROCm support on Windows
   - **Solution**: Improved platform-specific detection and configuration

## Code Examples

### Getting Configuration Instance

```python
from app.utils.config import Config

# Get the singleton configuration instance
config = Config.get_instance()

# Access configuration with dot notation
host = config.get("server.host", "0.0.0.0")
port = config.get("server.port", 8765)
model = config.get("ollama.model", "mistral:latest")
```

### Platform and GPU Detection

```python
# Get platform information
platform_info = config.get_platform_info()
if platform_info["is_mac"]:
    # Handle Mac-specific logic
    print("Running on macOS")
elif platform_info["is_windows"]:
    # Handle Windows-specific logic
    print("Running on Windows")
elif platform_info["is_linux"]:
    # Handle Linux-specific logic
    print("Running on Linux")

# Get GPU information
gpu_type, gpu_name, gpu_available = config.get_gpu_info()
if gpu_available:
    print(f"Using {gpu_type} GPU: {gpu_name}")
    
    if gpu_type == "nvidia":
        # CUDA-specific optimizations
        print("CUDA acceleration enabled")
    elif gpu_type == "amd" and platform_info["is_mac"]:
        # Metal-specific optimizations
        print("Metal Performance Shaders enabled")
    elif gpu_type == "apple":
        # Apple Silicon optimizations
        print("Apple Silicon acceleration enabled")
else:
    print("GPU acceleration not available, using CPU")
```

### Environment Variable Configuration

```python
# Set environment variables for testing
import os
os.environ["VR_INTERVIEW_SERVER__PORT"] = "9000"
os.environ["VR_INTERVIEW_OLLAMA__OPTIONS__TEMPERATURE"] = "0.8"
os.environ["VR_INTERVIEW_AUDIO__DEVICE"] = "cpu"

# Create a fresh configuration instance
Config._instance = None  # Reset singleton for testing
config = Config.get_instance()

# Verify that environment variables were applied
assert config.get("server.port") == 9000
assert config.get("ollama.options.temperature") == 0.8
assert config.get("audio.device") == "cpu"
```

### Creating Default Configuration

```python
# Force creation of default configuration
import os
from app.utils.config import Config
from app.utils.platform_utils import PlatformUtils

# Get platform-specific config path
config_path = os.path.join(PlatformUtils.get_app_data_path(), "config", "config.json")

# Create new Config instance
Config._instance = None  # Reset singleton
config = Config.get_instance()

# Create default config
if not os.path.exists(config_path):
    config._create_default_config(config_path)
    print(f"Created default configuration at {config_path}")
```

### Full Configuration Loading Example

```python
def initialize_configuration():
    """Initialize configuration with proper platform detection and validation."""
    from app.utils.config import Config
    
    # Get the singleton configuration instance
    config = Config.get_instance()
    
    # Log platform and GPU information
    platform_info = config.get_platform_info()
    platform_name = "macOS" if platform_info["is_mac"] else "Windows" if platform_info["is_windows"] else "Linux"
    
    gpu_type, gpu_name, gpu_available = config.get_gpu_info()
    device = config.get("audio.device", "cpu")
    
    print(f"Platform: {platform_name}")
    print(f"GPU: {gpu_type} - {gpu_name} (Available: {gpu_available})")
    print(f"Using device: {device}")
    
    # Get essential configuration
    server_port = config.get("server.port", 8765)
    log_level = config.get("server.log_level", "INFO")
    ollama_url = config.get("ollama.url", "http://localhost:11434")
    ollama_model = config.get("ollama.model", "mistral:latest")
    
    print(f"Server will run on port {server_port}")
    print(f"Using Ollama at {ollama_url} with model {ollama_model}")
    
    return config
```