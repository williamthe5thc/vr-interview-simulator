using System.Collections;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.UI;
using System;
using System.IO;
using TMPro; // For TextMeshPro UI

public class VoiceCaptureManager : MonoBehaviour
{
    [SerializeField] private string serverURL = "http://YOUR_PC_LAN_IP:8080/transcribe";
    [SerializeField] private int recordingLength = 10; // seconds
    [SerializeField] private AudioSource feedbackSource; // To play response
    [SerializeField] private Text statusText; // Optional UI text for status
    [SerializeField] private TextMeshProUGUI interviewerResponseText; // For displaying LLM responses
    [SerializeField] private float textDisplayDuration = 10f; // How long to show text
    
    private bool isRecording = false;
    private AudioClip recordingClip;
    
    public void StartRecording()
    {
        if (!isRecording)
        {
            recordingClip = Microphone.Start(null, false, recordingLength, 44100);
            isRecording = true;
            Debug.Log("Recording started...");
            UpdateStatus("Recording...");
        }
    }
    
    public void StopRecordingAndProcess()
    {
        if (isRecording)
        {
            Microphone.End(null);
            isRecording = false;
            Debug.Log("Recording stopped, processing...");
            UpdateStatus("Processing...");
            
            // Convert AudioClip to WAV
            byte[] wavData = ConvertAudioClipToWav(recordingClip);
            
            // Send to server
            StartCoroutine(SendAudioToServer(wavData));
        }
    }
    
    private IEnumerator SendAudioToServer(byte[] audioData)
    {
        WWWForm form = new WWWForm();
        form.AddBinaryData("audio", audioData, "recording.wav", "audio/wav");
        
        using (UnityWebRequest www = UnityWebRequest.Post(serverURL, form))
        {
            yield return www.SendWebRequest();
            
            if (www.result != UnityWebRequest.Result.Success)
            {
                Debug.LogError($"Error: {www.error}");
                UpdateStatus($"Error: {www.error}");
            }
            else
            {
                Debug.Log("Audio successfully sent to server");
                UpdateStatus("Audio sent, waiting for response...");
                
                // Extract session ID from response
                string responseText = www.downloadHandler.text;
                string sessionId = JsonUtility.FromJson<SessionResponse>(responseText).session_id;
                
                // Start polling for response
                StartCoroutine(PollForAudioResponse(sessionId));
            }
        }
    }
    
    private IEnumerator PollForAudioResponse(string sessionId)
    {
        string responseUrl = $"http://YOUR_PC_LAN_IP:8080/response?session={sessionId}";
        string textResponseUrl = $"http://YOUR_PC_LAN_IP:8080/text_response?session={sessionId}";
        bool responseReceived = false;
        int attempts = 0;
        int maxAttempts = 60; // Increased timeout
        
        UpdateStatus("Waiting for interview response...");
        
        while (!responseReceived && attempts < maxAttempts)
        {
            // First try to get text response
            using (UnityWebRequest textRequest = UnityWebRequest.Get(textResponseUrl))
            {
                yield return textRequest.SendWebRequest();
                
                if (textRequest.result == UnityWebRequest.Result.Success)
                {
                    string responseText = textRequest.downloadHandler.text;
                    DisplayTextResponse(responseText);
                    responseReceived = true;
                    Debug.Log("Displaying text response: " + responseText);
                    UpdateStatus("Displaying interviewer response as text");
                    break;
                }
                else if (textRequest.responseCode == 202) // Processing
                {
                    string progressInfo = textRequest.downloadHandler.text;
                    UpdateStatus($"Processing: {progressInfo}");
                }
            }
            
            // Then try for audio response as fallback
            using (UnityWebRequest www = UnityWebRequestMultimedia.GetAudioClip(responseUrl, AudioType.WAV))
            {
                yield return www.SendWebRequest();
                
                if (www.result == UnityWebRequest.Result.Success)
                {
                    // Handle audio response
                    AudioClip responseClip = DownloadHandlerAudioClip.GetContent(www);
                    feedbackSource.clip = responseClip;
                    feedbackSource.Play();
                    responseReceived = true;
                    Debug.Log("Playing response audio");
                    UpdateStatus("Playing response...");
                }
                else if (www.responseCode == 202) // Processing
                {
                    string progressInfo = www.downloadHandler.text;
                    UpdateStatus($"Processing: {progressInfo}");
                }
                else if (www.responseCode != 404) // Error (not 404 which means "not ready")
                {
                    Debug.LogError($"Error getting response: {www.error}");
                    UpdateStatus($"Error: {www.error}");
                }
            }
            
            attempts++;
            if (!responseReceived)
            {
                yield return new WaitForSeconds(1.0f); // Poll every second
                
                // Update status with attempt count periodically
                if (attempts % 5 == 0)
                {
                    UpdateStatus($"Waiting for response... ({attempts}/{maxAttempts})");
                }
            }
        }
        
        if (!responseReceived)
        {
            UpdateStatus("Timed out waiting for response. Please try again.");
        }
    }
    
    // Display text response in UI
    private void DisplayTextResponse(string text)
    {
        if (interviewerResponseText != null)
        {
            interviewerResponseText.text = text;
            interviewerResponseText.gameObject.SetActive(true);
            
            // Hide text after a delay
            StartCoroutine(HideTextAfterDelay(textDisplayDuration));
        }
        else
        {
            Debug.LogError("Interviewer response text component is not assigned!");
        }
    }
    
    // Hide text after delay
    private IEnumerator HideTextAfterDelay(float delay)
    {
        yield return new WaitForSeconds(delay);
        if (interviewerResponseText != null)
        {
            interviewerResponseText.gameObject.SetActive(false);
        }
    }
    
    private void UpdateStatus(string message)
    {
        if (statusText != null)
        {
            statusText.text = message;
        }
        Debug.Log(message);
    }
    
    private byte[] ConvertAudioClipToWav(AudioClip clip)
    {
        // Get data from AudioClip
        float[] samples = new float[clip.samples * clip.channels];
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
                writer.Write((short)clip.channels);
                writer.Write(clip.frequency);
                writer.Write(clip.frequency * clip.channels * 2); // Byte rate
                writer.Write((short)(clip.channels * 2)); // Block align
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
    
    // Helper class for JSON deserialization
    [Serializable]
    private class SessionResponse
    {
        public string session_id;
    }
    
    // Test microphone function
    public void TestMicrophone()
    {
        if (Microphone.devices.Length == 0)
        {
            Debug.LogError("No microphone detected!");
            if (statusText != null)
                statusText.text = "ERROR: No microphone detected!";
            return;
        }
        
        Debug.Log("Microphones detected: " + string.Join(", ", Microphone.devices));
        if (statusText != null)
            statusText.text = "Mic found: " + Microphone.devices[0];
    }
}