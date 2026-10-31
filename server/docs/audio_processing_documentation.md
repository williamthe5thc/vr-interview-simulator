# VR Interview System: Audio Processing Documentation

## Title and Overview

The Audio Processing component of the VR Interview System handles speech-to-text (STT) and text-to-speech (TTS) capabilities, enabling natural spoken interaction between users and the system. This component receives audio from clients, transcribes it to text for LLM processing, and converts LLM responses back to spoken audio. It implements fallback mechanisms to ensure robustness and includes optimizations for performance.

## Architecture

The Audio Processing system consists of two primary components:

1. **Speech-to-Text (STT)**: Transcribes user audio input to text
   - Uses OpenAI Whisper models with fallback options
   - Implemented as a wrapper to handle multiple STT implementations

2. **Text-to-Speech (TTS)**: Converts text responses to speech audio
   - Primary implementation uses AllTalk TTS with direct API
   - Includes fallback to gTTS (Google Text-to-Speech)
   - Handles audio format validation and delivery

### Component Diagram
```
┌──────────────────────────────────────────────────────┐
│                 Audio Processing System               │
└───────────────────────┬──────────────────────────────┘
            ┌───────────┴──────────┐
            │                      │
┌───────────▼──────────┐  ┌────────▼─────────┐
│    STT Component     │  │   TTS Component  │
│                      │  │                  │
│ ┌──────────────────┐ │  │ ┌──────────────┐ │
│ │  STT Wrapper     │ │  │ │ AllTalk TTS  │ │
│ │(Model Selection) │ │  │ │  Direct API  │ │
│ └────────┬─────────┘ │  │ └──────┬───────┘ │
│          │           │  │        │         │
│ ┌────────▼─────────┐ │  │ ┌──────▼───────┐ │
│ │  Whisper Model   │ │  │ │  gTTS        │ │
│ │   (Primary)      │ │  │ │  (Fallback)  │ │
│ └────────┬─────────┘ │  │ └──────────────┘ │
│          │           │  │                  │
│ ┌────────▼─────────┐ │  │                  │
│ │  Simple STT      │ │  │                  │
│ │   (Fallback)     │ │  │                  │
│ └──────────────────┘ │  │                  │
└──────────────────────┘  └──────────────────┘
```

## Key Classes/Functions

### Speech-to-Text (STT)

#### STTService Class (Wrapper)
```python
class STTService:
    """
    A wrapper for different Speech-to-Text services.
    This will try to use the OpenAI Whisper model first, then fall back to other implementations.
    """
```

#### Key Methods
- **`__init__(model_name)`**: Initializes STT with specific model size
- **`transcribe(audio_data)`**: Converts audio data to text
- **`get_model_info()`**: Retrieves information about the loaded model

### Text-to-Speech (TTS)

#### TTSService Class
```python
class TTSService:
    """
    TTS service with AllTalk direct API and gTTS fallback.
    
    Features:
    - Primary use of AllTalk direct API for high-quality speech
    - Multiple API endpoint attempts for reliable operation
    - Automatic fallback to gTTS when AllTalk is unavailable
    - Response caching to improve performance
    - Robust error handling with graceful degradation
    """
```

#### Key Methods
- **`__init__(config)`**: Initializes TTS with configuration settings
- **`_check_server()`**: Verifies AllTalk server availability
- **`is_available()`**: Checks if AllTalk service is available
- **`synthesize(text, session_id)`**: Converts text to speech audio
- **`_try_tts_generate_api(text)`**: Attempts to use the tts-generate API endpoint
- **`_try_synthesize_api(text)`**: Attempts to use the synthesize API endpoint
- **`_try_tts_api(text)`**: Attempts to use the tts API endpoint
- **`_synthesize_gtts(text)`**: Fallback synthesis using gTTS
- **`_generate_silence(duration_ms)`**: Generates silent audio as last-resort fallback

## Usage Patterns

### Speech-to-Text Flow

1. **Audio Data Reception**: The system receives audio data from the WebSocket
2. **Transcription Request**: The audio is passed to the STT service
   ```python
   transcript = await asyncio.to_thread(self.stt_service.transcribe, audio_data)
   ```
