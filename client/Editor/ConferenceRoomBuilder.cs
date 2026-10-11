using System.Collections.Generic;
using System.IO;
using System.Linq;
using TMPro;
using UnityEditor;
using UnityEngine;
using UnityEngine.SceneManagement;

/// <summary>
/// Procedurally builds a realistic corporate conference-room interview environment.
/// Menu: VR Interview > Build Conference Room (prefab only).  Batch: -executeMethod ConferenceRoomBuilder.Build
/// Outputs: Assets/ConferenceRoom/ (materials, textures, prefab). ConferenceInterviewSceneBuilder uses the prefab.
/// </summary>
public static class ConferenceRoomBuilder
{
    const string Root = "Assets/ConferenceRoom";
    const string MatDir = Root + "/Materials";
    const string TexDir = Root + "/Textures";
    public const string PrefabPath = Root + "/ConferenceRoomEnvironment.prefab";

    // Room is centred on the origin, floor at y = 0.
    const float W = 8f;   // x extent
    const float D = 6f;   // z extent
    const float H = 3f;   // ceiling height
    const float TableTop = 0.775f;

    static Material carpet, wall, ceilingMat, wood, darkWood, fabric, metal,
        whiteboard, panel, glass, building, white, black, leaf, soil, pot, frameMat, paper, screen, tableWood;
    static Dictionary<string, Material> modelMats;
    static Dictionary<string, Material> art;
    const string ModelDir = Root + "/Models";

    [MenuItem("VR Interview/Build Conference Room")]
    public static void Build()
    {
        Directory.CreateDirectory(MatDir);
        Directory.CreateDirectory(TexDir);
        ImportPbrTextures();
        AssetDatabase.Refresh();
        MakeMaterials();

        var room = new GameObject("ConferenceRoomEnvironment");
        BuildShell(room.transform);
        BuildWindow(room.transform);
        BuildExterior(room.transform);
        BuildTable(room.transform);
        BuildSeating(room.transform);
        BuildWallDecor(room.transform);
        BuildProps(room.transform);
        BuildDetails(room.transform);
        BuildLighting(room.transform);
        BuildProbes(room.transform);
        MarkStatic(room.transform);

        var spawn = new GameObject("CandidateSpawn").transform;
        spawn.SetParent(room.transform, false);
        spawn.localPosition = new Vector3(0f, 0f, -0.98f);   // origin of the XR rig (seated, facing +z)

        PrefabUtility.SaveAsPrefabAsset(room, PrefabPath);
        Object.DestroyImmediate(room);

        AssetDatabase.SaveAssets();
        Debug.Log("[ConferenceRoomBuilder] Prefab written to " + PrefabPath);
    }

    // ---------------------------------------------------------------- textures / materials

    // CC0 PBR texture sets from ambientCG (see Assets/ConferenceRoom/Textures/PBR/*/License.txt)
    static void ImportPbrTextures()
    {
        AssetDatabase.Refresh();
        foreach (var guid in AssetDatabase.FindAssets("t:Texture2D", new[] { TexDir + "/PBR" }))
        {
            string path = AssetDatabase.GUIDToAssetPath(guid);
            var ti = AssetImporter.GetAtPath(path) as TextureImporter;
            if (ti == null) continue;
            bool normal = path.Contains("_NormalGL");
            bool data = path.Contains("_Roughness") || path.Contains("_AmbientOcclusion") || path.Contains("_Metalness");
            var wantType = normal ? TextureImporterType.NormalMap : TextureImporterType.Default;
            bool wantSrgb = !(normal || data);
            if (ti.textureType != wantType || ti.sRGBTexture != wantSrgb || ti.maxTextureSize != 1024)
            {
                ti.textureType = wantType;
                if (!normal) ti.sRGBTexture = wantSrgb;
                ti.maxTextureSize = 1024;
                ti.SaveAndReimport();
            }
        }
    }

    static Texture2D LoadTex(string path) => AssetDatabase.LoadAssetAtPath<Texture2D>(path);

    /// Standard-shader material from an ambientCG set: colour + normal + ambient occlusion, scalar smoothness.
    static Material Pbr(string name, string id, Color tint, Vector2 tiling, float smoothness, float normalStrength = 1f)
    {
        string dir = $"{TexDir}/PBR/{id}/{id}_1K-JPG";
        var m = new Material(Shader.Find("Standard")) { color = tint };
        m.SetTexture("_MainTex", LoadTex(dir + "_Color.jpg"));
        m.mainTextureScale = tiling;
        var normal = LoadTex(dir + "_NormalGL.jpg");
        if (normal != null)
        {
            m.SetTexture("_BumpMap", normal);
            m.SetFloat("_BumpScale", normalStrength);
            m.EnableKeyword("_NORMALMAP");
        }
        var ao = LoadTex(dir + "_AmbientOcclusion.jpg");
        if (ao != null)
        {
            m.SetTexture("_OcclusionMap", ao);
            m.SetFloat("_OcclusionStrength", 0.85f);
        }
        m.SetFloat("_Metallic", 0f);
        m.SetFloat("_Glossiness", smoothness);
        AssetDatabase.CreateAsset(m, $"{MatDir}/{name}.mat");
        return m;
    }

    static Material Mat(string name, Color c, float metallic = 0f, float smooth = 0.3f, string tex = null, Vector2? tiling = null)
    {
        var m = new Material(Shader.Find("Standard")) { color = c };
        m.SetFloat("_Metallic", metallic);
        m.SetFloat("_Glossiness", smooth);
        if (tex != null)
        {
            m.mainTexture = AssetDatabase.LoadAssetAtPath<Texture2D>($"{TexDir}/{tex}.png");
            m.mainTextureScale = tiling ?? Vector2.one;
        }
        AssetDatabase.CreateAsset(m, $"{MatDir}/{name}.mat");
        return m;
    }

