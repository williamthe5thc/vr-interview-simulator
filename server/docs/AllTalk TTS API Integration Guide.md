# VR Interview System: AllTalk TTS Integration Documentation

## Overview

The VR Interview System integrates with AllTalk Text-to-Speech (TTS) to provide high-quality speech synthesis for the virtual interviewer. This document details the implementation of AllTalk integration, including the newer direct API approach, improved handling, and robust fallback mechanisms.

## AllTalk Integration Architecture

The system now implements multiple AllTalk integration methods in a hierarchical approach:

1. **Primary: AllTalk Direct API** (`alltalk_tts_direct.py`)
   - Direct API calls for faster response times
   - Improved error handling and retry mechanisms
   - File-based recovery for timeouts

2. **Secondary: AllTalk Improved** (`alltalk_tts_improved.py`)
   - Enhanced version with streaming capabilities
   - Better metadata handling and progress tracking
   - Compatible with more AllTalk server versions

3. **Fallback: Google TTS** (`gtts_only_service.py`)
   - Complete fallback when AllTalk server is unavailable
   - Lower quality but highly reliable
   - No external server dependencies

### Integration Flow Diagram

```
┌─────────────┐
│TTS Request  │
└──────┬──────┘
       │
       ▼
┌──────────────┐  Success  ┌────────────────┐
│ AllTalk      │─────────► │Return Audio    │
│ Direct API   │           └────────────────┘
└──────┬───────┘
       │ Failure
       ▼
┌──────────────┐  Success  ┌────────────────┐
│ AllTalk      │─────────► │Return Audio    │
│ Improved     │           └────────────────┘
└──────┬───────┘
       │ Failure
       ▼
┌──────────────┐  Success  ┌────────────────┐
│ gTTS         │─────────► │Return Audio    │
│ Fallback     │           └────────────────┘
└──────┬───────┘
       │ Failure
       ▼
┌──────────────┐
│Return Error  │
│Response      │
└──────────────┘
```

## Component Implementation

### 1. AllTalk Direct Service (`alltalk_tts_direct.py`)

The `AllTalkTTSDirectService` class provides optimized direct API access to AllTalk:

```python
class AllTalkTTSDirectService:
    """
    TTS service using AllTalk's direct API with improved error handling and fallbacks.
    
    Features:
    - Direct API access for faster responses
    - Multiple API endpoint attempts for reliability
    - Automatic fallback to gTTS
    - Response caching
    - Output file recovery for timeout cases
    """
    
    def __init__(self, url=None, voice=None, config=None):
        self.logger = logging.getLogger("alltalk_tts_direct")
        
        # Load configuration
        self.config = config or {}
        alltalk_config = self.config.get("alltalk", {})
        
        # Set up base parameters
        self.base_url = url or alltalk_config.get("url", "http://127.0.0.1:7851")
        self.voice = voice or alltalk_config.get("voice", "female_06.wav")
        self.timeout = alltalk_config.get("direct_api_timeout", 60)
        self.retries = alltalk_config.get("retries", 3)
        self.alltalk_dir = alltalk_config.get("alltalk_dir", "D:/AllTalk/alltalk_tts")
        self.outputs_dir = os.path.join(self.alltalk_dir, "outputs")
        
        # Set up cache if enabled
        self.cache_enabled = self.config.get("cache", {}).get("enabled", True)
        if self.cache_enabled:
            os.makedirs("audio_out", exist_ok=True)
            
        # Check if AllTalk is available
        self.alltalk_available = self._check_alltalk_server()
        if self.alltalk_available:
            self.logger.info(f"AllTalk TTS Direct service initialized with voice: {self.voice}")
        else:
            self.logger.warning("AllTalk server not available, will use gTTS fallback")
```

#### Key Methods:

1. **Server Availability Check**:
```python
def _check_alltalk_server(self):
    """Check if AllTalk server is available."""
    try:
        response = requests.get(f"{self.base_url}/api/ready", timeout=5)
        return response.status_code == 200
    except Exception as e:
        self.logger.warning(f"Error checking AllTalk server: {e}")
        return False
```