3. **Model Selection**: The STT wrapper selects an appropriate model
4. **Transcription Processing**: The audio is converted to text
5. **Result Return**: Transcribed text is returned to the caller

### Text-to-Speech Flow

1. **Text Reception**: The LLM generates a text response
2. **TTS Request**: The text is passed to the TTS service
   ```python
   audio_response = await asyncio.to_thread(self.tts_service.synthesize, response)
   ```
3. **AllTalk Attempt**: The system attempts to use AllTalk TTS
4. **Method Selection**: Multiple API endpoints are tried in sequence
5. **Fallback Processing**: If AllTalk fails, fallback to gTTS
6. **Audio Return**: Generated audio is returned to the caller

### File-Based TTS Recovery

When direct TTS API calls timeout but still succeed in the background:

1. TTS request times out from the server's perspective
2. Error handler is triggered, providing text fallback to client
3. In the background, the `_check_delayed_tts_response()` method runs
4. Checks for recently generated audio files that match the expected pattern
5. If a matching file is found, it is sent to the client as a delayed audio response
6. Otherwise, the system sticks with the text fallback

### Error Handling and Fallbacks

```
┌──────────────┐     Success     ┌─────────────┐
│ Primary STT  │────────────────►│ Return Text │
└──────┬───────┘                 └─────────────┘
       │ Failure
       ▼
┌──────────────┐     Success     ┌─────────────┐
│ Fallback STT │────────────────►│ Return Text │
└──────┬───────┘                 └─────────────┘
       │ Failure
       ▼
┌─────────────────┐
│ Return Error    │
│ Message as Text │
└─────────────────┘


┌──────────────┐     Success     ┌─────────────┐
│ AllTalk TTS  │────────────────►│Return Audio │
│ (API 1)      │                 └─────────────┘
└──────┬───────┘
       │ Failure
       ▼
┌──────────────┐     Success     ┌─────────────┐
│ AllTalk TTS  │────────────────►│Return Audio │
│ (API 2)      │                 └─────────────┘
└──────┬───────┘
       │ Failure
       ▼
┌──────────────┐     Success     ┌─────────────┐
│ AllTalk TTS  │────────────────►│Return Audio │
│ (API 3)      │                 └─────────────┘
└──────┬───────┘
       │ Failure
       ▼
┌──────────────┐     Success     ┌─────────────┐
│ gTTS Fallback│────────────────►│Return Audio │
└──────┬───────┘                 └─────────────┘
       │ Failure
       ▼
┌──────────────┐     Success     ┌─────────────┐
│ Generate     │────────────────►│Return Audio │
│ Silence      │                 └─────────────┘
└──────────────┘
```

## Implementation Details

### Speech-to-Text Implementation

The STT component is implemented as a layered wrapper to provide fallback options:

```python
def __init__(self, model_name: str = "base"):
    self.model_name = model_name
    self.logger = logging.getLogger("stt_wrapper")
    self.logger.info(f"Initializing STT wrapper with model: {model_name}")
    
    # First try to load the original STT module
    self.original_stt = None
    try:
        # Directly try to use the original STT class but with safe import
        safe_whisper_import = False
        try:
            # Try to import whisper first to see if it works
            import whisper
            if hasattr(whisper, 'load_model'):
                safe_whisper_import = True
                self.logger.info("Detected proper OpenAI Whisper installation")
        except (ImportError, TypeError, AttributeError) as e:
            self.logger.warning(f"Whisper import error: {e}")
            
        if safe_whisper_import:
            # Original STT should now work since whisper import worked
            from .stt import STTService as OriginalSTT
            self.original_stt = OriginalSTT(model_name)
            self.logger.info("Successfully loaded original STT service")
    except Exception as e:
        self.logger.warning(f"Could not load original STT: {e}")
    
    # If original fails, try the simple STT
    if self.original_stt is None:
        try:
            from .simple_stt import SimpleSTTService
            self.original_stt = SimpleSTTService(model_name)
            self.logger.info("Using SimpleSTTService as fallback")
        except Exception as e:
            self.logger.warning(f"Could not load SimpleSTTService: {e}")
    
    # Set availability based on whether we found an implementation
    self.is_available = (self.original_stt is not None)
```

