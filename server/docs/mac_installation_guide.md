# VR Interview System - Mac & AMD GPU Installation Guide

This guide provides instructions for installing and configuring the VR Interview System on macOS systems, with special considerations for AMD GPUs.

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Installing the Python Server](#installing-the-python-server)
3. [Configuring GPU Acceleration](#configuring-gpu-acceleration)
4. [Installing AllTalk on Mac](#installing-alltalk-on-mac)
5. [Building the Unity Client for Mac](#building-the-unity-client-for-mac)
6. [Launching the System](#launching-the-system)
7. [Troubleshooting](#troubleshooting)

## System Requirements

### macOS Requirements

- macOS 10.13 (High Sierra) or newer
- 8GB RAM minimum, 16GB recommended
- 10GB free disk space
- AMD Radeon, Intel Integrated, or Apple Silicon GPU

### Python Server Requirements

- Python 3.8 or newer
- Ollama installed locally
- ffmpeg (for audio conversion)

### Unity Client Requirements

- Unity 2021.3 LTS or newer
- macOS build support module installed
- XR Plugin Management package (if building for VR)

## Installing the Python Server

Follow these steps to install the Python server component on macOS:

1. Clone or download the VR Interview System repository:
   ```bash
   git clone https://github.com/your-repo/vr_interview_system.git
   cd vr_interview_system
   ```

2. Run the cross-platform setup script:
   ```bash
   python3 setup.py
   ```

3. If the setup script is not available, you can manually install dependencies:
   ```bash
   pip3 install -r requirements.txt
   
   # Install platform-specific dependencies
   pip3 install torch torchvision torchaudio
   ```

4. Install Homebrew if you don't have it already:
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```

5. Install ffmpeg for audio processing:
   ```bash
   brew install ffmpeg
   ```

6. Install Ollama for local LLM processing:
   ```bash
   brew install ollama
   ```

## Configuring GPU Acceleration

### Apple Silicon (M1/M2/M3) Macs

On Apple Silicon Macs, the system will automatically use Metal Performance Shaders (MPS) for GPU acceleration. This is configured in the `config.json` file with:

```json
"audio": {
  "device": "mps"
}
```

### AMD GPUs on Intel Macs

For Intel Macs with AMD GPUs, MPS is also used but may require additional configuration:

1. Ensure you have the latest macOS updates installed

2. Check if your AMD GPU is supported by running:
   ```bash
   system_profiler SPDisplaysDataType
   ```

3. The configuration will automatically be set to use MPS:
   ```json
   "audio": {
     "device": "mps"
   }
   ```

4. If you experience issues with MPS acceleration, you can switch to CPU processing by editing the configuration file in `~/Library/Application Support/VRInterviewSystem/config/config.json`:
   ```json
   "audio": {
     "device": "cpu"
   }
   ```

## Installing AllTalk on Mac

AllTalk provides high-quality text-to-speech for the interviewer voice. Follow these steps to install it on macOS:

1. Download AllTalk for Mac (check for macOS builds or compile from source)

2. Install to `~/Applications/AllTalk` or your preferred location

3. Update the AllTalk path in the configuration:
   ```json
   "alltalk": {
     "alltalk_dir": "/Users/yourusername/Applications/AllTalk",
     "url": "http://127.0.0.1:7851"
   }
   ```

4. If AllTalk isn't available, the system will automatically fall back to Google TTS

## Building the Unity Client for Mac

To build the Unity client for macOS:

1. Open the Unity project in the Unity Editor

2. Go to VR Interview > Build Settings in the menu (this option is available after adding the BuildManager.cs script)

3. Select "macOS" as the build target

4. Check "Universal Build" to support both Intel and Apple Silicon

5. Configure XR settings if you're building for VR headsets

6. Click "Configure Build Settings" followed by "Build"

7. The build will be generated in the specified build folder

## Launching the System

To start the VR Interview System on macOS:

1. Launch Ollama and download the required model:
   ```bash
   ollama run mistral
   ```

2. Start the Python server:
   ```bash
   cd /path/to/vr_interview_system
   ./run_server.sh
   ```

3. Launch the Unity client application

4. In the Unity client, ensure the server URL is set to `ws://localhost:8765` (or your server's address)

5. Connect to the server and begin your VR interview session

## Troubleshooting

### Common Issues

1. **AllTalk connection failed**:
   - Ensure AllTalk is running on port 7851
   - Check that the path in the configuration is correct
   - The system will fall back to Google TTS automatically

2. **Audio recording issues**:
   - Grant microphone permissions to the application
   - Check system audio input settings
   - Try changing the sample rate in the client settings

3. **GPU acceleration not working**:
   - Verify your macOS version supports Metal Performance Shaders
   - Check the system log for MPS-related errors
   - Fall back to CPU processing if needed

4. **WebSocket connection issues**:
   - Ensure the server is running and listening on the correct port
   - Check for firewall restrictions
   - Verify the client is using the correct server URL

5. **Poor performance with AMD GPUs**:
   - Update to the latest macOS version for improved AMD drivers
   - Reduce graphics quality settings in the Unity client
   - Consider disabling GPU acceleration for the server component

### Getting Help

If you encounter issues not covered in this guide:

1. Check the logs in `~/Library/Application Support/VRInterviewSystem/logs/`
2. Run the server with increased logging level:
   ```bash
   VR_INTERVIEW_SERVER__LOG_LEVEL=DEBUG ./run_server.sh
   ```
3. Report issues on the project's GitHub repository with full logs and system information

## Advanced Configuration

For advanced users who need additional customization:

1. The main configuration file is located at:
   ```
   ~/Library/Application Support/VRInterviewSystem/config/config.json
   ```

2. Log files are stored in:
   ```
   ~/Library/Application Support/VRInterviewSystem/logs/
   ```

3. Audio recordings and cached TTS audio are stored in:
   ```
   ~/Library/Application Support/VRInterviewSystem/audio/
   ~/Library/Application Support/VRInterviewSystem/cache/tts/
   ```

4. You can override configuration with environment variables:
   ```bash
   VR_INTERVIEW_AUDIO__DEVICE=cpu VR_INTERVIEW_SERVER__PORT=8766 ./run_server.sh
   ```