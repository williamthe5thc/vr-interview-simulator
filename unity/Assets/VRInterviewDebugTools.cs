using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using TMPro;

/// <summary>
/// Creates a debug UI system for the VR Interview System.
/// Add this to any GameObject in your scene to automatically create debug tools.
/// </summary>
public class VRInterviewDebugTools : MonoBehaviour
{
    [Header("Debug Settings")]
    [SerializeField] private bool createOnStart = true;
    [SerializeField] private bool showConnectionTester = true;
    [SerializeField] private bool showSystemTester = true;
    [SerializeField] private bool showDebugPanel = true;
    
    [Header("UI Settings")]
    [SerializeField] private Canvas existingCanvas;
    [SerializeField] private string serverUrl = "http://YOUR_PC_LAN_IP:8765";
    
    private GameObject debugCanvas;
    private ServerConnectionTester connectionTester;
    private SystemIntegrityTest systemTester;
    private DebugPanel debugPanel;
    
    void Start()
    {
        if (createOnStart)
        {
            CreateDebugTools();
        }
    }
    
    public void CreateDebugTools()
    {
        // Find or create a canvas
        Canvas canvas = existingCanvas;
        if (canvas == null)
        {
            // Create a new canvas for debug UI
            debugCanvas = new GameObject("VRInterviewDebugCanvas");
            canvas = debugCanvas.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.WorldSpace;
            
            // Position the canvas in front of the camera
            Camera mainCamera = Camera.main;
            if (mainCamera != null)
            {
                canvas.transform.position = mainCamera.transform.position + mainCamera.transform.forward * 1.5f;
                canvas.transform.rotation = mainCamera.transform.rotation;
                canvas.transform.localScale = new Vector3(0.001f, 0.001f, 0.001f); // Scale for VR readability
            }
            
            // Add a canvas scaler
            CanvasScaler scaler = debugCanvas.AddComponent<CanvasScaler>();
            scaler.dynamicPixelsPerUnit = 100;
            scaler.referencePixelsPerUnit = 100;
            
            // Add a GraphicRaycaster for UI interaction
            debugCanvas.AddComponent<GraphicRaycaster>();
        }
        
        // Create a background panel
        GameObject panel = new GameObject("DebugPanel");
        panel.transform.SetParent(canvas.transform, false);
        
        RectTransform panelRect = panel.AddComponent<RectTransform>();
        panelRect.anchorMin = new Vector2(0, 0);
        panelRect.anchorMax = new Vector2(1, 1);
        panelRect.offsetMin = new Vector2(10, 10);
        panelRect.offsetMax = new Vector2(-10, -10);
        
        Image panelImage = panel.AddComponent<Image>();
        panelImage.color = new Color(0.1f, 0.1f, 0.1f, 0.8f);
        
        // Add a layout group
        VerticalLayoutGroup layout = panel.AddComponent<VerticalLayoutGroup>();
        layout.padding = new RectOffset(10, 10, 10, 10);
        layout.spacing = 10;
        layout.childAlignment = TextAnchor.UpperCenter;
        layout.childControlHeight = true;
        layout.childControlWidth = true;
        layout.childForceExpandHeight = false;
        layout.childForceExpandWidth = true;
        
        // Create header
        GameObject header = CreateTextObject("Header", panel.transform, "VR INTERVIEW SYSTEM DEBUG TOOLS");
        header.GetComponent<TextMeshProUGUI>().fontSize = 24;
        header.GetComponent<TextMeshProUGUI>().color = Color.white;
        
        // Create debug tools based on settings
        if (showConnectionTester)
        {
            CreateConnectionTester(panel.transform);
        }
        
        if (showSystemTester)
        {
            CreateSystemTester(panel.transform);
        }
        
        if (showDebugPanel)
        {
            CreateDebugPanel(panel.transform);
        }
        
        // Create a close button
        GameObject closeButtonObj = new GameObject("CloseButton");
        closeButtonObj.transform.SetParent(panel.transform, false);
        
        RectTransform closeRect = closeButtonObj.AddComponent<RectTransform>();
        closeRect.sizeDelta = new Vector2(100, 40);
        
        Button closeButton = closeButtonObj.AddComponent<Button>();
        Image closeImage = closeButtonObj.AddComponent<Image>();
        closeImage.color = new Color(0.7f, 0.2f, 0.2f);
        
        GameObject closeText = CreateTextObject("CloseText", closeButtonObj.transform, "CLOSE");
        
        // Add click handler to close debug panel
        closeButton.onClick.AddListener(() => {
            gameObject.SetActive(false);
        });
        
        // Make panel draggable
        panel.AddComponent<DragPanel>();
    }
    
