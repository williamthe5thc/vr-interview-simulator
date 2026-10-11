using UnityEditor;
using UnityEngine;

/// Import settings for the Blender-generated props in Assets/ConferenceRoom/Models (made in Blender; the Blender scripts are not included):
/// lightmap UVs so they can take baked light, no cameras/lights/animation.
public class ConferenceModelImport : AssetPostprocessor
{
    // bump to make Unity re-import every model when the import steps change
    public override uint GetVersion() => 3;

    // Microsoft Rocketbox characters (Assets/Rocketbox): humanoid rig, face shapes kept, materials made by the scene builder
    void OnPreprocessTexture()
    {
        if (!assetPath.StartsWith("Assets/Rocketbox/")) return;
        var ti = (TextureImporter)assetImporter;
        string lower = assetPath.ToLowerInvariant();
        if (lower.EndsWith("_normal.png")) ti.textureType = TextureImporterType.NormalMap;
        ti.maxTextureSize = 1024;
        ti.mipmapEnabled = true;
        ti.textureCompression = TextureImporterCompression.CompressedHQ;
        if (lower.Contains("opacity")) ti.alphaIsTransparency = true;
    }

    // The Rocketbox faces ship with 176 blend shapes; the interview only needs the 15 visemes, blinks, brows and a few more.
    // Keeping them all made every character ~15-20 MB of mesh data (about 200 MB for the 11 interviewers) and the build crashed on Quest 1.
    static readonly string[] KeepShapes =
    {
        "AA_VI_00_Sil", "AA_VI_01_PP", "AA_VI_02_FF", "AA_VI_03_TH", "AA_VI_04_DD", "AA_VI_05_KK", "AA_VI_06_CH", "AA_VI_07_SS",
        "AA_VI_08_nn", "AA_VI_09_RR", "AA_VI_10_aa", "AA_VI_11_E", "AA_VI_12_I", "AA_VI_13_O", "AA_VI_14_U",
        "AK_01_", "AK_02_", "AK_03_", "AK_04_", "AK_05_", "AK_09_", "AK_10_", "AK_19_", "AK_20_", "AK_21_", "AK_22_", "AK_25_", "AK_27_",
        "MouthSmile",
    };

    void OnPostprocessModel(GameObject root)
    {
        if (!assetPath.StartsWith("Assets/Rocketbox/")) return;
        foreach (var smr in root.GetComponentsInChildren<SkinnedMeshRenderer>(true))
        {
            var mesh = smr.sharedMesh;
            if (mesh == null || mesh.blendShapeCount == 0) continue;
            int before = mesh.blendShapeCount;
            var names = new System.Collections.Generic.List<string>();
            var weights = new System.Collections.Generic.List<float>();
            var dv = new System.Collections.Generic.List<Vector3[]>();
            var dn = new System.Collections.Generic.List<Vector3[]>();
            var dt = new System.Collections.Generic.List<Vector3[]>();
            for (int i = 0; i < before; i++)
            {
                string name = mesh.GetBlendShapeName(i);
                bool keep = false;
                foreach (var k in KeepShapes) if (name.Contains(k)) { keep = true; break; }
                if (!keep) continue;
                var v = new Vector3[mesh.vertexCount]; var n = new Vector3[mesh.vertexCount]; var t = new Vector3[mesh.vertexCount];
                mesh.GetBlendShapeFrameVertices(i, 0, v, n, t);
                names.Add(name); weights.Add(mesh.GetBlendShapeFrameWeight(i, 0)); dv.Add(v); dn.Add(n); dt.Add(t);
            }
            mesh.ClearBlendShapes();
            for (int i = 0; i < names.Count; i++) mesh.AddBlendShapeFrame(names[i], weights[i], dv[i], dn[i], dt[i]);
            Debug.Log($"[RocketboxImport] {assetPath}: {smr.name} blend shapes {before} -> {mesh.blendShapeCount}");
        }
    }

    void OnPreprocessModel()
    {
        if (assetPath.StartsWith("Assets/Rocketbox/"))
        {
            var rb = (ModelImporter)assetImporter;
            rb.animationType = ModelImporterAnimationType.Human;
            rb.avatarSetup = ModelImporterAvatarSetup.CreateFromThisModel;
            rb.importBlendShapes = true;
            rb.importAnimation = false;
            rb.importCameras = false;
            rb.importLights = false;
            rb.isReadable = false;
            rb.meshCompression = ModelImporterMeshCompression.Off;
            rb.materialImportMode = ModelImporterMaterialImportMode.ImportViaMaterialDescription;
            rb.materialLocation = ModelImporterMaterialLocation.InPrefab;
            return;
        }
        if (!assetPath.StartsWith("Assets/ConferenceRoom/Models/")) return;
        var mi = (ModelImporter)assetImporter;
        mi.generateSecondaryUV = true;
        mi.importCameras = false;
        mi.importLights = false;
        mi.importAnimation = false;
        mi.isReadable = false;
        mi.meshCompression = ModelImporterMeshCompression.Off;
        mi.globalScale = 1f;
    }

    /// Batch helper: prints which way each prop faces after import. -executeMethod ConferenceModelImport.Probe
    public static void Probe()
    {
        AssetDatabase.Refresh();
        foreach (var name in new[] { "OfficeChair", "PottedPlant", "Laptop", "Mug", "TableTop" })
        {
            var go = AssetDatabase.LoadAssetAtPath<GameObject>($"Assets/ConferenceRoom/Models/{name}.fbx");
            if (go == null) { Debug.Log($"[Probe] {name}: missing"); continue; }
            var mf = go.GetComponentInChildren<MeshFilter>();
            var mesh = mf.sharedMesh;
            var verts = mesh.vertices;
            Vector3 top = verts[0], maxX = verts[0];
            foreach (var v in verts) { if (v.y > top.y) top = v; if (v.x > maxX.x) maxX = v; }
            Debug.Log($"[Probe] {name}: bounds center={mesh.bounds.center:F3} size={mesh.bounds.size:F3} topVertex={top:F3} " +
                      $"rootRot={go.transform.localRotation.eulerAngles} childRot={mf.transform.localRotation.eulerAngles} childScale={mf.transform.localScale} " +
                      $"uv2={(mesh.uv2 != null && mesh.uv2.Length > 0)} materials=[{string.Join(",", System.Array.ConvertAll(mf.GetComponent<Renderer>().sharedMaterials, m => m.name))}]");
        }
        EditorApplication.Exit(0);
    }
}