    static Material Emissive(string name, Color c, float intensity)
    {
        var m = Mat(name, c, 0f, 0.2f);
        m.EnableKeyword("_EMISSION");
        m.globalIlluminationFlags = MaterialGlobalIlluminationFlags.None;   // area lights provide the light
        m.SetColor("_EmissionColor", c * intensity);
        return m;
    }

    static Material Transparent(string name, Color c)
    {
        var m = Mat(name, c, 0f, 0.95f);
        m.SetFloat("_Mode", 3);
        m.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.SrcAlpha);
        m.SetInt("_DstBlend", (int)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
        m.SetInt("_ZWrite", 0);
        m.DisableKeyword("_ALPHATEST_ON");
        m.EnableKeyword("_ALPHABLEND_ON");
        m.DisableKeyword("_ALPHAPREMULTIPLY_ON");
        m.renderQueue = 3000;
        return m;
    }

    static void MakeMaterials()
    {
        carpet = Pbr("Carpet", "Carpet012", new Color(0.85f, 0.87f, 0.92f), new Vector2(9, 7), 0.08f);
        wall = Pbr("Wall", "PaintedPlaster017", new Color(0.93f, 0.92f, 0.89f), new Vector2(3, 1.5f), 0.12f, 0.6f);
        ceilingMat = Pbr("Ceiling", "OfficeCeiling001", new Color(0.95f, 0.95f, 0.95f), new Vector2(2.4f, 1.9f), 0.06f);
        wood = Pbr("TableWood", "Wood049", new Color(0.95f, 0.88f, 0.82f), new Vector2(2.2f, 1f), 0.55f, 0.8f);
        darkWood = Pbr("DarkWood", "Wood049", new Color(0.42f, 0.32f, 0.28f), new Vector2(1.5f, 0.6f), 0.4f, 0.8f);
        fabric = Pbr("ChairFabric", "Fabric023", new Color(0.5f, 0.54f, 0.62f), new Vector2(1.5f, 1.5f), 0.12f);
        metal = Mat("Metal", new Color(0.65f, 0.66f, 0.68f), 0.9f, 0.7f);
        whiteboard = Mat("Whiteboard", new Color(0.96f, 0.96f, 0.97f), 0f, 0.85f);
        panel = Emissive("CeilingPanel", new Color(1f, 0.97f, 0.9f), 1.6f);
        glass = Transparent("WindowGlass", new Color(0.75f, 0.85f, 0.95f, 0.07f));
        building = Mat("Building", new Color(0.55f, 0.62f, 0.72f), 0.2f, 0.5f);
        white = Mat("White", new Color(0.95f, 0.95f, 0.95f), 0f, 0.3f);
        black = Mat("Black", new Color(0.04f, 0.04f, 0.04f), 0.3f, 0.6f);
        leaf = Mat("Leaf", new Color(0.12f, 0.38f, 0.14f), 0f, 0.4f);
        soil = Mat("Soil", new Color(0.15f, 0.1f, 0.07f), 0f, 0.05f);
        pot = Mat("Pot", new Color(0.85f, 0.85f, 0.82f), 0f, 0.5f);
        frameMat = Mat("Frame", new Color(0.7f, 0.7f, 0.72f), 0.8f, 0.5f);
        paper = Mat("Paper", new Color(0.97f, 0.96f, 0.9f), 0f, 0.1f);
        screen = Emissive("LaptopScreen", new Color(0.55f, 0.7f, 0.95f), 0.6f);
        tableWood = Pbr("TableTopWood", "Wood049", new Color(0.95f, 0.88f, 0.82f), new Vector2(3.1f, 1f), 0.55f, 0.8f);

        var chairPlastic = Mat("ChairPlastic", new Color(0.035f, 0.035f, 0.04f), 0.05f, 0.45f);
        var chrome = Mat("Chrome", new Color(0.75f, 0.77f, 0.8f), 1f, 0.8f);
        var leafB = Mat("Leaf2", new Color(0.17f, 0.46f, 0.16f), 0f, 0.4f);
        var stem = Mat("Stem", new Color(0.2f, 0.3f, 0.1f), 0f, 0.3f);
        var laptopMetal = Mat("LaptopMetal", new Color(0.62f, 0.63f, 0.66f), 0.9f, 0.55f);
        var laptopDark = Mat("LaptopDark", new Color(0.04f, 0.04f, 0.045f), 0.1f, 0.35f);
        var laptopScreen = Emissive("LaptopScreenGlow", new Color(0.35f, 0.5f, 0.75f), 0.55f);
        var mugWhite = Mat("MugWhite", new Color(0.93f, 0.93f, 0.9f), 0f, 0.75f);
        var mugCoffee = Mat("MugCoffee", new Color(0.12f, 0.07f, 0.04f), 0f, 0.9f);
        modelMats = new Dictionary<string, Material>
        {
            ["chair_fabric"] = fabric, ["chair_plastic"] = chairPlastic, ["chair_metal"] = chrome,
            ["leaf"] = leaf, ["leaf2"] = leafB, ["pot"] = pot, ["soil"] = soil, ["stem"] = stem,
            ["laptop_metal"] = laptopMetal, ["laptop_dark"] = laptopDark, ["laptop_screen"] = laptopScreen,
            ["mug_white"] = mugWhite, ["mug_coffee"] = mugCoffee, ["table_wood"] = tableWood,
        };
        var glassWare = Transparent("GlassWare", new Color(0.82f, 0.92f, 0.97f, 0.22f));
        var waterMat = Transparent("WaterInGlass", new Color(0.62f, 0.8f, 0.95f, 0.4f));
        modelMats["glass"] = glassWare;
        modelMats["water"] = waterMat;
        modelMats["plate_metal"] = frameMat;
        modelMats["led"] = Mat("PodRing", new Color(0.12f, 0.12f, 0.13f), 0.5f, 0.4f);
        modelMats["shelf_wood"] = darkWood;
        modelMats["trophy_gold"] = Mat("TrophyGold", new Color(0.85f, 0.66f, 0.22f), 0.9f, 0.7f);
        var bookCols = new Dictionary<string, Color>
        {
            ["book_red"] = new Color(0.55f, 0.1f, 0.1f), ["book_blue"] = new Color(0.1f, 0.2f, 0.5f), ["book_green"] = new Color(0.12f, 0.35f, 0.2f),
            ["book_tan"] = new Color(0.7f, 0.6f, 0.4f), ["book_black"] = new Color(0.06f, 0.06f, 0.07f), ["book_orange"] = new Color(0.8f, 0.4f, 0.1f),
            ["book_white"] = new Color(0.85f, 0.85f, 0.82f), ["book_teal"] = new Color(0.1f, 0.45f, 0.5f),
        };
        foreach (var kv in bookCols) modelMats[kv.Key] = Mat(kv.Key, kv.Value, 0f, 0.35f);
        modelMats["cooler_white"] = Mat("CoolerWhite", new Color(0.9f, 0.9f, 0.92f), 0f, 0.5f);
        modelMats["tap_blue"] = Mat("TapBlue", new Color(0.1f, 0.3f, 0.9f), 0f, 0.5f);
        modelMats["tap_red"] = Mat("TapRed", new Color(0.9f, 0.15f, 0.1f), 0f, 0.5f);
        modelMats["water_jug"] = Transparent("WaterJug", new Color(0.35f, 0.6f, 0.92f, 0.6f));
        modelMats["jacket"] = Mat("Jacket", new Color(0.15f, 0.17f, 0.22f), 0f, 0.2f);
        modelMats["bin_metal"] = Mat("BinMetal", new Color(0.35f, 0.36f, 0.38f), 0.7f, 0.5f);
        modelMats["blind"] = Mat("BlindSlat", new Color(0.9f, 0.88f, 0.84f), 0f, 0.4f);
        modelMats["blind_head"] = white;
        modelMats["lampshade"] = Mat("Lampshade", new Color(0.95f, 0.9f, 0.78f), 0f, 0.2f);

        art = new Dictionary<string, Material>();
        foreach (var n in new[] { "poster_mountains", "poster_city", "poster_abstract", "poster_teamwork", "whiteboard_notes", "corkboard", "certificate", "poster_map" })
            art[n] = ArtMat(n);
    }

