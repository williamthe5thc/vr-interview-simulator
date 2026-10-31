# Changelog

All notable changes to the VR Interview System will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Cross-platform setup script (setup.py) with automatic GPU detection
- Comprehensive documentation in the `docs/` directory
- Function reference documentation for key components
- CHANGELOG.md to track project changes
- LICENSE file (MIT License)

### Changed
- Updated README.md with complete system overview
- Enhanced requirements.txt with categorized dependencies
- Fixed import path for ollama_client.py (renamed from Ollama_client.py)

### Fixed
- Import path consistency in server.py

## [0.2.0] - 2024-01-XX

### Added
- Enhanced LLM response handling with extended timeout (45 seconds)
- Progressive updates during LLM processing
- Background processing for LLM responses exceeding timeout
- Improved AllTalk TTS integration with multiple fallback strategies
- Session ID synchronization between client and server
- Granular processing state reporting (PROCESSING_STT, PROCESSING_LLM, PROCESSING_TTS)
- Heartbeat mechanism for long-running operations
- Message validation for all outgoing WebSocket messages
- Transcript display with "Interviewer is thinking..." messages

### Changed
- Consolidated multiple TTS implementations into single robust service
- Simplified heartbeat implementation with enhanced features
- Improved error handling with specialized recovery strategies
- Enhanced state machine with deadlock prevention

### Fixed
- AllTalk API endpoint paths to match current implementation
- Session ID mismatch issues after reconnection
- WebSocket timeout during long LLM processing
- Audio generation timeouts with graceful degradation

### Removed
- Redundant and experimental files
- Legacy streaming implementation

## [0.1.0] - 2024-01-XX

### Added
- Initial implementation of VR Interview System
- WebSocket communication between Unity client and Python server
- Speech-to-text using Whisper models
- Text-to-speech using AllTalk with gTTS fallback
- LLM integration via Ollama
- State machine architecture for conversation management
- Basic error handling and recovery
- Audio processing pipeline
- Session management system

### Features
- Real-time conversation with AI interviewer
- VR environment with animated avatar
- Local processing without cloud dependencies
- Configurable system parameters

[Unreleased]: https://github.com/yourusername/vr-interview-system/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/yourusername/vr-interview-system/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/yourusername/vr-interview-system/releases/tag/v0.1.0
