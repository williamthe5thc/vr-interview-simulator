using System.Collections.Generic;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;
using UnityEngine.XR;
using UnityEngine.XR.Interaction.Toolkit;

/// <summary>
/// Makes a trigger pull click the UI button under the controller's pointer.
///
/// The scene's controllers have no input-action bindings (UI Press / Select / Activate are empty), so the ray could
/// hover and highlight a button but nothing ever clicked it. This reads the trigger through the same XR input API that
/// push-to-talk uses, asks the ray interactor which UI element it is pointing at, and invokes that Button.
/// Every click plays a short click sound and buzzes the controller that pressed, so it is obvious a button was pressed.
/// </summary>
public class XRUIClicker : MonoBehaviour
{
    /// True while either pointer is on a UI element; push-to-talk ignores the trigger then (the grip still works).
    public static bool PointingAtUI { get; private set; }

    private class Hand
    {
        public XRRayInteractor ray;
        public XRNode node;
        public bool wasDown;
    }

    private readonly List<Hand> hands = new List<Hand>();
    private readonly HashSet<XRNode> clickedThisFrame = new HashSet<XRNode>();
    private float nextSearch;
    private AudioSource audioSource;
    private AudioClip clickClip, confirmClip;

    private void Awake()
    {
        audioSource = gameObject.AddComponent<AudioSource>();
        audioSource.playOnAwake = false;
        audioSource.spatialBlend = 0f;
        audioSource.volume = 0.6f;
        clickClip = MakeTone("UiClick", new[] { 1300f }, 0.05f, 0.5f);
        confirmClip = MakeTone("UiConfirm", new[] { 880f, 1320f }, 0.16f, 0.5f);
    }

    private void Update()
    {
        if (hands.Count == 0 && Time.unscaledTime >= nextSearch)
        {
            nextSearch = Time.unscaledTime + 1f;
            FindHands();
        }

        clickedThisFrame.Clear();
        bool any = false;
        foreach (var hand in hands)
        {
            if (hand.ray == null) continue;
            bool hit = hand.ray.TryGetCurrentUIRaycastResult(out RaycastResult result) && result.gameObject != null;
            any |= hit;

            bool down = TriggerDown(hand.node);
            if (hit && down && !hand.wasDown && clickedThisFrame.Add(hand.node)) Click(result.gameObject, hand.node);
            hand.wasDown = down;
        }
        PointingAtUI = any;
    }

    private void FindHands()
    {
        foreach (var ray in FindObjectsOfType<XRRayInteractor>())
        {
            XRNode? node = null;
            for (var t = ray.transform; t != null && node == null; t = t.parent)
            {
                if (t.name.Contains("Left")) node = XRNode.LeftHand;
                else if (t.name.Contains("Right")) node = XRNode.RightHand;
            }
            if (node.HasValue) hands.Add(new Hand { ray = ray, node = node.Value });
        }
    }

    private static bool TriggerDown(XRNode node)
    {
        var device = InputDevices.GetDeviceAtXRNode(node);
        return device.isValid && device.TryGetFeatureValue(CommonUsages.triggerButton, out bool value) && value;
    }

    private void Click(GameObject target, XRNode node)
    {
        var button = target.GetComponentInParent<Button>();
        if (button != null && button.IsInteractable())
        {
            Debug.Log("[XRUIClicker] clicked " + button.name);
            bool primary = button.name == "StartInterview" || button.name == "CoachReview";
            audioSource.PlayOneShot(primary ? confirmClip : clickClip);
            Buzz(node, primary ? 0.8f : 0.5f, primary ? 0.12f : 0.06f);
            button.onClick.Invoke();
        }
    }

    private static void Buzz(XRNode node, float amplitude, float seconds)
    {
        var device = InputDevices.GetDeviceAtXRNode(node);
        if (device.isValid && device.TryGetHapticCapabilities(out HapticCapabilities caps) && caps.supportsImpulse)
            device.SendHapticImpulse(0, amplitude, seconds);
    }

    /// A short sine beep (or two in a row) with a fast fade, generated so no audio asset is needed.
    private static AudioClip MakeTone(string name, float[] frequencies, float seconds, float volume)
    {
        const int rate = 44100;
        int count = (int)(rate * seconds);
        var samples = new float[count];
        for (int i = 0; i < count; i++)
        {
            float t = i / (float)rate;
            int part = Mathf.Min((int)(i / (float)count * frequencies.Length), frequencies.Length - 1);
            float local = (i - part * (count / (float)frequencies.Length)) / (count / (float)frequencies.Length);
            float envelope = Mathf.Clamp01(Mathf.Min(local * 12f, (1f - local) * 3f));
            samples[i] = Mathf.Sin(2f * Mathf.PI * frequencies[part] * t) * volume * envelope;
        }
        var clip = AudioClip.Create(name, count, 1, rate, false);
        clip.SetData(samples, 0);
        return clip;
    }
}