    static Material ArtMat(string name)
    {
        string path = $"{TexDir}/Art/{name}.png";
        // sharp text on the whiteboard and certificate: high-quality compression, trilinear, anisotropic filtering
        var ti = AssetImporter.GetAtPath(path) as TextureImporter;
        if (ti != null)
        {
            ti.maxTextureSize = 2048;
            ti.filterMode = FilterMode.Trilinear;
            ti.anisoLevel = 8;
            ti.textureCompression = TextureImporterCompression.CompressedHQ;
            var android = ti.GetPlatformTextureSettings("Android");
            android.overridden = true;
            android.maxTextureSize = 2048;
            android.format = TextureImporterFormat.ASTC_4x4;
            ti.SetPlatformTextureSettings(android);
            ti.SaveAndReimport();
        }
        var m = new Material(Shader.Find("Standard")) { color = Color.white };
        m.mainTexture = AssetDatabase.LoadAssetAtPath<Texture2D>(path);
        m.SetFloat("_Metallic", 0f);
        m.SetFloat("_Glossiness", name == "whiteboard_notes" ? 0.7f : 0.25f);
        AssetDatabase.CreateAsset(m, $"{MatDir}/Art_{name}.mat");
        return m;
    }

    /// A framed picture on a wall. facing = +1 / -1 direction of the wall normal along the given axis (x or z).
    static void Picture(Transform parent, string name, string artName, Vector3 pos, Vector2 size, Quaternion rot, Material frame)
    {
        var g = Group(parent, name, pos);
        g.localRotation = rot;
        Box(g, "Frame", Vector3.zero, new Vector3(size.x + 0.08f, size.y + 0.08f, 0.04f), frame);
        var quad = GameObject.CreatePrimitive(PrimitiveType.Quad);
        quad.name = "Art";
        quad.transform.SetParent(g, false);
        quad.transform.localPosition = new Vector3(0f, 0f, -0.0215f);
        quad.transform.localScale = new Vector3(size.x, size.y, 1f);
        Object.DestroyImmediate(quad.GetComponent<Collider>());
        quad.GetComponent<Renderer>().sharedMaterial = art[artName];
    }

    /// Instantiate a Blender-generated FBX (Assets/ConferenceRoom/Models) and swap its materials for the project's.
    static Transform Model(Transform parent, string name, string fbx, Vector3 pos, float yaw, float scale = 1f)
    {
        var src = AssetDatabase.LoadAssetAtPath<GameObject>($"{ModelDir}/{fbx}.fbx");
        if (src == null) throw new System.Exception("Missing model " + fbx);
        var go = (GameObject)PrefabUtility.InstantiatePrefab(src);
        go.name = name;
        go.transform.SetParent(parent, false);
        go.transform.localPosition = pos;
        go.transform.localRotation = Quaternion.Euler(0f, yaw, 0f);
        go.transform.localScale = Vector3.one * scale;
        foreach (var r in go.GetComponentsInChildren<Renderer>())
        {
            var mats = r.sharedMaterials;
            for (int i = 0; i < mats.Length; i++)
                if (mats[i] != null && modelMats.TryGetValue(mats[i].name, out var m)) mats[i] = m;
            r.sharedMaterials = mats;
        }
        return go.transform;
    }

    static BoxCollider ColliderBox(Transform parent, string name, Vector3 center, Vector3 size)
    {
        var g = new GameObject(name);
        g.transform.SetParent(parent, false);
        g.transform.localPosition = center;
        var bc = g.AddComponent<BoxCollider>();
        bc.size = size;
        return bc;
    }

