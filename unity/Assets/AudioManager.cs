using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using System.Threading.Tasks;
using UnityEngine.Networking;

public class AudioManager : MonoBehaviour
{
    [Header("Components")]
    [SerializeField] private WebSocketManager webSocketManager;
    [SerializeField] private AvatarController avatarController;
    
    [Header("Recording Settings")]
    [SerializeField] private int sampleRate = 16000;
    [SerializeField] private int recordingBufferLength = 60;
    [SerializeField] private float voiceDetectionThreshold = 0.02f;
    [SerializeField] private float silenceTimeoutSec = 1.5f;
    
    [Header("Playback Settings")]
    [SerializeField] private AudioSource audioSource;
    [SerializeField] private float streamingVolume = 1.0f;
    [SerializeField] private bool preferStreaming = true;
    
    // Recording state
    private AudioClip recordingClip;
    private string selectedMicrophone;
    private bool isRecording = false;
    private float silenceTimer = 0f;
    private int lastSamplePosition = 0;
    private bool isProcessingAudio = false;
    
    // Events
    public event Action OnRecordingStarted;
    public event Action OnRecordingStopped;
    public event Action<float> OnAudioLevelChanged;
    public event Action OnPlaybackStarted;
    public event Action OnPlaybackCompleted;
    public event Action<string> OnPlaybackError;
    
    /// <summary>Raised after a recording was processed: seconds, peak level (0 = silence), and whether it was sent.</summary>
    public event Action<float, float, bool> OnRecordingProcessed;
    
    /// <summary>When false, the server entering LISTENING no longer starts a recording (push-to-talk owns recording).</summary>
    public bool ServerDrivenRecording = true;
    public float LastPeak { get; private set; }
    public float LastRecordedSeconds { get; private set; }
    
    private bool autoStopOnSilence = true;
    private float recordStartTime;
    
    public bool IsRecording => isRecording;
    public bool IsPlaying => audioSource != null && audioSource.isPlaying;
    
    private void Start()
    {
        // Initialize microphone
        InitializeMicrophone();
        
        // Initialize audio source if not set
        if (audioSource == null)
        {
            audioSource = gameObject.AddComponent<AudioSource>();
            audioSource.spatialBlend = 1.0f; // 3D audio
            audioSource.volume = 1.0f;
        }

        // Lip sync and talking-state detection must read the same source the server audio plays on
        if (avatarController != null)
        {
            avatarController.SetAudioSource(audioSource);
        }

        // Replies are played by WebSocketManager calling PlayAudioResponse(data, more) directly. Subscribing to its
        // OnAudioResponse event as well played every chunk a second time.
    }
    
    private void InitializeMicrophone()
    {
        // Check for available microphones
        if (Microphone.devices.Length == 0)
        {
            Debug.LogError("No microphone found");
            return;
        }
        
        // Use first microphone by default
        selectedMicrophone = Microphone.devices[0];
        Debug.Log($"Using microphone: {selectedMicrophone}");
    }
    
    /// <summary>Server-driven or button recording: stops by itself after a stretch of silence.</summary>
    public void StartRecording() => BeginRecording(true);

    /// <summary>Hold-to-talk recording: runs until StopRecording(), never auto-stops on silence.</summary>
    public void StartPushToTalk() => BeginRecording(false);

    private void BeginRecording(bool autoStop)
    {
        if (isRecording) return;
        
        autoStopOnSilence = autoStop;
        recordStartTime = Time.realtimeSinceStartup;
        
        // Start microphone recording
        recordingClip = Microphone.Start(selectedMicrophone, true, recordingBufferLength, sampleRate);
        isRecording = true;
        lastSamplePosition = 0;
        silenceTimer = 0f;
        
        Debug.Log($"Started recording audio (device '{selectedMicrophone}', {sampleRate} Hz, autoStop={autoStop})");
        
        // Notify listeners
        OnRecordingStarted?.Invoke();
    }
    
