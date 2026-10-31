#!/usr/bin/env python3
"""
Cross-platform setup script for VR Interview System.
This script handles installation and configuration on Windows, macOS, and Linux.
"""

import os
import sys
import platform
import json
import subprocess
import shutil
from pathlib import Path
import argparse

class SetupUtils:
    """Utilities for cross-platform setup."""
    
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
    def get_app_data_path():
        """Get the appropriate application data directory for current platform."""
        if SetupUtils.is_windows():
            app_data = os.environ.get('APPDATA', 
                                     os.path.join(os.environ['USERPROFILE'], 'AppData', 'Roaming'))
            return os.path.join(app_data, "VRInterviewSystem")
        elif SetupUtils.is_mac():
            return os.path.join(os.path.expanduser('~'), 'Library', 'Application Support', 'VRInterviewSystem')
        else:  # Linux and others
            return os.path.join(os.path.expanduser('~'), '.vr_interview_system')
    
    @staticmethod
    def get_gpu_info():
        """Get GPU information."""
        gpu_type = "none"
        gpu_name = "none"
        
        try:
            if SetupUtils.is_windows():
                # Check for NVIDIA GPU
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
                except (FileNotFoundError, subprocess.SubprocessError):
                    pass
                
                # Check for AMD GPU if NVIDIA not found
                if gpu_type == "none":
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
                    except (FileNotFoundError, subprocess.SubprocessError):
                        pass
            
            elif SetupUtils.is_mac():
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
                except (FileNotFoundError, subprocess.SubprocessError):
                    pass
                
                # Check for Apple Silicon
                if gpu_type == "none" and "arm" in platform.processor().lower():
                    gpu_type = "apple"
                    gpu_name = "Apple Silicon"
            
            elif SetupUtils.is_linux():
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
                except (FileNotFoundError, subprocess.SubprocessError):
                    pass
                
                # Check for AMD if NVIDIA not found
                if gpu_type == "none":
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
                    except (FileNotFoundError, subprocess.SubprocessError):
                        pass
        
        except Exception as e:
            print(f"Error detecting GPU: {str(e)}")
        
        return (gpu_type, gpu_name)


def setup_directories():
    """Create necessary directories for the application."""
    base_dir = SetupUtils.get_app_data_path()
    
    # Create main directory
    os.makedirs(base_dir, exist_ok=True)
    print(f"Created application directory: {base_dir}")
    
    # Create subdirectories
    for subdir in ['audio', 'cache', 'cache/tts', 'conversations', 'logs', 'config']:
        dir_path = os.path.join(base_dir, subdir)
        os.makedirs(dir_path, exist_ok=True)
        print(f"Created directory: {dir_path}")
    
    return base_dir


def create_default_config(base_dir, script_dir):
    """Create default configuration file."""
    # Path to template config
    template_config = os.path.join(script_dir, "config", "config.json")
    
    # Target config path
    target_config = os.path.join(base_dir, "config", "config.json")
    
    # Check if template exists
    if not os.path.exists(template_config):
        print(f"Template config not found at {template_config}.")
        print("Creating minimal default configuration.")
        
        # Create minimal config
        config = {
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
                "url": "http://localhost:11434",
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
    else:
        # Load template config
        with open(template_config, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        print(f"Loaded template configuration from {template_config}")
    
    # Update paths for platform
    config["storage"] = {
        "audio_dir": os.path.join(base_dir, "audio"),
        "conversation_dir": os.path.join(base_dir, "conversations"),
        "retention_days": 30
    }
    
    # Set AllTalk paths based on platform
    if "alltalk" not in config:
        config["alltalk"] = {}
        
    if SetupUtils.is_windows():
        alltalk_dir = "D:/AllTalk/alltalk_tts"
    elif SetupUtils.is_mac():
        alltalk_dir = os.path.join(os.path.expanduser('~'), 'Applications', 'AllTalk')
    else:  # Linux
        alltalk_dir = os.path.join(os.path.expanduser('~'), 'alltalk_tts')
    
    config["alltalk"]["alltalk_dir"] = alltalk_dir
    config["alltalk"]["url"] = "http://127.0.0.1:7851"
    config["alltalk"]["voice"] = "female_06.wav"
    config["alltalk"]["endpoints"] = ["tts-generate", "synthesize", "tts"]
    config["alltalk"]["use_fallback"] = True
    
    # Set cache paths
    config["cache"] = {
        "enabled": True,
        "dir": os.path.join(base_dir, "cache", "tts"),
        "max_entries": 1000
    }
    
    # GPU-specific settings
    gpu_type, gpu_name = SetupUtils.get_gpu_info()
    print(f"Detected GPU: {gpu_type} - {gpu_name}")
    
    if "audio" not in config:
        config["audio"] = {}
    
    if gpu_type == "nvidia":
        config["audio"]["device"] = "cuda"
    elif gpu_type == "amd":
        if SetupUtils.is_mac():
            config["audio"]["device"] = "mps"
        elif SetupUtils.is_linux():
            config["audio"]["device"] = "rocm"
        else:
            config["audio"]["device"] = "cpu"
    elif gpu_type == "apple":
        config["audio"]["device"] = "mps"
    else:
        config["audio"]["device"] = "cpu"
    
    # Write config file
    with open(target_config, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)
    
    print(f"Created configuration file at {target_config}")
    return target_config


def install_dependencies():
    """Install Python dependencies."""
    print("Installing Python dependencies...")
    
    # Check if pip is available
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    except subprocess.SubprocessError:
        print("Error: pip is not available. Please install pip first.")
        return False
    
    # Install basic requirements
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            check=True
        )
        print("Installed basic dependencies.")
    except subprocess.SubprocessError as e:
        print(f"Error installing dependencies: {str(e)}")
        return False
    
    # Install platform-specific packages
    try:
        if SetupUtils.is_windows():
            # Windows-specific packages
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "pywin32"],
                check=True
            )
        elif SetupUtils.is_mac():
            # Mac-specific packages
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "torch", "torchvision", "torchaudio"],
                check=True
            )
        elif SetupUtils.is_linux():
            # Linux-specific packages
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "python-xlib"],
                check=True
            )
        
        # Install GPU-specific packages
        gpu_type, _ = SetupUtils.get_gpu_info()
        
        if gpu_type == "nvidia":
            print("Installing NVIDIA GPU support...")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "torch", "torchvision", "torchaudio", "--extra-index-url", "https://download.pytorch.org/whl/cu118"],
                check=True
            )
        elif gpu_type == "amd" and SetupUtils.is_linux():
            print("Installing AMD GPU support for Linux...")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "torch", "torchvision", "torchaudio", "--extra-index-url", "https://download.pytorch.org/whl/rocm5.6"],
                check=True
            )
        elif (gpu_type == "amd" or gpu_type == "apple") and SetupUtils.is_mac():
            print("Installing MPS (Metal Performance Shaders) support for Mac...")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "torch", "torchvision", "torchaudio"],
                check=True
            )
    
    except subprocess.SubprocessError as e:
        print(f"Warning: Error installing platform-specific dependencies: {str(e)}")
        print("The system may still work with reduced functionality.")
    
    print("Dependency installation completed.")
    return True


