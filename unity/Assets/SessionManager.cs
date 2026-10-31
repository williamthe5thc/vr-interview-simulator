using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class SessionManager : MonoBehaviour
{
    [Header("Components")]
    [SerializeField] private WebSocketManager webSocketManager;
    [SerializeField] private AudioManager audioManager;
    [SerializeField] private AvatarController avatarController;

    /// <summary>Use another interviewer (the cast rotates between interviews).</summary>
    public void SetAvatar(AvatarController avatar) => avatarController = avatar;
    [SerializeField] private UIManager uiManager;
    
    [Header("Settings")]
    [SerializeField] private float idleTimeoutSeconds = 90f;
    
    // Current state
    private string currentState = "IDLE";
    private bool isSessionActive = false;
    private Coroutine idleTimeoutCoroutine;
    private bool isPlayingResponse = false;
    
    // Events
    public event Action<string, string> OnStateChanged;
    public event Action OnSessionStarted;
    public event Action OnSessionEnded;
    
    private void Start()
    {
        // Register for WebSocket events
        if (webSocketManager != null)
        {
            webSocketManager.OnStateUpdate += HandleStateUpdate;
            webSocketManager.OnConnected += HandleConnected;
        }
        
        // Register for audio events
        if (audioManager != null)
        {
            audioManager.OnPlaybackStarted += HandlePlaybackStarted;
            audioManager.OnPlaybackCompleted += HandlePlaybackCompleted;
        }
    }
    
    public void StartSession()
    {
        if (isSessionActive) return;
        
        // Set session as active
        isSessionActive = true;
        
        // Send start message to server
        if (webSocketManager != null)
        {
            webSocketManager.SendControlMessage("start");
        }
        
        // Fire event
        OnSessionStarted?.Invoke();
        
        // Set initial state
        UpdateState("IDLE", "IDLE");
        
        Debug.Log("Interview session started");
        
        // Show UI message
        if (uiManager != null)
        {
            uiManager.UpdateStatus("Interview session started. Say hello to begin.");
        }
    }
    
    public void EndSession()
    {
        if (!isSessionActive) return;
        
        // Send end message to server
        if (webSocketManager != null)
        {
            webSocketManager.SendControlMessage("end");
        }
        
        // Stop any active processing. Clear the flag first so the forced
        // StopPlayback below does not emit a playback_complete after "end".
        isPlayingResponse = false;
        
        if (audioManager != null)
        {
            audioManager.StopRecording();
            audioManager.StopPlayback();
        }
        
        // Set session as inactive
        isSessionActive = false;
        
        // Fire event
        OnSessionEnded?.Invoke();
        
        // Reset state
        UpdateState(currentState, "IDLE");
        
        Debug.Log("Interview session ended");
        
        // Show UI message
        if (uiManager != null)
        {
            uiManager.UpdateStatus("Interview session ended.");
        }
    }
    
    public void ResetSession()
    {
        // End current session if active
        if (isSessionActive)
        {
            EndSession();
        }
        
        // Start a new session
        StartSession();
    }
    
    public void UpdateState(string previousState, string newState)
    {
        string oldState = currentState;
        currentState = newState;
        
        // Handle state-specific actions
        switch (newState)
        {
            case "IDLE":
                HandleIdleState();
                break;
                
            case "LISTENING":
                HandleListeningState();
                break;
                
            // The server reports each processing stage separately; all of them are "thinking" for the avatar.
            case "PROCESSING":
            case "PROCESSING_STT":
            case "PROCESSING_LLM":
            case "PROCESSING_TTS":
                HandleProcessingState();
                break;
                
            case "RESPONDING":
                HandleRespondingState();
                break;
                
            case "WAITING":
                HandleWaitingState();
                break;
                
            case "ERROR":
                HandleErrorState();
                break;
                
            default:
                Debug.LogWarning($"Unknown state: {newState}");
                break;
        }
        
        // Notify state change
        OnStateChanged?.Invoke(oldState, newState);
        
        Debug.Log($"Session state changed: {oldState} → {newState}");
    }
    
    private void HandleStateUpdate(string previousState, string newState, Dictionary<string, object> metadata)
    {
        // Update our state
        UpdateState(previousState, newState);
    }
    
    private void HandleConnected()
    {
        // Start session if not already active
        if (!isSessionActive)
        {
            StartSession();
            return;
        }
        
        // The session was already running and the socket reconnected. Re-announce
        // it on the new connection without restarting the local session state.
        if (webSocketManager != null)
        {
            webSocketManager.SendControlMessage("start");
        }
    }
    
    private void HandlePlaybackStarted()
    {
        // We now owe the server a playback_complete for this response.
        isPlayingResponse = true;
    }
    
    private void HandlePlaybackCompleted()
    {
        // Notify the server that playback finished.
        //
        // This used to be gated on currentState == "RESPONDING". Playback
        // completion arrives from a coroutine after the clip's full duration,
        // by which point the server may already have advanced us to WAITING -
        // the notification was then dropped and the server waited forever.
        // Gate on "did we actually start playing a response" instead.
        if (!isPlayingResponse) return;
        
        isPlayingResponse = false;
        
        if (webSocketManager != null)
        {
            webSocketManager.NotifyPlaybackComplete();
        }
    }
    
    private void HandleIdleState()
    {
        // Stop any idle timeout
        StopIdleTimeout();
        
        // Update avatar
        if (avatarController != null)
        {
            avatarController.SetIdleState();
        }
        
        // Update UI
        if (uiManager != null)
        {
            uiManager.UpdateStateDisplay("IDLE");
        }
    }
    
    private void HandleListeningState()
    {
        // Stop any idle timeout
        StopIdleTimeout();
        
        // Start recording if not already (push-to-talk turns this off: the server enters LISTENING only after the
        // audio has already been sent, so recording again here would capture and send a stray second clip)
        if (audioManager != null && audioManager.ServerDrivenRecording && !audioManager.IsRecording)
        {
            audioManager.StartRecording();
        }
        
        // Update avatar
        if (avatarController != null)
        {
            avatarController.SetListeningState();
        }
        
        // Update UI
        if (uiManager != null)
        {
            uiManager.UpdateStateDisplay("LISTENING");
            uiManager.UpdateStatus("Listening...");
        }
    }
    
    private void HandleProcessingState()
    {
        // Stop recording if still recording
        if (audioManager != null && audioManager.IsRecording)
        {
            audioManager.StopRecording();
        }
        
        // Update avatar
        if (avatarController != null)
        {
            avatarController.SetThinkingState();
        }
        
        // Update UI
        if (uiManager != null)
        {
            uiManager.UpdateStateDisplay("PROCESSING");
            uiManager.UpdateStatus("Processing your question...");
        }
    }
    
    private void HandleRespondingState()
    {
        // Update avatar
        if (avatarController != null)
        {
            avatarController.SetSpeakingState();
        }
        
        // Update UI
        if (uiManager != null)
        {
            uiManager.UpdateStateDisplay("RESPONDING");
            uiManager.UpdateStatus("Interviewer is speaking...");
        }
    }
    
    private void HandleWaitingState()
    {
        // Start idle timeout
        StartIdleTimeout();
        
        // Update avatar
        if (avatarController != null)
        {
            avatarController.SetAttentiveState();
        }
        
        // Update UI
        if (uiManager != null)
        {
            uiManager.UpdateStateDisplay("WAITING");
            uiManager.UpdateStatus("Waiting for your response...");
        }
    }
    
    private void HandleErrorState()
    {
        // Update avatar
        if (avatarController != null)
        {
            avatarController.SetConfusedState();
        }
        
        // Update UI
        if (uiManager != null)
        {
            uiManager.UpdateStateDisplay("ERROR");
            uiManager.UpdateStatus("There was an error. Please try again.");
        }
    }
    
    /// <summary>Push-to-talk is recording: the candidate is answering, so the idle clock must not run.</summary>
    public void PauseIdleTimeout() => StopIdleTimeout();

    /// <summary>Push-to-talk released without sending anything: the server is still WAITING, so start the clock again.</summary>
    public void ResumeIdleTimeout()
    {
        if (currentState == "WAITING") StartIdleTimeout();
    }

    private void StartIdleTimeout()
    {
        // Stop existing timeout if any
        StopIdleTimeout();
        
        // Start new timeout
        idleTimeoutCoroutine = StartCoroutine(IdleTimeoutCoroutine());
    }
    
    private void StopIdleTimeout()
    {
        if (idleTimeoutCoroutine != null)
        {
            StopCoroutine(idleTimeoutCoroutine);
            idleTimeoutCoroutine = null;
        }
    }
    
    private IEnumerator IdleTimeoutCoroutine()
    {
        float timer = 0f;
        
        while (timer < idleTimeoutSeconds)
        {
            yield return null;
            timer += Time.deltaTime;
            
            // Show countdown when getting close to timeout
            if (timer > idleTimeoutSeconds - 10f && uiManager != null)
            {
                int remainingSeconds = Mathf.CeilToInt(idleTimeoutSeconds - timer);
                uiManager.UpdateStatus($"Waiting for your response... ({remainingSeconds}s)");
            }
        }
        
        // Timeout reached, return to idle state
        Debug.Log("Idle timeout reached, returning to IDLE state");
        
        // Send control message to server
        if (webSocketManager != null)
        {
            webSocketManager.SendControlMessage("timeout");
        }
        
        // Update state locally
        UpdateState(currentState, "IDLE");
        
        // Show UI message
        if (uiManager != null)
        {
            uiManager.UpdateStatus("Session timed out due to inactivity. Say hello to continue.");
        }
    }
    
    public string GetCurrentState()
    {
        return currentState;
    }
    
    public bool IsSessionActive()
    {
        return isSessionActive;
    }
}
