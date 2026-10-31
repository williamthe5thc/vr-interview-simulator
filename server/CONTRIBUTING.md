# Contributing to VR Interview System

Thank you for your interest in contributing to the VR Interview System! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [How to Contribute](#how-to-contribute)
- [Development Setup](#development-setup)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Documentation](#documentation)
- [Pull Request Process](#pull-request-process)
- [Reporting Issues](#reporting-issues)

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment. We expect all contributors to:

- Be respectful and considerate in all interactions
- Welcome newcomers and help them get started
- Focus on constructive criticism and helpful feedback
- Respect differing viewpoints and experiences

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/yourusername/vr-interview-system.git
   cd vr-interview-system
   ```
3. Add the upstream repository:
   ```bash
   git remote add upstream https://github.com/originalowner/vr-interview-system.git
   ```
4. Create a new branch for your feature or fix:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## How to Contribute

### Types of Contributions

We welcome various types of contributions:

- **Bug Fixes**: Fix issues reported in GitHub Issues
- **Features**: Implement new functionality
- **Documentation**: Improve or add documentation
- **Tests**: Add or improve test coverage
- **Performance**: Optimize existing code
- **Refactoring**: Improve code structure and readability

### Areas of Focus

Current areas where contributions are particularly welcome:

1. **Unity Client Improvements**
   - VR interaction enhancements
   - Avatar animation improvements
   - Performance optimization for Quest

2. **Server Enhancements**
   - Additional LLM model support
   - Improved audio processing
   - Better error recovery mechanisms

3. **Documentation**
   - Tutorial videos or guides
   - API documentation
   - Deployment guides

4. **Testing**
   - Unit tests for components
   - Integration tests
   - Performance benchmarks

## Development Setup

### Python Server Setup

1. Install Python 3.9 or higher
2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the setup script:
   ```bash
   python setup.py
   ```

### Unity Client Setup

1. Install Unity 2022.3.7f1 or later
2. Open the project in Unity
3. Install required packages through Package Manager
4. Configure for Oculus Quest development

## Coding Standards

### Python Code Style

- Follow PEP 8 guidelines
- Use meaningful variable and function names
- Add docstrings to all functions and classes
- Keep functions focused and single-purpose
- Use type hints where appropriate

Example:
```python
async def process_audio(
    audio_data: bytes, 
    sample_rate: int = 16000
) -> str:
    """
    Process audio data and return transcribed text.
    
    Args:
        audio_data: Raw audio bytes
        sample_rate: Audio sample rate in Hz
        
    Returns:
        Transcribed text from audio
        
    Raises:
        AudioProcessingError: If audio cannot be processed
    """
    # Implementation here
```

### C# Code Style (Unity)

- Follow Unity's coding conventions
- Use PascalCase for public members
- Use camelCase for private members
- Add XML documentation comments
- Keep Update() methods lightweight

Example:
```csharp
/// <summary>
/// Handles avatar animation based on audio input
/// </summary>
public class AvatarAnimator : MonoBehaviour
{
    private AudioSource audioSource;
    
    /// <summary>
    /// Updates lip sync based on audio amplitude
    /// </summary>
    /// <param name="amplitude">Current audio amplitude (0-1)</param>
    public void UpdateLipSync(float amplitude)
    {
        // Implementation here
    }
}
```

### Commit Messages

Follow the conventional commits format:

```
type(scope): brief description

Longer explanation if needed

Fixes #123
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Code style changes
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Maintenance tasks

## Testing

### Running Tests

Python tests:
```bash
python -m pytest test_scripts/
```

Specific test categories:
```bash
python -m pytest test_scripts/test_websocket.py
python -m pytest test_scripts/test_integration.py -v
```

### Writing Tests

- Write tests for new features
- Ensure tests are isolated and repeatable
- Use descriptive test names
- Mock external dependencies

Example test:
```python
@pytest.mark.asyncio
async def test_websocket_connection():
    """Test that WebSocket server accepts connections."""
    server = WebSocketServer("localhost", 8765)
    # Test implementation
```

## Documentation

### Code Documentation

- Add docstrings to all public functions and classes
- Update relevant .md files in the `docs/` directory
- Include examples in documentation

### README Updates

When adding features, update:
- Feature list in README.md
- Configuration section if new options added
- Troubleshooting section for common issues

## Pull Request Process

1. **Before submitting**:
   - Ensure all tests pass
   - Update documentation
   - Run code formatters
   - Test on target platforms

2. **Pull Request checklist**:
   - [ ] Code follows project style guidelines
   - [ ] Tests are included and passing
   - [ ] Documentation is updated
   - [ ] Commit messages are clear
   - [ ] PR description explains the changes

3. **PR Description Template**:
   ```markdown
   ## Description
   Brief description of changes
   
   ## Type of Change
   - [ ] Bug fix
   - [ ] New feature
   - [ ] Documentation update
   - [ ] Performance improvement
   
   ## Testing
   - How has this been tested?
   - Test configuration details
   
   ## Screenshots (if applicable)
   Add screenshots for UI changes
   ```

4. **Review Process**:
   - Maintainers will review within 48 hours
   - Address feedback promptly
   - Be open to suggestions

## Reporting Issues

### Bug Reports

Use the bug report template and include:
- System information (OS, Python version, Unity version)
- Steps to reproduce
- Expected behavior
- Actual behavior
- Error messages and logs
- Screenshots if applicable

### Feature Requests

For feature requests, include:
- Use case description
- Proposed solution
- Alternative solutions considered
- Impact on existing features

## Development Tips

### Debugging

Python server:
- Enable DEBUG logging in config.json
- Check server_diagnostic.log
- Use test scripts in test_scripts/

Unity client:
- Use Unity Console for logs
- Enable verbose logging in WebSocketClient
- Test in Unity Editor before building

### Performance Considerations

- Profile before optimizing
- Consider Quest hardware limitations
- Minimize allocations in Update loops
- Use async/await properly in Python

## Questions?

If you have questions:
1. Check existing documentation
2. Search closed issues
3. Ask in an issue or discussion
4. Contact maintainers

Thank you for contributing to VR Interview System!