    public void StopRecording()
    {
        if (!isRecording) return;
        
        // The position must be read BEFORE Microphone.End: afterwards GetPosition returns 0 and nothing would be sent.
        float elapsed = Time.realtimeSinceStartup - recordStartTime;
        int endPosition = Microphone.GetPosition(selectedMicrophone);
        bool wrapped = recordingClip != null && elapsed >= recordingBufferLength - 0.5f;
        if (endPosition <= 0 && elapsed > 0.2f)
        {
            // some devices report 0 until the mic has warmed up; fall back to elapsed time
            endPosition = Mathf.Min((int)(elapsed * sampleRate), recordingClip != null ? recordingClip.samples : 0);
        }
        int sampleCount = wrapped ? recordingClip.samples : endPosition;
        
        // Stop microphone
        Microphone.End(selectedMicrophone);
        isRecording = false;
        
        // Process the recorded audio
        StartCoroutine(ProcessRecordedAudio(sampleCount));
        
        Debug.Log($"Stopped recording audio ({elapsed:F1}s, {sampleCount} samples)");
        
        // Notify listeners
        OnRecordingStopped?.Invoke();
    }
    
    /// <summary>Stop recording and throw the audio away (nothing is sent to the server).</summary>
    public void CancelRecording()
    {
        if (!isRecording) return;
        Microphone.End(selectedMicrophone);
        isRecording = false;
        Debug.Log("Recording cancelled");
        OnRecordingStopped?.Invoke();
    }
    
    private IEnumerator ProcessRecordedAudio(int sampleCount)
    {
        if (isProcessingAudio) yield break;
        
        isProcessingAudio = true;
        
        // Wait one frame to ensure microphone data is available
        yield return null;
        
        if (sampleCount <= 0 || recordingClip == null)
        {
            Debug.LogWarning("No audio data recorded");
            LastRecordedSeconds = 0f;
            LastPeak = 0f;
            OnRecordingProcessed?.Invoke(0f, 0f, false);
            isProcessingAudio = false;
            yield break;
        }
        
        // Get audio data
        float[] samples = new float[recordingClip.samples];
        recordingClip.GetData(samples, 0);
        
        // Create a new clip with just the recorded portion
        AudioClip processedClip = AudioClip.Create(
            "ProcessedRecording",
            sampleCount,
            1, // Mono
            sampleRate,
            false
        );
        
        // Copy only the recorded samples
        float[] processedSamples = new float[sampleCount];
        Array.Copy(samples, processedSamples, sampleCount);
        processedClip.SetData(processedSamples, 0);
        
        // Report what the microphone actually captured: a peak of exactly 0 means the mic delivered silence.
        float peak = 0f;
        for (int i = 0; i < processedSamples.Length; i++)
        {
            float a = Mathf.Abs(processedSamples[i]);
            if (a > peak) peak = a;
        }
        LastRecordedSeconds = sampleCount / (float)sampleRate;
        LastPeak = peak;
        Debug.Log($"Recorded {LastRecordedSeconds:F2}s, peak level {peak:F4}" + (peak < 0.0005f ? "  <-- MICROPHONE CAPTURED SILENCE" : ""));
        bool tooShort = LastRecordedSeconds < 0.4f;
        OnRecordingProcessed?.Invoke(LastRecordedSeconds, peak, !tooShort);
        if (tooShort)
        {
            Debug.LogWarning("Recording too short, not sent");
            isProcessingAudio = false;
            yield break;
        }
        
        // Convert to WAV format for server
        byte[] wavData = ConvertAudioClipToWav(processedClip);
        
        // Send to server via WebSocket
        if (webSocketManager != null)
        {
            try {
                // Changed from await to direct call since we're in a coroutine
                webSocketManager.SendAudioData(wavData);
            }
            catch (Exception e) {
                Debug.LogError($"Failed to send audio data: {e.Message}");
            }
        }
        
        isProcessingAudio = false;
    }
    
