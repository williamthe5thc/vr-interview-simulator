using UnityEngine;
using UnityEngine.XR;

/// <summary>
/// Hold-to-talk for the candidate: hold either controller's trigger or grip to record, release to send.
/// (Use the grip when pointing at a UI button so the trigger doesn't also click it.)
///
/// The interview server only enters LISTENING after it has received audio, so the client has to start each turn
/// itself; the old flow waited for LISTENING and never started. While this component is active the server entering
/// LISTENING no longer starts a second recording.
/// </summary>
public class PushToTalk : MonoBehaviour
{
    [Header("References (auto-found if empty)")]
    [SerializeField] private AudioManager audioManager;
    [SerializeField] private SessionManager sessionManager;
    [SerializeField] private WebSocketManager webSocketManager;
    [SerializeField] private AvatarController avatarController;
    [SerializeField] private UIManager uiManager;

    [Header("Input")]
    [SerializeField] private bool useTrigger = true;
    [SerializeField] private bool useGrip = true;

    private bool held;
    private float holdStart;

    private void Start()
    {
        if (audioManager == null) audioManager = FindObjectOfType<AudioManager>();
        if (sessionManager == null) sessionManager = FindObjectOfType<SessionManager>();
        if (webSocketManager == null) webSocketManager = FindObjectOfType<WebSocketManager>();
        if (avatarController == null) avatarController = FindObjectOfType<AvatarController>();
        if (uiManager == null) uiManager = FindObjectOfType<UIManager>();

        if (audioManager != null)
        {
            audioManager.ServerDrivenRecording = false;
            audioManager.OnRecordingProcessed += HandleRecordingProcessed;
        }
        Status("Hold a trigger or grip to talk");
    }

    private void OnDestroy()
    {
        if (audioManager != null)
        {
            audioManager.OnRecordingProcessed -= HandleRecordingProcessed;
            audioManager.ServerDrivenRecording = true;
        }
    }

    private void Update()
    {
        bool down = Pressed(XRNode.RightHand) || Pressed(XRNode.LeftHand);
        if (down && !held) Begin();
        else if (!down && held) End();
    }

    private bool Pressed(XRNode node)
    {
        var device = InputDevices.GetDeviceAtXRNode(node);
        if (!device.isValid) return false;
        bool value;
        if (useTrigger && !XRUIClicker.PointingAtUI && device.TryGetFeatureValue(CommonUsages.triggerButton, out value) && value) return true;
        if (useGrip && device.TryGetFeatureValue(CommonUsages.gripButton, out value) && value) return true;
        return false;
    }

    private void Begin()
    {
        held = true;
        if (audioManager == null) return;

        if (webSocketManager != null && !webSocketManager.IsConnected())
        {
            Status("Not connected to the server");
            held = false;   // swallow this press; the user must release and press again once connected
            return;
        }
        string state = sessionManager != null ? sessionManager.GetCurrentState() : "IDLE";
        if (audioManager.IsPlaying || (state != "IDLE" && state != "WAITING" && state != "ERROR"))
        {
            Status("Wait for the interviewer to finish");
            return;
        }

        holdStart = Time.time;
        audioManager.StartPushToTalk();
        if (sessionManager != null) sessionManager.PauseIdleTimeout();
        if (avatarController != null) avatarController.SetListeningState();
        Status("Listening... release to send");
        Buzz(XRNode.RightHand); Buzz(XRNode.LeftHand);
    }

    private void End()
    {
        held = false;
        if (audioManager == null || !audioManager.IsRecording) return;
        float seconds = Time.time - holdStart;
        audioManager.StopRecording();   // sends the audio; the server then drives thinking / speaking
        Status(seconds < 0.4f ? "Too short, hold while you speak" : "Sending...");
    }

    private void HandleRecordingProcessed(float seconds, float peak, bool sent)
    {
        if (!sent)
        {
            Status("Too short, hold while you speak");
            if (sessionManager != null) sessionManager.ResumeIdleTimeout();
            if (avatarController != null) avatarController.SetAttentiveState();
            return;
        }
        if (peak < 0.0005f)
        {
            Status($"Sent {seconds:F1}s but the MIC CAPTURED SILENCE");
            return;
        }
        Status($"Sent {seconds:F1}s (mic level {peak:F2}), thinking...");
    }

    private void Status(string text)
    {
        if (uiManager != null) uiManager.UpdateStatus(text);
        Debug.Log("[PushToTalk] " + text);
    }

    private static void Buzz(XRNode node)
    {
        var device = InputDevices.GetDeviceAtXRNode(node);
        if (device.isValid && device.TryGetHapticCapabilities(out HapticCapabilities caps) && caps.supportsImpulse)
            device.SendHapticImpulse(0, 0.25f, 0.05f);
    }
}
