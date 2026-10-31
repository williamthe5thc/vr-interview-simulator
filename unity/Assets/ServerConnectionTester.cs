using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using TMPro;
using UnityEngine.Networking;
using System;

public class ServerConnectionTester : MonoBehaviour
{
    [Header("Server Settings")]
    [SerializeField] private string serverUrl = "http://YOUR_PC_LAN_IP:8765";
    [SerializeField] private float testInterval = 5f;
    
    [Header("UI References")]
    [SerializeField] private TextMeshProUGUI statusText;
    [SerializeField] private Image connectionIndicator;
    [SerializeField] private Button testConnectionButton;
    [SerializeField] private Button sendPingButton;
    [SerializeField] private Button simulateAudioButton;
    [SerializeField] private Toggle autoTestToggle;
    
    [Header("Test Settings")]
    [SerializeField] private bool autoTestOnStart = true;
    [SerializeField] private AudioClip testAudioClip;
    [SerializeField] private TextMeshProUGUI logText;
    [SerializeField] private int maxLogLines = 20;
    
    private bool isAutoTesting = false;
    private Coroutine autoTestCoroutine;
    private string sessionId;
    private List<string> logLines = new List<string>();
    
    private void Start()
    {
        // Generate a session ID for testing
        sessionId = Guid.NewGuid().ToString();
        
        // Set up UI buttons
        if (testConnectionButton != null)
            testConnectionButton.onClick.AddListener(TestConnection);
            
        if (sendPingButton != null)
            sendPingButton.onClick.AddListener(SendPing);
            
        if (simulateAudioButton != null)
            simulateAudioButton.onClick.AddListener(SimulateAudioSend);
            
        if (autoTestToggle != null)
            autoTestToggle.onValueChanged.AddListener(ToggleAutoTest);
        
        // Start auto-testing if enabled
        if (autoTestOnStart && autoTestToggle != null)
        {
            autoTestToggle.isOn = true;
        }
        
        UpdateStatus("Ready to test connection");
    }
    
    public void TestConnection()
    {
        StartCoroutine(TestConnectionCoroutine());
    }
    
    private IEnumerator TestConnectionCoroutine()
    {
        UpdateStatus("Testing connection...");
        SetIndicator(Color.yellow);
        
        // Try to ping the server
        using (UnityWebRequest request = UnityWebRequest.Get(serverUrl + "/ping"))
        {
            yield return request.SendWebRequest();
            
            if (request.result == UnityWebRequest.Result.Success)
            {
                UpdateStatus("Connection successful! Server is reachable.");
                SetIndicator(Color.green);
                LogTestResult("Connection test succeeded. Response: " + request.downloadHandler.text);
            }
            else
            {
                UpdateStatus("Connection failed: " + request.error);
                SetIndicator(Color.red);
                LogTestResult("Connection test failed. Error: " + request.error);
            }
        }
    }
    
    public void SendPing()
    {
        StartCoroutine(SendPingCoroutine());
    }
    
    private IEnumerator SendPingCoroutine()
    {
        UpdateStatus("Sending ping...");
        
        // Create form with session ID
        WWWForm form = new WWWForm();
        form.AddField("session_id", sessionId);
        
        // Send POST request
        using (UnityWebRequest request = UnityWebRequest.Post(serverUrl + "/ping", form))
        {
            yield return request.SendWebRequest();
            
            if (request.result == UnityWebRequest.Result.Success)
            {
                UpdateStatus("Ping succeeded!");
                LogTestResult("Ping succeeded. Response: " + request.downloadHandler.text);
            }
            else
            {
                UpdateStatus("Ping failed: " + request.error);
                LogTestResult("Ping failed. Error: " + request.error);
            }
        }
    }
    
    public void SimulateAudioSend()
    {
        StartCoroutine(SimulateAudioSendCoroutine());
    }
    