2. **Main Synthesis Method**:
```python
def synthesize(self, text: str, session_id: Optional[str] = None) -> bytes:
    """
    Convert text to speech using AllTalk with gTTS fallback.
    
    Args:
        text: Text to convert to speech
        session_id: Optional session ID for tracking
            
    Returns:
        WAV audio data as bytes
    """
    if not text:
        self.logger.warning("Empty text provided to synthesize")
        return self._generate_silence()
    
    # Check cache first if enabled
    if self.cache_enabled:
        cache_key = self._create_cache_key(text)
        cached_audio = self._get_from_cache(cache_key)
        if cached_audio:
            self.logger.info(f"Using cached TTS response for text: {text[:30]}...")
            return cached_audio
    
    # Check if AllTalk is available
    if self.alltalk_available:
        try:
            # Try multiple AllTalk API methods in sequence
            for endpoint in ["tts_generate", "synthesize", "tts"]:
                method_name = f"_try_{endpoint}_api"
                method = getattr(self, method_name, None)
                
                if method:
                    audio_data = method(text)
                    if audio_data and len(audio_data) > 1000:
                        # Cache successful result if enabled
                        if self.cache_enabled:
                            self._add_to_cache(self._create_cache_key(text), audio_data)
                        return audio_data
            
            # If no API method succeeded, try to find recently generated file
            timestamp = int(time.time())
            filename_pattern = f"vr_interview_{timestamp - 5}"
            audio_data = self._try_load_output_file(filename_pattern)
            if audio_data:
                self.logger.info(f"Found recently generated file after API failures")
                return audio_data
                
            # All AllTalk methods failed
            self.logger.warning("All AllTalk methods failed, falling back to gTTS")
            
        except Exception as e:
            self.logger.error(f"Error in AllTalk synthesis: {e}")
            self.logger.warning("Falling back to gTTS after AllTalk error")
    
    # Use gTTS as fallback
    try:
        audio_data = self._synthesize_gtts(text)
        
        # Cache the result if enabled
        if audio_data and len(audio_data) > 1000 and self.cache_enabled:
            self._add_to_cache(self._create_cache_key(text), audio_data)
            
        return audio_data
    except Exception as e:
        self.logger.error(f"Error in gTTS synthesis: {e}")
        return self._generate_silence()
```

3. **API Endpoint Attempts**:
```python
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
            # Check if response has content or just JSON
            if 'application/json' in response.headers.get('Content-Type', ''):
                # Parse JSON response
                try:
                    result = response.json()
                    if 'output_file_path' in result:
                        file_path = result['output_file_path']
                        if os.path.exists(file_path):
                            with open(file_path, 'rb') as f:
                                return f.read()
                except Exception as e:
                    self.logger.warning(f"Error parsing JSON response: {e}")
            elif len(response.content) > 1000:
                # Direct audio response
                return response.content
                
        # If first attempt failed, try with JSON payload
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
                
    except Exception as e:
        self.logger.warning(f"Error using tts-generate API: {e}")
    
    return None
```

4. **Output File Recovery**:
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

### 2. AllTalk Improved Service (`alltalk_tts_improved.py`)

The `AllTalkTTSImprovedService` class adds streaming capabilities and enhanced error handling:

```python
class AllTalkTTSImprovedService:
    """
    Improved TTS service using AllTalk with streaming capabilities and enhanced error handling.
    
    Features:
    - Support for both XTTS and Piper models
    - Streaming audio for faster perceived response times
    - Progressive audio chunk delivery
    - Better error handling and retry mechanisms
    """
    
    def __init__(self, url=None, voice=None, config=None):
        self.logger = logging.getLogger("alltalk_tts_improved")
        
        # Load configuration
        self.config = config or {}
        alltalk_config = self.config.get("alltalk", {})
        
        # Set up base parameters
        self.base_url = url or alltalk_config.get("url", "http://127.0.0.1:7851")
        self.voice = voice or alltalk_config.get("voice", "female_06.wav")
        self.timeout = alltalk_config.get("timeout", 60)
        self.retries = alltalk_config.get("retries", 3)
        self.stream_mode = alltalk_config.get("stream_mode", True)
        
        # Chunk configuration for streaming
        self.chunk_size = alltalk_config.get("chunk_size", 4096)
        self.chunk_delay = alltalk_config.get("chunk_delay", 0.05)
        
        # Set up cache if enabled
        self.cache_enabled = self.config.get("cache", {}).get("enabled", True)
        if self.cache_enabled:
            os.makedirs("audio_out", exist_ok=True)
            
        # Check voice type (XTTS or Piper)
        if self.voice.endswith(".wav"):
            self.voice_type = "xtts"
        elif self.voice.endswith(".onnx"):
            self.voice_type = "piper"
        else:
            self.voice_type = "unknown"
            
        # Check if AllTalk is available
        self.alltalk_available = self._check_alltalk_server()
        if self.alltalk_available:
            self.logger.info(f"AllTalk TTS Improved service initialized with voice: {self.voice}")
            self.logger.info(f"Voice type detected: {self.voice_type}")
            self.logger.info(f"Streaming mode: {self.stream_mode}")
        else:
            self.logger.warning("AllTalk server not available, will use gTTS fallback")
```

#### Key Methods:

1. **Streaming Synthesis**:
```python
async def synthesize_streaming(self, text: str, chunk_callback: Callable[[bytes], Awaitable[None]]) -> bool:
    """
    Stream audio synthesis with chunks delivered progressively.
    
    Args:
        text: Text to convert to speech
        chunk_callback: Async callback function that receives audio chunks
        
    Returns:
        bool: Success status
    """
    if not self.alltalk_available or not self.stream_mode:
        self.logger.warning("Streaming not available, falling back to standard synthesis")
        audio_data = await asyncio.to_thread(self.synthesize, text)
        if audio_data:
            # Split the complete audio into chunks for streaming simulation
            chunks = [audio_data[i:i + self.chunk_size] for i in range(0, len(audio_data), self.chunk_size)]
            for chunk in chunks:
                await chunk_callback(chunk)
                await asyncio.sleep(self.chunk_delay)
            return True
        return False
    
    # Try streaming synthesis
    try:
        # Determine which API endpoint to use based on server version
        server_info = await self._get_server_info()
        if server_info.get("has_streaming", False):
            return await self._stream_synthesis_v2(text, chunk_callback)
        else:
            return await self._stream_synthesis_v1(text, chunk_callback)
    except Exception as e:
        self.logger.error(f"Error in streaming synthesis: {e}")
        # Fall back to standard synthesis
        audio_data = await asyncio.to_thread(self.synthesize, text)
        if audio_data:
            # Split the complete audio into chunks
            chunks = [audio_data[i:i + self.chunk_size] for i in range(0, len(audio_data), self.chunk_size)]
            for chunk in chunks:
                await chunk_callback(chunk)
                await asyncio.sleep(self.chunk_delay)
            return True
        return False
```

2. **Enhanced Server Information**:
```python
async def _get_server_info(self) -> Dict[str, Any]:
    """Get detailed server information to determine capabilities."""
    try:
        # Try modern API endpoint first
        response = await asyncio.to_thread(
            requests.get,
            f"{self.base_url}/api/server_info",
            timeout=5
        )
        
        if response.status_code == 200:
            info = response.json()
            return {
                "version": info.get("version", "unknown"),
                "has_streaming": info.get("features", {}).get("streaming", False),
                "supported_voices": info.get("voices", []),
                "current_engine": info.get("current_engine", "unknown")
            }
            
        # Try alternative endpoints for older servers
        # Check version endpoint
        response = await asyncio.to_thread(
            requests.get,
            f"{self.base_url}/api/version",
            timeout=5
        )
        
        if response.status_code == 200:
            version = response.json().get("version", "unknown")
            # Parse version to determine streaming support
            has_streaming = False
            if version and isinstance(version, str):
                # Versions >= 1.5.0 typically support streaming
                parts = version.split('.')
                if len(parts) >= 2:
                    try:
                        major, minor = int(parts[0]), int(parts[1])
                        if major > 1 or (major == 1 and minor >= 5):
                            has_streaming = True
                    except ValueError:
                        pass
                        
            return {
                "version": version,
                "has_streaming": has_streaming,
                "supported_voices": [],
                "current_engine": "unknown"
            }
    except Exception as e:
        self.logger.warning(f"Error getting server info: {e}")
        
    # Default response for legacy or unreachable servers
    return {
        "version": "unknown",
        "has_streaming": False,
        "supported_voices": [],
        "current_engine": "unknown"
    }
```

