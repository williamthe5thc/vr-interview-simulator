using System;
using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// Handles client capabilities detection and reporting for the VR Interview System.
/// This class detects and reports device capabilities such as audio streaming support
/// and available audio formats to the server.
/// </summary>
[Serializable]
public class ClientCapabilities
{
    [Serializable]
    public class BrowserInfo
    {
        public string name = "unity";
        public string version;
    }

    public bool supports_streaming = true;
    public List<string> audio_formats = new List<string>() { "wav", "mp3" };
    public BrowserInfo browser = new BrowserInfo();

    public ClientCapabilities()
    {
        // Get Unity version for reporting
        browser.version = Application.unityVersion;
        
        // Detect if the client supports streaming
        DetectStreamingSupport();
        
        // Detect supported audio formats
        DetectSupportedFormats();
    }

    private void DetectStreamingSupport()
    {
        // For Oculus Quest, streaming is generally supported
        // We could add more sophisticated detection based on OS/device
        supports_streaming = true;
        
#if UNITY_ANDROID && !UNITY_EDITOR
        // Check if we're on Oculus Quest 1 (which might have more limitations)
        if (SystemInfo.deviceModel.Contains("Quest 1"))
        {
            // Quest 1 might have more limitations, but still generally supports streaming
            supports_streaming = true;
        }
#endif
    }

    private void DetectSupportedFormats()
    {
        // Clear the list and add known supported formats
        audio_formats.Clear();
        
        // WAV format is always supported
        audio_formats.Add("wav");
        
        // MP3 format is supported
        audio_formats.Add("mp3");
        
        // Add additional formats as needed
#if UNITY_ANDROID && !UNITY_EDITOR
        // Oculus Quest supports these formats
        audio_formats.Add("ogg");
        audio_formats.Add("aac");
#endif
    }

    public string ToJson()
    {
        return JsonUtility.ToJson(this);
    }
}

/// <summary>
/// Message class for sending client capabilities to the server
/// </summary>
[Serializable]
public class ClientCapabilitiesMessage
{
    public string type = "client_capabilities";
    public string session_id;
    public double timestamp;
    public ClientCapabilities capabilities;

    public ClientCapabilitiesMessage(string sessionId, ClientCapabilities capabilities)
    {
        this.session_id = sessionId;
        this.timestamp = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0;
        this.capabilities = capabilities;
    }
}

/// <summary>
/// Message class for streaming status updates
/// </summary>
[Serializable]
public class StreamingStatusMessage
{
    public string type = "streaming_status";
    public string session_id;
    public double timestamp;
    public string status; // "started", "failed", or "completed"
    public string url;
    public string error;

    public StreamingStatusMessage(string sessionId, string status, string url, string error = null)
    {
        this.session_id = sessionId;
        this.timestamp = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0;
        this.status = status;
        this.url = url;
        this.error = error;
    }
}