    private void Update()
    {
        if (!isRecording) return;
        
        // Get current microphone position
        int currentPosition = Microphone.GetPosition(selectedMicrophone);
        
        // Check if new audio data is available
        if (currentPosition != lastSamplePosition && recordingClip != null)
        {
            // Get samples from last position to current
            float[] samples = GetMicrophoneData(lastSamplePosition, currentPosition);
            
            // Calculate audio level for UI feedback
            float audioLevel = CalculateAudioLevel(samples);
            OnAudioLevelChanged?.Invoke(audioLevel);
            
            // Check for silence
            if (autoStopOnSilence && audioLevel < voiceDetectionThreshold)
            {
                silenceTimer += Time.deltaTime;
                
                // If silence lasts too long, stop recording
                if (silenceTimer > silenceTimeoutSec)
                {
                    StopRecording();
                    return;
                }
            }
            else
            {
                silenceTimer = 0f;
            }
            
            // Update last position
            lastSamplePosition = currentPosition;
        }
    }
    
    private float[] GetMicrophoneData(int fromPosition, int toPosition)
    {
        int sampleCount;
        
        // Handle wrap-around in the circular buffer
        if (toPosition < fromPosition)
        {
            sampleCount = (recordingClip.samples - fromPosition) + toPosition;
        }
        else
        {
            sampleCount = toPosition - fromPosition;
        }
        
        float[] samples = new float[sampleCount];
        float[] tempSamples = new float[recordingClip.samples];
        
        // Get all clip data
        recordingClip.GetData(tempSamples, 0);
        
        // Handle wrap-around when copying data
        if (toPosition < fromPosition)
        {
            // Copy from fromPosition to end of clip
            int firstPartSamples = recordingClip.samples - fromPosition;
            Array.Copy(tempSamples, fromPosition, samples, 0, firstPartSamples);
            
            // Copy from start of clip to toPosition
            Array.Copy(tempSamples, 0, samples, firstPartSamples, toPosition);
        }
        else
        {
            // Simple case, no wrap-around
            Array.Copy(tempSamples, fromPosition, samples, 0, sampleCount);
        }
        
        return samples;
    }
    
    private float CalculateAudioLevel(float[] samples)
    {
        float sum = 0f;
        
        // Calculate RMS (Root Mean Square) of the audio samples
        for (int i = 0; i < samples.Length; i++)
        {
            sum += samples[i] * samples[i];
        }
        
        return Mathf.Sqrt(sum / samples.Length);
    }
    
    private byte[] ConvertAudioClipToWav(AudioClip clip)
    {
        // Get data from AudioClip
        float[] samples = new float[clip.samples];
        clip.GetData(samples, 0);
        
        // Convert to 16-bit PCM
        Int16[] intData = new Int16[samples.Length];
        for (int i = 0; i < samples.Length; i++)
        {
            intData[i] = (short)(samples[i] * 32767);
        }
        
        using (MemoryStream stream = new MemoryStream())
        {
            using (BinaryWriter writer = new BinaryWriter(stream))
            {
                // WAV header
                writer.Write(System.Text.Encoding.ASCII.GetBytes("RIFF"));
                writer.Write(36 + intData.Length * 2);
                writer.Write(System.Text.Encoding.ASCII.GetBytes("WAVE"));
                writer.Write(System.Text.Encoding.ASCII.GetBytes("fmt "));
                writer.Write(16);
                writer.Write((short)1); // PCM format
                writer.Write((short)1); // Mono
                writer.Write(clip.frequency);
                writer.Write(clip.frequency * 2); // Byte rate
                writer.Write((short)2); // Block align
                writer.Write((short)16); // Bits per sample
                writer.Write(System.Text.Encoding.ASCII.GetBytes("data"));
                writer.Write(intData.Length * 2);
                
                // Write sample data
                foreach (short sample in intData)
                {
                    writer.Write(sample);
                }
            }
            
            return stream.ToArray();
        }
    }
    
    private void HandleAudioResponse(byte[] audioData)
    {
        StartCoroutine(PlayAudioResponseCoroutine(audioData));
    }
    