### 3. gTTS Fallback Service (`gtts_only_service.py`)

The `GTTSOnlyService` provides a reliable fallback when AllTalk is unavailable:

```python
class GTTSOnlyService:
    """
    TTS service using Google Text-to-Speech (gTTS).
    
    This service is used as a fallback when AllTalk is unavailable.
    It provides lower quality but highly reliable synthesis.
    """
    
    def __init__(self, language='en', config=None):
        self.logger = logging.getLogger("gtts_service")
        
        # Set up parameters
        self.language = language
        self.config = config or {}
        
        # Set up cache if enabled
        self.cache_enabled = self.config.get("cache", {}).get("enabled", True)
        if self.cache_enabled:
            os.makedirs("audio_out", exist_ok=True)
            
        self.logger.info(f"gTTS service initialized with language: {language}")
        
    def synthesize(self, text: str, session_id: Optional[str] = None) -> bytes:
        """
        Convert text to speech using gTTS.
        
        Args:
            text: Text to convert to speech
            session_id: Optional session ID (unused, for API compatibility)
            
        Returns:
            WAV audio data as bytes
        """
        if not text:
            self.logger.warning("Empty text provided to synthesize")
            return self._generate_silence()
        
        # Check cache first if enabled
        if self.cache_enabled:
            cache_key = self._create_cache_key(text)
            cached_audio = self._get_from_cache(cache_key)
            if cached_audio:
                self.logger.info(f"Using cached gTTS response")
                return cached_audio
                
        try:
            from gtts import gTTS
            import io
            from pydub import AudioSegment
            
            start_time = time.time()
            
            # Use gTTS to generate MP3
            tts = gTTS(text=text, lang=self.language)
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
            
            # Save to cache if enabled
            if self.cache_enabled:
                self._add_to_cache(self._create_cache_key(text), audio_data)
                
            return audio_data
            
        except Exception as e:
            self.logger.error(f"Error in gTTS synthesis: {e}")
            self.logger.warning("Using silent audio as fallback")
            return self._generate_silence()
```

## Enhanced TTS Service Integration (`enhanced_tts.py`)

The `EnhancedTTSService` acts as the primary interface for speech synthesis, managing the different TTS providers:

```python
class EnhancedTTSService:
    """
    Enhanced TTS Service that manages multiple TTS providers.
    
    Features:
    - Provider management and fallback chain
    - Caching with intelligent invalidation
    - Voice selection based on content and context
    - Analytics for synthesis performance
    """
    
    def __init__(self, config=None):
        self.logger = logging.getLogger("enhanced_tts")
        self.config = config or {}
        
        # Initialize providers based on configuration
        tts_config = self.config.get("tts", {})
        alltalk_config = self.config.get("alltalk", {})
        
        # Determine primary provider
        primary_engine = tts_config.get("primary_engine", "alltalk")
        
        # Initialize providers
        self.providers = {}
        
        # AllTalk Direct (primary if available)
        if primary_engine == "alltalk":
            try:
                from services.audio.alltalk_tts_direct import AllTalkTTSDirectService
                alltalk_direct = AllTalkTTSDirectService(config=self.config)
                if alltalk_direct.is_available():
                    self.providers["alltalk_direct"] = alltalk_direct
                    self.logger.info("Initialized AllTalk Direct as primary provider")
            except Exception as e:
                self.logger.warning(f"Failed to initialize AllTalk Direct: {e}")
                
        # AllTalk Improved (alternative streaming provider)
        try:
            if alltalk_config.get("use_streaming", False):
                from services.audio.alltalk_tts_improved import AllTalkTTSImprovedService
                alltalk_improved = AllTalkTTSImprovedService(config=self.config)
                if alltalk_improved.alltalk_available:
                    self.providers["alltalk_improved"] = alltalk_improved
                    self.logger.info("Initialized AllTalk Improved with streaming support")
        except Exception as e:
            self.logger.warning(f"Failed to initialize AllTalk Improved: {e}")
                
        # gTTS (fallback provider)
        try:
            from services.audio.gtts_only_service import GTTSOnlyService
            self.providers["gtts"] = GTTSOnlyService(config=self.config)
            self.logger.info("Initialized gTTS as fallback provider")
        except Exception as e:
            self.logger.warning(f"Failed to initialize gTTS: {e}")
            
        # Initialize TTS Provider-specific engines
        self._init_voice_providers()
        
        # Set up cache
        self.cache_enabled = tts_config.get("cache_enabled", True)
        if self.cache_enabled:
            os.makedirs("audio_out", exist_ok=True)
            self.logger.info("TTS caching enabled")
            
        # Performance analytics
        self.synthesis_times = {}
        
        # Check if we have any providers
        if not self.providers:
            self.logger.error("No TTS providers available!")
        else:
            self.logger.info(f"TTS initialized with {len(self.providers)} providers")
```

### Key Methods:

1. **Provider Selection and Fallback**:
```python
def synthesize(self, text: str, session_id: Optional[str] = None, 
               voice_profile: Optional[str] = None) -> bytes:
    """
    Synthesize speech using the best available provider.
    
    Args:
        text: Text to synthesize
        session_id: Optional session ID for analytics
        voice_profile: Optional voice profile to use
        
    Returns:
        WAV audio data
    """
    if not text:
        self.logger.warning("Empty text provided to synthesize")
        return self._generate_silence()
    
    # Check cache first if enabled
    if self.cache_enabled:
        cache_key = self._create_cache_key(text, voice_profile)
        cached_audio = self._get_from_cache(cache_key)
        if cached_audio:
            self.logger.info(f"Using cached TTS response for: {text[:30]}...")
            return cached_audio
    
    # Select voice profile if needed
    if not voice_profile:
        voice_profile = self._select_voice_profile(text)
    
    # Try providers in order based on availability and capabilities
    start_time = time.time()
    
    # Try AllTalk Direct first if available
    if "alltalk_direct" in self.providers:
        try:
            audio_data = self.providers["alltalk_direct"].synthesize(text, session_id)
            if audio_data and len(audio_data) > 1000:
                duration = time.time() - start_time
                self._log_synthesis_performance("alltalk_direct", len(text), duration)
                
                # Cache result if enabled
                if self.cache_enabled:
                    self._add_to_cache(self._create_cache_key(text, voice_profile), audio_data)
                    
                return audio_data
        except Exception as e:
            self.logger.warning(f"AllTalk Direct synthesis failed: {e}")
    
    # Try AllTalk Improved next
    if "alltalk_improved" in self.providers:
        try:
            audio_data = self.providers["alltalk_improved"].synthesize(text, session_id)
            if audio_data and len(audio_data) > 1000:
                duration = time.time() - start_time
                self._log_synthesis_performance("alltalk_improved", len(text), duration)
                
                # Cache result if enabled
                if self.cache_enabled:
                    self._add_to_cache(self._create_cache_key(text, voice_profile), audio_data)
                    
                return audio_data
        except Exception as e:
            self.logger.warning(f"AllTalk Improved synthesis failed: {e}")
    
    # Fall back to gTTS
    if "gtts" in self.providers:
        try:
            audio_data = self.providers["gtts"].synthesize(text, session_id)
            if audio_data and len(audio_data) > 1000:
                duration = time.time() - start_time
                self._log_synthesis_performance("gtts", len(text), duration)
                
                # Cache result if enabled
                if self.cache_enabled:
                    self._add_to_cache(self._create_cache_key(text, voice_profile), audio_data)
                    
                return audio_data
        except Exception as e:
            self.logger.warning(f"gTTS synthesis failed: {e}")
    
    # If all providers failed, generate silence as last resort
    self.logger.error("All TTS providers failed, generating silence")
    return self._generate_silence()
```