    // ---------------------------------------------------------------- primitive helpers

    static GameObject Prim(PrimitiveType type, Transform parent, string name, Vector3 pos, Vector3 scale, Material m, bool collider = false)
    {
        var g = GameObject.CreatePrimitive(type);
        g.name = name;
        g.transform.SetParent(parent, false);
        g.transform.localPosition = pos;
        g.transform.localScale = scale;
        g.GetComponent<Renderer>().sharedMaterial = m;
        if (!collider) Object.DestroyImmediate(g.GetComponent<Collider>());
        return g;
    }

    static GameObject Box(Transform p, string n, Vector3 pos, Vector3 size, Material m, bool col = false) => Prim(PrimitiveType.Cube, p, n, pos, size, m, col);
    static GameObject Ball(Transform p, string n, Vector3 pos, Vector3 size, Material m) => Prim(PrimitiveType.Sphere, p, n, pos, size, m);

    /// Cylinder of given radius/height standing on its centre point.
    static GameObject Cyl(Transform p, string n, Vector3 pos, float radius, float height, Material m, bool col = false) =>
        Prim(PrimitiveType.Cylinder, p, n, pos, new Vector3(radius * 2f, height * 0.5f, radius * 2f), m, col);

    /// Capsule spanning two points (arms, legs, stems).
    static GameObject Limb(Transform p, string n, Vector3 a, Vector3 b, float radius, Material m)
    {
        var g = Prim(PrimitiveType.Capsule, p, n, (a + b) * 0.5f, new Vector3(radius * 2f, (b - a).magnitude * 0.5f, radius * 2f), m);
        g.transform.localRotation = Quaternion.FromToRotation(Vector3.up, b - a);
        return g;
    }

    static Transform Group(Transform parent, string name, Vector3? pos = null, float yaw = 0f)
    {
        var t = new GameObject(name).transform;
        t.SetParent(parent, false);
        t.localPosition = pos ?? Vector3.zero;
        t.localRotation = Quaternion.Euler(0f, yaw, 0f);
        return t;
    }

    // ---------------------------------------------------------------- room

    static void BuildShell(Transform root)
    {
        var s = Group(root, "Shell");
        Box(s, "Floor", new Vector3(0, -0.05f, 0), new Vector3(W + 0.4f, 0.1f, D + 0.4f), carpet, true);
        Box(s, "Ceiling", new Vector3(0, H + 0.05f, 0), new Vector3(W + 0.4f, 0.1f, D + 0.4f), ceilingMat, true);
        Box(s, "Wall_North", new Vector3(0, H / 2, D / 2 + 0.1f), new Vector3(W + 0.4f, H, 0.2f), wall, true);
        Box(s, "Wall_South", new Vector3(0, H / 2, -D / 2 - 0.1f), new Vector3(W + 0.4f, H, 0.2f), wall, true);
        Box(s, "Wall_West", new Vector3(-W / 2 - 0.1f, H / 2, 0), new Vector3(0.2f, H, D), wall, true);

        // Baseboards
        Box(s, "Base_North", new Vector3(0, 0.07f, D / 2 - 0.01f), new Vector3(W, 0.14f, 0.02f), white);
        Box(s, "Base_South", new Vector3(0, 0.07f, -D / 2 + 0.01f), new Vector3(W, 0.14f, 0.02f), white);
        Box(s, "Base_West", new Vector3(-W / 2 + 0.01f, 0.07f, 0), new Vector3(0.02f, 0.14f, D), white);
        Box(s, "Base_East", new Vector3(W / 2 - 0.01f, 0.07f, 0), new Vector3(0.02f, 0.14f, D), white);

        // Door on the west wall
        Box(s, "DoorFrame", new Vector3(-W / 2 + 0.03f, 1.06f, -1.8f), new Vector3(0.06f, 2.12f, 1.05f), white);
        Box(s, "Door", new Vector3(-W / 2 + 0.06f, 1.02f, -1.8f), new Vector3(0.05f, 2.04f, 0.92f), darkWood);
        var handle = Cyl(s, "DoorHandle", new Vector3(-W / 2 + 0.12f, 1.0f, -1.5f), 0.015f, 0.12f, metal);
        handle.transform.localRotation = Quaternion.Euler(90, 0, 0);
    }

    static void BuildWindow(Transform root)
    {
        var w = Group(root, "Window");
        float x = W / 2 + 0.1f;
        // Wall pieces around a 3.6 m x 1.5 m opening (sill 0.9 m)
        Box(w, "Wall_East_Bottom", new Vector3(x, 0.45f, 0), new Vector3(0.2f, 0.9f, D), wall, true);
        Box(w, "Wall_East_Top", new Vector3(x, 2.7f, 0), new Vector3(0.2f, 0.6f, D), wall, true);
        Box(w, "Wall_East_Left", new Vector3(x, 1.65f, -2.4f), new Vector3(0.2f, 1.5f, 1.2f), wall, true);
        Box(w, "Wall_East_Right", new Vector3(x, 1.65f, 2.4f), new Vector3(0.2f, 1.5f, 1.2f), wall, true);

        Box(w, "Sill", new Vector3(W / 2 - 0.1f, 0.92f, 0), new Vector3(0.3f, 0.04f, 3.7f), white);
        Box(w, "Transom", new Vector3(W / 2 + 0.02f, 1.65f, 0), new Vector3(0.05f, 0.05f, 3.6f), frameMat);
        for (int i = -1; i <= 1; i += 2)
            Box(w, "Mullion", new Vector3(W / 2 + 0.02f, 1.65f, 1.2f * i * 0.5f), new Vector3(0.05f, 1.5f, 0.05f), frameMat);
        Box(w, "Mullion_Mid", new Vector3(W / 2 + 0.02f, 1.65f, 0), new Vector3(0.05f, 1.5f, 0.05f), frameMat);
        Box(w, "Glass", new Vector3(W / 2 + 0.03f, 1.65f, 0), new Vector3(0.01f, 1.5f, 3.6f), glass);

        // Venetian blinds, drawn a third of the way down
        var blinds = Model(w, "Blinds", "Blinds", new Vector3(W / 2 - 0.12f, 1.78f, 0f), 270f);
        blinds.localScale = new Vector3(1f, 0.55f, 1f);
    }

