using System.Collections;
using UnityEngine;
using UnityEngine.UI;
using TMPro;

public class UIManager : MonoBehaviour
{
    [Header("Status Panels")]
    [SerializeField] private GameObject statePanel;
    [SerializeField] private TextMeshProUGUI stateText;
    [SerializeField] private Image stateIndicator;
    
    [Header("Audio Visualization")]
    [SerializeField] private GameObject audioVisualizer;
    [SerializeField] private RectTransform audioLevelBar;
    
    [Header("Progress")]
    [SerializeField] private GameObject progressPanel;
    [SerializeField] private Image progressBarFill;
    
    [Header("Status Messages")]
    [SerializeField] private TextMeshProUGUI statusText;
    [SerializeField] private float statusFadeTime = 5f;
    
    [Header("Error Handling")]
    [SerializeField] private GameObject errorPanel;
    [SerializeField] private TextMeshProUGUI errorText;
    [SerializeField] private Button dismissErrorButton;
    
    [Header("Debug Panel")]
    [SerializeField] private GameObject debugPanel;
    [SerializeField] private TextMeshProUGUI debugText;
    [SerializeField] private Button toggleDebugButton;
    [SerializeField] private ScrollRect debugScrollRect;
    
    [Header("State Colors")]
    [SerializeField] private Color idleColor = Color.gray;
    [SerializeField] private Color listeningColor = Color.green;
    [SerializeField] private Color processingColor = Color.yellow;
    [SerializeField] private Color respondingColor = Color.blue;
    [SerializeField] private Color waitingColor = Color.cyan;
    [SerializeField] private Color errorColor = Color.red;
    
    private bool isDebugVisible = false;
    private Coroutine statusFadeCoroutine;
    
    private void Start()
    {
        // Set up error panel
        if (dismissErrorButton != null)
        {
            dismissErrorButton.onClick.AddListener(HideError);
        }
        
        // Set up debug panel
        if (toggleDebugButton != null)
        {
            toggleDebugButton.onClick.AddListener(ToggleDebugPanel);
        }
        
        // Initialize state display
        UpdateStateDisplay("IDLE");
        
        // Hide error panel initially
        if (errorPanel != null)
        {
            errorPanel.SetActive(false);
        }
        
        // Set debug panel visibility
        if (debugPanel != null)
        {
            debugPanel.SetActive(isDebugVisible);
        }
        
        // Set initial status
        if (statusText != null)
        {
            statusText.text = "Ready to start interview. Say hello to begin.";
            statusText.alpha = 1f;
        }
    }
    