2. **Voice Selection Based on Content**:
```python
def _select_voice_profile(self, text: str) -> str:
    """
    Select appropriate voice profile based on text content.
    
    Args:
        text: Text to analyze for voice selection
        
    Returns:
        Voice profile name
    """
    # Default voice profile
    default_profile = "default"
    
    # Check if voice selection is enabled
    if not self.config.get("tts", {}).get("dynamic_voice_selection", False):
        return default_profile
        
    # Simple text analysis for demonstration
    text_lower = text.lower()
    
    # Detect question vs statement
    is_question = "?" in text
    
    # Detect emotional content
    has_positive = any(word in text_lower for word in [
        "great", "excellent", "good", "impressive", "happy"
    ])
    has_negative = any(word in text_lower for word in [
        "concerned", "issue", "problem", "difficult", "challenge"
    ])
    
    # Select profile based on content
    if is_question:
        if has_positive:
            return "encouraging"
        elif has_negative:
            return "concerned"
        else:
            return "curious"
    else:
        if has_positive:
            return "positive"
        elif has_negative:
            return "serious"
        else:
            return default_profile
```

3. **Streaming Synthesis Support**:
```python
async def synthesize_streaming(self, text: str, chunk_callback: Callable[[bytes], Awaitable[None]],
                              session_id: Optional[str] = None) -> bool:
    """
    Stream synthesis with progressive audio chunks.
    
    Args:
        text: Text to synthesize
        chunk_callback: Async function to call with each audio chunk
        session_id: Optional session ID for analytics
        
    Returns:
        bool: Success status
    """
    # Try streaming with AllTalk Improved first
    if "alltalk_improved" in self.providers:
        provider = self.providers["alltalk_improved"]
        if hasattr(provider, "synthesize_streaming"):
            try:
                success = await provider.synthesize_streaming(text, chunk_callback)
                if success:
                    return True
            except Exception as e:
                self.logger.warning(f"Streaming synthesis failed: {e}")
    
    # Fall back to chunking standard synthesis
    try:
        # Generate full audio
        full_audio = await asyncio.to_thread(self.synthesize, text, session_id)
        
        # Split into chunks
        chunk_size = 4096  # Default chunk size
        chunks = [full_audio[i:i + chunk_size] for i in range(0, len(full_audio), chunk_size)]
        
        # Send chunks with small delays to simulate streaming
        for chunk in chunks:
            await chunk_callback(chunk)
            await asyncio.sleep(0.05)
            
        return True
    except Exception as e:
        self.logger.error(f"Error in fallback streaming synthesis: {e}")
        return False
```

## Implementation in WebSocket Server

The WebSocket Server uses the TTS service for audio responses:

```python
# In WebSocketServer.process_audio_pipeline
try:
    # Generate speech from text with timeout
    tts_future = None
    try:
        tts_future = asyncio.create_task(
            asyncio.to_thread(self.tts_service.synthesize, response)
        )
        
        # Add a timeout for TTS processing
        audio_response = await asyncio.wait_for(tts_future, timeout=15.0)
    except asyncio.TimeoutError:
        self.logger.warning(f"TTS timeout for session {session_id}")
        
        # Don't cancel the TTS future - let it continue in the background
        if session_id in self.state_manager.sessions:
            session = self.state_manager.sessions[session_id]
            if not hasattr(session, 'pending_tts_tasks'):
                session.pending_tts_tasks = []
            if tts_future and not tts_future.done():
                session.pending_tts_tasks.append(tts_future)
        
        # Handle TTS timeout with error handler
        if self.error_handler:
            await self.error_handler.handle_error(
                ErrorHandler.TTS_ERROR,
                session_id,
                Exception("Speech synthesis timed out"),
                {"websocket": websocket, "text_response": response}
            )
        
        # Don't return yet - use fallback
        audio_response = None
```