    static void BuildExterior(Transform root)
    {
        var e = Group(root, "Exterior");
        Box(e, "Ground", new Vector3(80f, -12f, 0), new Vector3(150f, 0.5f, 220f), Mat("Ground", new Color(0.25f, 0.27f, 0.3f)));
        var rng = new System.Random(7);
        for (int i = 0; i < 40; i++)
        {
            float bx = 18f + (float)rng.NextDouble() * 70f;
            float bz = -70f + (float)rng.NextDouble() * 140f;
            float h = 6f + (float)rng.NextDouble() * 45f;
            float wd = 5f + (float)rng.NextDouble() * 9f;
            var b = Box(e, "Building" + i, new Vector3(bx, -12f + (h + 12f) / 2f, bz), new Vector3(wd, h + 12f, wd * (0.8f + (float)rng.NextDouble() * 0.6f)), building);
            var r = b.GetComponent<Renderer>();
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            r.receiveShadows = false;
        }
    }

    // ---------------------------------------------------------------- furniture

    static void BuildTable(Transform root)
    {
        var t = Group(root, "ConferenceTable");
        var top = Model(t, "TableTop", "TableTop", new Vector3(0, 0.75f, 0), 0f);
        top.gameObject.AddComponent<MeshCollider>().sharedMesh = top.GetComponent<MeshFilter>().sharedMesh;
        foreach (int s in new[] { -1, 1 })
        {
            Box(t, "Leg", new Vector3(1.25f * s, 0.36f, 0), new Vector3(0.08f, 0.72f, 0.9f), darkWood, true);
            Box(t, "Foot", new Vector3(1.25f * s, 0.015f, 0), new Vector3(0.4f, 0.03f, 0.9f), metal);
        }
        Box(t, "Rail", new Vector3(0, 0.55f, 0), new Vector3(2.5f, 0.08f, 0.06f), darkWood);
    }

    static Transform Chair(Transform parent, string name, Vector3 pos, float yaw)
    {
        var c = Model(parent, name, "OfficeChair", pos, yaw);
        ColliderBox(c, "SeatCollider", new Vector3(0, 0.42f, 0), new Vector3(0.5f, 0.1f, 0.5f));
        ColliderBox(c, "BackCollider", new Vector3(0, 0.78f, -0.25f), new Vector3(0.48f, 0.52f, 0.1f));
        foreach (int s in new[] { -1, 1 })
            ColliderBox(c, "ArmCollider", new Vector3(0.27f * s, 0.64f, 0.0f), new Vector3(0.07f, 0.06f, 0.3f));
        return c;
    }

    static void BuildSeating(Transform root)
    {
        var g = Group(root, "Seating");
        // Candidate side (south, faces +z). Centre seat is where the XR rig sits.
        Chair(g, "Chair_Candidate", new Vector3(0, 0, -0.95f), 0f);
        Chair(g, "Chair_S1", new Vector3(-1.0f, 0, -0.95f), 8f);
        Chair(g, "Chair_S2", new Vector3(1.0f, 0, -1.05f), -5f);
        // Interviewer side (north, faces -z)
        Chair(g, "Chair_Interviewer", new Vector3(0, 0, 0.95f), 180f);   // the avatar sits here
        Chair(g, "Chair_N1", new Vector3(-1.0f, 0, 1.05f), 170f);
        Chair(g, "Chair_N2", new Vector3(1.0f, 0, 1.0f), 185f);
    }

    // ---------------------------------------------------------------- decor / props