    public void PlayAudioResponse(byte[] audioData)
    {
        PlayAudioResponse(audioData, false);
    }

    private readonly Queue<(byte[] data, int seq)> replyQueue = new Queue<(byte[] data, int seq)>();
    private readonly Dictionary<int, MouthCue[]> pendingCues = new Dictionary<int, MouthCue[]>();
    private int playingSeq = -1;
    private AudioClip playingClip;
    private bool replyPlayerRunning;

    /// While true, a reply that has arrived waits (it is queued, not dropped). Used during the walk-in so she starts
    /// speaking only once the candidate is seated.
    public bool HoldPlayback { get; set; }
    private bool replyExpectsMore;

    /// <summary>
    /// Queue one chunk of a spoken reply. The server sends the first sentence early with more=true and the remainder
    /// as soon as it is synthesized; chunks play back to back and OnPlaybackCompleted fires once, after the last.
    /// </summary>
    public void PlayAudioResponse(byte[] audioData, bool more) => PlayAudioResponse(audioData, more, -1);

    /// <summary>Use another interviewer: she talks through the shared voice source.</summary>
    public void SetAvatar(AvatarController avatar)
    {
        avatarController = avatar;
        if (avatarController != null && audioSource != null) avatarController.SetAudioSource(audioSource);
    }

    /// <summary>The server's mouth-shape timeline for chunk <paramref name="seq"/> (it arrives just after the audio).</summary>
    public void ApplyMouthCues(int seq, MouthCue[] cues)
    {
        if (seq == playingSeq && playingClip != null && avatarController != null)
        {
            avatarController.SetMouthCues(cues, playingClip);   // already playing: start following the cues now
            return;
        }
        pendingCues[seq] = cues;                                   // not started yet: use them when it does
        var stale = new List<int>();
        foreach (var key in pendingCues.Keys) if (key < seq - 8) stale.Add(key);
        foreach (var key in stale) pendingCues.Remove(key);
    }

    public void PlayAudioResponse(byte[] audioData, bool more, int seq)
    {
        if (audioData != null && audioData.Length > 0) replyQueue.Enqueue((audioData, seq));
        replyExpectsMore = more;
        if (!replyPlayerRunning) StartCoroutine(ReplyPlayerCoroutine());
    }

    private IEnumerator ReplyPlayerCoroutine()
    {
        replyPlayerRunning = true;
        bool started = false;
        float waited = 0f;
        float originalVolume = audioSource.volume;

        while (true)
        {
            if (!started && HoldPlayback) { yield return null; continue; }
            if (replyQueue.Count == 0)
            {
                // Stop once the last chunk is in; otherwise give the next one a few seconds to arrive.
                if (!replyExpectsMore || waited > 6f) break;
                waited += Time.unscaledDeltaTime;
                yield return null;
                continue;
            }
            waited = 0f;

            var item = replyQueue.Dequeue();
            var data = item.data;
            AudioClip clip = WavBytesToClip(data);
            if (clip == null)
            {
                Debug.LogWarning("Reply chunk could not be decoded in memory");
                continue;
            }

            if (!started)
            {
                started = true;
                if (audioSource.isPlaying) audioSource.Stop();
                OnPlaybackStarted?.Invoke();
                if (avatarController != null) avatarController.StartTalking();
            }

            var previous = audioSource.clip;
            audioSource.clip = clip;
            audioSource.Play();
            playingSeq = item.seq;
            playingClip = clip;
            if (item.seq >= 0 && pendingCues.TryGetValue(item.seq, out var readyCues))
            {
                pendingCues.Remove(item.seq);
                if (avatarController != null) avatarController.SetMouthCues(readyCues, clip);
            }
            if (previous != null && previous.name == "ServerReply") Destroy(previous);
            yield return new WaitForSeconds(clip.length);
        }

        audioSource.volume = originalVolume;
        if (started && avatarController != null) avatarController.StopTalking();
        replyPlayerRunning = false;
        OnPlaybackCompleted?.Invoke();
    }
    