    public void UpdateStateDisplay(string state)
    {
        if (stateText != null)
        {
            stateText.text = state;
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
        
        // Show/hide audio visualizer based on state
        if (audioVisualizer != null)
        {
            audioVisualizer.SetActive(state == "LISTENING");
        }
        
        // Log to debug
        LogDebug($"State changed: {state}");
    }
    
    public void UpdateAudioLevel(float level)
    {
        if (audioLevelBar != null)
        {
            // Scale bar based on audio level (0-1)
            audioLevelBar.localScale = new Vector3(Mathf.Clamp01(level * 5f), 1f, 1f);
        }
    }
    
    /// <summary>
    /// Update the streaming/loading progress bar. Expects a 0-1 value.
    /// The bar hides itself when there is no transfer in flight.
    /// </summary>
    public void UpdateProgressBar(float progress)
    {
        progress = Mathf.Clamp01(progress);
        
        if (progressPanel != null)
        {
            progressPanel.SetActive(progress > 0f && progress < 1f);
        }
        
        if (progressBarFill != null)
        {
            progressBarFill.fillAmount = progress;
        }
    }
    
    /// <summary>
    /// Show the interviewer's response as text when audio playback is
    /// unavailable, so the session can continue without the spoken reply.
    /// </summary>
    public void ShowFallbackText(string text)
    {
        if (string.IsNullOrEmpty(text)) return;
        
        UpdateStatus(text);
        LogDebug($"Fallback text shown (audio unavailable): {text}");
    }
    
    public void UpdateStatus(string message)
    {
        if (statusText == null) return;
        
        // Stop any existing fade
        if (statusFadeCoroutine != null)
        {
            StopCoroutine(statusFadeCoroutine);
        }
        
        // Set new message
        statusText.text = message;
        statusText.alpha = 1f;
        
        // Start fade coroutine for non-critical messages
        if (!message.ToLower().Contains("error"))
        {
            statusFadeCoroutine = StartCoroutine(FadeStatusText());
        }
        
        // Log to debug
        LogDebug($"Status: {message}");
    }
    
    private IEnumerator FadeStatusText()
    {
        // Wait before starting fade
        yield return new WaitForSeconds(statusFadeTime);
        
        // Fade out gradually
        float fadeTime = 1.5f;
        float timer = 0f;
        
        while (timer < fadeTime)
        {
            if (statusText != null)
            {
                float alpha = Mathf.Lerp(1f, 0.2f, timer / fadeTime);
                statusText.alpha = alpha;
            }
            
            timer += Time.deltaTime;
            yield return null;
        }
        
        // Set final alpha
        if (statusText != null)
        {
            statusText.alpha = 0.2f;
        }
    }
    
    public void ShowError(string message)
    {
        if (errorPanel != null && errorText != null)
        {
            errorText.text = message;
            errorPanel.SetActive(true);
            
            // Auto-hide after a delay for non-critical errors
            if (!message.ToLower().Contains("critical") && !message.ToLower().Contains("failed"))
            {
                StartCoroutine(AutoHideError(7f));
            }
        }
        
        // Update status text as well
        UpdateStatus($"Error: {message}");
        
        // Log to debug
        LogDebug($"ERROR: {message}");
    }
    
    public void HideError()
    {
        if (errorPanel != null)
        {
            errorPanel.SetActive(false);
        }
    }
    
    private IEnumerator AutoHideError(float delay)
    {
        yield return new WaitForSeconds(delay);
        HideError();
    }
    
    public void LogDebug(string message)
    {
        if (debugText == null) return;
        
        // Add timestamp
        string timestamp = System.DateTime.Now.ToString("HH:mm:ss");
        string entry = $"[{timestamp}] {message}";
        
        // Add new message
        debugText.text += entry + "\n";
        
        // Scroll to bottom (next frame to ensure layout updates)
        StartCoroutine(ScrollToBottomNextFrame());
        
        // Trim log if too long
        const int maxLines = 100;
        string[] lines = debugText.text.Split('\n');
        if (lines.Length > maxLines)
        {
            string newText = "";
            for (int i = lines.Length - maxLines; i < lines.Length; i++)
            {
                if (!string.IsNullOrEmpty(lines[i]))
                {
                    newText += lines[i] + "\n";
                }
            }
            debugText.text = newText;
        }
    }
    
    private IEnumerator ScrollToBottomNextFrame()
    {
        yield return null; // Wait for next frame
        
        if (debugScrollRect != null)
        {
            debugScrollRect.verticalNormalizedPosition = 0f; // Scroll to bottom
        }
    }
    
    private void ToggleDebugPanel()
    {
        isDebugVisible = !isDebugVisible;
        
        if (debugPanel != null)
        {
            debugPanel.SetActive(isDebugVisible);
        }
    }
    
    // VR-specific UI methods
    public void SetUIDistance(float distance)
    {
        // Adjust UI canvas distance for comfortable viewing in VR
        Canvas[] canvases = GetComponentsInChildren<Canvas>();
        foreach (Canvas canvas in canvases)
        {
            if (canvas.renderMode == RenderMode.WorldSpace)
            {
                // Get direction to current position
                Vector3 direction = canvas.transform.position - Camera.main.transform.position;
                direction.Normalize();
                
                // Set new position at specified distance
                canvas.transform.position = Camera.main.transform.position + direction * distance;
                
                // Make canvas face the camera
                canvas.transform.rotation = Quaternion.LookRotation(direction);
            }
        }
    }
    
    public void ShowInfoPanel(string title, string content, float duration = 0)
    {
        // To be implemented - show a customizable info panel in VR
        // Could be used for tutorial messages, hints, etc.
        
        // For now, just update status
        UpdateStatus(content);
    }
    
    public void EnableLaserPointer(bool enable)
    {
        // To be implemented - enable/disable laser pointer for UI interaction
        // This would integrate with Oculus XR interaction system
    }
}