    static void BuildWallDecor(Transform root)
    {
        var d = Group(root, "WallDecor");
        // Whiteboard on the north wall
        Box(d, "WB_Frame", new Vector3(-1.8f, 1.55f, D / 2 - 0.015f), new Vector3(2.3f, 1.3f, 0.03f), frameMat);
        Box(d, "WB_Board", new Vector3(-1.8f, 1.55f, D / 2 - 0.035f), new Vector3(2.2f, 1.2f, 0.02f), whiteboard, true);
        var wbArt = GameObject.CreatePrimitive(PrimitiveType.Quad);   // quad faces -z (into the room), so the writing reads correctly
        wbArt.name = "WB_Writing";
        wbArt.transform.SetParent(d, false);
        wbArt.transform.localPosition = new Vector3(-1.8f, 1.55f, D / 2 - 0.0465f);
        wbArt.transform.localScale = new Vector3(2.2f, 1.2f, 1f);
        Object.DestroyImmediate(wbArt.GetComponent<Collider>());
        wbArt.GetComponent<Renderer>().sharedMaterial = art["whiteboard_notes"];
        Box(d, "WB_Tray", new Vector3(-1.8f, 0.88f, D / 2 - 0.06f), new Vector3(1.0f, 0.03f, 0.08f), frameMat);
        // faint marker diagram lines
        // markers on the tray
        foreach (var mk in new[] { (-2.1f, new Color(0.1f, 0.2f, 0.7f)), (-1.98f, new Color(0.7f, 0.1f, 0.1f)), (-1.86f, new Color(0.1f, 0.45f, 0.2f)) })
            Cyl(d, "Marker", new Vector3(mk.Item1, 0.9f, D / 2 - 0.07f), 0.009f, 0.13f, Mat("Marker" + mk.Item1, mk.Item2)).transform.localRotation = Quaternion.Euler(0, 0, 90);

        // Framed abstract art
        Box(d, "Art_Frame", new Vector3(1.9f, 1.65f, D / 2 - 0.02f), new Vector3(1.1f, 0.8f, 0.04f), darkWood);
        Box(d, "Art_Canvas", new Vector3(1.9f, 1.65f, D / 2 - 0.045f), new Vector3(1.0f, 0.7f, 0.02f), white);
        Box(d, "Art_A", new Vector3(1.65f, 1.7f, D / 2 - 0.058f), new Vector3(0.45f, 0.5f, 0.006f), Mat("ArtTeal", new Color(0.1f, 0.45f, 0.5f)));
        Box(d, "Art_B", new Vector3(2.1f, 1.55f, D / 2 - 0.058f), new Vector3(0.4f, 0.3f, 0.006f), Mat("ArtOrange", new Color(0.9f, 0.5f, 0.15f)));

        // Pictures: north wall right of the art, east wall either side of the window, west wall between door and display
        var picFrame = Mat("PictureFrame", new Color(0.12f, 0.12f, 0.13f), 0.2f, 0.4f);
        var facingMinusZ = Quaternion.identity;                       // north wall: normal -z
        var facingMinusX = Quaternion.Euler(0f, 90f, 0f);             // east wall: normal -x
        var facingPlusX = Quaternion.Euler(0f, -90f, 0f);             // west wall: normal +x
        var facingPlusZ = Quaternion.Euler(0f, 180f, 0f);             // south wall: normal +z
        Picture(d, "Poster_City", "poster_city", new Vector3(0.55f, 1.55f, D / 2 - 0.03f), new Vector2(0.64f, 0.48f), facingMinusZ, picFrame);
        Picture(d, "Certificate", "certificate", new Vector3(W / 2 - 0.03f, 1.6f, 2.55f), new Vector2(0.64f, 0.48f), facingMinusX, darkWood);
        Picture(d, "Poster_Map", "poster_map", new Vector3(W / 2 - 0.03f, 1.6f, -2.4f), new Vector2(0.64f, 0.48f), facingMinusX, picFrame);
        Picture(d, "Poster_Mountains", "poster_mountains", new Vector3(-W / 2 + 0.03f, 1.65f, -0.1f + 0.0f), new Vector2(0.8f, 0.6f), facingPlusX, picFrame);
        Picture(d, "Corkboard", "corkboard", new Vector3(-W / 2 + 0.03f, 1.55f, 0.85f), new Vector2(0.52f, 0.34f), facingPlusX, darkWood);
        Picture(d, "Poster_Teamwork", "poster_teamwork", new Vector3(0f, 1.8f, -D / 2 + 0.03f), new Vector2(0.8f, 0.6f), facingPlusZ, picFrame);
        Picture(d, "Poster_Abstract", "poster_abstract", new Vector3(-2.2f, 1.6f, -D / 2 + 0.03f), new Vector2(0.54f, 0.72f), facingPlusZ, picFrame);

        // Wall clock on the south wall (behind the candidate)
        var clock = Cyl(d, "Clock", new Vector3(0, 2.4f, -D / 2 + 0.03f), 0.22f, 0.04f, white);
        clock.transform.localRotation = Quaternion.Euler(90, 0, 0);
        Box(d, "ClockHandH", new Vector3(0.03f, 2.43f, -D / 2 + 0.055f), new Vector3(0.012f, 0.1f, 0.006f), black);
        Box(d, "ClockHandM", new Vector3(0, 2.46f, -D / 2 + 0.055f), new Vector3(0.008f, 0.16f, 0.006f), black);

        // Ceiling light panels (emissive)
        foreach (float x in new[] { -2.4f, 0f, 2.4f })
            Box(d, "LightPanel", new Vector3(x, H - 0.015f, 0), new Vector3(1.4f, 0.03f, 0.7f), panel);
    }

