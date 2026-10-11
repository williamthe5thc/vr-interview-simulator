using System;
using System.Collections;
using System.Collections.Generic;
using System.Text;
using UnityEngine;
using NativeWebSocket;

public class WebSocketManager : MonoBehaviour
{
    [Header("Connection Settings")]
    // Server address: YOUR_PC_LAN_IP / YOUR_PC_TAILSCALE_IP are placeholders, set per install.
    [SerializeField] public string serverUrl = "ws://YOUR_PC_LAN_IP:8765";   // one address, or several separated by commas: they are tried in turn (e.g. Tailscale first, then the home LAN)
    [SerializeField] private float connectTimeoutSeconds = 4f;               // give up on an address that does not answer (an unreachable one can hang for a minute)
    [SerializeField] private float reconnectDelay = 2f;
    [SerializeField] private int maxReconnectAttempts = 5;
    
    [Header("Components")]
    [SerializeField] private SessionManager sessionManager;
    [SerializeField] private AudioManager audioManager;
    [SerializeField] private UIManager uiManager;

    // WebSocket object
    private WebSocket websocket;
    
    // Connection state
    private bool isConnected = false;
    private bool isConnecting = false;
    private int reconnectAttempts = 0;
    private int urlIndex = 0;            // which of the addresses in serverUrl to try next (stays on the one that last worked)
    private int attemptCounter = 0;
    private int lastAdvancedAttempt = -1;
    private string sessionId;
    
    // Message queue
    private Queue<string> messageQueue = new Queue<string>();
    
    // Events
    public event Action OnConnected;
    public event Action<string> OnDisconnected;
    public event Action<string> OnError;
    public event Action<string, string, Dictionary<string, object>> OnStateUpdate;
    public event Action<byte[]> OnAudioResponse;
    /// <summary>Raised (before the audio is played) when the server flags a reply as the interviewer's closing line.</summary>
    public event Action OnInterviewComplete;
    public event Action<string, int> OnExportSaved;      // file name, number of questions saved on the server
    public event Action<int, int> OnCoachProgress;       // answers reviewed so far, total
    public event Action<CoachReport> OnCoachReport;
    public event Action<string> OnServerStatus;           // a notice about the server's language model / voice engine ("" = all fine)

    private void Start()
    {
        // Generate a unique session ID
        sessionId = Guid.NewGuid().ToString();
        
        // Connect to server
        ConnectToServer();
        
        // Start ping coroutine
        StartCoroutine(SendPingMessages());
    }
    
    private void Update()
    {
        #if !UNITY_WEBGL || UNITY_EDITOR
        if (websocket != null)
        {
            // Process WebSocket message queue - MUST be called in Update
            websocket.DispatchMessageQueue();
        }
        #endif
    }
    