    /// <summary>
    /// Play streamed audio from an AudioClip
    /// </summary>
    public void PlayStreamedAudio(AudioClip clip)
    {
        StartCoroutine(PlayStreamedAudioCoroutine(clip));
    }
    
    /// <summary>Parse a 16-bit PCM WAV (any chunk layout, e.g. with a LIST chunk) into an AudioClip. Null if unsupported.</summary>
    private AudioClip WavBytesToClip(byte[] wav)
    {
        try
        {
            if (wav == null || wav.Length < 44 || wav[0] != 'R' || wav[1] != 'I' || wav[2] != 'F' || wav[3] != 'F') return null;
            int channels = 1, rate = 24000, bits = 16, format = 1, dataStart = -1, dataLength = 0;
            int pos = 12;
            while (pos + 8 <= wav.Length)
            {
                string id = System.Text.Encoding.ASCII.GetString(wav, pos, 4);
                int size = BitConverter.ToInt32(wav, pos + 4);
                int body = pos + 8;
                if (id == "fmt ")
                {
                    format = BitConverter.ToInt16(wav, body);
                    channels = BitConverter.ToInt16(wav, body + 2);
                    rate = BitConverter.ToInt32(wav, body + 4);
                    bits = BitConverter.ToInt16(wav, body + 14);
                }
                else if (id == "data")
                {
                    dataStart = body;
                    dataLength = (size <= 0 || size > wav.Length - body) ? wav.Length - body : size;   // streamed WAVs can have a bogus size
                    break;
                }
                if (size < 0) break;
                pos = body + size + (size & 1);
            }
            if (dataStart < 0 || bits != 16 || channels < 1 || (format != 1 && format != 0xFFFE)) return null;

            int sampleCount = (dataLength / 2) / channels * channels;
            var samples = new float[sampleCount];
            for (int i = 0; i < sampleCount; i++)
                samples[i] = BitConverter.ToInt16(wav, dataStart + i * 2) / 32768f;

            var clip = AudioClip.Create("ServerReply", sampleCount / channels, channels, rate, false);
            clip.SetData(samples, 0);
            return clip;
        }
        catch (Exception e)
        {
            Debug.LogWarning("WavBytesToClip failed: " + e.Message);
            return null;
        }
    }

    private IEnumerator PlayAudioResponseCoroutine(byte[] audioData)
    {
        // Decode the WAV straight from memory. (Saving it to a temp file and reloading it through UnityWebRequest failed
        // intermittently on the headset with "Unable to read data".) Free the previous reply's samples first.
        if (audioSource.isPlaying) audioSource.Stop();
        var previousClip = audioSource.clip;
        audioSource.clip = null;
        if (previousClip != null && previousClip.name == "ServerReply") Destroy(previousClip);
        AudioClip memoryClip = WavBytesToClip(audioData);
        if (memoryClip != null)
        {
            yield return PlayClipAndWait(memoryClip, audioSource.volume);
            yield break;
        }
        Debug.LogWarning("In-memory WAV decode failed, falling back to file decode");

        // Stop any playing audio
        if (audioSource.isPlaying)
        {
            audioSource.Stop();
        }
        
        // Write the response to a temp file so UnityWebRequest can decode it.
        // Note: file IO is wrapped separately because C# forbids yielding
        // inside a try block that has a catch clause.
        string tempPath = Path.Combine(Application.temporaryCachePath, "temp_response.wav");
        string writeError = null;
        
        try
        {
            File.WriteAllBytes(tempPath, audioData);
        }
        catch (Exception e)
        {
            writeError = e.Message;
        }
        
        if (writeError != null)
        {
            Debug.LogError($"Error writing audio response to disk: {writeError}");
            OnPlaybackError?.Invoke(writeError);
            yield break;
        }
        
        // Decode the file into an AudioClip
        AudioClip clip = null;
        
        using (UnityWebRequest request = UnityWebRequestMultimedia.GetAudioClip("file://" + tempPath, AudioType.WAV))
        {
            yield return request.SendWebRequest();
            
            if (request.result != UnityWebRequest.Result.Success)
            {
                Debug.LogError($"Error loading audio: {request.error}");
                OnPlaybackError?.Invoke(request.error);
                OnPlaybackCompleted?.Invoke();
                yield break;
            }
            
            clip = DownloadHandlerAudioClip.GetContent(request);
        }
        
        if (clip == null)
        {
            Debug.LogError("Failed to convert audio response to AudioClip");
            OnPlaybackError?.Invoke("Failed to convert audio response");
            yield break;
        }
        
        yield return PlayClipAndWait(clip, audioSource.volume);
    }
    