    private IEnumerator SimulateAudioSendCoroutine()
    {
        UpdateStatus("Simulating audio send...");
        
        // Create mock audio data from test clip
        byte[] audioData;
        
        if (testAudioClip != null)
        {
            // Convert test audio clip to WAV
            audioData = AudioClipToWav(testAudioClip);
        }
        else
        {
            // Generate simple test tone if no clip provided
            audioData = GenerateTestTone();
        }
        
        // Create form with audio data
        WWWForm form = new WWWForm();
        form.AddBinaryData("audio", audioData, "test_audio.wav", "audio/wav");
        form.AddField("session_id", sessionId);
        
        // Send POST request
        using (UnityWebRequest request = UnityWebRequest.Post(serverUrl + "/audio", form))
        {
            yield return request.SendWebRequest();
            
            if (request.result == UnityWebRequest.Result.Success)
            {
                UpdateStatus("Audio sent successfully!");
                LogTestResult("Audio test succeeded. Response: " + request.downloadHandler.text);
                
                // Check for response audio
                StartCoroutine(CheckForAudioResponse());
            }
            else
            {
                UpdateStatus("Audio send failed: " + request.error);
                LogTestResult("Audio test failed. Error: " + request.error);
            }
        }
    }
    
    private IEnumerator CheckForAudioResponse()
    {
        UpdateStatus("Checking for audio response...");
        
        // Wait a bit for processing
        yield return new WaitForSeconds(2f);
        
        // Poll for audio responses
        using (UnityWebRequestMultimedia.GetAudioClip(
            serverUrl + "/audio_response?session=" + sessionId, AudioType.WAV))
        {
            yield return new WaitForSeconds(5f); // Extended wait for response
            
            UpdateStatus("Audio response check complete.");
        }
    }
    
    private void ToggleAutoTest(bool enabled)
    {
        isAutoTesting = enabled;
        
        if (enabled)
        {
            if (autoTestCoroutine != null)
                StopCoroutine(autoTestCoroutine);
                
            autoTestCoroutine = StartCoroutine(AutoTestCoroutine());
            UpdateStatus("Auto-testing enabled");
        }
        else
        {
            if (autoTestCoroutine != null)
            {
                StopCoroutine(autoTestCoroutine);
                autoTestCoroutine = null;
            }
            
            UpdateStatus("Auto-testing disabled");
        }
    }
    
    private IEnumerator AutoTestCoroutine()
    {
        while (isAutoTesting)
        {
            // Run connection test
            yield return StartCoroutine(TestConnectionCoroutine());
            
            // Wait for the specified interval
            yield return new WaitForSeconds(testInterval);
        }
    }
    
    private void UpdateStatus(string message)
    {
        if (statusText != null)
        {
            statusText.text = message;
        }
        
        Debug.Log("[ServerTest] " + message);
    }
    
    private void SetIndicator(Color color)
    {
        if (connectionIndicator != null)
        {
            connectionIndicator.color = color;
        }
    }
    
    private void LogTestResult(string message)
    {
        // Add timestamp
        string timestamp = DateTime.Now.ToString("HH:mm:ss");
        string logEntry = $"[{timestamp}] {message}";
        
        // Add to log lines
        logLines.Add(logEntry);
        
        // Keep only the most recent lines
        while (logLines.Count > maxLogLines)
        {
            logLines.RemoveAt(0);
        }
        
        // Update UI
        if (logText != null)
        {
            logText.text = string.Join("\n", logLines);
        }
        
        Debug.Log("[ServerTest] " + message);
    }
    
    private byte[] AudioClipToWav(AudioClip clip)
    {
        // Get audio data
        float[] samples = new float[clip.samples];
        clip.GetData(samples, 0);
        
        // Convert to Int16
        Int16[] intData = new Int16[samples.Length];
        for (int i = 0; i < samples.Length; i++)
        {
            intData[i] = (short)(samples[i] * 32767);
        }
        
        // Create WAV file bytes
        byte[] bytes = new byte[intData.Length * 2 + 44];
        
        // WAV header
        byte[] header = CreateWavHeader(clip.frequency, 16, 1, intData.Length);
        Buffer.BlockCopy(header, 0, bytes, 0, header.Length);
        
        // Audio data
        Buffer.BlockCopy(intData, 0, bytes, 44, intData.Length * 2);
        
        return bytes;
    }
    
