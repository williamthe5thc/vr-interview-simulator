using System.Collections;
using UnityEngine;

public class AvatarController : MonoBehaviour
{
    [Header("References")]
    [SerializeField] private Animator animator;
    [SerializeField] private AudioSource audioSource;
    [SerializeField] private Transform headBone;
    [SerializeField] private SkinnedMeshRenderer faceMesh;

    [Header("Procedural Interviewer Rig (optional, auto-found on this object)")]
    [Tooltip("When these components are present they drive posture, lip sync and gaze, and the legacy blend-shape-index code below is skipped.")]
    [SerializeField] private InterviewerBody body;
    [SerializeField] private InterviewerFace face;
    [SerializeField] private InterviewerGaze gaze;

    [Header("Animation Parameters")]
    [SerializeField] private string idleTrigger = "Idle";
    [SerializeField] private string listeningTrigger = "Listening";
    [SerializeField] private string thinkingTrigger = "Thinking";
    [SerializeField] private string speakingTrigger = "Speaking";
    [SerializeField] private string attentiveTrigger = "Attentive";
    [SerializeField] private string confusedTrigger = "Confused";
    
    [Header("Blend Shape Indices")]
    [SerializeField] private int mouthOpenIndex = 0;
    [SerializeField] private int mouthCloseIndex = 1;
    [SerializeField] private int mouthWideIndex = 2;
    [SerializeField] private int mouthNarrowIndex = 3;
    [SerializeField] private int eyeBlinkLeftIndex = 4;
    [SerializeField] private int eyeBlinkRightIndex = 5;
    
    [Header("Head Movement Settings")]
    [SerializeField] private float talkingHeadIntensity = 0.05f;
    [SerializeField] private float idleHeadIntensity = 0.02f;
    [SerializeField] private float talkingHeadSpeed = 4.0f;
    [SerializeField] private float idleHeadSpeed = 0.5f;
    
    [Header("Lip Sync Settings")]
    [SerializeField] private float lipSyncSensitivity = 1.0f;
    [SerializeField] private float lipSyncSmoothingFactor = 0.1f;
    [SerializeField] private bool useLipSync = true;
    
    private Quaternion initialHeadRotation;
    private string currentState = "IDLE";
    private bool isTalking = false;
    private float[] audioSampleData = new float[256];
    private float currentMouthOpen = 0f;
    private Coroutine randomBlinkCoroutine;
    private Coroutine randomGestureCoroutine;
    private bool forcedTalking;

    private bool HasRig => body != null || face != null || gaze != null;
    private bool AnimatorUsable => animator != null && animator.enabled && animator.runtimeAnimatorController != null;

    private void Awake()
    {
        if (body == null) body = GetComponent<InterviewerBody>();
        if (face == null) face = GetComponent<InterviewerFace>();
        if (gaze == null) gaze = GetComponent<InterviewerGaze>();
    }

    private void Start()
    {
        // Find components if not assigned
        if (animator == null)
            animator = GetComponent<Animator>();

        if (audioSource == null)
            audioSource = GetComponentInChildren<AudioSource>();

        // Share the voice source with the face so lip sync analyses what is actually playing
        if (face != null) face.SetAudioSource(audioSource);

        // Store initial head rotation
        if (headBone != null)
        {
            initialHeadRotation = headBone.localRotation;
        }
        else if (body == null)
        {
            Debug.LogWarning("Head bone not assigned. Head animation will not work.");
        }

        // Start random animations
        StartRandomAnimations();
    }

    /// <summary>
    /// Use the given AudioSource as the interviewer's voice. AudioManager calls this so that the source it plays
    /// server audio on is the same one lip sync and talking-state detection read from.
    /// </summary>
    public void SetAudioSource(AudioSource source)
    {
        audioSource = source;
        if (face != null) face.SetAudioSource(source);
    }

    /// <summary>Mouth-shape timeline for the clip that is playing (from the server's lip-sync analysis).</summary>
    public void SetMouthCues(MouthCue[] cues, AudioClip clip)
    {
        if (face != null) face.SetMouthCues(cues, clip);
    }
    
    private void StartRandomAnimations()
    {
        // The procedural rig blinks and gestures by itself
        if (face == null)
        {
            if (randomBlinkCoroutine != null)
                StopCoroutine(randomBlinkCoroutine);
            randomBlinkCoroutine = StartCoroutine(RandomBlinkCoroutine());
        }

        if (body == null)
        {
            if (randomGestureCoroutine != null)
                StopCoroutine(randomGestureCoroutine);
            randomGestureCoroutine = StartCoroutine(RandomGestureCoroutine());
        }
    }

    private void Update()
    {
        // Update talking state from audio
        UpdateTalkingState();

        // Legacy head animation and lip sync; the procedural rig replaces both
        if (body == null)
            UpdateHeadAnimation();

        if (face == null && useLipSync && faceMesh != null)
        {
            UpdateLipSync();
        }
    }