    public async void ConnectToServer()
    {
        if (isConnecting || isConnected) return;
        
        isConnecting = true;

        string[] urls = serverUrl.Split(new[] { ',', ';', ' ' }, StringSplitOptions.RemoveEmptyEntries);
        if (urls.Length == 0) urls = new[] { serverUrl };
        string url = urls[urlIndex % urls.Length];
        int myAttempt = ++attemptCounter;
        bool opened = false;
        Debug.Log("Connecting to server: " + url + (urls.Length > 1 ? " (address " + (urlIndex % urls.Length + 1) + " of " + urls.Length + ")" : ""));
        
        // Update UI
        if (uiManager != null)
        {
            uiManager.UpdateStatus("Connecting to server...");
        }
        
        try
        {
            // Close existing WebSocket if any
            if (websocket != null)
            {
                await websocket.Close();
            }
            
            // Create new WebSocket
            websocket = new WebSocket(url);
            var thisSocket = websocket;
            StartCoroutine(CancelIfNoAnswer(thisSocket, myAttempt));
            
            // Set up event handlers
            websocket.OnOpen += () => {
                Debug.Log("WebSocket connection opened");
                opened = true;
                isConnected = true;
                isConnecting = false;
                reconnectAttempts = 0;
                
                // Update UI
                if (uiManager != null)
                {
                    uiManager.UpdateStatus("Connected to server");
                }
                
                // Notify listeners first. SessionManager owns sending the session
                // "start" control message (see SessionManager.HandleConnected) - this
                // used to also send it here, so the server got two starts per connect.
                OnConnected?.Invoke();
                
                // Process any queued messages
                while (messageQueue.Count > 0 && isConnected)
                {
                    string message = messageQueue.Dequeue();
                    websocket.SendText(message);
                }
            };
            
            websocket.OnMessage += (bytes) => {
                ProcessMessage(bytes);
            };
            
            websocket.OnError += (errorMsg) => {
                Debug.LogError("WebSocket error: " + errorMsg);
                
                if (uiManager != null)
                {
                    uiManager.ShowError("WebSocket error: " + errorMsg);
                }
                
                OnError?.Invoke(errorMsg);
            };
            
            websocket.OnClose += (closeCode) => {
                Debug.Log("WebSocket connection closed: " + closeCode);
                
                isConnected = false;
                bool firstReport = true;
                if (!opened) firstReport = FailAttempt(myAttempt);   // never got through: try the next address next time
                
                // Notify disconnect
                OnDisconnected?.Invoke("Connection closed: " + closeCode);
                
                // Update UI
                if (uiManager != null)
                {
                    uiManager.UpdateStatus("Disconnected: " + closeCode);
                }
                
                // Try to reconnect (once per failed attempt: the catch below can report the same failure)
                if (firstReport) TryReconnect();
            };
            
            // Connect to the server
            await websocket.Connect();
        }
        catch (Exception e)
        {
            Debug.LogError("WebSocket connection error: " + e.Message);
            bool firstReport = FailAttempt(myAttempt);
            
            if (uiManager != null)
            {
                uiManager.ShowError("Connection error: " + e.Message);
            }
            
            // Try to reconnect (unless OnClose already scheduled the retry for this same attempt)
            if (firstReport) TryReconnect();
        }
    }
    
    /// A connection attempt failed (error, close before opening, or no answer). Releases the "connecting" flag so the retry can run, moves on to the next
    /// address, and returns true only the first time this attempt is reported (OnClose and the catch can both report the same failure).
    private bool FailAttempt(int attempt)
    {
        isConnecting = false;
        if (attempt == lastAdvancedAttempt) return false;
        lastAdvancedAttempt = attempt;
        urlIndex++;
        return true;
    }

    private IEnumerator CancelIfNoAnswer(WebSocket socket, int attempt)
    {
        yield return new WaitForSeconds(connectTimeoutSeconds);
        if (attempt == attemptCounter && !isConnected && socket != null && socket == websocket)
        {
            Debug.LogWarning("No answer from the server address within " + connectTimeoutSeconds + " s: giving up on it");
            try { socket.CancelConnection(); } catch (Exception e) { Debug.Log("CancelConnection: " + e.Message); }
            // Safety net: if the library reports neither an error nor a close for the cancelled attempt, move on ourselves.
            yield return new WaitForSeconds(1.5f);
            if (attempt == attemptCounter && !isConnected && attempt != lastAdvancedAttempt && FailAttempt(attempt)) TryReconnect();
        }
    }

    private void TryReconnect()
    {
        if (reconnectAttempts < Mathf.Max(maxReconnectAttempts, 8))
        {
            reconnectAttempts++;
            Debug.Log("Attempting to reconnect (" + reconnectAttempts + "/" + maxReconnectAttempts + ")...");
            
            if (uiManager != null)
            {
                uiManager.UpdateStatus("Reconnecting... (" + reconnectAttempts + "/" + maxReconnectAttempts + ")");
            }
            
            // Wait before reconnecting with exponential backoff
            float delay = reconnectDelay * Mathf.Pow(1.5f, reconnectAttempts - 1);
            StartCoroutine(ReconnectAfterDelay(delay));
        }
        else
        {
            Debug.LogError("Failed to reconnect after multiple attempts");
            
            if (uiManager != null)
            {
                uiManager.ShowError("Failed to connect to the server. Please check your network connection and try again.");
            }
        }
    }
    
    private IEnumerator ReconnectAfterDelay(float delay)
    {
        yield return new WaitForSeconds(delay);
        ConnectToServer();
    }
    