    private byte[] CreateWavHeader(int frequency, int bits, int channels, int samples)
    {
        byte[] header = new byte[44];
        
        // RIFF header
        byte[] chunkID = System.Text.Encoding.ASCII.GetBytes("RIFF");
        Buffer.BlockCopy(chunkID, 0, header, 0, 4);
        
        int chunkSize = 36 + samples * channels * bits / 8;
        header[4] = (byte)(chunkSize & 0xff);
        header[5] = (byte)((chunkSize >> 8) & 0xff);
        header[6] = (byte)((chunkSize >> 16) & 0xff);
        header[7] = (byte)((chunkSize >> 24) & 0xff);
        
        byte[] format = System.Text.Encoding.ASCII.GetBytes("WAVE");
        Buffer.BlockCopy(format, 0, header, 8, 4);
        
        // fmt chunk
        byte[] subchunk1ID = System.Text.Encoding.ASCII.GetBytes("fmt ");
        Buffer.BlockCopy(subchunk1ID, 0, header, 12, 4);
        
        header[16] = 16; // Subchunk1Size is 16
        header[17] = 0;
        header[18] = 0;
        header[19] = 0;
        
        header[20] = 1; // AudioFormat is PCM
        header[21] = 0;
        
        header[22] = (byte)channels;
        header[23] = 0;
        
        header[24] = (byte)(frequency & 0xff);
        header[25] = (byte)((frequency >> 8) & 0xff);
        header[26] = (byte)((frequency >> 16) & 0xff);
        header[27] = (byte)((frequency >> 24) & 0xff);
        
        int byteRate = frequency * channels * bits / 8;
        header[28] = (byte)(byteRate & 0xff);
        header[29] = (byte)((byteRate >> 8) & 0xff);
        header[30] = (byte)((byteRate >> 16) & 0xff);
        header[31] = (byte)((byteRate >> 24) & 0xff);
        
        header[32] = (byte)(channels * bits / 8); // Block align
        header[33] = 0;
        
        header[34] = (byte)bits; // Bits per sample
        header[35] = 0;
        
        // data chunk
        byte[] subchunk2ID = System.Text.Encoding.ASCII.GetBytes("data");
        Buffer.BlockCopy(subchunk2ID, 0, header, 36, 4);
        
        int subchunk2Size = samples * channels * bits / 8;
        header[40] = (byte)(subchunk2Size & 0xff);
        header[41] = (byte)((subchunk2Size >> 8) & 0xff);
        header[42] = (byte)((subchunk2Size >> 16) & 0xff);
        header[43] = (byte)((subchunk2Size >> 24) & 0xff);
        
        return header;
    }
    
    private byte[] GenerateTestTone()
    {
        // Generate a simple 1-second sine wave tone at 440Hz
        int sampleRate = 16000;
        int numSamples = sampleRate;
        float[] samples = new float[numSamples];
        
        for (int i = 0; i < numSamples; i++)
        {
            float t = (float)i / sampleRate;
            samples[i] = Mathf.Sin(2 * Mathf.PI * 440f * t) * 0.5f; // 440Hz sine wave at half amplitude
        }
        
        // Convert to WAV
        Int16[] intData = new Int16[samples.Length];
        for (int i = 0; i < samples.Length; i++)
        {
            intData[i] = (short)(samples[i] * 32767);
        }
        
        // Create WAV file bytes
        byte[] bytes = new byte[intData.Length * 2 + 44];
        
        // WAV header
        byte[] header = CreateWavHeader(sampleRate, 16, 1, intData.Length);
        Buffer.BlockCopy(header, 0, bytes, 0, header.Length);
        
        // Audio data
        Buffer.BlockCopy(intData, 0, bytes, 44, intData.Length * 2);
        
        return bytes;
    }
    
    public void SendServerCommand(string command)
    {
        StartCoroutine(SendControlMessageCoroutine(command));
    }
    
    private IEnumerator SendControlMessageCoroutine(string action)
    {
        UpdateStatus($"Sending command: {action}...");
        
        // Create control message
        WWWForm form = new WWWForm();
        form.AddField("session_id", sessionId);
        form.AddField("action", action);
        
        // Send POST request
        using (UnityWebRequest request = UnityWebRequest.Post(serverUrl + "/control", form))
        {
            yield return request.SendWebRequest();
            
            if (request.result == UnityWebRequest.Result.Success)
            {
                UpdateStatus($"Command '{action}' sent successfully!");
                LogTestResult($"Command '{action}' succeeded. Response: " + request.downloadHandler.text);
            }
            else
            {
                UpdateStatus($"Command '{action}' failed: " + request.error);
                LogTestResult($"Command '{action}' failed. Error: " + request.error);
            }
        }
    }
    
    // Helper methods for common commands
    public void StartSession()
    {
        SendServerCommand("start");
    }
    
    public void EndSession()
    {
        SendServerCommand("end");
    }
    
    public void ResetSession()
    {
        SendServerCommand("reset");
    }
}
