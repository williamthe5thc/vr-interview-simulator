using System.Collections;
using UnityEngine;
using UnityEngine.XR;
using UnityEngine.SceneManagement;
using UnityEngine.Android; // Add this import for Android permissions

public class AppManager : MonoBehaviour
{
    [Header("Components")]
    [SerializeField] private WebSocketManager webSocketManager;
    [SerializeField] private SessionManager sessionManager;
    [SerializeField] private AudioManager audioManager;
    [SerializeField] private EnvironmentManager environmentManager;
    [SerializeField] private UIManager uiManager;
    
    [Header("Settings")]
    // YOUR_PC_LAN_IP is a placeholder, set per install.
    [SerializeField] private string serverUrl = "ws://YOUR_PC_LAN_IP:8765";
    [SerializeField] private bool startSessionOnLoad = true;
    [SerializeField] private bool enableDebugMode = false;
    
    private bool isInitialized = false;
    
    // Singleton pattern
    private static AppManager _instance;
    public static AppManager Instance
    {
        get
        {
            if (_instance == null)
            {
                _instance = FindObjectOfType<AppManager>();
                if (_instance == null)
                {
                    GameObject obj = new GameObject("AppManager");
                    _instance = obj.AddComponent<AppManager>();
                }
            }
            return _instance;
        }
    }
    
    private void Awake()
    {
        // Ensure singleton behavior
        if (_instance != null && _instance != this)
        {
            Destroy(gameObject);
            return;
        }
        
        _instance = this;
        DontDestroyOnLoad(gameObject);
    }
    
    private void Start()
    {
        // Initialize components
        InitializeComponents();
        
        // Configure VR settings
        ConfigureVRSettings();
        
        // Start session if enabled
        if (startSessionOnLoad)
        {
            StartCoroutine(StartSessionDelayed(2f));
        }
        
        // Set debug mode
        SetDebugMode(enableDebugMode);
        
        isInitialized = true;
        
        // Log initialization
        Debug.Log("AppManager initialized");
        if (uiManager != null)
        {
            uiManager.LogDebug("VR Interview System initialized");
        }
    }
    