    private void ProcessMessage(byte[] bytes)
    {
        string jsonMessage = Encoding.UTF8.GetString(bytes);
        Debug.Log("Received message: " + jsonMessage);
        
        try
        {
            // Parse message to determine type
            JsonMessage message = JsonUtility.FromJson<JsonMessage>(jsonMessage);
            
            switch (message.type)
            {
                case "state_update":
                    ProcessStateUpdate(jsonMessage);
                    break;
                
                case "audio_response":
                    ProcessAudioResponse(jsonMessage);
                    break;
                
                case "session_init":
                    // Adopt the session id the server assigned. State-based commands (begin, reset) look the session up
                    // by this id; the random id the client made up before was never known to the server.
                    var init = JsonUtility.FromJson<BaseMessage>(jsonMessage);
                    if (!string.IsNullOrEmpty(init.session_id))
                    {
                        sessionId = init.session_id;
                        Debug.Log("Session id from server: " + sessionId);
                    }
                    break;
                
                case "server_status":
                    var status = JsonUtility.FromJson<ServerStatusMessage>(jsonMessage);
                    OnServerStatus?.Invoke(status.text ?? "");
                    break;

                case "visemes":
                    var mouth = JsonUtility.FromJson<VisemesMessage>(jsonMessage);
                    if (audioManager != null && mouth.cues != null) audioManager.ApplyMouthCues(mouth.seq, mouth.cues);
                    break;

                case "export_saved":
                    var saved = JsonUtility.FromJson<ExportSavedMessage>(jsonMessage);
                    Debug.Log("Interview saved on the server: " + saved.filename);
                    OnExportSaved?.Invoke(saved.filename, saved.questions);
                    break;

                case "coach_progress":
                    var progress = JsonUtility.FromJson<CoachProgressMessage>(jsonMessage);
                    OnCoachProgress?.Invoke(progress.done, progress.total);
                    break;

                case "coach_report":
                    var report = JsonUtility.FromJson<CoachReport>(jsonMessage);
                    Debug.Log("Coach report received (" + (report.items != null ? report.items.Length : 0) + " items)");
                    OnCoachReport?.Invoke(report);
                    break;

                case "pong":
                    Debug.Log("Received pong from server");
                    break;
                
                case "heartbeat":
                    break;

                case "error":
                    ProcessErrorMessage(jsonMessage);
                    break;
                
                default:
                    Debug.LogWarning("Unknown message type: " + message.type);
                    break;
            }
        }
        catch (Exception e)
        {
            Debug.LogError("Error processing message: " + e.Message);
        }
    }
    
    private void ProcessStateUpdate(string jsonMessage)
    {
        var stateUpdate = JsonUtility.FromJson<StateUpdateMessage>(jsonMessage);
        
        Debug.Log("State update: " + stateUpdate.previous + " → " + stateUpdate.current);
        
        // Extract metadata if present
        Dictionary<string, object> metadata = new Dictionary<string, object>();
        
        // SessionManager subscribes to OnStateUpdate and drives both the per-state
        // behaviour and the UI. We must NOT also call it directly here - doing both
        // ran every single state transition (and its side effects) twice.
        if (OnStateUpdate != null)
        {
            OnStateUpdate.Invoke(stateUpdate.previous, stateUpdate.current, metadata);
        }
        else if (sessionManager != null)
        {
            // Nothing subscribed - drive the session directly so state still advances.
            sessionManager.UpdateState(stateUpdate.previous, stateUpdate.current);
        }
    }
    
    private void ProcessAudioResponse(string jsonMessage)
    {
        var audioResponse = JsonUtility.FromJson<AudioResponseMessage>(jsonMessage);
        
        // Convert base64 to binary
        byte[] audioData = Convert.FromBase64String(audioResponse.data);
        
        Debug.Log("Received audio response (" + audioData.Length + " bytes)" + (audioResponse.interview_complete ? " [closing reply]" : ""));
        
        if (audioResponse.interview_complete)
            OnInterviewComplete?.Invoke();
        
        // Notify listeners
        OnAudioResponse?.Invoke(audioData);
        
        // Play audio if AudioManager is present
        if (audioManager != null)
        {
            audioManager.PlayAudioResponse(audioData, audioResponse.more, audioResponse.seq);
        }
    }
    
