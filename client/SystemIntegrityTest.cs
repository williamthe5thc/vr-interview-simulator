using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using System;
using UnityEngine.Networking;
using TMPro;

// This script runs a comprehensive test of all VR Interview system components
// to verify integration and proper functioning
public class SystemIntegrityTest : MonoBehaviour
{
    [Header("System Components")]
    [SerializeField] private AppManager appManager;
    [SerializeField] private WebSocketManager webSocketManager;
    [SerializeField] private SessionManager sessionManager;
    [SerializeField] private AudioManager audioManager;
    [SerializeField] private AvatarController avatarController;
    [SerializeField] private UIManager uiManager;
    
    [Header("Test Settings")]
    [SerializeField] private bool runTestOnStart = false;
    [SerializeField] private string serverUrl = "http://YOUR_PC_LAN_IP:8765";
    [SerializeField] private AudioClip testAudioClip;
    
    [Header("Test Output")]
    [SerializeField] private TextMeshProUGUI testOutputText;
    
    private List<string> testResults = new List<string>();
    private int totalTests = 0;
    private int passedTests = 0;
    
    void Start()
    {
        if (runTestOnStart)
        {
            StartCoroutine(RunFullSystemTest());
        }
    }
    
    public void StartTests()
    {
        StartCoroutine(RunFullSystemTest());
    }
    
    private IEnumerator RunFullSystemTest()
    {
        // Clear previous test results
        testResults.Clear();
        totalTests = 0;
        passedTests = 0;
        
        LogTestStart("VR INTERVIEW SYSTEM INTEGRITY TEST");
        
        // First find all required components
        yield return StartCoroutine(TestComponentAvailability());
        
        // Test server connection
        yield return StartCoroutine(TestServerConnection());
        
        // Test state machine
        yield return StartCoroutine(TestStateMachine());
        
        // Test audio pipeline
        yield return StartCoroutine(TestAudioPipeline());
        
        // Test avatar controller
        yield return StartCoroutine(TestAvatarController());
        
        // Summarize results
        LogTestResult($"TEST SUMMARY: {passedTests}/{totalTests} tests passed");
        
        if (passedTests == totalTests)
        {
            LogTestResult("ALL TESTS PASSED! System is ready for use.");
        }
        else
        {
            LogTestResult($"SOME TESTS FAILED! ({totalTests - passedTests} failures). Check logs for details.");
        }
        
        UpdateTestOutputUI();
    }
    
    private IEnumerator TestComponentAvailability()
    {
        LogTestStart("COMPONENT AVAILABILITY TESTS");
        
        // Find components if not assigned
        if (appManager == null) appManager = FindObjectOfType<AppManager>();
        if (webSocketManager == null) webSocketManager = FindObjectOfType<WebSocketManager>();
        if (sessionManager == null) sessionManager = FindObjectOfType<SessionManager>();
        if (audioManager == null) audioManager = FindObjectOfType<AudioManager>();
        if (avatarController == null) avatarController = FindObjectOfType<AvatarController>();
        if (uiManager == null) uiManager = FindObjectOfType<UIManager>();
        
        // Test App Manager
        TestComponentExists("AppManager", appManager);
        
        // Test WebSocket Manager
        TestComponentExists("WebSocketManager", webSocketManager);
        
        // Test Session Manager
        TestComponentExists("SessionManager", sessionManager);
        
        // Test Audio Manager
        TestComponentExists("AudioManager", audioManager);
        
        // Test Avatar Controller
        TestComponentExists("AvatarController", avatarController);
        
        // Test UI Manager
        TestComponentExists("UIManager", uiManager);
        
        yield return null;
    }
    
