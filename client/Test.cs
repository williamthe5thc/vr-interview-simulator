using UnityEngine;
//using VRInterview.Utilities; // Include this if using the AnimatorExtensions

public class Test : MonoBehaviour
{
    [Header("Environment References")]
    [SerializeField] private GameObject corporateEnvironmentPrefab;
    [SerializeField] private GameObject startupEnvironmentPrefab;
    [SerializeField] private GameObject casualEnvironmentPrefab;
    
    [Header("Settings")]
    [SerializeField] private string defaultEnvironment = "Corporate";
    
    // Called when the script is first enabled
    private void Start()
    {
        Debug.Log("Test script is running!");
        
        // Load the default environment
        LoadEnvironment(defaultEnvironment);
    }
    
    // Load a specific environment
    public void LoadEnvironment(string environmentType)
    {
        Debug.Log($"Loading environment: {environmentType}");
        
        // Remove any existing environment
        GameObject existingEnvironment = GameObject.FindGameObjectWithTag("Environment");
        if (existingEnvironment != null)
        {
            Destroy(existingEnvironment);
        }
        
        // Instantiate the new environment based on type
        GameObject prefabToUse = null;
        
        switch(environmentType.ToLower())
        {
            case "corporate":
                prefabToUse = corporateEnvironmentPrefab;
                break;
            case "startup":
                prefabToUse = startupEnvironmentPrefab;
                break;
            case "casual":
                prefabToUse = casualEnvironmentPrefab;
                break;
            default:
                Debug.LogWarning($"Unknown environment type: {environmentType}. Using corporate as fallback.");
                prefabToUse = corporateEnvironmentPrefab;
                break;
        }
        
        if (prefabToUse != null)
        {
            GameObject newEnvironment = Instantiate(prefabToUse, Vector3.zero, Quaternion.identity);
            newEnvironment.tag = "Environment";
            Debug.Log($"Successfully loaded {environmentType} environment");
        }
        else
        {
            Debug.LogError($"Failed to load environment: Prefab for {environmentType} is not assigned");
        }
    }
    
    // You can call this from a UI button
    public void SwitchToCorporateEnvironment()
    {
        LoadEnvironment("Corporate");
    }
    
    // You can call this from a UI button
    public void SwitchToStartupEnvironment()
    {
        LoadEnvironment("Startup");
    }
    
    // You can call this from a UI button
    public void SwitchToCasualEnvironment()
    {
        LoadEnvironment("Casual");
    }
}