    static void BuildProps(Transform root)
    {
        var p = Group(root, "Props");
        float ty = TableTop;

        // Credenza against the north wall
        Box(p, "Credenza", new Vector3(0, 0.35f, D / 2 - 0.3f), new Vector3(2.0f, 0.7f, 0.45f), darkWood, true);
        Box(p, "CredenzaTop", new Vector3(0, 0.71f, D / 2 - 0.3f), new Vector3(2.06f, 0.03f, 0.5f), wood);
        for (int i = -1; i <= 1; i++)
            Box(p, "CredenzaDoorLine", new Vector3(0.66f * i + 0.33f, 0.35f, D / 2 - 0.075f), new Vector3(0.01f, 0.64f, 0.005f), black);
        // Coffee machine, carafe and mugs on the credenza
        Model(p, "CoffeeMachine", "CoffeeMachine", new Vector3(0.55f, 0.725f, D / 2 - 0.3f), 180f);
        Model(p, "Carafe", "WaterCarafe", new Vector3(-0.65f, 0.725f, D / 2 - 0.3f), 0f);
        for (int i = 0; i < 3; i++) Model(p, "Mug", "Mug", new Vector3(-0.2f + i * 0.14f, 0.725f, D / 2 - 0.3f), 20f + i * 50f);

        // Water carafe & glasses on the table
        Model(p, "WaterCarafe", "WaterCarafe", new Vector3(0.15f, ty, 0.05f), 0f);
        foreach (var gp in new[] { new Vector3(0.32f, ty, 0.1f), new Vector3(-0.3f, ty, -0.1f), new Vector3(-0.62f, ty, 0.0f) })
            Model(p, "Glass", "WaterGlass", gp, 0f);

        // Furniture and dressing around the room
        Model(p, "Bookshelf", "Bookshelf", new Vector3(3.1f, 0f, D / 2 - 0.16f), 180f);
        ColliderBox(p.Find("Bookshelf"), "Collider", new Vector3(0, 0.95f, 0), new Vector3(0.95f, 1.9f, 0.3f));
        Model(p, "WaterCooler", "WaterCooler", new Vector3(-3.5f, 0f, D / 2 - 0.25f), 180f);
        ColliderBox(p.Find("WaterCooler"), "Collider", new Vector3(0, 0.7f, 0), new Vector3(0.34f, 1.45f, 0.34f));
        Model(p, "CoatStand", "CoatStand", new Vector3(-3.55f, 0f, -2.75f), 0f);
        Model(p, "WasteBin", "WasteBin", new Vector3(1.3f, 0f, D / 2 - 0.25f), 0f);
        Model(p, "FloorLamp", "FloorLamp", new Vector3(3.6f, 0f, 2.0f), 0f);

        // Interviewer notepad + pen + laptop (positions world-space, interviewer at +z)
        Box(p, "Notepad_I", new Vector3(0, ty + 0.008f, 0.36f), new Vector3(0.22f, 0.012f, 0.3f), paper).transform.localRotation = Quaternion.Euler(0, 6, 0);
        Cyl(p, "Pen_I", new Vector3(0.18f, ty + 0.01f, 0.36f), 0.006f, 0.15f, black).transform.localRotation = Quaternion.Euler(90, 0, 25);
        Model(p, "Laptop", "Laptop", new Vector3(-0.85f, ty, 0.4f), 18f);
        Model(p, "Mug_I", "Mug", new Vector3(0.45f, ty, 0.55f), 70f);
        Model(p, "Mug_C", "Mug", new Vector3(-0.4f, ty, -0.55f), -40f);
        Model(p, "NamePlate", "Nameplate", new Vector3(0.0f, ty, 0.22f), 0f);

        // Candidate notepad
        Box(p, "Notepad_C", new Vector3(0, ty + 0.008f, -0.45f), new Vector3(0.22f, 0.012f, 0.3f), paper).transform.localRotation = Quaternion.Euler(0, -4, 0);
        Box(p, "ResumeFolder", new Vector3(0.45f, ty + 0.012f, -0.4f), new Vector3(0.24f, 0.02f, 0.32f), Mat("Folder", new Color(0.15f, 0.25f, 0.45f)));

        BuildPlant(p, new Vector3(3.45f, 0, -2.35f));
        BuildPlant(p, new Vector3(-3.4f, 0, -0.75f));
    }

    static void BuildPlant(Transform parent, Vector3 pos)
    {
        var p = Model(parent, "Plant", "PottedPlant", pos, pos.x * 37f, 0.85f);
        ColliderBox(p, "PotCollider", new Vector3(0, 0.25f, 0), new Vector3(0.5f, 0.5f, 0.5f));
    }

    static void BuildDetails(Transform root)
    {
        var d = Group(root, "Details");

        // ceiling: two air vents, sprinkler heads, a smoke detector
        foreach (float x in new[] { -1.2f, 1.2f })
        {
            Box(d, "VentFrame", new Vector3(x, H - 0.012f, -1.9f), new Vector3(0.6f, 0.02f, 0.6f), white);
            for (int i = 0; i < 6; i++)
                Box(d, "VentSlat", new Vector3(x, H - 0.024f, -1.9f + (i - 2.5f) * 0.09f), new Vector3(0.52f, 0.008f, 0.025f), black);
        }
        foreach (var p in new[] { new Vector3(-3.1f, 0, -2.3f), new Vector3(3.1f, 0, -2.3f), new Vector3(-3.1f, 0, 2.3f), new Vector3(3.1f, 0, 2.3f) })
            Cyl(d, "Sprinkler", new Vector3(p.x, H - 0.015f, p.z), 0.022f, 0.03f, metal);
        Cyl(d, "SmokeDetector", new Vector3(0f, H - 0.02f, -2.55f), 0.07f, 0.035f, white);

        // walls: light switch by the door, power outlets
        Box(d, "LightSwitch", new Vector3(-W / 2 + 0.008f, 1.25f, -0.85f), new Vector3(0.016f, 0.12f, 0.08f), white);
        Box(d, "SwitchToggle", new Vector3(-W / 2 + 0.018f, 1.25f, -0.85f), new Vector3(0.012f, 0.04f, 0.025f), white);
        foreach (var o in new[] { new Vector3(-W / 2 + 0.008f, 0.35f, 2.5f), new Vector3(W / 2 - 0.008f, 0.35f, -2.6f), new Vector3(0f, 0.35f, D / 2 - 0.008f) })
            Box(d, "Outlet", o, o.x == 0f ? new Vector3(0.08f, 0.12f, 0.016f) : new Vector3(0.016f, 0.12f, 0.08f), white);

        // wall display on the west wall
        Box(d, "DisplayFrame", new Vector3(-W / 2 + 0.03f, 1.6f, 1.8f), new Vector3(0.05f, 0.68f, 1.18f), black, true);
        var screenMat = Mat("DisplayScreen", new Color(0.02f, 0.025f, 0.035f), 0.2f, 0.92f);
        Box(d, "DisplayScreen", new Vector3(-W / 2 + 0.057f, 1.6f, 1.8f), new Vector3(0.006f, 0.62f, 1.1f), screenMat);

        // company sign above the credenza
        Box(d, "SignPlaque", new Vector3(0f, 2.2f, D / 2 - 0.012f), new Vector3(1.9f, 0.34f, 0.024f), darkWood);
        var sign = new GameObject("CompanySign");
        sign.transform.SetParent(d, false);
        sign.transform.localPosition = new Vector3(0f, 2.2f, D / 2 - 0.03f);
        var text = sign.AddComponent<TextMeshPro>();
        text.text = "NIMBUS LABS";
        text.fontSize = 2.2f;
        text.enableAutoSizing = true;
        text.fontSizeMin = 0.9f;
        text.fontSizeMax = 2.2f;
        text.enableWordWrapping = false;
        text.alignment = TextAlignmentOptions.Center;
        text.color = new Color(0.88f, 0.92f, 0.96f);
        text.fontStyle = FontStyles.Bold;
        text.characterSpacing = 8f;
        text.rectTransform.sizeDelta = new Vector2(1.8f, 0.3f);

        // table: conference speakerphone and a cable grommet
        Model(d, "Speakerphone", "Speakerphone", new Vector3(-0.1f, TableTop, 0f), 0f);
        // (no cable grommet: the little black disc read as a button to press)
    }

