using UnityEngine;

public class SimpleHeadMovement : MonoBehaviour
{
    [Header("References")]
    [SerializeField] private Transform headBone;
    [SerializeField] private AudioSource audioSource;

    [Header("Movement Settings")]
    [SerializeField] private float talkingIntensity = 0.05f;
    [SerializeField] private float idleIntensity = 0.02f;
    [SerializeField] private float talkingSpeed = 4.0f;
    [SerializeField] private float idleSpeed = 0.5f;

    private Quaternion initialHeadRotation;
    private bool isTalking = false;

    void Start()
    {
        // Find components if not assigned
        if (audioSource == null)
            audioSource = GetComponent<AudioSource>();
            
        // If head bone not assigned, try to find it
        if (headBone == null)
        {
            // Try to find a head bone in children (assuming the first child of the avatar might be the head)
            // This is a simple approach - in a real project, you'd want more specific targeting
            Transform[] children = GetComponentsInChildren<Transform>();
            foreach (Transform child in children)
            {
                if (child.name.ToLower().Contains("head"))
                {
                    headBone = child;
                    Debug.Log("Found head bone: " + child.name);
                    break;
                }
            }
            
            // If still not found, use the first child as a fallback
            if (headBone == null && transform.childCount > 0)
            {
                headBone = transform.GetChild(0);
                Debug.Log("Using first child as head: " + headBone.name);
            }
        }
        
        // Store initial rotation if we have a head bone
        if (headBone != null)
        {
            initialHeadRotation = headBone.localRotation;
            Debug.Log("Initial head rotation stored");
        }
        else
        {
            Debug.LogWarning("No head bone found or assigned. Head movement will not work.");
        }
        
        // Add an audio source if missing
        if (audioSource == null)
        {
            audioSource = gameObject.AddComponent<AudioSource>();
            audioSource.spatialBlend = 1.0f; // 3D sound
            audioSource.volume = 0.8f;
        }
    }

    void Update()
    {
        // Detect talking state from audio
        if (audioSource != null)
        {
            bool currentlyPlaying = audioSource.isPlaying;
            if (isTalking != currentlyPlaying)
            {
                isTalking = currentlyPlaying;
                if (isTalking)
                    Debug.Log("Started talking");
                else
                    Debug.Log("Stopped talking");
            }
        }
        
        // Animate head if we have a head bone
        if (headBone != null)
        {
            if (isTalking)
            {
                // More active head movement when talking
                float nodAmount = Mathf.Sin(Time.time * talkingSpeed) * talkingIntensity;
                float turnAmount = Mathf.Sin(Time.time * (talkingSpeed * 0.5f)) * talkingIntensity;
                
                headBone.localRotation = initialHeadRotation * 
                    Quaternion.Euler(nodAmount * 10f, turnAmount * 5f, 0);
            }
            else
            {
                // Subtle idle head movement
                float idleAmount = Mathf.Sin(Time.time * idleSpeed) * idleIntensity;
                
                headBone.localRotation = initialHeadRotation * 
                    Quaternion.Euler(idleAmount * 5f, idleAmount * 10f, 0);
            }
        }
    }

    public void StartTalking()
    {
        isTalking = true;
    }

    public void StopTalking()
    {
        isTalking = false;
    }

    public void PlayAudioClip(AudioClip clip)
    {
        if (audioSource != null && clip != null)
        {
            audioSource.clip = clip;
            audioSource.Play();
            // Talking state will be detected automatically in Update
        }
    }
}