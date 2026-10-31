using UnityEngine;
using UnityEngine.UI;
using TMPro;

public class ServerConnectionTesterUI : MonoBehaviour
{
    [Header("Main Components")]
    [SerializeField] private ServerConnectionTester tester;
    [SerializeField] private GameObject uiPanel;
    
    [Header("UI Elements")]
    [SerializeField] private TMP_InputField serverUrlInput;
    [SerializeField] private Button applyUrlButton;
    [SerializeField] private Button showHideButton;
    [SerializeField] private TextMeshProUGUI showHideButtonText;
    
    [Header("Additional Buttons")]
    [SerializeField] private Button startSessionButton;
    [SerializeField] private Button endSessionButton;
    [SerializeField] private Button resetSessionButton;
    
    private bool isUIVisible = true;
    
    private void Start()
    {
        // Set up event handlers
        if (applyUrlButton != null && serverUrlInput != null && tester != null)
        {
            applyUrlButton.onClick.AddListener(() => {
                string fieldUrl = serverUrlInput.text;
                if (!fieldUrl.StartsWith("http://") && !fieldUrl.StartsWith("https://"))
                {
                    fieldUrl = "http://" + fieldUrl;
                }
                
                // Use reflection to set the URL since it's private
                var urlField = tester.GetType().GetField("serverUrl", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
                if (urlField != null)
                {
                    urlField.SetValue(tester, fieldUrl);
                    Debug.Log($"Server URL set to: {fieldUrl}");
                }
            });
        }
        
        if (showHideButton != null)
        {
            showHideButton.onClick.AddListener(ToggleUIVisibility);
        }
        
        // Set up session control buttons
        if (startSessionButton != null && tester != null)
        {
            startSessionButton.onClick.AddListener(() => tester.StartSession());
        }
        
        if (endSessionButton != null && tester != null)
        {
            endSessionButton.onClick.AddListener(() => tester.EndSession());
        }
        
        if (resetSessionButton != null && tester != null)
        {
            resetSessionButton.onClick.AddListener(() => tester.ResetSession());
        }
        
        // Set initial URL in the input field
        if (serverUrlInput != null && tester != null)
        {
            var urlField = tester.GetType().GetField("serverUrl", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
            if (urlField != null)
            {
                string currentUrl = (string)urlField.GetValue(tester);
                serverUrlInput.text = currentUrl;
            }
        }
    }
    
    private void ToggleUIVisibility()
    {
        isUIVisible = !isUIVisible;
        
        if (uiPanel != null)
        {
            uiPanel.SetActive(isUIVisible);
        }
        
        if (showHideButtonText != null)
        {
            showHideButtonText.text = isUIVisible ? "Hide Panel" : "Show Panel";
        }
    }
    
    // Method to allow toggling from other scripts
    public void SetUIVisibility(bool visible)
    {
        isUIVisible = visible;
        
        if (uiPanel != null)
        {
            uiPanel.SetActive(isUIVisible);
        }
        
        if (showHideButtonText != null)
        {
            showHideButtonText.text = isUIVisible ? "Hide Panel" : "Show Panel";
        }
    }
}