    private void CreateConnectionTester(Transform parent)
    {
        // Create a group for the connection tester
        GameObject testerGroup = new GameObject("ConnectionTesterGroup");
        testerGroup.transform.SetParent(parent, false);
        
        // Create section title
        GameObject title = CreateTextObject("Title", testerGroup.transform, "SERVER CONNECTION TESTER");
        title.GetComponent<TextMeshProUGUI>().fontSize = 18;
        title.GetComponent<TextMeshProUGUI>().color = new Color(0.4f, 0.8f, 1.0f);
        
        // Add the ServerConnectionTester component
        connectionTester = testerGroup.AddComponent<ServerConnectionTester>();
        
        // Set the server URL using reflection
        System.Reflection.FieldInfo urlField = typeof(ServerConnectionTester).GetField("serverUrl", 
            System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
        if (urlField != null)
        {
            urlField.SetValue(connectionTester, serverUrl);
        }
        
        // Create the UI elements
        GameObject statusObj = CreateTextObject("StatusText", testerGroup.transform, "Ready to test connection");
        TextMeshProUGUI statusText = statusObj.GetComponent<TextMeshProUGUI>();
        
        GameObject indicatorObj = new GameObject("ConnectionIndicator");
        indicatorObj.transform.SetParent(testerGroup.transform, false);
        RectTransform indicatorRect = indicatorObj.AddComponent<RectTransform>();
        indicatorRect.sizeDelta = new Vector2(20, 20);
        Image connectionIndicator = indicatorObj.AddComponent<Image>();
        connectionIndicator.color = Color.gray;
        
        // Create test button
        GameObject testButtonObj = CreateButton("TestConnectionButton", testerGroup.transform, "Test Connection");
        Button testConnectionButton = testButtonObj.GetComponent<Button>();
        testConnectionButton.onClick.AddListener(() => connectionTester.TestConnection());
        
        // Create ping button
        GameObject pingButtonObj = CreateButton("PingButton", testerGroup.transform, "Send Ping");
        Button sendPingButton = pingButtonObj.GetComponent<Button>();
        sendPingButton.onClick.AddListener(() => connectionTester.SendPing());
        
        // Create audio test button
        GameObject audioButtonObj = CreateButton("AudioTestButton", testerGroup.transform, "Test Audio");
        Button simulateAudioButton = audioButtonObj.GetComponent<Button>();
        simulateAudioButton.onClick.AddListener(() => connectionTester.SimulateAudioSend());
        
        // Create auto-test toggle
        GameObject toggleObj = CreateToggle("AutoTestToggle", testerGroup.transform, "Auto-Test Connection");
        Toggle autoTestToggle = toggleObj.GetComponent<Toggle>();
        
        // Create log area
        GameObject logObj = CreateTextObject("LogText", testerGroup.transform, "");
        TextMeshProUGUI logText = logObj.GetComponent<TextMeshProUGUI>();
        logText.fontSize = 12;
        RectTransform logRect = logObj.GetComponent<RectTransform>();
        logRect.sizeDelta = new Vector2(0, 100);
        
        // Connect UI references to the tester
        System.Reflection.FieldInfo statusTextField = typeof(ServerConnectionTester).GetField("statusText", 
            System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
        if (statusTextField != null) statusTextField.SetValue(connectionTester, statusText);
        
        System.Reflection.FieldInfo connectionIndicatorField = typeof(ServerConnectionTester).GetField("connectionIndicator", 
            System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
        if (connectionIndicatorField != null) connectionIndicatorField.SetValue(connectionTester, connectionIndicator);
        
        System.Reflection.FieldInfo testConnectionButtonField = typeof(ServerConnectionTester).GetField("testConnectionButton", 
            System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
        if (testConnectionButtonField != null) testConnectionButtonField.SetValue(connectionTester, testConnectionButton);
        
        System.Reflection.FieldInfo sendPingButtonField = typeof(ServerConnectionTester).GetField("sendPingButton", 
            System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
        if (sendPingButtonField != null) sendPingButtonField.SetValue(connectionTester, sendPingButton);
        
        System.Reflection.FieldInfo simulateAudioButtonField = typeof(ServerConnectionTester).GetField("simulateAudioButton", 
            System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
        if (simulateAudioButtonField != null) simulateAudioButtonField.SetValue(connectionTester, simulateAudioButton);
        
        System.Reflection.FieldInfo autoTestToggleField = typeof(ServerConnectionTester).GetField("autoTestToggle", 
            System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
        if (autoTestToggleField != null) autoTestToggleField.SetValue(connectionTester, autoTestToggle);
        
        System.Reflection.FieldInfo logTextField = typeof(ServerConnectionTester).GetField("logText", 
            System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
        if (logTextField != null) logTextField.SetValue(connectionTester, logText);
    }
    
    private void CreateSystemTester(Transform parent)
    {
        // Create a group for the system tester
        GameObject testerGroup = new GameObject("SystemTesterGroup");
        testerGroup.transform.SetParent(parent, false);
        
        // Create section title
        GameObject title = CreateTextObject("Title", testerGroup.transform, "SYSTEM INTEGRITY TESTER");
        title.GetComponent<TextMeshProUGUI>().fontSize = 18;
        title.GetComponent<TextMeshProUGUI>().color = new Color(0.4f, 1.0f, 0.8f);
        
        // Add the SystemIntegrityTest component
        systemTester = testerGroup.AddComponent<SystemIntegrityTest>();
        
        // Create run test button
        GameObject runTestButtonObj = CreateButton("RunTestButton", testerGroup.transform, "Run System Tests");
        Button runTestButton = runTestButtonObj.GetComponent<Button>();
        runTestButton.onClick.AddListener(() => systemTester.StartTests());
        
        // Create test output area
        GameObject outputObj = CreateTextObject("TestOutput", testerGroup.transform, "Click 'Run System Tests' to begin testing");
        TextMeshProUGUI testOutputText = outputObj.GetComponent<TextMeshProUGUI>();
        testOutputText.fontSize = 12;
        RectTransform outputRect = outputObj.GetComponent<RectTransform>();
        outputRect.sizeDelta = new Vector2(0, 150);
        
        // Connect the output text to the system tester
        System.Reflection.FieldInfo testOutputField = typeof(SystemIntegrityTest).GetField("testOutputText", 
            System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
        if (testOutputField != null) testOutputField.SetValue(systemTester, testOutputText);
    }
    
    private void CreateDebugPanel(Transform parent)
    {
        // Create a group for the debug panel
        GameObject debugGroup = new GameObject("DebugPanelGroup");
        debugGroup.transform.SetParent(parent, false);
        
        // Create section title
        GameObject title = CreateTextObject("Title", debugGroup.transform, "REAL-TIME DEBUG MONITOR");
        title.GetComponent<TextMeshProUGUI>().fontSize = 18;
        title.GetComponent<TextMeshProUGUI>().color = new Color(1.0f, 0.8f, 0.4f);
        
        // Add the DebugPanel component
        debugPanel = debugGroup.AddComponent<DebugPanel>();
        
        // Create status elements
        GameObject connectionStatusObj = CreateTextObject("ConnectionStatus", debugGroup.transform, "Connection: Unknown");
        TextMeshProUGUI connectionStatusText = connectionStatusObj.GetComponent<TextMeshProUGUI>();
        
        GameObject connectionIndicatorObj = new GameObject("ConnectionStatusIndicator");
        connectionIndicatorObj.transform.SetParent(debugGroup.transform, false);
        RectTransform indicatorRect = connectionIndicatorObj.AddComponent<RectTransform>();
        indicatorRect.sizeDelta = new Vector2(20, 20);
        Image connectionStatusIndicator = connectionIndicatorObj.AddComponent<Image>();
        connectionStatusIndicator.color = Color.gray;
        
        GameObject stateTextObj = CreateTextObject("CurrentState", debugGroup.transform, "State: IDLE");
        TextMeshProUGUI currentStateText = stateTextObj.GetComponent<TextMeshProUGUI>();
        
        GameObject stateIndicatorObj = new GameObject("StateIndicator");
        stateIndicatorObj.transform.SetParent(debugGroup.transform, false);
        RectTransform stateRect = stateIndicatorObj.AddComponent<RectTransform>();
        stateRect.sizeDelta = new Vector2(20, 20);
        Image stateIndicator = stateIndicatorObj.AddComponent<Image>();
        stateIndicator.color = Color.gray;
        
        // Create log area
        GameObject logObj = CreateTextObject("LogText", debugGroup.transform, "Debug logs will appear here...");
        TextMeshProUGUI logText = logObj.GetComponent<TextMeshProUGUI>();
        logText.fontSize = 12;
        RectTransform logRect = logObj.GetComponent<RectTransform>();
        logRect.sizeDelta = new Vector2(0, 150);
        
        // Create control buttons
        GameObject clearLogButtonObj = CreateButton("ClearLogButton", debugGroup.transform, "Clear Log");
        Button clearLogButton = clearLogButtonObj.GetComponent<Button>();
        
        GameObject toggleLogButtonObj = CreateToggle("ListenForLogsToggle", debugGroup.transform, "Listen For Logs");
        Toggle listenForLogsToggle = toggleLogButtonObj.GetComponent<Toggle>();
        listenForLogsToggle.isOn = true;
        
        // Connect UI references to the debug panel
        System.Reflection.FieldInfo connectionStatusTextField = typeof(DebugPanel).GetField("connectionStatusText", 
            System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
        if (connectionStatusTextField != null) connectionStatusTextField.SetValue(debugPanel, connectionStatusText);
        
        System.Reflection.FieldInfo connectionStatusIndicatorField = typeof(DebugPanel).GetField("connectionStatusIndicator", 
            System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
        if (connectionStatusIndicatorField != null) connectionStatusIndicatorField.SetValue(debugPanel, connectionStatusIndicator);
        
        System.Reflection.FieldInfo currentStateTextField = typeof(DebugPanel).GetField("currentStateText", 
            System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
        if (currentStateTextField != null) currentStateTextField.SetValue(debugPanel, currentStateText);
        
        System.Reflection.FieldInfo stateIndicatorField = typeof(DebugPanel).GetField("stateIndicator", 
            System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
        if (stateIndicatorField != null) stateIndicatorField.SetValue(debugPanel, stateIndicator);
        
        System.Reflection.FieldInfo logTextField = typeof(DebugPanel).GetField("logText", 
            System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
        if (logTextField != null) logTextField.SetValue(debugPanel, logText);
        
        System.Reflection.FieldInfo clearLogButtonField = typeof(DebugPanel).GetField("clearLogButton", 
            System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
        if (clearLogButtonField != null) clearLogButtonField.SetValue(debugPanel, clearLogButton);
        
        System.Reflection.FieldInfo listenForLogsToggleField = typeof(DebugPanel).GetField("listenForLogsToggle", 
            System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
        if (listenForLogsToggleField != null) listenForLogsToggleField.SetValue(debugPanel, listenForLogsToggle);
    }
    
    // Helper methods for creating UI elements
    private GameObject CreateTextObject(string name, Transform parent, string text)
    {
        GameObject textObject = new GameObject(name);
        textObject.transform.SetParent(parent, false);
        
        RectTransform rect = textObject.AddComponent<RectTransform>();
        rect.anchorMin = new Vector2(0, 0);
        rect.anchorMax = new Vector2(1, 0);
        rect.sizeDelta = new Vector2(0, 30);
        
        TextMeshProUGUI textComponent = textObject.AddComponent<TextMeshProUGUI>();
        textComponent.text = text;
        textComponent.fontSize = 14;
        textComponent.color = Color.white;
        textComponent.alignment = TextAlignmentOptions.Center;
        
        return textObject;
    }
    
    private GameObject CreateButton(string name, Transform parent, string text)
    {
        GameObject buttonObj = new GameObject(name);
        buttonObj.transform.SetParent(parent, false);
        
        RectTransform rect = buttonObj.AddComponent<RectTransform>();
        rect.sizeDelta = new Vector2(150, 30);
        
        Button button = buttonObj.AddComponent<Button>();
        Image buttonImage = buttonObj.AddComponent<Image>();
        buttonImage.color = new Color(0.2f, 0.3f, 0.4f);
        
        GameObject textObj = CreateTextObject("Text", buttonObj.transform, text);
        RectTransform textRect = textObj.GetComponent<RectTransform>();
        textRect.anchorMin = new Vector2(0, 0);
        textRect.anchorMax = new Vector2(1, 1);
        textRect.offsetMin = Vector2.zero;
        textRect.offsetMax = Vector2.zero;
        
        ColorBlock colors = button.colors;
        colors.normalColor = new Color(0.2f, 0.3f, 0.4f);
        colors.highlightedColor = new Color(0.3f, 0.4f, 0.5f);
        colors.pressedColor = new Color(0.1f, 0.2f, 0.3f);
        button.colors = colors;
        
        return buttonObj;
    }
    
    private GameObject CreateToggle(string name, Transform parent, string text)
    {
        GameObject toggleObj = new GameObject(name);
        toggleObj.transform.SetParent(parent, false);
        
        RectTransform rect = toggleObj.AddComponent<RectTransform>();
        rect.sizeDelta = new Vector2(200, 30);
        
        Toggle toggle = toggleObj.AddComponent<Toggle>();
        
        // Create background
        GameObject background = new GameObject("Background");
        background.transform.SetParent(toggleObj.transform, false);
        RectTransform bgRect = background.AddComponent<RectTransform>();
        bgRect.anchorMin = new Vector2(0, 0.5f);
        bgRect.anchorMax = new Vector2(0, 0.5f);
        bgRect.sizeDelta = new Vector2(20, 20);
        bgRect.anchoredPosition = new Vector2(10, 0);
        Image bgImage = background.AddComponent<Image>();
        bgImage.color = new Color(0.2f, 0.2f, 0.2f);
        
        // Create checkmark
        GameObject checkmark = new GameObject("Checkmark");
        checkmark.transform.SetParent(background.transform, false);
        RectTransform checkRect = checkmark.AddComponent<RectTransform>();
        checkRect.anchorMin = Vector2.zero;
        checkRect.anchorMax = Vector2.one;
        checkRect.offsetMin = new Vector2(4, 4);
        checkRect.offsetMax = new Vector2(-4, -4);
        Image checkImage = checkmark.AddComponent<Image>();
        checkImage.color = new Color(0.2f, 0.8f, 0.2f);
        
        // Create label
        GameObject label = CreateTextObject("Label", toggleObj.transform, text);
        RectTransform labelRect = label.GetComponent<RectTransform>();
        labelRect.anchorMin = new Vector2(0, 0);
        labelRect.anchorMax = new Vector2(1, 1);
        labelRect.offsetMin = new Vector2(35, 0);
        labelRect.offsetMax = Vector2.zero;
        label.GetComponent<TextMeshProUGUI>().alignment = TextAlignmentOptions.Left;
        
        // Set up the toggle component
        toggle.targetGraphic = bgImage;
        toggle.graphic = checkImage;
        
        return toggleObj;
    }
}

/// <summary>
/// Simple draggable panel component
/// </summary>
public class DragPanel : MonoBehaviour
{
    private RectTransform rectTransform;
    private Canvas canvas;
    private bool isDragging = false;
    private Vector2 dragOffset;
    
    private void Awake()
    {
        rectTransform = GetComponent<RectTransform>();
        canvas = GetComponentInParent<Canvas>();
    }
    
    public void OnBeginDrag()
    {
        isDragging = true;
        RectTransformUtility.ScreenPointToLocalPointInRectangle(rectTransform, Input.mousePosition, canvas.worldCamera, out dragOffset);
    }
    
    public void OnDrag()
    {
        if (!isDragging) return;
        
        Vector2 localPoint;
        RectTransformUtility.ScreenPointToLocalPointInRectangle(rectTransform.parent as RectTransform, Input.mousePosition, canvas.worldCamera, out localPoint);
        rectTransform.localPosition = localPoint - dragOffset;
    }
    
    public void OnEndDrag()
    {
        isDragging = false;
    }
    
    private void Update()
    {
        if (Input.GetMouseButtonDown(0))
        {
            if (RectTransformUtility.RectangleContainsScreenPoint(rectTransform, Input.mousePosition, canvas.worldCamera))
            {
                OnBeginDrag();
            }
        }
        
        if (Input.GetMouseButton(0) && isDragging)
        {
            OnDrag();
        }
        
        if (Input.GetMouseButtonUp(0) && isDragging)
        {
            OnEndDrag();
        }
    }
}