    private IEnumerator TestServerConnection()
    {
        LogTestStart("SERVER CONNECTION TESTS");
        
        // Skip if WebSocketManager is not available
        if (webSocketManager == null)
        {
            LogTestResult("SERVER CONNECTION TESTS SKIPPED - WebSocketManager not found");
            yield break;
        }
        
        // Test simple ping
        bool pingSuccess = false;
        UnityWebRequest pingRequest = UnityWebRequest.Get(serverUrl + "/ping");
        // We need to move the yield outside the try-catch
        yield return pingRequest.SendWebRequest();
        
        pingSuccess = pingRequest.result == UnityWebRequest.Result.Success;
        TestResult("Server Ping", pingSuccess);
        
        if (pingSuccess)
        {
            LogTestInfo("Server response: " + pingRequest.downloadHandler.text);
        }
        else
        {
            LogTestInfo("Server error: " + pingRequest.error);
        }
        pingRequest.Dispose();
        
        // Skip further tests if ping failed
        if (!pingSuccess)
        {
            LogTestResult("Remaining server tests skipped due to connection failure");
            yield break;
        }
        
        // Test session start
        bool sessionStartSuccess = false;
        string testSessionId = Guid.NewGuid().ToString();
        
        WWWForm startForm = new WWWForm();
        startForm.AddField("session_id", testSessionId);
        startForm.AddField("action", "start");
        
        UnityWebRequest startRequest = UnityWebRequest.Post(serverUrl + "/control", startForm);
        yield return startRequest.SendWebRequest();
        
        sessionStartSuccess = startRequest.result == UnityWebRequest.Result.Success;
        TestResult("Session Start", sessionStartSuccess);
        startRequest.Dispose();
        
        // Test session end
        if (sessionStartSuccess)
        {
            WWWForm endForm = new WWWForm();
            endForm.AddField("session_id", testSessionId);
            endForm.AddField("action", "end");
            
            UnityWebRequest endRequest = UnityWebRequest.Post(serverUrl + "/control", endForm);
            yield return endRequest.SendWebRequest();
            
            TestResult("Session End", endRequest.result == UnityWebRequest.Result.Success);
            endRequest.Dispose();
        }
    }
    
