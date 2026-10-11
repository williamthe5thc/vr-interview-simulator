using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using TMPro;
using System;

public class DebugPanel : MonoBehaviour
{
    [Header("References")]
    [SerializeField] private WebSocketManager webSocketManager;
    [SerializeField] private SessionManager sessionManager;
    [SerializeField] private AudioManager audioManager;
    
    [Header("UI Elements")]
    [SerializeField] private GameObject panel;
    [SerializeField] private TextMeshProUGUI connectionStatusText;
    [SerializeField] private Image connectionStatusIndicator;
    [SerializeField] private TextMeshProUGUI currentStateText;
    [SerializeField] private Image stateIndicator;
    [SerializeField] private TextMeshProUGUI logText;
    [SerializeField] private Toggle autoScrollToggle;
    [SerializeField] private Button clearLogButton;
    [SerializeField] private Button hideShowButton;
    [SerializeField] private TextMeshProUGUI hideShowButtonText;
    [SerializeField] private Toggle listenForLogsToggle;
    
    [Header("State Colors")]
    [SerializeField] private Color idleColor = Color.gray;
    [SerializeField] private Color listeningColor = Color.green;
    [SerializeField] private Color processingColor = Color.yellow;
    [SerializeField] private Color respondingColor = Color.blue;
    [SerializeField] private Color waitingColor = Color.cyan;
    [SerializeField] private Color errorColor = Color.red;
    
    private bool isPanelVisible = true;
    private bool isAutoScrollEnabled = true;
    private bool isListeningForLogs = true;
    private List<string> logEntries = new List<string>();
    private int maxLogEntries = 100;
    
    private void Start()
    {
        // Find components if not assigned
        if (webSocketManager == null) webSocketManager = FindObjectOfType<WebSocketManager>();
        if (sessionManager == null) sessionManager = FindObjectOfType<SessionManager>();
        if (audioManager == null) audioManager = FindObjectOfType<AudioManager>();
        
        // Set up UI components
        if (autoScrollToggle != null)
        {
            autoScrollToggle.isOn = isAutoScrollEnabled;
            autoScrollToggle.onValueChanged.AddListener((value) => isAutoScrollEnabled = value);
        }
        
        if (clearLogButton != null)
        {
            clearLogButton.onClick.AddListener(ClearLog);
        }
        
        if (hideShowButton != null)
        {
            hideShowButton.onClick.AddListener(TogglePanel);
        }
        
        if (listenForLogsToggle != null)
        {
            listenForLogsToggle.isOn = isListeningForLogs;
            listenForLogsToggle.onValueChanged.AddListener((value) => isListeningForLogs = value);
        }
        
        // Subscribe to events
        if (webSocketManager != null)
        {
            webSocketManager.OnConnected += () => {
                UpdateConnectionStatus(true);
                AddLog("WebSocket connected");
            };
            
            webSocketManager.OnDisconnected += (reason) => {
                UpdateConnectionStatus(false);
                AddLog($"WebSocket disconnected: {reason}");
            };
            
            webSocketManager.OnError += (error) => {
                AddLog($"WebSocket error: {error}");
            };
            
            webSocketManager.OnStateUpdate += (previous, current, metadata) => {
                UpdateStateDisplay(current);
                AddLog($"State changed: {previous} → {current}");
            };
            
            webSocketManager.OnAudioResponse += (data) => {
                AddLog($"Received audio response: {data.Length} bytes");
            };
        }
        
        // Subscribe to log messages
        Application.logMessageReceived += HandleLog;
        
        // Initial UI update
        UpdateConnectionStatus(false);
        UpdateStateDisplay("IDLE");
        
        AddLog("Debug panel initialized");
    }
    
    private void UpdateConnectionStatus(bool isConnected)
    {
        if (connectionStatusText != null)
        {
            connectionStatusText.text = isConnected ? "Connected" : "Disconnected";
        }
        
        if (connectionStatusIndicator != null)
        {
            connectionStatusIndicator.color = isConnected ? Color.green : Color.red;
        }
    }
    
    private void UpdateStateDisplay(string state)
    {
        if (currentStateText != null)
        {
            currentStateText.text = state;
        }
        
        if (stateIndicator != null)
        {
            // Set color based on state
            switch (state)
            {
                case "IDLE":
                    stateIndicator.color = idleColor;
                    break;
                case "LISTENING":
                    stateIndicator.color = listeningColor;
                    break;
                case "PROCESSING":
                    stateIndicator.color = processingColor;
                    break;
                case "RESPONDING":
                    stateIndicator.color = respondingColor;
                    break;
                case "WAITING":
                    stateIndicator.color = waitingColor;
                    break;
                case "ERROR":
                    stateIndicator.color = errorColor;
                    break;
                default:
                    stateIndicator.color = idleColor;
                    break;
            }
        }
    }
    
    private void AddLog(string message)
    {
        // Create timestamped log entry
        string timestamp = DateTime.Now.ToString("HH:mm:ss.fff");
        string entry = $"[{timestamp}] {message}";
        
        // Add to log entries
        logEntries.Add(entry);
        
        // Limit the number of log entries
        while (logEntries.Count > maxLogEntries)
        {
            logEntries.RemoveAt(0);
        }
        
        // Update log text
        UpdateLogText();
    }
    
    private void UpdateLogText()
    {
        if (logText != null)
        {
            logText.text = string.Join("\n", logEntries);
            
            // Scroll to bottom if auto-scroll is enabled
            if (isAutoScrollEnabled)
            {
                Canvas.ForceUpdateCanvases();
                ScrollRect scrollRect = logText.GetComponentInParent<ScrollRect>();
                if (scrollRect != null)
                {
                    scrollRect.verticalNormalizedPosition = 0;
                }
            }
        }
    }
    
    private void HandleLog(string logString, string stackTrace, LogType type)
    {
        if (!isListeningForLogs) return;
        
        // Only log WebSocketManager, SessionManager, and AudioManager messages
        if (logString.Contains("[WebSocket]") || 
            logString.Contains("[Session]") || 
            logString.Contains("[Audio]") ||
            logString.Contains("[VRInterview]"))
        {
            AddLog(logString);
        }
        else if (type == LogType.Error || type == LogType.Exception)
        {
            // Also log errors and exceptions
            AddLog($"ERROR: {logString}");
        }
    }
    
    private void ClearLog()
    {
        logEntries.Clear();
        UpdateLogText();
    }
    
    private void TogglePanel()
    {
        isPanelVisible = !isPanelVisible;
        
        if (panel != null)
        {
            panel.SetActive(isPanelVisible);
        }
        
        if (hideShowButtonText != null)
        {
            hideShowButtonText.text = isPanelVisible ? "Hide Debug" : "Show Debug";
        }
    }
    
    public void SetPanelVisibility(bool visible)
    {
        isPanelVisible = visible;
        
        if (panel != null)
        {
            panel.SetActive(isPanelVisible);
        }
        
        if (hideShowButtonText != null)
        {
            hideShowButtonText.text = isPanelVisible ? "Hide Debug" : "Show Debug";
        }
    }
    
    private void OnDestroy()
    {
        // Unsubscribe from log messages
        Application.logMessageReceived -= HandleLog;
    }
}