    private void ProcessErrorMessage(string jsonMessage)
    {
        var errorMessage = JsonUtility.FromJson<ErrorMessage>(jsonMessage);
        
        Debug.LogError("Server error: " + errorMessage.message);
        
        // Show error to user
        if (uiManager != null)
        {
            uiManager.ShowError(errorMessage.message);
        }
        
        // Notify listeners
        OnError?.Invoke(errorMessage.message);
    }
    
    public async void SendAudioData(byte[] audioData)
    {
        if (!isConnected)
        {
            Debug.LogWarning("Cannot send audio: Not connected to server");
            
            // Queue message for when connection is established
            QueueMessage(CreateAudioDataMessage(audioData));
            
            // Try to connect
            ConnectToServer();
            return;
        }
        
        Debug.Log("Sending audio data (" + audioData.Length + " bytes)");
        
        try
        {
            // Create message with audio data
            string message = CreateAudioDataMessage(audioData);
            
            // Send message
            await websocket.SendText(message);
        }
        catch (Exception e)
        {
            Debug.LogError("Error sending audio data: " + e.Message);
            
            // Check if connection was lost
            if (websocket.State != WebSocketState.Open)
            {
                isConnected = false;
                OnDisconnected?.Invoke("Connection lost while sending audio");
                TryReconnect();
            }
        }
    }
    
    private string CreateAudioDataMessage(byte[] audioData)
    {
        var message = new AudioDataMessage
        {
            type = "audio_data",
            session_id = sessionId,
            data = Convert.ToBase64String(audioData),
            timestamp = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0
        };
        
        return JsonUtility.ToJson(message);
    }
    
    public async void SendControlMessage(string action, string job = null, string interviewer = null, string voice = null)
    {
        if (!isConnected)
        {
            Debug.LogWarning("Cannot send control message: Not connected to server");
            
            // Queue message
            QueueMessage(CreateControlMessage(action, job, interviewer, voice));
            
            // Try to connect
            ConnectToServer();
            return;
        }
        
        Debug.Log("Sending control message: " + action + (string.IsNullOrEmpty(job) ? "" : " (job " + job + ")"));
        
        try
        {
            // Create message
            string message = CreateControlMessage(action, job, interviewer, voice);
            
            // Send message
            await websocket.SendText(message);
        }
        catch (Exception e)
        {
            Debug.LogError("Error sending control message: " + e.Message);
            
            // Check if connection was lost
            if (websocket.State != WebSocketState.Open)
            {
                isConnected = false;
                OnDisconnected?.Invoke("Connection lost while sending control message");
                TryReconnect();
            }
        }
    }
    
    private string CreateControlMessage(string action, string job = null, string interviewer = null, string voice = null)
    {
        var message = new ControlMessage
        {
            type = "control",
            session_id = sessionId,
            action = action,
            job = job,
            interviewer = interviewer,
            voice = voice,
            timestamp = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0
        };
        
        return JsonUtility.ToJson(message);
    }
    
    private IEnumerator SendPingMessages()
    {
        while (true)
        {
            yield return new WaitForSeconds(5f);
            
            if (isConnected)
            {
                SendPingMessage();
            }
        }
    }
    
    public async void SendPingMessage()
    {
        if (!isConnected) return;
        
        Debug.Log("Sending ping");
        
        try
        {
            // Create ping message
            var message = new PingMessage
            {
                type = "ping",
                session_id = sessionId,
                timestamp = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0
            };
            
            // Send message
            await websocket.SendText(JsonUtility.ToJson(message));
        }
        catch (Exception e)
        {
            Debug.LogError("Error sending ping: " + e.Message);
            
            // Check if connection was lost
            if (websocket.State != WebSocketState.Open)
            {
                isConnected = false;
                OnDisconnected?.Invoke("Connection lost during ping");
                TryReconnect();
            }
        }
    }
    