    private void UpdateTalkingState()
    {
        // Talking = the voice AudioSource is playing, or StartTalking() was called explicitly.
        // (Previously the explicit call was overwritten every frame by an unrelated AudioSource.)
        bool currentlyTalking = (audioSource != null && audioSource.isPlaying) || forcedTalking;

        if (isTalking != currentlyTalking)
        {
            isTalking = currentlyTalking;
            PropagateTalking();
        }
    }

    private void PropagateTalking()
    {
        if (AnimatorUsable)
            animator.SetBool("IsTalking", isTalking);
        if (body != null) body.SetTalking(isTalking);
        if (face != null) face.SetTalking(isTalking);
        if (gaze != null) gaze.SetTalking(isTalking);
    }

    // Maps an interview state onto the procedural rig
    private void ApplyRig(InterviewerBody.Posture posture, InterviewerGaze.GazeMode gazeMode, float browRaise)
    {
        if (body != null) body.SetPosture(posture);
        if (gaze != null) gaze.SetMode(gazeMode);
        if (face != null) face.SetBrowRaise(browRaise);
    }

    private void Trigger(string trigger)
    {
        if (AnimatorUsable) animator.SetTrigger(trigger);
    }
    
    private void UpdateHeadAnimation()
    {
        if (headBone == null) return;
        
        if (isTalking)
        {
            // More active head movement when talking
            float nodAmount = Mathf.Sin(Time.time * talkingHeadSpeed) * talkingHeadIntensity;
            float turnAmount = Mathf.Sin(Time.time * (talkingHeadSpeed * 0.5f) + 0.3f) * talkingHeadIntensity;
            
            headBone.localRotation = initialHeadRotation * 
                Quaternion.Euler(nodAmount * 10f, turnAmount * 5f, 0);
        }
        else
        {
            // Subtle idle head movement
            float idleAmount = Mathf.Sin(Time.time * idleHeadSpeed) * idleHeadIntensity;
            float idleTurn = Mathf.Sin(Time.time * (idleHeadSpeed * 0.7f) + 0.5f) * idleHeadIntensity;
            
            headBone.localRotation = initialHeadRotation * 
                Quaternion.Euler(idleAmount * 5f, idleTurn * 10f, 0);
        }
    }
    
    private void UpdateLipSync()
    {
        if (!isTalking)
        {
            // Reset mouth when not talking
            if (currentMouthOpen > 0.01f)
            {
                currentMouthOpen = Mathf.Lerp(currentMouthOpen, 0f, lipSyncSmoothingFactor * 5f);
                faceMesh.SetBlendShapeWeight(mouthOpenIndex, currentMouthOpen);
            }
            return;
        }
        
        // Get audio data
        audioSource.GetSpectrumData(audioSampleData, 0, FFTWindow.BlackmanHarris);
        
        // Calculate volume in voice range (higher frequencies for speech)
        float volume = 0;
        for (int i = 1; i < 20; i++)
        {
            volume += audioSampleData[i];
        }
        volume /= 20;
        
        // Scale the volume to blend shape weight
        float targetMouthOpen = Mathf.Clamp01(volume * 100f * lipSyncSensitivity) * 100f;
        
        // Smooth the mouth movement
        currentMouthOpen = Mathf.Lerp(currentMouthOpen, targetMouthOpen, lipSyncSmoothingFactor);
        
        // Apply to blend shapes
        faceMesh.SetBlendShapeWeight(mouthOpenIndex, currentMouthOpen);
        
        // Additional expressions based on volume
        if (currentMouthOpen > 50f)
        {
            faceMesh.SetBlendShapeWeight(mouthWideIndex, 30f);
            faceMesh.SetBlendShapeWeight(mouthNarrowIndex, 0f);
            // Use mouthCloseIndex to fix the warning
            faceMesh.SetBlendShapeWeight(mouthCloseIndex, 0f);
        }
        else if (currentMouthOpen > 20f)
        {
            faceMesh.SetBlendShapeWeight(mouthWideIndex, 15f);
            faceMesh.SetBlendShapeWeight(mouthNarrowIndex, 10f);
            faceMesh.SetBlendShapeWeight(mouthCloseIndex, 5f);
        }
        else
        {
            faceMesh.SetBlendShapeWeight(mouthWideIndex, 5f);
            faceMesh.SetBlendShapeWeight(mouthNarrowIndex, 20f);
            faceMesh.SetBlendShapeWeight(mouthCloseIndex, 15f);
        }
    }
    
    // State setters
    public void SetIdleState()
    {
        if (currentState == "IDLE") return;
        currentState = "IDLE";

        ApplyRig(InterviewerBody.Posture.Neutral, InterviewerGaze.GazeMode.Contact, 0f);
        Trigger(idleTrigger);
    }
    
    public void SetListeningState()
    {
        if (currentState == "LISTENING") return;
        currentState = "LISTENING";

        ApplyRig(InterviewerBody.Posture.Listening, InterviewerGaze.GazeMode.Contact, 0.15f);
        Trigger(listeningTrigger);
    }
    
