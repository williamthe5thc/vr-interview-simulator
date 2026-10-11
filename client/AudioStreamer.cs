using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Networking;

/// <summary>
/// Handles streaming audio from URLs for the VR Interview System.
/// This class manages the streaming of audio from AllTalk TTS server 
/// and reports streaming status.
/// </summary>
public class AudioStreamer : MonoBehaviour
{
    [Header("Components")]
    [SerializeField] private WebSocketManager webSocketManager;
    [SerializeField] private AudioManager audioManager;
    [SerializeField] private UIManager uiManager;
    
    [Header("Streaming Settings")]
    [SerializeField] private float streamingTimeout = 30f; // Maximum time to wait for streaming
    [SerializeField] private int maxRetryAttempts = 2;
    
    // Events
    public event Action<float> OnStreamingProgress;
    public event Action<AudioClip> OnStreamingComplete;
    public event Action<string> OnStreamingFailed;
    
    private Coroutine activeStreamingCoroutine;

    private void Start()
    {
        // Ensure references are set
        if (webSocketManager == null)
        {
            webSocketManager = FindObjectOfType<WebSocketManager>();
        }
        
        if (audioManager == null)
        {
            audioManager = FindObjectOfType<AudioManager>();
        }
    }

    /// <summary>
    /// Stream audio from a URL
    /// </summary>
    /// <param name="url">URL to stream audio from</param>
    /// <param name="format">Format of the audio (wav, mp3, etc.)</param>
    /// <param name="fallbackText">Fallback text if streaming fails</param>
    public void StreamAudioFromUrl(string url, string format, string fallbackText)
    {
        // Cancel any active streaming
        if (activeStreamingCoroutine != null)
        {
            StopCoroutine(activeStreamingCoroutine);
        }
        
        // Start new streaming coroutine
        activeStreamingCoroutine = StartCoroutine(StreamAudioCoroutine(url, format, fallbackText));
    }

    /// <summary>
    /// Cancel active streaming
    /// </summary>
    public void CancelStreaming()
    {
        if (activeStreamingCoroutine != null)
        {
            StopCoroutine(activeStreamingCoroutine);
            activeStreamingCoroutine = null;
        }
    }

    private IEnumerator StreamAudioCoroutine(string url, string format, string fallbackText)
    {
        Debug.Log($"Starting audio streaming from URL: {url}");
        
        // Show streaming status in UI
        if (uiManager != null)
        {
            uiManager.UpdateStatus("Streaming audio response...");
        }

        // Determine the appropriate audio type based on format
        AudioType audioType = GetAudioTypeFromFormat(format);
        
        // Report streaming started
        if (webSocketManager != null)
        {
            SendStreamingStatus("started", url);
        }

        // Attempt streaming with retries
        AudioClip streamedClip = null;
        string errorMessage = null;
        int attempts = 0;
        
        while (streamedClip == null && attempts < maxRetryAttempts)
        {
            attempts++;
            
            // Create request with appropriate audio type
            UnityWebRequest request = UnityWebRequestMultimedia.GetAudioClip(url, audioType);
            
            // Set timeout
            request.timeout = (int)streamingTimeout;
            
            // Start request
            request.SendWebRequest();
            
            // Wait for completion with progress updates
            while (!request.isDone)
            {
                // Update progress
                float progress = request.downloadProgress;
                OnStreamingProgress?.Invoke(progress);
                
                // Update UI if available
                if (uiManager != null && progress > 0)
                {
                    uiManager.UpdateProgressBar(progress);
                }
                
                yield return null;
            }
            
            // Check for errors
            if (request.result != UnityWebRequest.Result.Success)
            {
                errorMessage = request.error;
                Debug.LogWarning($"Streaming attempt {attempts} failed: {errorMessage}");
                
                // Wait before retry
                if (attempts < maxRetryAttempts)
                {
                    yield return new WaitForSeconds(1f);
                }
            }
            else
            {
                // Get audio clip from response
                streamedClip = DownloadHandlerAudioClip.GetContent(request);
                
                if (streamedClip == null)
                {
                    errorMessage = "Failed to extract audio content from response";
                    Debug.LogWarning(errorMessage);
                }
                else
                {
                    // Success - break retry loop
                    break;
                }
            }
        }

        // Clear active coroutine reference
        activeStreamingCoroutine = null;
        
        // Handle result
        if (streamedClip != null)
        {
            // Report success
            if (webSocketManager != null)
            {
                SendStreamingStatus("completed", url);
            }
            
            Debug.Log("Audio streaming completed successfully");
            
            // Play the streamed audio
            if (audioManager != null)
            {
                audioManager.PlayStreamedAudio(streamedClip);
            }
            
            // Notify listeners
            OnStreamingComplete?.Invoke(streamedClip);
        }
        else
        {
            // Report failure
            if (webSocketManager != null)
            {
                SendStreamingStatus("failed", url, errorMessage);
            }
            
            Debug.LogError($"Audio streaming failed after {attempts} attempts: {errorMessage}");
            
            // Notify listeners
            OnStreamingFailed?.Invoke(errorMessage);
            
            // Show fallback text if available
            if (!string.IsNullOrEmpty(fallbackText) && uiManager != null)
            {
                uiManager.ShowFallbackText(fallbackText);
            }
        }
    }

    private AudioType GetAudioTypeFromFormat(string format)
    {
        switch (format.ToLower())
        {
            case "wav":
                return AudioType.WAV;
            case "mp3":
                return AudioType.MPEG;
            case "ogg":
                return AudioType.OGGVORBIS;
            case "aac":
                return AudioType.ACC;
            default:
                Debug.LogWarning($"Unknown audio format: {format}, defaulting to WAV");
                return AudioType.WAV;
        }
    }

    private void SendStreamingStatus(string status, string url, string error = null)
    {
        if (webSocketManager == null) return;
        
        StreamingStatusMessage message = new StreamingStatusMessage(
            webSocketManager.GetSessionId(),
            status,
            url,
            error
        );
        
        string json = JsonUtility.ToJson(message);
        
        // Send the message
        webSocketManager.SendJsonMessage(json);
    }
}
