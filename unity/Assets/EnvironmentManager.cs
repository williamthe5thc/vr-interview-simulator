using System;
using System.Collections;
using UnityEngine;
using UnityEngine.UI; // Added for UI components like Image and CanvasScaler

public class EnvironmentManager : MonoBehaviour
{
    [System.Serializable]
    public class InterviewEnvironment
    {
        public string name;
        public GameObject environmentPrefab;
        public AudioClip ambientAudio;
        [Range(0f, 1f)]
        public float ambientVolume = 0.1f;
        public Color lightingTint = Color.white;
    }
    
    [Header("Environments")]
    [SerializeField] private InterviewEnvironment[] environments;
    [SerializeField] private int defaultEnvironmentIndex = 0;
    
    [Header("Components")]
    [SerializeField] private Transform environmentParent;
    [SerializeField] private Light mainDirectionalLight;
    [SerializeField] private AudioSource ambientAudioSource;
    [SerializeField] private UIManager uiManager;
    
    private GameObject currentEnvironment;
    private int currentEnvironmentIndex = -1;
    private Coroutine transitionCoroutine;
    
    // Events
    public event Action<string> OnEnvironmentChanged;
    
    private void Start()
    {
        // Initialize components if needed
        if (environmentParent == null)
        {
            environmentParent = transform;
        }
        
        if (ambientAudioSource == null)
        {
            ambientAudioSource = gameObject.AddComponent<AudioSource>();
            ambientAudioSource.loop = true;
            ambientAudioSource.spatialBlend = 0f; // 2D sound
            ambientAudioSource.playOnAwake = false;
        }
        
        // Load default environment
        LoadEnvironment(defaultEnvironmentIndex);
    }
    
    public void LoadEnvironment(int index)
    {
        if (index < 0 || index >= environments.Length)
        {
            Debug.LogError($"Invalid environment index: {index}");
            return;
        }
        
        if (index == currentEnvironmentIndex) return;
        
        // Start transition
        if (transitionCoroutine != null)
        {
            StopCoroutine(transitionCoroutine);
        }
        
        transitionCoroutine = StartCoroutine(TransitionEnvironment(index));
    }
    
    public void LoadEnvironment(string environmentName)
    {
        for (int i = 0; i < environments.Length; i++)
        {
            if (environments[i].name == environmentName)
            {
                LoadEnvironment(i);
                return;
            }
        }
        
        Debug.LogError($"Environment not found: {environmentName}");
    }
    
    private IEnumerator TransitionEnvironment(int newIndex)
    {
        // Fade out
        yield return StartCoroutine(FadeOut(0.5f));
        
        // Remove current environment
        if (currentEnvironment != null)
        {
            Destroy(currentEnvironment);
        }
        
        // Instantiate new environment
        InterviewEnvironment newEnvironment = environments[newIndex];
        currentEnvironment = Instantiate(newEnvironment.environmentPrefab, environmentParent);
        currentEnvironmentIndex = newIndex;
        
        // Update lighting
        if (mainDirectionalLight != null)
        {
            mainDirectionalLight.color = newEnvironment.lightingTint;
        }
        
        // Update ambient audio
        if (ambientAudioSource != null && newEnvironment.ambientAudio != null)
        {
            ambientAudioSource.clip = newEnvironment.ambientAudio;
            ambientAudioSource.volume = newEnvironment.ambientVolume;
            ambientAudioSource.Play();
        }
        
        // Notify environment change
        OnEnvironmentChanged?.Invoke(newEnvironment.name);
        
        if (uiManager != null)
        {
            uiManager.UpdateStatus($"Environment changed to {newEnvironment.name}");
            uiManager.LogDebug($"Loaded environment: {newEnvironment.name}");
        }
        
        // Short delay to ensure environment is fully loaded
        yield return new WaitForSeconds(0.2f);
        
        // Fade in
        yield return StartCoroutine(FadeIn(0.5f));
    }
    
    private IEnumerator FadeOut(float duration)
    {
        // Create a temporary black overlay
        GameObject overlay = CreateOverlay();
        CanvasGroup canvasGroup = overlay.GetComponent<CanvasGroup>();
        
        // Fade in the black overlay (fade out the scene)
        float timer = 0f;
        while (timer < duration)
        {
            float t = timer / duration;
            canvasGroup.alpha = t;
            timer += Time.deltaTime;
            yield return null;
        }
        
        canvasGroup.alpha = 1f;
    }
    
    private IEnumerator FadeIn(float duration)
    {
        // Get the overlay
        GameObject overlay = GameObject.FindGameObjectWithTag("FadeOverlay");
        if (overlay == null) yield break;
        
        CanvasGroup canvasGroup = overlay.GetComponent<CanvasGroup>();
        
        // Fade out the black overlay (fade in the scene)
        float timer = 0f;
        while (timer < duration)
        {
            float t = timer / duration;
            canvasGroup.alpha = 1f - t;
            timer += Time.deltaTime;
            yield return null;
        }
        
        canvasGroup.alpha = 0f;
        
        // Remove the overlay
        Destroy(overlay);
    }
    
    private GameObject CreateOverlay()
    {
        // Find existing overlay or create new one
        GameObject overlay = GameObject.FindGameObjectWithTag("FadeOverlay");
        if (overlay != null) return overlay;
        
        // Create canvas for overlay
        overlay = new GameObject("FadeOverlay");
        overlay.tag = "FadeOverlay";
        
        Canvas canvas = overlay.AddComponent<Canvas>();
        canvas.renderMode = RenderMode.ScreenSpaceOverlay;
        canvas.sortingOrder = 999; // Ensure it's on top
        
        CanvasScaler scaler = overlay.AddComponent<CanvasScaler>();
        scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
        scaler.referenceResolution = new Vector2(1920, 1080);
        
        CanvasGroup canvasGroup = overlay.AddComponent<CanvasGroup>();
        canvasGroup.alpha = 0f;
        
        // Create black image
        GameObject imageObj = new GameObject("BlackImage");
        imageObj.transform.SetParent(overlay.transform, false);
        
        Image image = imageObj.AddComponent<Image>();
        image.color = Color.black;
        
        // Set to fill screen
        RectTransform rect = image.rectTransform;
        rect.anchorMin = Vector2.zero;
        rect.anchorMax = Vector2.one;
        rect.sizeDelta = Vector2.zero;
        
        return overlay;
    }
    
    public InterviewEnvironment GetCurrentEnvironment()
    {
        if (currentEnvironmentIndex >= 0 && currentEnvironmentIndex < environments.Length)
        {
            return environments[currentEnvironmentIndex];
        }
        return null;
    }
    
    public string[] GetAvailableEnvironmentNames()
    {
        string[] names = new string[environments.Length];
        for (int i = 0; i < environments.Length; i++)
        {
            names[i] = environments[i].name;
        }
        return names;
    }
    
    public void SetAmbientVolume(float volume)
    {
        if (ambientAudioSource != null)
        {
            ambientAudioSource.volume = Mathf.Clamp01(volume);
        }
    }
}
