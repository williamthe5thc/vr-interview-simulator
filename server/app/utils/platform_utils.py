"""
Platform utilities for cross-platform compatibility in the VR Interview System.
Handles platform detection, path normalization, and GPU detection.
"""

import os
import sys
import platform
import json
import subprocess
from pathlib import Path

class PlatformUtils:
    """Utilities for cross-platform compatibility."""
    
    @staticmethod
    def is_windows():
        """Check if the system is Windows."""
        return platform.system() == "Windows"
    
    @staticmethod
    def is_mac():
        """Check if the system is macOS."""
        return platform.system() == "Darwin"
    
    @staticmethod
    def is_linux():
        """Check if the system is Linux."""
        return platform.system() == "Linux"
    
    @staticmethod
    def get_gpu_info():
        """
        Get available GPU information.
        Returns a tuple of (gpu_type, gpu_name, available) where:
        - gpu_type: 'nvidia', 'amd', or 'none'
        - gpu_name: Name of the GPU or 'none'
        - available: Boolean indicating if GPU acceleration can be used
        """
        gpu_type = "none"
        gpu_name = "none"
        available = False
        
        try:
            if PlatformUtils.is_windows():
                # Check for NVIDIA GPU on Windows
                try:
                    nvidia_smi = subprocess.run(
                        ['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=False
                    )
                    if nvidia_smi.returncode == 0 and nvidia_smi.stdout.strip():
                        gpu_type = "nvidia"
                        gpu_name = nvidia_smi.stdout.strip()
                        available = True
                except (FileNotFoundError, subprocess.SubprocessError):
                    pass
                
                # Check for AMD GPU on Windows if NVIDIA not found
                if not available:
                    try:
                        amd_info = subprocess.run(
                            ['wmic', 'path', 'win32_VideoController', 'get', 'name'],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            check=False
                        )
                        if amd_info.returncode == 0:
                            output = amd_info.stdout.lower()
                            if "amd" in output or "radeon" in output:
                                gpu_type = "amd"
                                gpu_name = next((line for line in output.splitlines() 
                                               if "amd" in line or "radeon" in line), "AMD GPU")
                                available = True
                    except (FileNotFoundError, subprocess.SubprocessError):
                        pass
            
            elif PlatformUtils.is_mac():
                # Check for Metal-compatible GPU on Mac
                try:
                    system_profiler = subprocess.run(
                        ['system_profiler', 'SPDisplaysDataType'],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=False
                    )
                    if system_profiler.returncode == 0:
                        output = system_profiler.stdout.lower()
                        if "amd" in output or "radeon" in output:
                            gpu_type = "amd"
                            # Extract GPU name - this is a simplified approach
                            for line in output.splitlines():
                                if "amd" in line or "radeon" in line:
                                    gpu_name = line.strip()
                                    break
                            available = True
                        
                        # Check for Apple Silicon
                        if "apple" in output and "m1" in output or "m2" in output or "m3" in output:
                            gpu_type = "apple"
                            gpu_name = "Apple Silicon"
                            available = True
                except (FileNotFoundError, subprocess.SubprocessError):
                    pass
            
            elif PlatformUtils.is_linux():
                # Try to detect GPU on Linux
                try:
                    # Check for NVIDIA first
                    nvidia_smi = subprocess.run(
                        ['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=False
                    )
                    if nvidia_smi.returncode == 0 and nvidia_smi.stdout.strip():
                        gpu_type = "nvidia"
                        gpu_name = nvidia_smi.stdout.strip()
                        available = True
                except (FileNotFoundError, subprocess.SubprocessError):
                    pass
                
                # Check for AMD if NVIDIA not found
                if not available:
                    try:
                        # Using lspci to check for AMD GPU
                        lspci = subprocess.run(
                            ['lspci'],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            check=False
                        )
                        if lspci.returncode == 0:
                            output = lspci.stdout.lower()
                            if "amd" in output or "radeon" in output:
                                gpu_type = "amd"
                                for line in output.splitlines():
                                    if "amd" in line or "radeon" in line:
                                        gpu_name = line.strip()
                                        break
                                # Check for ROCm installation
                                rocm_smi = subprocess.run(
                                    ['rocm-smi'],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    text=True,
                                    check=False
                                )
                                available = rocm_smi.returncode == 0
                    except (FileNotFoundError, subprocess.SubprocessError):
                        pass
        
        except Exception as e:
            print(f"Error detecting GPU: {str(e)}")
        
        return (gpu_type, gpu_name, available)
    
    @staticmethod
    def get_app_data_path():
        """
        Get the appropriate application data directory for the current platform.
        This provides a cross-platform location for storing data files.
        """
        if PlatformUtils.is_windows():
            app_data = os.environ.get('APPDATA', os.path.join(os.environ['USERPROFILE'], 'AppData', 'Roaming'))
            return os.path.join(app_data, "VRInterviewSystem")
        elif PlatformUtils.is_mac():
            return os.path.join(os.path.expanduser('~'), 'Library', 'Application Support', 'VRInterviewSystem')
        else:  # Linux and others
            return os.path.join(os.path.expanduser('~'), '.vr_interview_system')
    
    @staticmethod
    def normalize_path(path):
        """
        Normalize a path for the current platform.
        Converts path separators and resolves relative paths.
        """
        # Convert to Path object for platform-safe operations
        norm_path = Path(path).resolve()
        return str(norm_path)
    
    @staticmethod
    def get_default_config_path():
        """Get the default path for configuration based on platform."""
        if PlatformUtils.is_mac():
            # Use a Mac-appropriate location for config
            return os.path.join(PlatformUtils.get_app_data_path(), "config", "config.json")
        else:
            # Default Windows/Linux location
            return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "config", "config.json")
    
    @staticmethod
    def get_alltalk_default_path():
        """Get the default AllTalk installation path for the current platform."""
        if PlatformUtils.is_windows():
            return "D:/AllTalk/alltalk_tts"
        elif PlatformUtils.is_mac():
            return os.path.join(os.path.expanduser('~'), 'Applications', 'AllTalk')
        else:  # Linux
            return os.path.join(os.path.expanduser('~'), 'alltalk_tts')
    
    @staticmethod
    def create_platform_dirs():
        """Create platform-specific directories needed for the application."""
        base_dir = PlatformUtils.get_app_data_path()
        
        # Create main directory
        os.makedirs(base_dir, exist_ok=True)
        
        # Create subdirectories
        for subdir in ['audio', 'cache', 'cache/tts', 'conversations', 'logs', 'config']:
            dir_path = os.path.join(base_dir, subdir)
            os.makedirs(dir_path, exist_ok=True)
        
        # Copy default config if not exists
        default_config = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                     "..", "..", "config", "config.json")
        target_config = os.path.join(base_dir, "config", "config.json")
        
        if os.path.exists(default_config) and not os.path.exists(target_config):
            # Read default config
            with open(default_config, 'r') as f:
                config = json.load(f)
            
            # Update paths for platform
            if 'storage' in config:
                config['storage']['audio_dir'] = os.path.join(base_dir, 'audio')
                config['storage']['conversation_dir'] = os.path.join(base_dir, 'conversations')
                
            if 'alltalk' in config:
                config['alltalk']['alltalk_dir'] = PlatformUtils.get_alltalk_default_path()
                
            if 'cache' in config:
                config['cache']['dir'] = os.path.join(base_dir, 'cache', 'tts')
            
            # Write updated config
            with open(target_config, 'w') as f:
                json.dump(config, f, indent=2)
        
        return base_dir