    public async void NotifyPlaybackComplete()
    {
        if (!isConnected) return;
        
        Debug.Log("Notifying playback complete");
        
        try
        {
            // Create playback complete message
            var message = new PlaybackCompleteMessage
            {
                type = "playback_complete",
                session_id = sessionId,
                timestamp = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0
            };
            
            // Send message
            await websocket.SendText(JsonUtility.ToJson(message));
        }
        catch (Exception e)
        {
            Debug.LogError("Error sending playback complete: " + e.Message);
            
            // Check if connection was lost
            if (websocket.State != WebSocketState.Open)
            {
                isConnected = false;
                OnDisconnected?.Invoke("Connection lost while notifying playback complete");
                TryReconnect();
            }
        }
    }
    
    /// <summary>
    /// Send a pre-serialized JSON payload over the socket.
    /// Deliberately NOT named SendMessage - that name collides with
    /// UnityEngine.Component.SendMessage(string), which silently swallowed
    /// these calls by trying to invoke a method named after the JSON.
    /// </summary>
    public async void SendJsonMessage(string json)
    {
        if (string.IsNullOrEmpty(json)) return;
        
        if (!isConnected)
        {
            Debug.LogWarning("Cannot send message: Not connected to server");
            QueueMessage(json);
            ConnectToServer();
            return;
        }
        
        try
        {
            await websocket.SendText(json);
        }
        catch (Exception e)
        {
            Debug.LogError("Error sending message: " + e.Message);
            
            if (websocket.State != WebSocketState.Open)
            {
                isConnected = false;
                OnDisconnected?.Invoke("Connection lost while sending message");
                TryReconnect();
            }
        }
    }
    
    private void QueueMessage(string message)
    {
        Debug.Log("Queueing message: " + message);
        messageQueue.Enqueue(message);
        
        // Limit queue size
        if (messageQueue.Count > 10)
        {
            messageQueue.Dequeue(); // Remove oldest message if queue gets too large
        }
    }
    
    private async void OnApplicationQuit()
    {
        // Send end session message
        if (isConnected)
        {
            SendControlMessage("end");
            
            // Close WebSocket
            await websocket.Close();
        }
    }
    
    // Message classes for JSON serialization/deserialization
    [Serializable]
    private class JsonMessage
    {
        public string type;
    }
    
    [Serializable]
    private class BaseMessage
    {
        public string type;
        public string session_id;
        public double timestamp;
    }
    
    [Serializable]
    private class StateUpdateMessage : BaseMessage
    {
        public string previous;
        public string current;
    }
    
    [Serializable]
    private class AudioResponseMessage : BaseMessage
    {
        public string data; // Base64 encoded audio
        public bool interview_complete; // true on the interviewer's closing reply
        public bool more;               // another audio chunk of the same reply follows
        public int seq;                 // chunk number; its mouth cues arrive in a "visemes" message with the same number
    }
    
    [Serializable]
    private class ServerStatusMessage : BaseMessage
    {
        public string text;
    }

    [Serializable]
    private class VisemesMessage : BaseMessage
    {
        public int seq;
        public MouthCue[] cues;
    }

    [Serializable]
    private class ExportSavedMessage : BaseMessage
    {
        public string filename;
        public int questions;
    }

    [Serializable]
    private class CoachProgressMessage : BaseMessage
    {
        public int done;
        public int total;
    }

    [Serializable]
    private class ErrorMessage : BaseMessage
    {
        public int code;
        public string message;
    }
    
    [Serializable]
    private class AudioDataMessage : BaseMessage
    {
        public string data; // Base64 encoded audio
    }
    
    [Serializable]
    private class ControlMessage : BaseMessage
    {
        public string action;
        public string job;   // which job to interview for (only sent with "begin")
        public string interviewer;   // the interviewer's name (begin)
        public string voice;         // her/his voice file, e.g. male_02.wav (begin)
    }
    
    [Serializable]
    private class PingMessage : BaseMessage
    {
        // No additional fields needed
    }
    
    [Serializable]
    private class PlaybackCompleteMessage : BaseMessage
    {
        // No additional fields needed
    }
    
    // Public methods to check connection state
    public bool IsConnected()
    {
        return isConnected;
    }
    
    public string GetSessionId()
    {
        return sessionId;
    }
}