    private void InitializeComponents()
    {
        // Find components if not assigned
        if (webSocketManager == null) webSocketManager = FindObjectOfType<WebSocketManager>();
        if (sessionManager == null) sessionManager = FindObjectOfType<SessionManager>();
        if (audioManager == null) audioManager = FindObjectOfType<AudioManager>();
        if (environmentManager == null) environmentManager = FindObjectOfType<EnvironmentManager>();
        if (uiManager == null) uiManager = FindObjectOfType<UIManager>();
        
        // Create missing components
        if (webSocketManager == null)
        {
            GameObject obj = new GameObject("WebSocketManager");
            webSocketManager = obj.AddComponent<WebSocketManager>();
            obj.transform.SetParent(transform);
        }
        
        if (sessionManager == null)
        {
            GameObject obj = new GameObject("SessionManager");
            sessionManager = obj.AddComponent<SessionManager>();
            obj.transform.SetParent(transform);
        }
        
        if (audioManager == null)
        {
            GameObject obj = new GameObject("AudioManager");
            audioManager = obj.AddComponent<AudioManager>();
            obj.transform.SetParent(transform);
        }
        
        // Set up references between components
        if (webSocketManager != null)
        {
            // Set server URL
            var serverUrlField = webSocketManager.GetType().GetField("serverUrl", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
            if (serverUrlField != null)
            {
                serverUrlField.SetValue(webSocketManager, serverUrl);
            }
            
            // Set component references
            var sessionManagerField = webSocketManager.GetType().GetField("sessionManager", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
            if (sessionManagerField != null)
            {
                sessionManagerField.SetValue(webSocketManager, sessionManager);
            }
            
            var audioManagerField = webSocketManager.GetType().GetField("audioManager", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
            if (audioManagerField != null)
            {
                audioManagerField.SetValue(webSocketManager, audioManager);
            }
            
            var uiManagerField = webSocketManager.GetType().GetField("uiManager", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
            if (uiManagerField != null)
            {
                uiManagerField.SetValue(webSocketManager, uiManager);
            }
        }
        
        if (audioManager != null)
        {
            var webSocketManagerField = audioManager.GetType().GetField("webSocketManager", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
            if (webSocketManagerField != null)
            {
                webSocketManagerField.SetValue(audioManager, webSocketManager);
            }
        }
    }
    
    private void ConfigureVRSettings()
    {
        // Set desired refresh rate for Oculus Quest
        if (XRDevice.refreshRate > 0)
        {
            Application.targetFrameRate = (int)XRDevice.refreshRate;
        }
        else
        {
            Application.targetFrameRate = 72; // Default for Quest
        }
        
        // Set performance level (if available)
        if (Unity.XR.Oculus.Performance.TrySetCPULevel(3))
        {
            Debug.Log("Set CPU performance level to 3");
        }
        
        if (Unity.XR.Oculus.Performance.TrySetGPULevel(3))
        {
            Debug.Log("Set GPU performance level to 3");
        }
        
        // Ensure microphone permission for Android
        #if UNITY_ANDROID && !UNITY_EDITOR
        if (!Permission.HasUserAuthorizedPermission(Permission.Microphone))
        {
            Permission.RequestUserPermission(Permission.Microphone);
        }
        #endif
    }
    
    public void StartSession()
    {
        if (sessionManager != null)
        {
            sessionManager.StartSession();
        }
    }
    
    public void EndSession()
    {
        if (sessionManager != null)
        {
            sessionManager.EndSession();
        }
    }
    
    public void RestartSession()
    {
        if (sessionManager != null)
        {
            sessionManager.ResetSession();
        }
    }
    
    public void LoadEnvironment(string environmentName)
    {
        if (environmentManager != null)
        {
            environmentManager.LoadEnvironment(environmentName);
        }
    }
    
    public void LoadScene(string sceneName)
    {
        StartCoroutine(LoadSceneAsync(sceneName));
    }
    
    private IEnumerator LoadSceneAsync(string sceneName)
    {
        // End any active session
        if (sessionManager != null && sessionManager.IsSessionActive())
        {
            sessionManager.EndSession();
        }
        
        // Display loading message
        if (uiManager != null)
        {
            uiManager.UpdateStatus("Loading...");
        }
        
        // Load the new scene
        AsyncOperation operation = SceneManager.LoadSceneAsync(sceneName);
        
        while (!operation.isDone)
        {
            float progress = Mathf.Clamp01(operation.progress / 0.9f);
            
            // Update loading progress
            if (uiManager != null)
            {
                uiManager.UpdateStatus($"Loading: {progress * 100:F0}%");
            }
            
            yield return null;
        }
    }
    
    private IEnumerator StartSessionDelayed(float delay)
    {
        yield return new WaitForSeconds(delay);
        StartSession();
    }
    
    public void SetDebugMode(bool enabled)
    {
        enableDebugMode = enabled;
        
        // Enable debug logs
        Debug.unityLogger.logEnabled = enabled;
        
        // Show debug UI if available
        if (uiManager != null)
        {
            var debugPanelField = uiManager.GetType().GetField("debugPanel", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
            if (debugPanelField != null)
            {
                GameObject debugPanel = debugPanelField.GetValue(uiManager) as GameObject;
                if (debugPanel != null)
                {
                    debugPanel.SetActive(enabled);
                }
            }
        }
    }
    
    public void QuitApplication()
    {
        StartCoroutine(QuitApplicationDelayed());
    }
    
    private IEnumerator QuitApplicationDelayed()
    {
        // End session if active
        if (sessionManager != null && sessionManager.IsSessionActive())
        {
            sessionManager.EndSession();
            yield return new WaitForSeconds(0.5f);
        }
        
        // Close WebSocket connection if connected
        if (webSocketManager != null)
        {
            var websocketField = webSocketManager.GetType().GetField("websocket", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
            if (websocketField != null)
            {
                var websocket = websocketField.GetValue(webSocketManager);
                if (websocket != null)
                {
                    var closeMethod = websocket.GetType().GetMethod("Close");
                    if (closeMethod != null)
                    {
                        closeMethod.Invoke(websocket, null);
                        yield return new WaitForSeconds(0.5f);
                    }
                }
            }
        }
        
        // Quit application
        #if UNITY_EDITOR
        UnityEditor.EditorApplication.isPlaying = false;
        #else
        Application.Quit();
        #endif
    }
}
