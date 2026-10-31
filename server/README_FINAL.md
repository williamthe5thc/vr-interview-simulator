# 🎤 VR Interview System

> **AI-Powered Virtual Reality Interview Practice Platform**

Experience realistic job interviews in VR with an intelligent AI interviewer that provides natural conversation, contextual follow-up questions, and professional feedback.

[![Production Ready](https://img.shields.io/badge/Status-Production%20Ready-green)](#)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-blue)](https://python.org)
[![Unity 2022.3](https://img.shields.io/badge/Unity-2022.3%20LTS-black)](https://unity.com)
[![WebSocket](https://img.shields.io/badge/Protocol-WebSocket-orange)](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API)

## 🎯 Features

- **🎭 Intelligent AI Interviewer** - Professional AI that acts as hiring manager, not candidate
- **🎧 High-Quality Audio** - GPU-accelerated speech recognition and natural text-to-speech
- **🔄 Real-Time Processing** - WebSocket-based communication with live state updates
- **💬 Context-Aware Conversations** - AI remembers and builds upon previous responses
- **🛡️ Robust Error Handling** - Multiple fallback mechanisms for reliable operation
- **📊 Professional Scenarios** - Configurable interview types and difficulty levels

## 🏗️ System Architecture

![System Architecture](docs/diagrams/system_architecture.svg)

The system consists of three main components:

1. **VR Client (Oculus Quest)**: Handles the VR environment, avatar animation, and user interaction
2. **Python Server**: Manages WebSocket communication, audio processing, state management, and LLM integration  
3. **LLM Service (Ollama)**: Processes natural language via local models such as Mistral

## 🚀 Quick Start

### Prerequisites

- **Python 3.9+** with pip
- **NVIDIA GPU** with CUDA support (recommended)
- **Unity 2022.3 LTS** for VR client (separate project at `D:\VRSystemTest`)
- **Oculus Quest** or compatible VR headset

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/vr-interview-system.git
   cd vr-interview-system
   ```

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up external services**
   ```bash
   # Install and start Ollama
   ollama serve
   ollama pull mistral:7b-instruct-q4_K_M
   
   # Set up AllTalk TTS (see documentation for details)
   ```

4. **Run setup script**
   ```bash
   # Windows
   run_setup.bat
   
   # Linux/Mac  
   ./run_setup.sh
   ```

5. **Start the server**
   ```bash
   python server.py
   ```

### Deployment Scripts

- **Production Deployment**: [`deploy_production.bat`](deploy_production.bat) - Full production setup with validation
- **Quick Deployment**: [`deploy_fixes.bat`](deploy_fixes.bat) - Deploy latest fixes

## 🎮 Usage

1. **Put on VR headset** and start the Unity application (separate VRSystemTest project)
2. **Wait for connection** - You'll see "Connected" status
3. **Begin speaking** - The AI interviewer will introduce themselves
4. **Have a conversation** - Answer questions naturally
5. **Continue the interview** - AI asks follow-up questions based on your responses

### Example Interview Flow

```
AI: "Hi there! I'm Morgan Zhang from TechStart Innovations. 
     Tell me about your background and experience."

You: "I'm a software engineer with 5 years of experience..."

AI: "That's impressive! Can you tell me more about your most 
     challenging project and how you handled it?"
```

## ⚙️ Configuration  

Edit `config/config.json` to customize:

```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 8765
  },
  "ollama": {
    "model": "mistral:7b-instruct-q4_K_M",
    "scenario_type": "interview"
  },
  "alltalk": {
    "voice": "female_06.wav",
    "url": "http://127.0.0.1:7851"
  }
}
```

## 📊 Performance

**Typical Response Times** (RTX 2080 Ti):
- **Speech-to-Text**: 4-7 seconds (GPU accelerated)
- **LLM Generation**: 5-10 seconds (Mistral 7B)
- **Text-to-Speech**: 3-8 seconds (AllTalk)
- **Total End-to-End**: 12-25 seconds

**Resource Usage**:
- **GPU Memory**: ~3GB (Whisper model)
- **RAM**: 4-8GB (depending on context size)
- **Network**: WebSocket + HTTP API calls

## 📁 Project Structure

```
vr-interview-system/
├── app/                       # Core application modules
│   ├── state/                # State management system
│   ├── utils/                # Utility functions and helpers
│   └── websocket/            # WebSocket server implementation
├── services/                  # External service integrations
│   ├── audio/               # STT/TTS services
│   └── llm/                 # Language model client (Ollama)
├── config/                   # Configuration files
├── docs/                     # Comprehensive documentation
├── data/                     # Runtime data storage
├── logs/                     # System logs
├── test_scripts/             # Testing utilities
├── tools/                    # Development tools
├── server.py                 # Main server entry point
├── requirements.txt          # Python dependencies
└── README.md                 # This file
```

**Note**: The Unity VR client is a separate project located at `D:\VRSystemTest\`

## 📚 Documentation

### 📖 **Core Documentation**
- [**System Overview**](docs/system_overview.md) - High-level architecture and component interactions
- [**Architecture Overview**](docs/architecture_overview.md) - Detailed system architecture
- [**WebSocket Documentation**](docs/websocket_documentation.md) - WebSocket protocol and API
- [**State Management**](docs/state_management_documentation.md) - State machine implementation
- [**Audio Processing**](docs/audio_processing_documentation.md) - STT/TTS integration and pipeline

### 🤖 **AI & Language Models**
- [**LLM Integration**](docs/llm_integration_documentation.md) - Ollama client and prompt engineering
- [**Enhanced Stream Processor**](docs/enhanced_stream_processor_documentation.md) - Optimized audio pipeline

### 🔧 **Configuration & Setup**
- [**Configuration Management**](docs/configuration_management_documentation.md) - Config structure and options
- [**AllTalk TTS Integration Guide**](docs/AllTalk%20TTS%20API%20Integration%20Guide.md) - TTS service setup
- [**Mac Installation Guide**](docs/mac_installation_guide.md) - macOS-specific setup instructions
- [**CUDA Optimization**](docs/CUDA%20Optimization%20Documentation.md) - GPU acceleration setup

### 🛠️ **System Management**
- [**Error Handling**](docs/error_handling_documentation.md) - Error recovery and handling strategies
- [**Heartbeat System**](docs/heartbeat_system_documentation.md) - Connection keepalive mechanism
- [**Function Reference**](docs/function_reference.md) - Complete API function reference

### 🚀 **Deployment & Optimization**
- [**Code Optimization Report**](CODE_OPTIMIZATION_REPORT.md) - Performance optimization analysis
- [**Documentation Status**](DOCUMENTATION_STATUS.md) - Documentation audit and roadmap
- [**Critical Fixes Summary**](CRITICAL_FIXES_SUMMARY.md) - Major bug fixes implemented

### 📋 **Project Management**
- [**Changelog**](CHANGELOG.md) - Version history and changes
- [**Contributing Guidelines**](CONTRIBUTING.md) - How to contribute to the project

## 🐛 Troubleshooting

### Common Issues

**Server won't start:**
```bash
# Check Python environment
python --version

# Verify dependencies
pip install -r requirements.txt

# Check external services
curl http://localhost:11434/api/tags  # Ollama
curl http://localhost:7851/api/ready  # AllTalk
```

**Audio processing fails:**
- Ensure NVIDIA GPU drivers are updated
- Check CUDA installation ([CUDA Optimization Guide](docs/CUDA%20Optimization%20Documentation.md))
- Verify microphone permissions in VR

**AI gives strange responses:**
- Check `config.json` for correct `scenario_type`
- Verify Ollama model is loaded
- Review conversation logs in `logs/` directory

For more troubleshooting help, see the [`docs/troubleshooting/`](docs/troubleshooting/) directory.

## 🛡️ Error Handling

The system includes comprehensive error recovery with multiple fallback mechanisms:

- **STT Failures**: Automatic retry with fallback models
- **LLM Timeouts**: Cached responses and graceful degradation  
- **TTS Issues**: Alternative synthesis methods (AllTalk → gTTS)
- **Connection Problems**: Automatic reconnection and state recovery

See [Error Handling Documentation](docs/error_handling_documentation.md) for detailed information.

## 🧪 Testing

Run the validation script to test your setup:
```bash
python validate_fixes.py
```

Additional test scripts are available in the [`test_scripts/`](test_scripts/) directory.

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable  
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **OpenAI Whisper** for speech recognition
- **Ollama** for local LLM hosting
- **AllTalk** for high-quality text-to-speech
- **Unity Technologies** for VR framework
- **Meta** for Oculus Quest platform

## 📞 Support

- 📖 **Documentation**: Comprehensive guides in [`docs/`](docs/) folder
- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/yourusername/vr-interview-system/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/yourusername/vr-interview-system/discussions)

---

<div align="center">

**Built with ❤️ for realistic VR interview practice**

[⭐ Star this repo](#) • [🍴 Fork it](#) • [📝 Contribute](CONTRIBUTING.md)

</div>
