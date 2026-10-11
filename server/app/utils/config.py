"""
Configuration module for the VR Interview System.
Handles loading, validation, and platform-specific configuration settings.
"""

import json
import os
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from app.utils.platform_utils import PlatformUtils

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
    
    def load_config(self, config_path: Optional[str] = None) -> None:
        """
        Load configuration from file with platform-specific overrides.
        
        Args:
            config_path: Optional path to config file. If not provided,
                         platform-specific default will be used.
        """
        if config_path is None:
            # Try environment variable first
            config_path = os.environ.get('VR_INTERVIEW_CONFIG')
            
            # If not set, use platform-specific default
            if not config_path:
                config_path = PlatformUtils.get_default_config_path()
        
        config_path = PlatformUtils.normalize_path(config_path)
        
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    Config._config = json.load(f)
                self.logger.info(f"Loaded configuration from {config_path}")
            else:
                # If config doesn't exist, create default
                self._create_default_config(config_path)
                self.logger.info(f"Created default configuration at {config_path}")
                
            # Apply platform-specific overrides
            self._apply_platform_overrides()
            
            # Apply environment variable overrides
            self._apply_env_overrides()
            
            # Validate configuration
            self._validate_config()
            
        except Exception as e:
            self.logger.error(f"Error loading configuration: {str(e)}")
            # Create a minimal default configuration
            Config._config = self._get_minimal_config()
    
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
    
    def _get_minimal_config(self) -> Dict[str, Any]:
        """Get a minimal default configuration."""
        return {
            "server": {
                "host": "0.0.0.0",
                "port": 8765,
                "log_level": "INFO"
            },
            "audio": {
                "stt_model": "medium",
                "tts_model": "en",
                "sample_rate": 16000,
                "channels": 1
            },
            "ollama": {
                "url": "http://127.0.0.1:11434",
                "model": "mistral:latest",
                "context_length": 8192,
                "system_prompt": "You are an AI interviewer conducting a job interview.",
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "top_k": 40,
                    "repeat_penalty": 1.1
                }
            },
            "heartbeat": {
                "enabled": True,
                "interval": 5.0
            }
        }
    
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
                
                # Mac typically uses different port for AllTalk
                if "url" in Config._config["alltalk"]:
                    # Check if it's the Windows default
                    if Config._config["alltalk"]["url"] == "http://127.0.0.1:7851":
                        # Update to Mac default if it exists
                        Config._config["alltalk"]["url"] = "http://127.0.0.1:7851"
    
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
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key."""
        keys = key.split('.')
        
        # Navigate through nested dictionaries
        value = Config._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_all(self) -> Dict[str, Any]:
        """Get entire configuration."""
        return Config._config.copy()
    
    def get_platform_info(self) -> Dict[str, bool]:
        """Get platform information."""
        return self.platform_info.copy()
    
    def get_gpu_info(self) -> tuple:
        """Get GPU information."""
        return self.gpu_info


# Backward compatibility for existing code
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
