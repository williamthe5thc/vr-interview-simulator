using UnityEditor;
using UnityEngine;

public class VRSetup : Editor
{
    [MenuItem("Tools/Setup VR Scene")]
    public static void SetupVRScene()
    {
        // Check if OVRCameraRig exists; if not, add it
        if (GameObject.Find("OVRCameraRig") == null)
        {
            string prefabPath = "Packages/com.unity.xr.oculus/Runtime/Prefabs/OVRCameraRig.prefab";
            GameObject rigPrefab = AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath);

            if (rigPrefab != null)
            {
                GameObject rig = PrefabUtility.InstantiatePrefab(rigPrefab) as GameObject;
                rig.name = "OVRCameraRig";
                rig.transform.position = Vector3.zero; // Position at origin
                Debug.Log("OVRCameraRig added successfully.");
            }
            else
            {
                Debug.LogError("Failed to load OVRCameraRig prefab at " + prefabPath + ". Ensure Oculus XR Plugin is installed correctly.");
            }
        }

        // Check if a light exists; if not, add a directional light
        if (GameObject.FindObjectOfType<Light>() == null)
        {
            GameObject light = new GameObject("Directional Light");
            Light dirLight = light.AddComponent<Light>();
            dirLight.type = LightType.Directional;
            light.transform.rotation = Quaternion.Euler(50, -30, 0); // Simulate sunlight
            Debug.Log("Directional Light added.");
        }

        // Optional: Add a ground plane
        if (GameObject.Find("Ground") == null)
        {
            GameObject plane = GameObject.CreatePrimitive(PrimitiveType.Plane);
            plane.name = "Ground";
            plane.transform.localScale = new Vector3(10, 1, 10); // Larger plane
            Debug.Log("Ground plane added.");
        }