    private IEnumerator TestStateMachine()
    {
        LogTestStart("STATE MACHINE TESTS");
        
        // Skip if Session Manager is not available
        if (sessionManager == null)
        {
            LogTestResult("STATE MACHINE TESTS SKIPPED - SessionManager not found");
            yield break;
        }
        
        // Test state transitions via reflection (since states are usually private)
        System.Reflection.MethodInfo updateStateMethod = sessionManager.GetType().GetMethod("UpdateState", 
            System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.Public);
            
        if (updateStateMethod == null)
        {
            // Try non-public method
            updateStateMethod = sessionManager.GetType().GetMethod("UpdateState", 
                System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
        }
        
        if (updateStateMethod != null)
        {
            // Test valid state transitions
            bool transitionSuccess = true;
            
            // Move try-catch outside the yield returns
            try
            {
                // IDLE → LISTENING
                updateStateMethod.Invoke(sessionManager, new object[] { "IDLE", "LISTENING" });
            }
            catch (Exception e)
            {
                transitionSuccess = false;
                LogTestInfo("State transition error (IDLE→LISTENING): " + e.Message);
            }
            yield return new WaitForSeconds(0.2f);
            
            if (transitionSuccess)
            {
                try
                {
                    // LISTENING → PROCESSING
                    updateStateMethod.Invoke(sessionManager, new object[] { "LISTENING", "PROCESSING" });
                }
                catch (Exception e)
                {
                    transitionSuccess = false;
                    LogTestInfo("State transition error (LISTENING→PROCESSING): " + e.Message);
                }
            }
            yield return new WaitForSeconds(0.2f);
            
            if (transitionSuccess)
            {
                try
                {
                    // PROCESSING → RESPONDING
                    updateStateMethod.Invoke(sessionManager, new object[] { "PROCESSING", "RESPONDING" });
                }
                catch (Exception e)
                {
                    transitionSuccess = false;
                    LogTestInfo("State transition error (PROCESSING→RESPONDING): " + e.Message);
                }
            }
            yield return new WaitForSeconds(0.2f);
            
            if (transitionSuccess)
            {
                try
                {
                    // RESPONDING → WAITING
                    updateStateMethod.Invoke(sessionManager, new object[] { "RESPONDING", "WAITING" });
                }
                catch (Exception e)
                {
                    transitionSuccess = false;
                    LogTestInfo("State transition error (RESPONDING→WAITING): " + e.Message);
                }
            }
            yield return new WaitForSeconds(0.2f);
            
            if (transitionSuccess)
            {
                try
                {
                    // WAITING → IDLE
                    updateStateMethod.Invoke(sessionManager, new object[] { "WAITING", "IDLE" });
                }
                catch (Exception e)
                {
                    transitionSuccess = false;
                    LogTestInfo("State transition error (WAITING→IDLE): " + e.Message);
                }
            }
            yield return new WaitForSeconds(0.2f);
            
            TestResult("State Transitions", transitionSuccess);
        }
        else
        {
            LogTestResult("State Machine Test Failed - UpdateState method not found");
            TestResult("State Transitions", false);
        }
    }
    
    private IEnumerator TestAudioPipeline()
    {
        LogTestStart("AUDIO PIPELINE TESTS");
        
        // Skip if Audio Manager is not available
        if (audioManager == null)
        {
            LogTestResult("AUDIO PIPELINE TESTS SKIPPED - AudioManager not found");
            yield break;
        }
        
        // Test microphone availability
        bool micAvailable = Microphone.devices.Length > 0;
        TestResult("Microphone Available", micAvailable);
        
        if (micAvailable)
        {
            LogTestInfo("Available microphones: " + string.Join(", ", Microphone.devices));
        }
        
        // Test audio playback
        if (testAudioClip != null)
        {
            bool playbackSuccess = true;
            System.Reflection.MethodInfo playMethod = null;
            
            try
            {
                // Use reflection to access PlayAudioClip method
                playMethod = audioManager.GetType().GetMethod("PlayAudioClip", 
                    System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.Public);
                    
                if (playMethod == null)
                {
                    // Try PlayAudioResponse method
                    playMethod = audioManager.GetType().GetMethod("PlayAudioResponse", 
                        System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.Public);
                }
                
                if (playMethod == null)
                {
                    playbackSuccess = false;
                    LogTestInfo("Could not find PlayAudioClip or PlayAudioResponse method");
                }
            }
            catch (Exception e)
            {
                playbackSuccess = false;
                LogTestInfo("Audio playback method lookup error: " + e.Message);
            }
            
            // If we found a valid method, try to invoke it
            if (playbackSuccess && playMethod != null)
            {
                try 
                {
                    // Convert AudioClip to byte array if needed
                    if (playMethod.GetParameters()[0].ParameterType == typeof(byte[]))
                    {
                        byte[] audioData = AudioClipToWav(testAudioClip);
                        playMethod.Invoke(audioManager, new object[] { audioData });
                    }
                    else
                    {
                        playMethod.Invoke(audioManager, new object[] { testAudioClip });
                    }
                }
                catch (Exception e)
                {
                    playbackSuccess = false;
                    LogTestInfo("Audio playback error: " + e.Message);
                }
            }
            
            TestResult("Audio Playback", playbackSuccess);
        }
        else
        {
            LogTestResult("Audio Playback test skipped - no test audio clip provided");
        }
        
        yield return null;
    }
    
    private IEnumerator TestAvatarController()
    {
        LogTestStart("AVATAR CONTROLLER TESTS");
        
        // Skip if Avatar Controller is not available
        if (avatarController == null)
        {
            LogTestResult("AVATAR CONTROLLER TESTS SKIPPED - AvatarController not found");
            yield break;
        }
        
        // Test basic animation states
        bool animationSuccess = true;
        
        // Move each try/catch outside of yield returns
        try
        {
            // Test IDLE state
            avatarController.SetIdleState();
        }
        catch (Exception e)
        {
            animationSuccess = false;
            LogTestInfo("IDLE state error: " + e.Message);
        }
        yield return new WaitForSeconds(0.5f);
        
        if (animationSuccess)
        {
            try
            {
                // Test LISTENING state
                avatarController.SetListeningState();
            }
            catch (Exception e)
            {
                animationSuccess = false;
                LogTestInfo("LISTENING state error: " + e.Message);
            }
        }
        yield return new WaitForSeconds(0.5f);
        
        if (animationSuccess)
        {
            try
            {
                // Test THINKING/PROCESSING state
                avatarController.SetThinkingState();
            }
            catch (Exception e)
            {
                animationSuccess = false;
                LogTestInfo("THINKING state error: " + e.Message);
            }
        }
        yield return new WaitForSeconds(0.5f);
        
        if (animationSuccess)
        {
            try
            {
                // Test SPEAKING/RESPONDING state
                avatarController.SetSpeakingState();
            }
            catch (Exception e)
            {
                animationSuccess = false;
                LogTestInfo("SPEAKING state error: " + e.Message);
            }
        }
        yield return new WaitForSeconds(0.5f);
        
        if (animationSuccess)
        {
            try
            {
                // Test ATTENTIVE/WAITING state
                avatarController.SetAttentiveState();
            }
            catch (Exception e)
            {
                animationSuccess = false;
                LogTestInfo("ATTENTIVE state error: " + e.Message);
            }
        }
        yield return new WaitForSeconds(0.5f);
        
        if (animationSuccess)
        {
            try
            {
                // Test ERROR/CONFUSED state
                avatarController.SetConfusedState();
            }
            catch (Exception e)
            {
                animationSuccess = false;
                LogTestInfo("CONFUSED state error: " + e.Message);
            }
        }
        yield return new WaitForSeconds(0.5f);
        
        if (animationSuccess)
        {
            try
            {
                // Return to IDLE
                avatarController.SetIdleState();
            }
            catch (Exception e)
            {
                animationSuccess = false;
                LogTestInfo("Return to IDLE error: " + e.Message);
            }
        }
        
        TestResult("Avatar Animation States", animationSuccess);
        
        // Test talking state
        bool talkingSuccess = true;
        
        try
        {
            // Test StartTalking
            avatarController.StartTalking();
        }
        catch (Exception e)
        {
            talkingSuccess = false;
            LogTestInfo("StartTalking error: " + e.Message);
        }
        yield return new WaitForSeconds(0.5f);
        
        if (talkingSuccess)
        {
            try
            {
                // Test StopTalking
                avatarController.StopTalking();
            }
            catch (Exception e)
            {
                talkingSuccess = false;
                LogTestInfo("StopTalking error: " + e.Message);
            }
        }
        
        TestResult("Avatar Talking Controls", talkingSuccess);
        
        // Test blink animation
        bool blinkSuccess = true;
        
        try
        {
            avatarController.Blink();
        }
        catch (Exception e)
        {
            blinkSuccess = false;
            LogTestInfo("Blink animation error: " + e.Message);
        }
        
        TestResult("Avatar Blink Animation", blinkSuccess);
        
        yield return null;
    }
    
    // Helper methods
    private void TestComponentExists(string componentName, Component component)
    {
        totalTests++;
        bool exists = component != null;
        passedTests += exists ? 1 : 0;
        
        LogTestResult($"{componentName} Component: {(exists ? "FOUND" : "NOT FOUND")}");
    }
    
    private void TestResult(string testName, bool success)
    {
        totalTests++;
        passedTests += success ? 1 : 0;
        
        LogTestResult($"{testName}: {(success ? "PASSED" : "FAILED")}");
    }
    
    private void LogTestStart(string message)
    {
        string formattedMessage = "\n=== " + message + " ===";
        testResults.Add(formattedMessage);
        Debug.Log("[SystemTest] " + message);
        UpdateTestOutputUI();
    }
    
    private void LogTestResult(string message)
    {
        testResults.Add(message);
        Debug.Log("[SystemTest] " + message);
        UpdateTestOutputUI();
    }
    
    private void LogTestInfo(string message)
    {
        testResults.Add("  • " + message);
        Debug.Log("[SystemTest] " + message);
        UpdateTestOutputUI();
    }
    
    private void UpdateTestOutputUI()
    {
        if (testOutputText != null)
        {
            testOutputText.text = string.Join("\n", testResults);
        }
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
}