    public void SetThinkingState()
    {
        if (currentState == "PROCESSING") return;
        currentState = "PROCESSING";

        ApplyRig(InterviewerBody.Posture.Thinking, InterviewerGaze.GazeMode.Thinking, 0f);
        Trigger(thinkingTrigger);
    }
    
    public void SetSpeakingState()
    {
        if (currentState == "RESPONDING") return;
        currentState = "RESPONDING";

        ApplyRig(InterviewerBody.Posture.Speaking, InterviewerGaze.GazeMode.Contact, 0.05f);
        Trigger(speakingTrigger);
    }
    
    public void SetAttentiveState()
    {
        if (currentState == "WAITING") return;
        currentState = "WAITING";

        ApplyRig(InterviewerBody.Posture.Attentive, InterviewerGaze.GazeMode.Contact, 0.2f);
        Trigger(attentiveTrigger);
    }
    
    public void SetConfusedState()
    {
        if (currentState == "ERROR") return;
        currentState = "ERROR";

        ApplyRig(InterviewerBody.Posture.Confused, InterviewerGaze.GazeMode.Contact, 0.6f);
        Trigger(confusedTrigger);
    }

    // Direct control methods
    public void StartTalking()
    {
        forcedTalking = true;
        if (!isTalking)
        {
            isTalking = true;
            PropagateTalking();
        }
    }

    public void StopTalking()
    {
        forcedTalking = false;
        // the voice source may still be draining; UpdateTalkingState clears isTalking when it stops
        if (audioSource == null || !audioSource.isPlaying)
        {
            isTalking = false;
            PropagateTalking();
        }
    }

    public void PlayAudioClip(AudioClip clip)
    {
        if (audioSource != null && clip != null)
        {
            audioSource.clip = clip;
            audioSource.Play();
            // The talking state follows audioSource.isPlaying, so it ends when the clip does.
            if (!isTalking)
            {
                isTalking = true;
                PropagateTalking();
            }
        }
    }

    /// <summary>One-shot hooks for scripted moments (e.g. nod when the candidate finishes an answer).</summary>
    public void Nod(float strength = 1f) { if (body != null) body.Nod(strength); }
    public void Gesture(int index = -1) { if (body != null) body.Gesture(index); }
    public void LookAtNotes() { if (gaze != null) gaze.GlanceAtNotes(); }
    public void LookAway() { if (gaze != null) gaze.GlanceAway(); }
    
    // Random animation coroutines
    private IEnumerator RandomBlinkCoroutine()
    {
        while (true)
        {
            // Wait random time between blinks
            float waitTime = Random.Range(2f, 6f);
            yield return new WaitForSeconds(waitTime);
            
            // Blink both eyes
            Blink();
        }
    }
    
    private IEnumerator RandomGestureCoroutine()
    {
        while (true)
        {
            // Only perform random gestures when not speaking
            if (!isTalking && currentState != "RESPONDING" && currentState != "ERROR")
            {
                // Wait random time between gestures
                float waitTime = Random.Range(8f, 15f);
                yield return new WaitForSeconds(waitTime);
                
                // Perform random gesture if the animator has a controller
                if (AnimatorUsable)
                {
                    int gestureType = Random.Range(0, 3);
                    animator.SetInteger("GestureType", gestureType);
                    animator.SetTrigger("DoGesture");
                }
            }
            else
            {
                yield return new WaitForSeconds(1f);
            }
        }
    }
    
    // Perform eye blink
    public void Blink()
    {
        if (face != null) { face.Blink(); return; }
        if (faceMesh == null) return;

        StartCoroutine(BlinkAnimation());
    }
    
    private IEnumerator BlinkAnimation()
    {
        float openWeight = 0f;
        float closedWeight = 100f;
        
        // Close eyes
        float blinkTime = 0.05f;
        float timer = 0f;
        
        while (timer < blinkTime)
        {
            float t = timer / blinkTime;
            float weight = Mathf.Lerp(openWeight, closedWeight, t);
            
            faceMesh.SetBlendShapeWeight(eyeBlinkLeftIndex, weight);
            faceMesh.SetBlendShapeWeight(eyeBlinkRightIndex, weight);
            
            timer += Time.deltaTime;
            yield return null;
        }
        
        // Hold closed for a moment
        yield return new WaitForSeconds(0.01f);
        
        // Open eyes
        timer = 0f;
        
        while (timer < blinkTime)
        {
            float t = timer / blinkTime;
            float weight = Mathf.Lerp(closedWeight, openWeight, t);
            
            faceMesh.SetBlendShapeWeight(eyeBlinkLeftIndex, weight);
            faceMesh.SetBlendShapeWeight(eyeBlinkRightIndex, weight);
            
            timer += Time.deltaTime;
            yield return null;
        }
        
        // Reset to fully open
        faceMesh.SetBlendShapeWeight(eyeBlinkLeftIndex, openWeight);
        faceMesh.SetBlendShapeWeight(eyeBlinkRightIndex, openWeight);
    }
}