def create_launch_script(script_dir, config_path):
    """Create platform-specific launch script."""
    if SetupUtils.is_windows():
        # Create batch script for Windows
        script_path = os.path.join(script_dir, "run_server.bat")
        
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(f'@echo off\n')
            f.write(f'set VR_INTERVIEW_CONFIG={config_path}\n')
            f.write(f'cd "{script_dir}"\n')
            f.write(f'"{sys.executable}" server.py\n')
            f.write(f'pause\n')
    else:
        # Create shell script for Mac/Linux
        script_path = os.path.join(script_dir, "run_server.sh")
        
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(f'#!/bin/bash\n')
            f.write(f'export VR_INTERVIEW_CONFIG="{config_path}"\n')
            f.write(f'cd "{script_dir}"\n')
            f.write(f'python3 server.py\n')
        
        # Make script executable
        os.chmod(script_path, 0o755)
    
    print(f"Created launch script: {script_path}")
    return script_path


def main():
    """Main setup function."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Setup VR Interview System')
    parser.add_argument('--force', action='store_true', help='Force reconfiguration even if already set up')
    args = parser.parse_args()
    
    print(f"Setting up VR Interview System for {platform.system()}...")
    
    # Get script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Create app directories
    base_dir = setup_directories()
    
    # Create default configuration
    config_path = create_default_config(base_dir, script_dir)
    
    # Install dependencies
    install_dependencies()
    
    # Create launch script
    launch_script = create_launch_script(script_dir, config_path)
    
    print("\nSetup completed successfully!")
    print(f"Configuration file: {config_path}")
    print(f"Launch script: {launch_script}")
    print("\nTo start the server, run the launch script.")
    
    # Print platform-specific instructions
    if SetupUtils.is_windows():
        print("\nWindows-specific notes:")
        print("1. Ensure Ollama is installed and running on your system")
        print("2. For NVIDIA GPUs, ensure CUDA is installed")
        print("3. For AMD GPUs, the system will use CPU fallback")
    elif SetupUtils.is_mac():
        print("\nmacOS-specific notes:")
        print("1. Ensure Ollama is installed and running on your system")
        print("2. For Apple Silicon, MPS acceleration will be used automatically")
        print("3. For AMD GPUs, MPS acceleration will be used if available")
        print("4. You may need to install ffmpeg: brew install ffmpeg")
    else:
        print("\nLinux-specific notes:")
        print("1. Ensure Ollama is installed and running on your system")
        print("2. For NVIDIA GPUs, ensure CUDA is installed")
        print("3. For AMD GPUs, ensure ROCm is installed for acceleration")
        print("4. You may need to install ffmpeg: sudo apt install ffmpeg")

    # Check for AllTalk
    config = None
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except:
        pass

    if config and "alltalk" in config and "alltalk_dir" in config["alltalk"]:
        alltalk_path = config["alltalk"]["alltalk_dir"]
        if not os.path.isdir(alltalk_path):
            print(f"\nWarning: AllTalk directory not found at {alltalk_path}")
            print("The system will use gTTS as a fallback for text-to-speech.")
            print("To use AllTalk:")
            if SetupUtils.is_windows():
                print("1. Download AllTalk from https://github.com/erew123/alltalk")
                print("2. Install to the default location or update the config file")
            elif SetupUtils.is_mac():
                print("1. Download AllTalk Mac version")
                print("2. Install to ~/Applications/AllTalk or update the config file")
            else:
                print("1. Download AllTalk Linux version")
                print("2. Install to ~/alltalk_tts or update the config file")


if __name__ == "__main__":
    main()