## Delayed Response Handling

The system can handle delayed TTS responses through a specialized handler:

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
```

## Configuration

Configure AllTalk integration in `config/config.json`:

```json
{
  "alltalk": {
    "url": "http://127.0.0.1:7851",
    "voice": "female_06.wav",
    "format": "wav",
    "retries": 3,
    "timeout": 60,
    "direct_api_timeout": 60,
    "alltalk_dir": "D:/AllTalk/alltalk_tts",
    "default_language": "en",
    "use_streaming": true,
    "endpoints": ["tts_generate", "synthesize", "tts"]
  },
  "tts": {
    "primary_engine": "alltalk",
    "fallback": "gtts",
    "cache_enabled": true,
    "dynamic_voice_selection": true
  }
}
```

## Common Issues and Solutions

### 1. AllTalk Server Connection Issues

**Symptoms**:
- "AllTalk server not available" warnings
- Falling back to gTTS
- Slow response times

**Solutions**:
- Verify AllTalk is running and accessible
- Check URL configuration
- Increase connection timeout
- Ensure proper network access

**Example Fix**:
```python
# Increase connection timeout and retries
config["alltalk"]["timeout"] = 10
config["alltalk"]["retries"] = 5

# Try alternative URL if using Docker
config["alltalk"]["url"] = "http://alltalk:7851"  # Docker container
```

### 2. API Endpoint Compatibility

**Symptoms**:
- "Method failed" warnings for specific endpoints
- Inconsistent behavior across AllTalk versions

**Solutions**:
- Try different API endpoints based on server version
- Update endpoint order in configuration
- Check compatibility with server version

**Example Fix**:
```python
# Modify endpoint order based on server version
if server_version < "1.5.0":
    config["alltalk"]["endpoints"] = ["tts", "tts_generate", "synthesize"]
else:
    config["alltalk"]["endpoints"] = ["tts_generate", "synthesize", "tts"]
```

### 3. File Output Issues

**Symptoms**:
- "Output file not found" errors
- Missing audio responses despite successful API calls

**Solutions**:
- Verify output directory configuration
- Check permissions for file access
- Use direct audio responses instead of file-based
- Implement file search fallback

**Example Fix**:
```python
# Update outputs directory with absolute path
config["alltalk"]["alltalk_dir"] = "D:/AllTalk/alltalk_tts"
config["alltalk"]["outputs_dir"] = "D:/AllTalk/alltalk_tts/outputs"

# Enable file search fallback
config["alltalk"]["enable_file_fallback"] = True
```

### 4. Streaming Issues

**Symptoms**:
- "Streaming not available" warnings
- Fallback to standard synthesis
- Choppy audio playback

**Solutions**:
- Verify server supports streaming
- Adjust chunk size and delay
- Fall back to standard synthesis when needed

**Example Fix**:
```python
# Optimize streaming parameters
config["alltalk"]["stream_mode"] = True
config["alltalk"]["chunk_size"] = 8192  # Larger chunks
config["alltalk"]["chunk_delay"] = 0.02  # Shorter delay
```

## Best Practices

1. **Multiple Fallback Paths**
   - Always implement multiple TTS providers
   - Test fallback chains regularly
   - Use caching to reduce repeated failures

2. **Robust Error Handling**
   - Implement timeouts for all API calls
   - Use retry mechanisms with exponential backoff
   - Provide text fallbacks for all audio responses

3. **Effective Caching**
   - Cache common responses to reduce latency
   - Implement cache invalidation strategies
   - Use content-based cache keys for better hits

4. **Voice Selection**
   - Match voice profiles to content
   - Consider emotion and context in selection
   - Provide consistent voice experiences

5. **Distributed Load**
   - Consider multiple AllTalk instances for high load
   - Implement load balancing across providers
   - Monitor performance metrics for optimization

## Conclusion

The VR Interview System provides comprehensive AllTalk TTS integration with sophisticated fallback mechanisms, error handling, and performance optimizations. By leveraging both the direct API and improved streaming capabilities, the system delivers high-quality speech synthesis with robust error recovery and degradation paths.