### Text-to-Speech Implementation

The TTS component is implemented with multiple API endpoint attempts and fallbacks:

```python
def synthesize(self, text: str, session_id: Optional[str] = None) -> bytes:
    """
    Convert text to speech using AllTalk with gTTS fallback.
    
    Args:
        text: Text to convert to speech
        session_id: Optional session ID for tracking (not used internally)
            
    Returns:
        WAV audio data as bytes
    """
    if not text:
        self.logger.warning("Empty text provided to synthesize")
        return self._generate_silence()
    
    # Check cache first if enabled
    if self.config["cache"]["enabled"]:
        cache_key = self._create_cache_key(text)
        cached_audio = self._get_from_cache(cache_key)
        if cached_audio:
            self.logger.info(f"Using cached TTS response for text: {text[:30]}...")
            return cached_audio
    
    # Check if AllTalk is available
    # We only do this periodically to avoid slowing down when AllTalk is down
    if not hasattr(self, '_last_check_time') or time.time() - self._last_check_time > 60:
        self.alltalk_available = self._check_alltalk_server()
        self._last_check_time = time.time()
    
    # If AllTalk is available, try to use it first
    if self.alltalk_available:
        try:
            self.logger.info(f"Synthesizing with AllTalk: {len(text)} characters")
            
            # Try multiple AllTalk API methods in sequence for best reliability
            audio_data = self._try_alltalk_api_methods(text)
            
            # If successful, cache and return the audio
            if audio_data and len(audio_data) > 1000:
                if self.config["cache"]["enabled"]:
                    self._add_to_cache(self._create_cache_key(text), audio_data)
                return audio_data
            
            # If we get here, AllTalk methods failed
            self.logger.warning("All AllTalk methods failed, falling back to gTTS")
        except Exception as e:
            self.logger.error(f"Error in AllTalk synthesis: {e}")
            self.logger.warning("Falling back to gTTS after AllTalk error")
    
    # If we get here, use gTTS as fallback
    try:
        audio_data = self._synthesize_gtts(text)
        
        # Cache the result if enabled
        if audio_data and len(audio_data) > 1000 and self.config["cache"]["enabled"]:
            self._add_to_cache(self._create_cache_key(text), audio_data)
            
        return audio_data
    except Exception as e:
        self.logger.error(f"Error in gTTS synthesis: {e}")
        return self._generate_silence()
```

### AllTalk API Methods

The TTS component tries multiple AllTalk API endpoints for robustness:

```python
def _try_alltalk_api_methods(self, text: str) -> Optional[bytes]:
    """Try multiple AllTalk API methods in sequence."""
    # Try each API endpoint in the configured order
    for endpoint in self.config["alltalk"]["endpoints"]:
        method_name = f"_try_{endpoint.replace('-', '_')}_api"
        method = getattr(self, method_name, None)
        
        if method:
            try:
                self.logger.debug(f"Trying AllTalk method: {method_name}")
                audio_data = method(text)
                if audio_data and len(audio_data) > 1000:
                    self.logger.info(f"Successfully generated audio using {method_name}: {len(audio_data)} bytes")
                    return audio_data
            except Exception as e:
                self.logger.warning(f"Method {method_name} failed: {e}")
        else:
            self.logger.warning(f"Method {method_name} not implemented")
    
    # Look for recently generated files in case the API returned success but no content
    try:
        timestamp = int(time.time())
        filename_pattern = f"vr_interview_{timestamp - 5}"  # Look for files from the last 5 seconds
        audio_data = self._try_load_output_file(filename_pattern)
        if audio_data:
            self.logger.info(f"Found recently generated audio file: {len(audio_data)} bytes")
            return audio_data
    except Exception as e:
        self.logger.warning(f"Error looking for recent files: {e}")
    
    return None

def _try_tts_generate_api(self, text: str) -> Optional[bytes]:
    """Try generating speech using tts-generate API."""
    # Create a safe output filename without special characters
    timestamp = int(time.time())
    output_file = f"vr_interview_{timestamp}"
    
    try:
        # First try with form data
        response = requests.post(
            f"{self.base_url}/api/tts-generate",
            data={
                "text_input": text,
                "character_voice_gen": self.voice,
                "format": "wav",
                "output_file_name": output_file
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=self.timeout
        )
        
        # Check for success
        if response.status_code == 200:
            # Check if response has content
            if len(response.content) > 1000:
                # Save to local file for caching
                try:
                    os.makedirs("audio_out", exist_ok=True)
                    with open(f"audio_out/{output_file}.wav", "wb") as f:
                        f.write(response.content)
                except Exception as e:
                    self.logger.warning(f"Could not save audio file: {e}")
                
                return response.content
            else:
                # Try to find the file that may have been generated
                audio_data = self._try_load_output_file(output_file)
                if audio_data:
                    return audio_data

        # If form data failed, try with JSON
        response = requests.post(
            f"{self.base_url}/api/tts-generate",
            json={
                "text": text,
                "voice": self.voice,
                "output_file": f"{output_file}.wav",
                "format": "wav"
            },
            timeout=self.timeout
        )
        
        if response.status_code == 200:
            if len(response.content) > 1000:
                return response.content
            else:
                # Try to find the file that may have been generated
                audio_data = self._try_load_output_file(output_file)
                if audio_data:
                    return audio_data
    except Exception as e:
        self.logger.warning(f"Error using tts-generate API: {e}")
    
    return None
```

### Output File Recovery

When direct API responses don't return audio data but write to a file:

```python
def _try_load_output_file(self, filename_base: str) -> Optional[bytes]:
    """
    Try to find and load AllTalk output file from possible locations.
    """
    try:
        self.logger.info(f"Looking for AllTalk output file with base name: {filename_base}")
        if os.path.exists(self.outputs_dir):
            files = os.listdir(self.outputs_dir)
            
            # Look for filenames containing our base name
            matching_files = [f for f in files if filename_base in f]
            if matching_files:
                # Use the most recent matching file
                matching_files.sort(key=lambda f: os.path.getmtime(os.path.join(self.outputs_dir, f)), reverse=True)
                most_recent = matching_files[0]
                
                with open(os.path.join(self.outputs_dir, most_recent), "rb") as f:
                    data = f.read()
                    if len(data) > 1000:
                        return data
    except Exception as e:
        self.logger.warning(f"Error examining outputs directory: {e}")
    
    # Try standard locations if no match found above
    possible_paths = [
        os.path.join(self.outputs_dir, f"{filename_base}.wav"),
        os.path.join(self.outputs_dir, f"{filename_base}_gen.wav"),
        os.path.join(self.alltalk_dir, "outputs", f"{filename_base}.wav"),
        os.path.join(self.alltalk_dir, "outputs", f"{filename_base}_gen.wav"),
        f"audio_out/{filename_base}.wav",
        # Try the last generated file regardless of name
        self._find_most_recent_wav(self.outputs_dir)
    ]
    
    # Filter out None values
    possible_paths = [p for p in possible_paths if p]
    
    for path in possible_paths:
        try:
            if os.path.exists(path):
                with open(path, "rb") as f:
                    data = f.read()
                    if len(data) > 1000:
                        return data
        except Exception as e:
            self.logger.warning(f"Error reading potential file {path}: {e}")
    
    return None
```

### gTTS Fallback Implementation

When AllTalk fails, the system falls back to gTTS:

```python
def _synthesize_gtts(self, text: str) -> bytes:
    """
    Fallback synthesis using gTTS.
    """
    try:
        from gtts import gTTS
        import io
        from pydub import AudioSegment
        
        start_time = time.time()
        
        # Use gTTS to generate MP3
        tts = gTTS(text=text, lang=self.config.get('default_language', 'en'))
        mp3_fp = io.BytesIO()
        tts.write_to_fp(mp3_fp)
        mp3_fp.seek(0)
        
        # Convert MP3 to WAV
        audio = AudioSegment.from_mp3(mp3_fp)
        wav_fp = io.BytesIO()
        audio.export(wav_fp, format="wav")
        wav_fp.seek(0)
        audio_data = wav_fp.read()
        
        duration = time.time() - start_time
        self.logger.info(f"gTTS synthesis complete: {len(audio_data)} bytes in {duration:.2f}s")
        
        # Save to file for possible retrieval later
        timestamp = int(time.time())
        output_file = f"vr_interview_gtts_{timestamp}"
        
        try:
            with open(f"audio_out/{output_file}.wav", "wb") as f:
                f.write(audio_data)
        except Exception as save_error:
            self.logger.warning(f"Failed to save gTTS audio file: {save_error}")
            
        return audio_data
        
    except Exception as e:
        self.logger.error(f"Error in gTTS synthesis: {e}")
        self.logger.warning("Using silent audio as fallback")
        return self._generate_silence()
```

## Configuration

The audio processing component is configured through the main system configuration file:

### STT Configuration
```json
"audio": {
  "stt_model": "medium",  // whisper model size: "tiny", "base", "small", "medium", "large"
  "sample_rate": 16000,
  "channels": 1
}
```

### TTS Configuration
```json
"alltalk": {
  "url": "http://127.0.0.1:7851",
  "voice": "female_06.wav",
  "format": "wav",
  "retries": 3,
  "timeout": 60,
  "direct_api_timeout": 60,
  "alltalk_dir": "D:/AllTalk/alltalk_tts",
  "default_language": "en"
}
```

## Common Issues

### Speech-to-Text Issues

1. **Whisper Model Not Found**:
   - **Symptoms**: STT initialization fails, fallback to SimpleSTT
   - **Causes**: Missing Whisper model files or incorrect model path
   - **Solution**: The STT wrapper automatically falls back to SimpleSTT

2. **Transcription Timeout**:
   - **Symptoms**: Long processing times, timeout errors in logs
   - **Causes**: Large audio files, CPU limitations
   - **Solution**: Timeout handler returns error message, allows retry

3. **Low Quality Transcriptions**:
   - **Symptoms**: Incorrect or garbled transcription text
   - **Causes**: Background noise, unclear speech, low-quality audio
   - **Solution**: Use larger model size ("medium" or "large")

### Text-to-Speech Issues

1. **AllTalk Connection Failures**:
   - **Symptoms**: Warnings about AllTalk unavailability, fallback to gTTS
   - **Causes**: AllTalk server not running, incorrect URL configuration
   - **Solution**: Automatic fallback to gTTS

2. **AllTalk Output File Access**:
   - **Symptoms**: "Could not find any audio file" warnings
   - **Causes**: Incorrect output directory configuration, permission issues
   - **Solution**: The system tries multiple possible file locations

3. **TTS Timeout with Background Success**:
   - **Symptoms**: TTS request times out but audio still gets generated
   - **Causes**: AllTalk continues processing after timeout
   - **Solution**: Delayed TTS response checker tries to find and send the file

4. **Multiple API Fallbacks**:
   - **Symptoms**: "Method failed" warnings for various API endpoints
   - **Causes**: AllTalk API version differences or configuration issues
   - **Solution**: System tries multiple API endpoints in sequence

## Code Examples

### STT Transcription

```python
# In WebSocketServer.process_audio_pipeline
try:
    # Transcribe audio (CPU intensive) in a separate thread
    try:
        transcript_future = asyncio.create_task(
            asyncio.to_thread(self.stt_service.transcribe, audio_data)
        )
        
        # Add a timeout to prevent hanging
        transcript = await asyncio.wait_for(transcript_future, timeout=15.0)
    except asyncio.TimeoutError:
        # Handle STT timeout specifically
        self.logger.warning(f"STT timeout for session {session_id}")
        if self.error_handler:
            await self.error_handler.handle_error(
                ErrorHandler.STT_ERROR,
                session_id,
                Exception("Speech transcription timed out"),
                {"websocket": websocket}
            )
        return
    except Exception as stt_error:
        if self.error_handler:
            # Handle STT errors with error handler
            success, _ = await self.error_handler.handle_error(
                ErrorHandler.STT_ERROR,
                session_id,
                stt_error,
                {"websocket": websocket}
            )
            if success:
                return
        # Re-raise the error if not handled
        raise
```