        Debug.Log("VR Scene Setup Complete!");
    }
    
    [MenuItem("Tools/Create Interview Environment/Corporate Office")]
    public static void CreateCorporateEnvironment()
    {
        // Create container
        GameObject environment = new GameObject("CorporateEnvironment");
        environment.tag = "Environment";
        
        // Floor
        GameObject floor = GameObject.CreatePrimitive(PrimitiveType.Plane);
        floor.name = "Floor";
        floor.transform.parent = environment.transform;
        floor.transform.localScale = new Vector3(2, 1, 2);
        ApplyMaterial(floor, Color.gray);
        
        // Walls
        CreateWall("WallNorth", environment.transform, new Vector3(0, 2.5f, 10), new Vector3(20, 5, 0.1f), Color.white);
        CreateWall("WallSouth", environment.transform, new Vector3(0, 2.5f, -10), new Vector3(20, 5, 0.1f), Color.white);
        CreateWall("WallEast", environment.transform, new Vector3(10, 2.5f, 0), new Vector3(0.1f, 5, 20), Color.white);
        CreateWall("WallWest", environment.transform, new Vector3(-10, 2.5f, 0), new Vector3(0.1f, 5, 20), Color.white);
        
        // Windows
        GameObject window = GameObject.CreatePrimitive(PrimitiveType.Cube);
        window.name = "Window";
        window.transform.parent = environment.transform;
        window.transform.position = new Vector3(0, 2.5f, 10);
        window.transform.localScale = new Vector3(10, 3, 0.1f);
        ApplyMaterial(window, new Color(0.7f, 0.9f, 1f, 0.3f), true);
        
        // Desk
        GameObject desk = GameObject.CreatePrimitive(PrimitiveType.Cube);
        desk.name = "InterviewDesk";
        desk.transform.parent = environment.transform;
        desk.transform.position = new Vector3(0, 0.5f, 0);
        desk.transform.localScale = new Vector3(2.5f, 1, 1.2f);
        ApplyMaterial(desk, new Color(0.4f, 0.2f, 0.1f));
        
        // Chairs
        GameObject interviewerChair = CreateChair("InterviewerChair", environment.transform, new Vector3(0, 0, 1.5f), Color.black);
        interviewerChair.transform.rotation = Quaternion.Euler(0, 180, 0);
        
        GameObject candidateChair = CreateChair("CandidateChair", environment.transform, new Vector3(0, 0, -1.5f), Color.black);
        candidateChair.tag = "PlayerPosition";
        
        // Office decoration
        CreatePlant(environment.transform, new Vector3(5, 0, 5));
        CreatePlant(environment.transform, new Vector3(-5, 0, 5));
        
        // Ceiling light
        GameObject ceilingLight = new GameObject("CeilingLight");
        ceilingLight.transform.parent = environment.transform;
        ceilingLight.transform.position = new Vector3(0, 4.9f, 0);
        
        Light light = ceilingLight.AddComponent<Light>();
        light.type = LightType.Point;
        light.range = 15;
        light.intensity = 1.5f;
        light.shadows = LightShadows.Soft;
        
        // Add environment manager script
        GameObject manager = new GameObject("EnvironmentManager");
        Test test = manager.AddComponent<Test>();
        
        // Try to assign this environment
        SerializedObject serializedObject = new SerializedObject(test);
        SerializedProperty corporateProp = serializedObject.FindProperty("corporateEnvironmentPrefab");
        
        // Save environment as prefab
        string prefabPath = "Assets/Prefabs";
        if (!AssetDatabase.IsValidFolder(prefabPath))
        {
            AssetDatabase.CreateFolder("Assets", "Prefabs");
        }
        
        string assetPath = prefabPath + "/CorporateEnvironment.prefab";
        GameObject prefab = PrefabUtility.SaveAsPrefabAsset(environment, assetPath);
        
        if (prefab != null && corporateProp != null)
        {
            corporateProp.objectReferenceValue = prefab;
            serializedObject.ApplyModifiedProperties();
            Debug.Log("Corporate environment prefab created and assigned to manager.");
        }
        
        Debug.Log("Corporate Environment Created!");
    }
    
    [MenuItem("Tools/Create Interview Environment/Startup Office")]
    public static void CreateStartupEnvironment()
    {
        // Create container
        GameObject environment = new GameObject("StartupEnvironment");
        environment.tag = "Environment";
        
        // Floor - wooden floor for startup
        GameObject floor = GameObject.CreatePrimitive(PrimitiveType.Plane);
        floor.name = "Floor";
        floor.transform.parent = environment.transform;
        floor.transform.localScale = new Vector3(2, 1, 2);
        ApplyMaterial(floor, new Color(0.6f, 0.4f, 0.2f));
        
        // Walls - more colorful
        CreateWall("WallNorth", environment.transform, new Vector3(0, 2.5f, 10), new Vector3(20, 5, 0.1f), new Color(0.9f, 0.9f, 1f));
        CreateWall("WallSouth", environment.transform, new Vector3(0, 2.5f, -10), new Vector3(20, 5, 0.1f), new Color(0.9f, 0.9f, 1f));
        CreateWall("WallEast", environment.transform, new Vector3(10, 2.5f, 0), new Vector3(0.1f, 5, 20), new Color(0.2f, 0.6f, 0.8f));
        CreateWall("WallWest", environment.transform, new Vector3(-10, 2.5f, 0), new Vector3(0.1f, 5, 20), new Color(0.2f, 0.6f, 0.8f));
        
        // Windows - larger for open space feeling
        GameObject window = GameObject.CreatePrimitive(PrimitiveType.Cube);
        window.name = "Window";
        window.transform.parent = environment.transform;
        window.transform.position = new Vector3(0, 2.5f, 10);
        window.transform.localScale = new Vector3(15, 3, 0.1f);
        ApplyMaterial(window, new Color(0.7f, 0.9f, 1f, 0.3f), true);
        
        // Modern table instead of desk
        GameObject desk = GameObject.CreatePrimitive(PrimitiveType.Cube);
        desk.name = "InterviewTable";
        desk.transform.parent = environment.transform;
        desk.transform.position = new Vector3(0, 0.4f, 0);
        desk.transform.localScale = new Vector3(2.2f, 0.1f, 1.2f);
        ApplyMaterial(desk, new Color(0.9f, 0.9f, 0.9f)); // White modern table
        
        // Glass table legs
        GameObject legFR = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        legFR.transform.parent = desk.transform;
        legFR.transform.localPosition = new Vector3(0.9f, -0.2f, 0.5f);
        legFR.transform.localScale = new Vector3(0.05f, 2f, 0.05f);
        ApplyMaterial(legFR, new Color(0.8f, 0.8f, 0.8f, 0.5f), true);
        
        GameObject legFL = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        legFL.transform.parent = desk.transform;
        legFL.transform.localPosition = new Vector3(-0.9f, -0.2f, 0.5f);
        legFL.transform.localScale = new Vector3(0.05f, 2f, 0.05f);
        ApplyMaterial(legFL, new Color(0.8f, 0.8f, 0.8f, 0.5f), true);
        
        GameObject legBR = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        legBR.transform.parent = desk.transform;
        legBR.transform.localPosition = new Vector3(0.9f, -0.2f, -0.5f);
        legBR.transform.localScale = new Vector3(0.05f, 2f, 0.05f);
        ApplyMaterial(legBR, new Color(0.8f, 0.8f, 0.8f, 0.5f), true);
        
        GameObject legBL = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        legBL.transform.parent = desk.transform;
        legBL.transform.localPosition = new Vector3(-0.9f, -0.2f, -0.5f);
        legBL.transform.localScale = new Vector3(0.05f, 2f, 0.05f);
        ApplyMaterial(legBL, new Color(0.8f, 0.8f, 0.8f, 0.5f), true);
        
        // Modern chairs
        GameObject interviewerChair = CreateModernChair("InterviewerChair", environment.transform, new Vector3(0, 0, 1.5f), Color.blue);
        interviewerChair.transform.rotation = Quaternion.Euler(0, 180, 0);
        
        GameObject candidateChair = CreateModernChair("CandidateChair", environment.transform, new Vector3(0, 0, -1.5f), Color.blue);
        candidateChair.tag = "PlayerPosition";
        
        // Startup decor
        CreateBeanbag(environment.transform, new Vector3(5, 0.1f, 3), new Color(0.3f, 0.8f, 0.3f));
        CreateBeanbag(environment.transform, new Vector3(-5, 0.1f, 3), new Color(1f, 0.5f, 0));
        
        // Whiteboard
        GameObject whiteboard = GameObject.CreatePrimitive(PrimitiveType.Cube);
        whiteboard.name = "Whiteboard";
        whiteboard.transform.parent = environment.transform;
        whiteboard.transform.position = new Vector3(0, 2.5f, -9.9f);
        whiteboard.transform.localScale = new Vector3(8, 4, 0.1f);
        ApplyMaterial(whiteboard, Color.white);
        
        // Modern lighting
        GameObject ceilingLight = new GameObject("ModernLighting");
        ceilingLight.transform.parent = environment.transform;
        ceilingLight.transform.position = new Vector3(0, 4.9f, 0);
        
        Light light = ceilingLight.AddComponent<Light>();
        light.type = LightType.Point;
        light.color = new Color(0.9f, 0.95f, 1f); // Slightly blue tint
        light.range = 20;
        light.intensity = 1.8f;
        
        // Add environment manager script if it doesn't exist
        GameObject manager = GameObject.Find("EnvironmentManager");
        if (manager == null)
        {
            manager = new GameObject("EnvironmentManager");
            manager.AddComponent<Test>();
        }
        
        Test test = manager.GetComponent<Test>();
        
        // Save environment as prefab
        string prefabPath = "Assets/Prefabs";
        if (!AssetDatabase.IsValidFolder(prefabPath))
        {
            AssetDatabase.CreateFolder("Assets", "Prefabs");
        }
        
        string assetPath = prefabPath + "/StartupEnvironment.prefab";
        GameObject prefab = PrefabUtility.SaveAsPrefabAsset(environment, assetPath);
        
        if (prefab != null && test != null)
        {
            SerializedObject serializedObject = new SerializedObject(test);
            SerializedProperty startupProp = serializedObject.FindProperty("startupEnvironmentPrefab");
            if (startupProp != null)
            {
                startupProp.objectReferenceValue = prefab;
                serializedObject.ApplyModifiedProperties();
                Debug.Log("Startup environment prefab created and assigned to manager.");
            }
        }
        
        Debug.Log("Startup Environment Created!");
    }
    
    [MenuItem("Tools/Create Interview Environment/Casual Setting")]
    public static void CreateCasualEnvironment()
    {
        // Create container
        GameObject environment = new GameObject("CasualEnvironment");
        environment.tag = "Environment";
        
        // Floor - carpet
        GameObject floor = GameObject.CreatePrimitive(PrimitiveType.Plane);
        floor.name = "CarpetFloor";
        floor.transform.parent = environment.transform;
        floor.transform.localScale = new Vector3(1.5f, 1, 1.5f);
        ApplyMaterial(floor, new Color(0.8f, 0.8f, 0.9f));
        
        // Walls - warm colors
        CreateWall("WallNorth", environment.transform, new Vector3(0, 2f, 7.5f), new Vector3(15, 4, 0.1f), new Color(0.95f, 0.9f, 0.8f));
        CreateWall("WallSouth", environment.transform, new Vector3(0, 2f, -7.5f), new Vector3(15, 4, 0.1f), new Color(0.95f, 0.9f, 0.8f));
        CreateWall("WallEast", environment.transform, new Vector3(7.5f, 2f, 0), new Vector3(0.1f, 4, 15), new Color(0.95f, 0.9f, 0.8f));
        CreateWall("WallWest", environment.transform, new Vector3(-7.5f, 2f, 0), new Vector3(0.1f, 4, 15), new Color(0.95f, 0.9f, 0.8f));
        
        // Coffee table
        GameObject table = GameObject.CreatePrimitive(PrimitiveType.Cube);
        table.name = "CoffeeTable";
        table.transform.parent = environment.transform;
        table.transform.position = new Vector3(0, 0.3f, 0);
        table.transform.localScale = new Vector3(1.2f, 0.1f, 0.8f);
        ApplyMaterial(table, new Color(0.4f, 0.3f, 0.2f));
        
        // Table legs
        for (int x = -1; x <= 1; x += 2)
        {
            for (int z = -1; z <= 1; z += 2)
            {
                GameObject leg = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
                leg.transform.parent = table.transform;
                leg.transform.localPosition = new Vector3(x * 0.4f, -1.5f, z * 0.3f);
                leg.transform.localScale = new Vector3(0.05f, 3f, 0.05f);
                ApplyMaterial(leg, new Color(0.3f, 0.2f, 0.1f));
            }
        }
        
        // Comfortable seating
        GameObject interviewerSofa = CreateSofa("InterviewerSofa", environment.transform, new Vector3(0, 0.5f, 2), new Color(0.7f, 0.5f, 0.3f));
        interviewerSofa.transform.rotation = Quaternion.Euler(0, 180, 0);
        
        GameObject candidateArmchair = CreateArmchair("CandidateArmchair", environment.transform, new Vector3(0, 0.5f, -2), new Color(0.5f, 0.6f, 0.7f));
        candidateArmchair.tag = "PlayerPosition";
        
        // Home decor
        // Bookshelf
        GameObject bookshelf = GameObject.CreatePrimitive(PrimitiveType.Cube);
        bookshelf.name = "Bookshelf";
        bookshelf.transform.parent = environment.transform;
        bookshelf.transform.position = new Vector3(-6, 2, 0);
        bookshelf.transform.localScale = new Vector3(1, 4, 6);
        ApplyMaterial(bookshelf, new Color(0.4f, 0.3f, 0.2f));
        
        // Books on shelf (simplified as colored blocks)
        for (int i = 0; i < 4; i++)
        {
            for (int j = 0; j < 8; j++)
            {
                GameObject book = GameObject.CreatePrimitive(PrimitiveType.Cube);
                book.transform.parent = bookshelf.transform;
                book.transform.localPosition = new Vector3(0.3f, 0.4f - i * 0.25f, -0.4f + j * 0.12f);
                book.transform.localScale = new Vector3(0.1f, 0.2f, 0.08f);
                
                // Random book color
                Color bookColor = new Color(
                    Random.Range(0.2f, 0.9f),
                    Random.Range(0.2f, 0.9f),
                    Random.Range(0.2f, 0.9f)
                );
                ApplyMaterial(book, bookColor);
            }
        }
        
        // Plants for homey feel
        CreatePlant(environment.transform, new Vector3(6, 0, -6));
        CreatePlant(environment.transform, new Vector3(-6, 0, -6));
        CreatePlant(environment.transform, new Vector3(6, 0, 6));
        
        // Warm lighting
        GameObject ambientLight = new GameObject("AmbientLight");
        ambientLight.transform.parent = environment.transform;
        ambientLight.transform.position = new Vector3(0, 3.5f, 0);
        
        Light light = ambientLight.AddComponent<Light>();
        light.type = LightType.Point;
        light.color = new Color(1f, 0.9f, 0.8f); // Warm light
        light.range = 15;
        light.intensity = 1.2f;
        
        // Table lamp
        GameObject lampBase = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        lampBase.name = "LampBase";
        lampBase.transform.parent = environment.transform;
        lampBase.transform.position = new Vector3(5, 0.6f, 5);
        lampBase.transform.localScale = new Vector3(0.2f, 1.2f, 0.2f);
        ApplyMaterial(lampBase, new Color(0.8f, 0.8f, 0.7f));
        
        GameObject lampShade = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        lampShade.name = "LampShade";
        lampShade.transform.parent = lampBase.transform;
        lampShade.transform.localPosition = new Vector3(0, 1f, 0);
        lampShade.transform.localScale = new Vector3(2f, 0.5f, 2f);
        ApplyMaterial(lampShade, new Color(1f, 0.95f, 0.8f, 0.7f), true);
        
        GameObject lampLight = new GameObject("LampLight");
        lampLight.transform.parent = lampBase.transform;
        lampLight.transform.localPosition = new Vector3(0, 1f, 0);
        
        Light lampPointLight = lampLight.AddComponent<Light>();
        lampPointLight.type = LightType.Point;
        lampPointLight.color = new Color(1f, 0.9f, 0.8f);
        lampPointLight.range = 8;
        lampPointLight.intensity = 1.5f;
        
        // Add environment manager script if it doesn't exist
        GameObject manager = GameObject.Find("EnvironmentManager");
        if (manager == null)
        {
            manager = new GameObject("EnvironmentManager");
            manager.AddComponent<Test>();
        }
        
        Test test = manager.GetComponent<Test>();
        
        // Save environment as prefab
        string prefabPath = "Assets/Prefabs";
        if (!AssetDatabase.IsValidFolder(prefabPath))
        {
            AssetDatabase.CreateFolder("Assets", "Prefabs");
        }
        
        string assetPath = prefabPath + "/CasualEnvironment.prefab";
        GameObject prefab = PrefabUtility.SaveAsPrefabAsset(environment, assetPath);
        
        if (prefab != null && test != null)
        {
            SerializedObject serializedObject = new SerializedObject(test);
            SerializedProperty casualProp = serializedObject.FindProperty("casualEnvironmentPrefab");
            if (casualProp != null)
            {
                casualProp.objectReferenceValue = prefab;
                serializedObject.ApplyModifiedProperties();
                Debug.Log("Casual environment prefab created and assigned to manager.");
            }
        }
        
        Debug.Log("Casual Environment Created!");
    }
    
    #region Helper Methods
    private static void CreateWall(string name, Transform parent, Vector3 position, Vector3 scale, Color color)
    {
        GameObject wall = GameObject.CreatePrimitive(PrimitiveType.Cube);
        wall.name = name;
        wall.transform.parent = parent;
        wall.transform.position = position;
        wall.transform.localScale = scale;
        ApplyMaterial(wall, color);
    }
    
    private static GameObject CreateChair(string name, Transform parent, Vector3 position, Color color)
    {
        GameObject chair = new GameObject(name);
        chair.transform.parent = parent;
        chair.transform.position = position;
        
        // Chair seat
        GameObject seat = GameObject.CreatePrimitive(PrimitiveType.Cube);
        seat.name = "Seat";
        seat.transform.parent = chair.transform;
        seat.transform.localPosition = new Vector3(0, 0.5f, 0);
        seat.transform.localScale = new Vector3(0.6f, 0.1f, 0.6f);
        ApplyMaterial(seat, color);
        
        // Chair back
        GameObject back = GameObject.CreatePrimitive(PrimitiveType.Cube);
        back.name = "Back";
        back.transform.parent = chair.transform;
        back.transform.localPosition = new Vector3(0, 1.2f, -0.3f);
        back.transform.localScale = new Vector3(0.6f, 1.5f, 0.1f);
        ApplyMaterial(back, color);
        
        // Chair legs
        for (int x = -1; x <= 1; x += 2)
        {
            for (int z = -1; z <= 1; z += 2)
            {
                GameObject leg = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
                leg.name = $"Leg_{x}_{z}";
                leg.transform.parent = chair.transform;
                leg.transform.localPosition = new Vector3(x * 0.25f, 0.25f, z * 0.25f);
                leg.transform.localScale = new Vector3(0.05f, 0.5f, 0.05f);
                ApplyMaterial(leg, color);
            }
        }
        
        return chair;
    }
    
    private static GameObject CreateModernChair(string name, Transform parent, Vector3 position, Color color)
    {
        GameObject chair = new GameObject(name);
        chair.transform.parent = parent;
        chair.transform.position = position;
        
        // Chair seat (cube with rounded edges look)
        GameObject seat = GameObject.CreatePrimitive(PrimitiveType.Cube);
        seat.name = "Seat";
        seat.transform.parent = chair.transform;
        seat.transform.localPosition = new Vector3(0, 0.5f, 0);
        seat.transform.localScale = new Vector3(0.6f, 0.1f, 0.6f);
        ApplyMaterial(seat, color);
        
        // Chair back (more modern, curved look)
        GameObject back = GameObject.CreatePrimitive(PrimitiveType.Cube);
        back.name = "Back";
        back.transform.parent = chair.transform;
        back.transform.localPosition = new Vector3(0, 1.1f, -0.25f);
        back.transform.localScale = new Vector3(0.6f, 1.3f, 0.1f);
        back.transform.localRotation = Quaternion.Euler(10, 0, 0); // Slight recline
        ApplyMaterial(back, color);
        
        // Modern pedestal base
        GameObject base1 = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        base1.name = "Base";
        base1.transform.parent = chair.transform;
        base1.transform.localPosition = new Vector3(0, 0.05f, 0);
        base1.transform.localScale = new Vector3(0.2f, 0.1f, 0.2f);
        ApplyMaterial(base1, Color.gray);
        
        GameObject stem = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        stem.name = "Stem";
        stem.transform.parent = chair.transform;
        stem.transform.localPosition = new Vector3(0, 0.3f, 0);
        stem.transform.localScale = new Vector3(0.05f, 0.5f, 0.05f);
        ApplyMaterial(stem, Color.gray);
        
        GameObject baseWheel = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        baseWheel.name = "BaseWheel";
        baseWheel.transform.parent = chair.transform;
        baseWheel.transform.localPosition = new Vector3(0, 0.1f, 0);
        baseWheel.transform.localRotation = Quaternion.Euler(90, 0, 0);
        baseWheel.transform.localScale = new Vector3(0.4f, 0.02f, 0.4f);
        ApplyMaterial(baseWheel, Color.gray);
        
        return chair;
    }
    
    private static void CreatePlant(Transform parent, Vector3 position)
    {
        GameObject plant = new GameObject("Plant");
        plant.transform.parent = parent;
        plant.transform.position = position;
        
        // Pot
        GameObject pot = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        pot.name = "Pot";
        pot.transform.parent = plant.transform;
        pot.transform.localPosition = Vector3.zero;
        pot.transform.localScale = new Vector3(0.5f, 0.5f, 0.5f);
        ApplyMaterial(pot, new Color(0.6f, 0.3f, 0.2f));
        
        // Plant base
        GameObject plantBase = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        plantBase.name = "PlantBase";
        plantBase.transform.parent = plant.transform;
        plantBase.transform.localPosition = new Vector3(0, 0.5f, 0);
        plantBase.transform.localScale = new Vector3(0.8f, 0.8f, 0.8f);
        ApplyMaterial(plantBase, new Color(0.2f, 0.5f, 0.3f));
        
        // Plant top
        GameObject plantTop = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        plantTop.name = "PlantTop";
        plantTop.transform.parent = plant.transform;
        plantTop.transform.localPosition = new Vector3(0, 1.2f, 0);
        plantTop.transform.localScale = new Vector3(0.6f, 0.6f, 0.6f);
        ApplyMaterial(plantTop, new Color(0.3f, 0.6f, 0.4f));
    }
    
    private static void CreateBeanbag(Transform parent, Vector3 position, Color color)
    {
        GameObject beanbag = new GameObject("Beanbag");
        beanbag.transform.parent = parent;
        beanbag.transform.position = position;
        
        GameObject bag = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        bag.name = "Bag";
        bag.transform.parent = beanbag.transform;
        bag.transform.localPosition = Vector3.zero;
        bag.transform.localScale = new Vector3(1.2f, 0.7f, 1.2f);
        ApplyMaterial(bag, color);
    }
    
    private static GameObject CreateSofa(string name, Transform parent, Vector3 position, Color color)
    {
        GameObject sofa = new GameObject(name);
        sofa.transform.parent = parent;
        sofa.transform.position = position;
        
        // Base
        GameObject base1 = GameObject.CreatePrimitive(PrimitiveType.Cube);
        base1.transform.parent = sofa.transform;
        base1.transform.localPosition = new Vector3(0, 0.3f, 0);
        base1.transform.localScale = new Vector3(2.5f, 0.6f, 1f);
        ApplyMaterial(base1, color);
        
        // Back
        GameObject back = GameObject.CreatePrimitive(PrimitiveType.Cube);
        back.transform.parent = sofa.transform;
        back.transform.localPosition = new Vector3(0, 1f, -0.45f);
        back.transform.localScale = new Vector3(2.5f, 1.4f, 0.2f);
        ApplyMaterial(back, color);
        
        // Arms
        GameObject armLeft = GameObject.CreatePrimitive(PrimitiveType.Cube);
        armLeft.transform.parent = sofa.transform;
        armLeft.transform.localPosition = new Vector3(-1.2f, 0.7f, 0);
        armLeft.transform.localScale = new Vector3(0.2f, 0.8f, 1f);
        ApplyMaterial(armLeft, color);
        
        GameObject armRight = GameObject.CreatePrimitive(PrimitiveType.Cube);
        armRight.transform.parent = sofa.transform;
        armRight.transform.localPosition = new Vector3(1.2f, 0.7f, 0);
        armRight.transform.localScale = new Vector3(0.2f, 0.8f, 1f);
        ApplyMaterial(armRight, color);
        
        // Cushions
        for (int i = -1; i <= 1; i++)
        {
            GameObject cushion = GameObject.CreatePrimitive(PrimitiveType.Cube);
            cushion.transform.parent = sofa.transform;
            cushion.transform.localPosition = new Vector3(i * 0.7f, 0.7f, 0.2f);
            cushion.transform.localScale = new Vector3(0.6f, 0.2f, 0.6f);
            ApplyMaterial(cushion, new Color(
                Mathf.Clamp01(color.r + 0.1f),
                Mathf.Clamp01(color.g + 0.1f),
                Mathf.Clamp01(color.b + 0.1f)
            ));
        }
        
        return sofa;
    }
    
    private static GameObject CreateArmchair(string name, Transform parent, Vector3 position, Color color)
    {
        GameObject armchair = new GameObject(name);
        armchair.transform.parent = parent;
        armchair.transform.position = position;
        
        // Base
        GameObject base1 = GameObject.CreatePrimitive(PrimitiveType.Cube);
        base1.transform.parent = armchair.transform;
        base1.transform.localPosition = new Vector3(0, 0.3f, 0);
        base1.transform.localScale = new Vector3(1.2f, 0.6f, 1.2f);
        ApplyMaterial(base1, color);
        
        // Back
        GameObject back = GameObject.CreatePrimitive(PrimitiveType.Cube);
        back.transform.parent = armchair.transform;
        back.transform.localPosition = new Vector3(0, 1f, -0.5f);
        back.transform.localScale = new Vector3(1.2f, 1.4f, 0.2f);
        ApplyMaterial(back, color);
        
        // Arms
        GameObject armLeft = GameObject.CreatePrimitive(PrimitiveType.Cube);
        armLeft.transform.parent = armchair.transform;
        armLeft.transform.localPosition = new Vector3(-0.6f, 0.7f, 0);
        armLeft.transform.localScale = new Vector3(0.2f, 0.8f, 1.2f);
        ApplyMaterial(armLeft, color);
        
        GameObject armRight = GameObject.CreatePrimitive(PrimitiveType.Cube);
        armRight.transform.parent = armchair.transform;
        armRight.transform.localPosition = new Vector3(0.6f, 0.7f, 0);
        armRight.transform.localScale = new Vector3(0.2f, 0.8f, 1.2f);
        ApplyMaterial(armRight, color);
        
        // Cushion
        GameObject cushion = GameObject.CreatePrimitive(PrimitiveType.Cube);
        cushion.transform.parent = armchair.transform;
        cushion.transform.localPosition = new Vector3(0, 0.7f, 0.2f);
        cushion.transform.localScale = new Vector3(1f, 0.2f, 0.7f);
        ApplyMaterial(cushion, new Color(
            Mathf.Clamp01(color.r + 0.1f),
            Mathf.Clamp01(color.g + 0.1f),
            Mathf.Clamp01(color.b + 0.1f)
        ));
        
        return armchair;
    }
    
    private static void ApplyMaterial(GameObject obj, Color color, bool transparent = false)
    {
        Renderer renderer = obj.GetComponent<Renderer>();
        if (renderer != null)
        {
            Material material = new Material(transparent ? Shader.Find("Standard") : Shader.Find("Standard"));
            material.color = color;
            
            if (transparent)
            {
                material.SetFloat("_Mode", 3); // Transparent mode
                material.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.One);
                material.SetInt("_DstBlend", (int)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
                material.SetInt("_ZWrite", 0);
                material.DisableKeyword("_ALPHATEST_ON");
                material.DisableKeyword("_ALPHABLEND_ON");
                material.EnableKeyword("_ALPHAPREMULTIPLY_ON");
                material.renderQueue = 3000;
            }
            
            renderer.material = material;
        }
    }
    #endregion
}