    /// <summary>
    /// Play audio from a streamed AudioClip
    /// </summary>
    private IEnumerator PlayStreamedAudioCoroutine(AudioClip clip)
    {
        // Stop any playing audio
        if (audioSource.isPlaying)
        {
            audioSource.Stop();
        }
        
        if (clip == null)
        {
            Debug.LogError("Cannot play null streamed audio clip");
            OnPlaybackError?.Invoke("Invalid audio clip");
            yield break;
        }
        
        yield return PlayClipAndWait(clip, streamingVolume);
    }
    
    /// <summary>
    /// Shared playback path: play a clip at the given volume, drive the avatar,
    /// and raise the playback events when it finishes.
    /// </summary>
    private IEnumerator PlayClipAndWait(AudioClip clip, float volume)
    {
        float originalVolume = audioSource.volume;
        
        audioSource.volume = volume;
        audioSource.clip = clip;
        audioSource.Play();
        
        OnPlaybackStarted?.Invoke();
        
        // Tell avatar to talk
        if (avatarController != null)
        {
            avatarController.StartTalking();
        }
        
        // Wait for audio to finish playing
        yield return new WaitForSeconds(clip.length);
        
        // Restore original volume
        audioSource.volume = originalVolume;
        
        // Stop avatar talking
        if (avatarController != null)
        {
            avatarController.StopTalking();
        }
        
        OnPlaybackCompleted?.Invoke();
    }
    
    private AudioClip ConvertToAudioClip(byte[] audioData)
    {
        // This method is now unused since we're using a coroutine approach
        // but keeping it for compatibility
        Debug.LogWarning("ConvertToAudioClip is deprecated - use PlayAudioResponseCoroutine instead");
        return null;
    }
    
    public void StopPlayback()
    {
        if (!audioSource.isPlaying) return;
        
        audioSource.Stop();
        
        // Stop avatar talking
        if (avatarController != null)
        {
            avatarController.StopTalking();
        }
        
        OnPlaybackCompleted?.Invoke();
    }
    
    public void SetMicrophone(string deviceName)
    {
        if (Array.IndexOf(Microphone.devices, deviceName) == -1)
        {
            Debug.LogWarning($"Microphone device not found: {deviceName}");
            return;
        }
        
        bool wasRecording = isRecording;
        
        // Stop recording if active
        if (isRecording)
        {
            StopRecording();
        }
        
        // Set new microphone
        selectedMicrophone = deviceName;
        
        // Resume recording if it was active
        if (wasRecording)
        {
            StartRecording();
        }
        
        Debug.Log($"Switched to microphone: {deviceName}");
    }
    
    public string[] GetAvailableMicrophones()
    {
        return Microphone.devices;
    }
    
    public void SetVolume(float volume)
    {
        if (audioSource != null)
        {
            audioSource.volume = Mathf.Clamp01(volume);
        }
    }
    
    /// <summary>
    /// Set the volume for streamed audio
    /// </summary>
    public void SetStreamingVolume(float volume)
    {
        streamingVolume = Mathf.Clamp01(volume);
    }
    
    /// <summary>
    /// Set preference for streaming vs direct audio
    /// </summary>
    public void SetStreamingPreference(bool prefer)
    {
        preferStreaming = prefer;
    }
    
    /// <summary>
    /// Get current streaming preference
    /// </summary>
    public bool PreferStreaming()
    {
        return preferStreaming;
    }
}