    static void BuildLighting(Transform root)
    {
        var l = Group(root, "Lights");
        // Baked rectangle lights under each ceiling panel (area lights only exist in the baker; the panel mesh is the visible part).
        foreach (float x in new[] { -2.4f, 0f, 2.4f })
            foreach (float z in new[] { -0.9f, 0.9f })
                PointLight(l, "CeilingLight", new Vector3(x, H - 0.7f, z), new Color(1f, 0.95f, 0.86f), 0.6f, 12f);
        // Daylight coming through the east window
        AreaLight(l, "WindowSky", new Vector3(W / 2 - 0.1f, 1.65f, 0), Quaternion.Euler(0f, 270f, 0f), new Vector2(3.6f, 1.5f),
            new Color(0.72f, 0.84f, 1f), 1.5f);
    }

    static void PointLight(Transform parent, string name, Vector3 pos, Color color, float intensity, float range)
    {
        var go = new GameObject(name);
        go.transform.SetParent(parent, false);
        go.transform.localPosition = pos;
        var light = go.AddComponent<Light>();
        light.type = LightType.Point;
        light.color = color;
        light.intensity = intensity;
        light.range = range;
        light.lightmapBakeType = LightmapBakeType.Baked;
        light.shadows = LightShadows.Soft;
    }

    static void AreaLight(Transform parent, string name, Vector3 pos, Quaternion rot, Vector2 size, Color color, float intensity)
    {
        var go = new GameObject(name);
        go.transform.SetParent(parent, false);
        go.transform.localPosition = pos;
        go.transform.localRotation = rot;
        var light = go.AddComponent<Light>();
        light.type = LightType.Rectangle;
        light.areaSize = size;
        light.color = color;
        light.intensity = intensity;
        light.lightmapBakeType = LightmapBakeType.Baked;
        light.range = 40f;
        light.shadows = LightShadows.Soft;   // baked shadows
    }

    /// Light probes so the moving avatar and the controllers pick up the baked room light.
    static void BuildProbes(Transform root)
    {
        var go = new GameObject("LightProbes");
        go.transform.SetParent(root, false);
        var group = go.AddComponent<LightProbeGroup>();
        var pts = new List<Vector3>();
        foreach (float x in new[] { -3f, -1.8f, -0.6f, 0.6f, 1.8f, 3f })
            foreach (float y in new[] { 0.35f, 1.0f, 1.65f, 2.4f })
                foreach (float z in new[] { -2.4f, -1.3f, -0.3f, 0.5f, 1.4f, 2.4f })
                    pts.Add(new Vector3(x, y, z));
        group.probePositions = pts.ToArray();

        // Reflection probe: glossy surfaces (glass, metal, table) reflect the room instead of the sky.
        var rp = new GameObject("RoomReflection");
        rp.transform.SetParent(root, false);
        rp.transform.localPosition = new Vector3(0f, 1.4f, 0f);
        var probe = rp.AddComponent<ReflectionProbe>();
        probe.mode = UnityEngine.Rendering.ReflectionProbeMode.Baked;
        probe.boxProjection = true;
        probe.size = new Vector3(W, H + 0.2f, D);
        probe.resolution = 128;
        probe.intensity = 1f;
        probe.clearFlags = UnityEngine.Rendering.ReflectionProbeClearFlags.SolidColor;
        probe.backgroundColor = new Color(0.55f, 0.6f, 0.68f);
        probe.hdr = false;
    }

    /// Everything inside the room takes part in the lightmap bake; the far-away exterior does not.
    static void MarkStatic(Transform root)
    {
        var bakeFlags = StaticEditorFlags.ContributeGI | StaticEditorFlags.ReflectionProbeStatic | StaticEditorFlags.BatchingStatic;
        foreach (var t in root.GetComponentsInChildren<Transform>(true))
        {
            var go = t.gameObject;
            if (go == root.gameObject) continue;
            bool exterior = t.IsChildOf(root.Find("Exterior"));
            bool glassOrText = go.name == "Glass" || go.GetComponent<TMP_Text>() != null;
            bool hasRenderer = go.GetComponent<Renderer>() != null;
            GameObjectUtility.SetStaticEditorFlags(go, (exterior || glassOrText || !hasRenderer) ? 0 : bakeFlags);
        }
    }

    // ---------------------------------------------------------------- preview helper

    public static void Shot(string path, Vector3 pos, Vector3 lookAt, float fov)
    {
        var go = new GameObject("PreviewCam");
        var cam = go.AddComponent<Camera>();
        cam.transform.position = pos;
        cam.transform.LookAt(lookAt);
        cam.fieldOfView = fov;
        cam.nearClipPlane = 0.05f;
        cam.farClipPlane = 300f;
        cam.clearFlags = CameraClearFlags.Skybox;
        const int w = 1600, h = 900;
        var rt = RenderTexture.GetTemporary(w, h, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
        cam.targetTexture = rt;
        cam.Render();
        var prev = RenderTexture.active;
        RenderTexture.active = rt;
        var tex = new Texture2D(w, h, TextureFormat.RGB24, false);
        tex.ReadPixels(new Rect(0, 0, w, h), 0, 0);
        tex.Apply();
        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(path)));
        File.WriteAllBytes(path, tex.EncodeToPNG());
        RenderTexture.active = prev;
        cam.targetTexture = null;
        RenderTexture.ReleaseTemporary(rt);
        Object.DestroyImmediate(tex);
        Object.DestroyImmediate(go);
    }
}
