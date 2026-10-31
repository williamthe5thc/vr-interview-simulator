using UnityEngine;
using UnityEngine.UI;
using TMPro; // Add this for TextMeshPro support

public class ButtonController : MonoBehaviour
{
    [Header("References")]
    public AudioManager audioManager;
    public Button startButton;
    public Button stopButton;
    
    [Header("Feedback")]
    public TMP_Text statusText;  // Changed from Text to TMP_Text
    
    void Start()
    {
        // Find AudioManager if not set
        if (audioManager == null)
            audioManager = FindObjectOfType<AudioManager>();
            
        // Set up button listeners
        if (startButton != null)
            startButton.onClick.AddListener(StartRecording);
            
        if (stopButton != null)
            stopButton.onClick.AddListener(StopRecording);
    }
    
    void Update()
    {
        // Optional: Update button visuals based on recording state
        if (audioManager != null && startButton != null && stopButton != null)
        {
            // Update button colors based on current state
            startButton.interactable = !audioManager.IsRecording;
            stopButton.interactable = audioManager.IsRecording;
        }
    }
    
    public void StartRecording()
    {
        Debug.Log("Start Recording button pressed!");
        
        if (startButton != null)
            startButton.GetComponent<Image>().color = Color.green;
        
        if (stopButton != null)
            stopButton.GetComponent<Image>().color = Color.white;
        
        if (audioManager != null)
        {
            audioManager.StartRecording();
            
            if (statusText != null)
                statusText.text = "Recording...";
        }
        else
            Debug.LogError("AudioManager not found!");
    }
    
    public void StopRecording()
    {
        Debug.Log("Stop Recording button pressed!");
        
        if (stopButton != null)
            stopButton.GetComponent<Image>().color = Color.red;
        
        if (startButton != null)
            startButton.GetComponent<Image>().color = Color.white;
        
        if (audioManager != null)
        {
            audioManager.StopRecording();
            
            if (statusText != null)
                statusText.text = "Processing...";
        }
        else
            Debug.LogError("AudioManager not found!");
    }
    
    // Additional method for testing server connection
    public void TestServerConnection()
    {
        Debug.Log("Testing server connection");
        
        // Find WebSocketManager
        WebSocketManager wsManager = FindObjectOfType<WebSocketManager>();
        if (wsManager != null)
        {
            wsManager.ConnectToServer();
            
            if (statusText != null)
                statusText.text = "Connecting to server...";
        }
        else
            Debug.LogError("WebSocketManager not found!");
    }
}