# Troubleshooting Streaming Issues

This guide helps diagnose and resolve streaming issues with the VR Interview System's AllTalk integration.

## Streaming Flow Overview

The complete streaming process follows these steps:

1. Client sends audio to server
2. Server transcribes audio with Whisper
3. Server generates LLM response
4. Server creates streaming URL for AllTalk
5. Server sends streaming URL to client
6. Client streams audio directly from AllTalk
7. Client reports streaming status back to server

If streaming fails at any point, the system falls back to direct audio delivery.

## Common Issues and Solutions

### 1. Streaming URL Generation Fails

**Symptoms:**
- Server logs show "Failed to get streaming URL" messages
- No streaming happens, system uses fallback

**Possible Causes:**
- AllTalk server not running
- Incorrect URL in config
- Voice file not found
- Output directory permission issues

**Solutions:**
- Verify AllTalk is running (`http://127.0.0.1:7851/api/ready`)
- Check config.json for correct AllTalk URL
- Verify voice file exists in AllTalk
- Check permissions on the AllTalk outputs directory

### 2. Client Cannot Stream Audio

**Symptoms:**
- Client logs show "Streaming failed" messages
- No audio plays on client
- Server logs show timeout waiting for streaming confirmation

**Possible Causes:**
- Client cannot access AllTalk server (network/firewall)
- URL format issues
- AllTalk responses with error
- Timeout too short for large responses

**Solutions:**
- Check network connectivity between client and AllTalk server
- Verify URL format in client logs
- Increase streamingTimeout in AudioStreamer.cs
- Check AllTalk logs for errors
- Try with a shorter text response

### 3. Audio File Not Found

**Symptoms:**
- Server logs show "File not found at expected location"
- System falls back to text-only response

**Possible Causes:**
- AllTalk creates files with unexpected extensions/names
- File path mismatch
- File generation takes too long
- Permission issues on output directory

**Solutions:**
- Check the AllTalk outputs directory for the generated file
- Look for files with both .wav and .wav.wav extensions
- Increase timeout values
- Add write/read test for the outputs directory

### 4. Timing Issues

**Symptoms:**
- Streaming times out
- Audio plays after long delay
- System falls back to direct audio unnecessarily

**Possible Causes:**
- AllTalk generation takes longer than timeout values
- Client timeout too short
- Network latency between components

**Solutions:**
- Increase streamingTimeout in AudioStreamer.cs
- Modify _monitor_streaming_status timeout in stream_processor.py
- Enable DeepSpeed in AllTalk for faster generation
- Use shorter responses

## Diagnostic Steps

### Server-Side Diagnostics

1. Enable verbose logging:
   ```json
   "server": {
     "log_level": "DEBUG"
   }
   ```

2. Run server with diagnostic output:
   ```
   python server.py > server_diagnostic.log 2>&1
   ```

3. Look for these key log messages:
   - `Creating AllTalk streaming URL`
   - `Checking for file at`
   - `Streaming not confirmed for session`

4. Monitor AllTalk's processing time:
   - Look for `TTS Generate: X.XX seconds` in AllTalk logs
   - Compare with timeout settings

### Client-Side Diagnostics

1. Enable debug mode in AudioStreamer:
   ```csharp
   [SerializeField] private bool debugMode = true;
   [SerializeField] private bool verboseLogging = true;
   ```

2. Check these Unity logs:
   - `StreamAudioFromUrl called with URL`
   - `URL parameters - text: {hasText}, voice: {hasVoice}`
   - `Streaming progress:`

3. Test direct URL access:
   - Try the streaming URL directly in a browser
   - Check if audio file is being generated correctly

## Quick Fixes

### Fix 1: Update AllTalk Directory in Config

Make sure the `alltalk_dir` setting points to the correct location:

```json
"alltalk": {
  "alltalk_dir": "D:/AllTalk/alltalk_tts"  // Adjust to your installation path
}
```

### Fix 2: Increase Streaming Timeout

In `AudioStreamer.cs`, increase the timeout:

```csharp
[SerializeField] private float streamingTimeout = 60f; // Increased from 30f
```

### Fix 3: Force Default Streaming Capability

In `stream_processor.py`, you can force streaming capability:

```python
def _check_client_streaming_capability(self, session_id: str) -> bool:
    # Always use streaming by default
    default_streaming_support = True
    # Rest of the function...
```

### Fix 4: Fix File Extension Handling

In `alltalk_tts_improved.py`, add more file extension checks:

```python
# Look for files with all possible extensions
extensions = ["", ".wav", ".wav.wav"]
for ext in extensions:
    file_path = os.path.join(self.outputs_dir, f"{base_name}{ext}")
    if os.path.exists(file_path):
        # Found file
```

## Logging Commands

To enable all diagnostic logging for streaming:

1. Server-side:
   ```python
   # Add in stream_processor.py
   self.logger.info(f"==== CLIENT STREAMING CAPABILITY CHECK for {session_id} ====")
   self.logger.info(f"==== ALLTALK STREAMING CAPABILITY CHECK for {session_id} ====")
   self.logger.info(f"==== AUDIO FILE RETRIEVAL DIAGNOSTICS =====")
   ```

2. Client-side:
   ```csharp
   // Add in AudioStreamer.cs
   Debug.Log($"StreamAudioCoroutine - URL Format Check: '{url}'");
   Debug.Log($"Streaming progress: {progress:P2}");
   ```

## Contacting Support

If you're still experiencing issues after trying these solutions:

1. Collect the following logs:
   - server_diagnostic.log
   - Unity Editor Console output
   - AllTalk console output

2. Check GitHub issues for similar problems

3. For AllTalk-specific issues, consult the AllTalk TTS documentation