### TTS Synthesis

```python
# In WebSocketServer.process_audio_pipeline
try:
    # Generate speech from text with timeout
    tts_future = None
    try:
        tts_future = asyncio.create_task(
            asyncio.to_thread(self.tts_service.synthesize, response)
        )
        
        # Add a timeout for TTS processing but let the task continue
        audio_response = await asyncio.wait_for(tts_future, timeout=15.0)
    except asyncio.TimeoutError:
        self.logger.warning(f"TTS timeout for session {session_id}")
        
        # Don't cancel the TTS future - let it continue in the background
        # Store task for potential completion later
        if session_id in self.state_manager.sessions:
            session = self.state_manager.sessions[session_id]
            if not hasattr(session, 'pending_tts_tasks'):
                session.pending_tts_tasks = []
            if tts_future and not tts_future.done():
                self.logger.info(f"Storing pending TTS task for session {session_id}")
                session.pending_tts_tasks.append(tts_future)
        
        if self.error_handler:
            await self.error_handler.handle_error(
                ErrorHandler.TTS_ERROR,
                session_id,
                Exception("Speech synthesis timed out"),
                {"websocket": websocket, "text_response": response}
            )
        
        # Don't return yet - let the server transition to WAITING state normally
        audio_response = None
    except Exception as tts_error:
        if self.error_handler:
            success, _ = await self.error_handler.handle_error(
                ErrorHandler.TTS_ERROR,
                session_id,
                tts_error,
                {"websocket": websocket, "text_response": response}
            )
            if success:
                return
        raise
```

### Delayed TTS Response Check

```python
async def _check_delayed_tts_response(self, session_id, text_response, context):
    """Check if a delayed TTS response becomes available"""
    try:
        self.logger.info(f"Starting delayed TTS response check for session {session_id}")
        
        # Wait a bit to allow TTS to finish
        await asyncio.sleep(10)
        
        # Check if session still exists
        session = self.state_manager.get_session(session_id)
        if not session:
            self.logger.warning(f"Session {session_id} no longer exists for delayed TTS")
            return
            
        # Check if websocket is still connected
        websocket = self.websocket_server.active_connections.get(session_id)
        if not websocket:
            self.logger.warning(f"Websocket for session {session_id} no longer connected")
            return
            
        # Try to find the audio file that might have been generated
        try:
            # Construct a filename pattern that matches what alltalk_tts_direct would use
            timeframe = int(time.time()) - 120  # Look for files from the last 2 minutes
            file_pattern = f"vr_interview_{timeframe}"
            
            # Ask the TTS service to look for recent files
            if hasattr(self.tts_service, '_try_load_output_file'):
                audio_data = self.tts_service._try_load_output_file(file_pattern)
                
                if audio_data and len(audio_data) > 1000:
                    self.logger.info(f"Found delayed TTS response for session {session_id}: {len(audio_data)} bytes")
                    
                    # Send the audio to the client
                    audio_message = {
                        "type": "audio_response",
                        "timestamp": time.time(),
                        "format": "wav",
                        "data": base64.b64encode(audio_data).decode('utf-8'),
                        "text": text_response  # Include text as fallback
                    }
                    await websocket.send(json.dumps(audio_message))
                    
                    self.logger.info(f"Sent delayed audio response to {session_id}")
                    return
        except Exception as e:
            self.logger.error(f"Error checking for delayed TTS files: {e}")
            
        # No audio found, or exception occurred - send text fallback
        self.logger.warning(f"No delayed TTS response found for session {session_id}, using text fallback")
        try:
            fallback_message = {
                "type": "text_response",
                "text": text_response,
                "message": "Audio generation took too long. Displaying text instead."
            }
            await websocket.send(json.dumps(fallback_message))
        except Exception as e:
            self.logger.error(f"Error sending delayed text fallback: {e}")
            
    except Exception as e:
        self.logger.error(f"Error in delayed TTS response check: {e}")
```
