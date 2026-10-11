using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using TMPro;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;
using UnityEngine.XR.Interaction.Toolkit.UI;

/// <summary>
/// Builds Assets/Scenes/VRInterviewScene_Conference.unity: a copy of the main VR interview scene with
///  - the procedural conference room (via EnvironmentManager, spawned at runtime like the other environments),
///  - the project's rigged avatar seated across the table, animated by InterviewerBody / Face / Gaze,
///  - the candidate's XR rig moved to the candidate chair,
///  - SessionManager and AudioManager wired to the AvatarController (they were unassigned).
/// The original scene is never modified.
/// Menu: VR Interview > Build Conference Interview Scene.  Batch: -executeMethod ConferenceInterviewSceneBuilder.Build
/// </summary>
public static class ConferenceInterviewSceneBuilder
{
    const string SrcScene = "Assets/VRInterviewScene.unity";
    const string DstScene = "Assets/Scenes/VRInterviewScene_Conference.unity";
    const string PreviewDir = "ConferenceRoomPreviews";

    // The interview server (D:r_interview_system, port 8765) runs on this PC. The old scene pointed at YOUR_PC_LAN_IP,
    // which is not this machine. Change this if the PC's address changes.
    const string ServerUrl = "ws://YOUR_PC_TAILSCALE_IP:8765,ws://YOUR_PC_LAN_IP:8765";   // Tailscale address first (works anywhere), then the home LAN

    // Room geometry shared with ConferenceRoomBuilder (table top 0.775, table edge on the interviewer side at z = 0.65,
    // interviewer chair at z = 0.95 with a seat top of 0.48 m).
    const float TableTop = 0.775f, TableEdgeZ = 0.65f;
    const float SeatedHipsY = 0.58f, SeatedHipsZ = 0.93f;
    // Seated eye height should be ~1.25 m (seat top 0.48 + ~0.77). The XR Origin adds its camera height on top of the rig
    // position (about 1.12 m offset in Device mode, or a seated user's real head height in Floor mode), so the rig itself
    // sits near the floor. The original scene put it at y = 0.96, which put the candidate's eyes at ~2.1 m.
    static readonly Vector3 CandidateRigPosition = new Vector3(0f, 0.13f, -1.0f);
    static readonly Color SunColor = new Color(1f, 0.93f, 0.8f);

    class Interviewer
    {
        public GameObject root;
        public Animator animator;
        public AvatarController controller;
        public InterviewerBody body;
        public InterviewerFace face;
        public InterviewerGaze gaze;
        public Sunbox.Avatars.AvatarCustomization customization;
    }

    [MenuItem("VR Interview/Build Conference Interview Scene")]
    public static void Build()
    {
        ConferenceRoomBuilder.Build();   // (re)generates materials and the room prefab
        var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(ConferenceRoomBuilder.PrefabPath);

        Directory.CreateDirectory("Assets/Scenes");
        AssetDatabase.DeleteAsset(DstScene);
        if (!AssetDatabase.CopyAsset(SrcScene, DstScene))
            throw new System.Exception("Could not copy " + SrcScene);
        var scene = EditorSceneManager.OpenScene(DstScene, OpenSceneMode.Single);

        ReplaceEnvironment(prefab);
        SetupLighting();
        MoveCandidateRig();
        AddCandidateHands();
        Interviewer iv;
        if (castLimit > 0)
        {
            BuildCast(out iv, out var castVoice);
            WireManagers(iv, castVoice);
        }
        else
        {
            // bisecting a crash: the original single pack avatar and no cast
            iv = SetupInterviewer();
            AddAvatarHitboxes(iv);
            WireManagers(iv, null);
        }
        SetServerUrl();
        FixUiInput();
        HideOldButtons();
        AddPushToTalk();
        BuildFlowUi();

        EditorSceneManager.MarkSceneDirty(scene);
        EditorSceneManager.SaveScene(scene);
        BakeLighting();
        EditorSceneManager.MarkSceneDirty(scene);
        EditorSceneManager.SaveScene(scene);
        Debug.Log("[ConferenceInterviewSceneBuilder] Saved " + DstScene);

        // Previews pose the skeleton and instantiate the room; none of that is saved.
        RenderPreviews(prefab, iv);
    }

    // ---------------------------------------------------------------- scene edits

    static SerializedObject SO(Object o) => new SerializedObject(o);

    static void ReplaceEnvironment(GameObject prefab)
    {
        var old = GameObject.Find("CorporateEnvironment");
        if (old != null) Object.DestroyImmediate(old);

        // EnvironmentManager instantiates under its parent. The old scene parented it to the manager itself,
        // which sits 5 m up and to the side; a zero transform keeps the room where the rig expects it.
        var parent = new GameObject("EnvironmentRoot");

        var em = Object.FindObjectOfType<EnvironmentManager>();
        var so = SO(em);
        var envs = so.FindProperty("environments");
        envs.arraySize = 1;
        var e = envs.GetArrayElementAtIndex(0);
        e.FindPropertyRelative("name").stringValue = "Conference Room";
        e.FindPropertyRelative("environmentPrefab").objectReferenceValue = prefab;
        e.FindPropertyRelative("ambientAudio").objectReferenceValue = null;
        e.FindPropertyRelative("ambientVolume").floatValue = 0.1f;
        e.FindPropertyRelative("lightingTint").colorValue = SunColor;   // was (0,0,0,0): switched the sun off
        so.FindProperty("defaultEnvironmentIndex").intValue = 0;
        so.FindProperty("environmentParent").objectReferenceValue = parent.transform;
        so.ApplyModifiedProperties();

        // Static scene object: the lightmap bake needs it in the scene, and EnvironmentManager would spawn a second, unbaked copy.
        em.enabled = false;
        var room = (GameObject)PrefabUtility.InstantiatePrefab(prefab);
        room.name = "ConferenceRoomEnvironment";
        room.transform.SetParent(parent.transform, false);
    }

    static void SetupLighting()
    {
        var em = Object.FindObjectOfType<EnvironmentManager>();
        var so = SO(em);
        var sun = so.FindProperty("mainDirectionalLight").objectReferenceValue as Light;
        if (sun == null)
            foreach (var l in Object.FindObjectsOfType<Light>(true))
                if (l.type == LightType.Directional) { sun = l; break; }
        if (sun == null)
        {
            var go = new GameObject("Sun");
            sun = go.AddComponent<Light>();
            sun.type = LightType.Directional;
        }
        sun.gameObject.SetActive(true);
        sun.enabled = true;
        sun.transform.rotation = Quaternion.Euler(38f, 270f, 0f);   // in through the east window
        sun.color = SunColor;
        sun.intensity = 1.1f;
        sun.shadows = LightShadows.Soft;
        sun.shadowStrength = 0.75f;
        sun.lightmapBakeType = LightmapBakeType.Baked;   // no realtime shadows: they crash Quest 1 with Rocketbox characters (SIGSEGV, found Oct 6); the room's light and shadows are baked
        so.FindProperty("mainDirectionalLight").objectReferenceValue = sun;
        so.ApplyModifiedProperties();

        RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Flat;
        RenderSettings.ambientLight = new Color(0.62f, 0.64f, 0.68f);
        RenderSettings.fog = false;

        // Light probes light the avatar and the controllers; the room itself is lightmapped.
        Directory.CreateDirectory("Assets/Scenes");
        var ls = AssetDatabase.LoadAssetAtPath<LightingSettings>(LightingPath);
        if (ls == null)
        {
            ls = new LightingSettings();
            AssetDatabase.CreateAsset(ls, LightingPath);
        }
        ls.lightmapper = LightingSettings.Lightmapper.ProgressiveCPU;
        ls.bakedGI = true;
        ls.realtimeGI = false;
        ls.autoGenerate = false;
        ls.mixedBakeMode = MixedLightingMode.IndirectOnly;
        ls.lightmapResolution = 40f;
        ls.lightmapPadding = 2;
        ls.lightmapMaxSize = 2048;
        ls.directSampleCount = 64;
        ls.indirectSampleCount = 256;
        ls.environmentSampleCount = 128;
        ls.maxBounces = 5;
        ls.ao = true;
        ls.aoMaxDistance = 0.8f;
        ls.compressLightmaps = true;
        ls.directionalityMode = LightmapsMode.NonDirectional;   // one texture, cheaper shaders on Quest
        ls.filteringMode = LightingSettings.FilterMode.Auto;
        ls.prioritizeView = false;
        EditorUtility.SetDirty(ls);
        AssetDatabase.SaveAssets();
        Lightmapping.lightingSettings = ls;
    }

    const string LightingPath = "Assets/Scenes/ConferenceLighting.lighting";

    static bool skipBake;
    static int castLimit = 11;    // how many Rocketbox interviewers to build (0 = the original pack avatar only; the Rocketbox cast crashes on Quest 1 for now)

    public static void BuildFastCast0() { castLimit = 0; BuildFast(); }
    public static void BuildFastCast1() { castLimit = 1; BuildFast(); }

    /// Same as Build but without the lightmap bake (about 1.5 minutes): for checking poses and props.
    public static void BuildFast()
    {
        skipBake = true;
        Build();
    }

    static void BakeLighting()
    {
        if (skipBake) { Debug.Log("[ConferenceInterviewSceneBuilder] Bake skipped (BuildFast)"); return; }
        Lightmapping.Clear();
        var sw = System.Diagnostics.Stopwatch.StartNew();
        bool ok = Lightmapping.Bake();
        Debug.Log($"[ConferenceInterviewSceneBuilder] Lightmap bake ok={ok} in {sw.Elapsed.TotalSeconds:F0}s, lightmaps={LightmapSettings.lightmaps.Length}" + (LightmapSettings.lightmaps.Length > 0 ? $" size={LightmapSettings.lightmaps[0].lightmapColor.width}" : ""));
    }

    static void MoveCandidateRig()
    {
        var rig = GameObject.Find("XR Origin (XR Rig)");
        if (rig == null) return;
        Vector3 delta = CandidateRigPosition - rig.transform.position;
        rig.transform.position = CandidateRigPosition;

        // The world-space UI was laid out ~1.4 m in front of the candidate; keep that distance. Its heights (1.3 to 1.6 m)
        // sit at or just above the new 1.25 m eye height, so they need no change.
        var canvas = GameObject.Find("Canvas");
        if (canvas != null) canvas.transform.position += new Vector3(delta.x, 0f, delta.z);
    }

    /// The scene's controllers have no visible model, so the candidate sees nothing of themselves. Give each controller a hand.
    static void AddCandidateHands()
    {
        var src = AssetDatabase.LoadAssetAtPath<GameObject>("Assets/ConferenceRoom/Models/VRHandRight.fbx");
        if (src == null) { Debug.LogWarning("VRHandRight.fbx missing; candidate hands skipped"); return; }
        var skin = new Material(Shader.Find("Standard")) { color = new Color(0.74f, 0.55f, 0.42f) };
        skin.SetFloat("_Glossiness", 0.3f);
        AssetDatabase.CreateAsset(skin, "Assets/ConferenceRoom/Materials/CandidateHand.mat");

        foreach (var side in new[] { "Left", "Right" })
        {
            var controller = GameObject.Find(side + " Controller");
            if (controller == null) { Debug.LogWarning("No '" + side + " Controller' object; hand skipped"); continue; }
            var old = controller.transform.Find("CandidateHand");
            if (old != null) Object.DestroyImmediate(old.gameObject);
            var hand = (GameObject)PrefabUtility.InstantiatePrefab(src);
            hand.name = "CandidateHand";
            hand.transform.SetParent(controller.transform, false);
            hand.transform.localPosition = new Vector3(0f, -0.03f, -0.04f);
            hand.transform.localRotation = Quaternion.Euler(35f, 0f, 0f);
            hand.transform.localScale = side == "Left" ? new Vector3(-1f, 1f, 1f) : Vector3.one;   // mirrored copy
            foreach (var r in hand.GetComponentsInChildren<Renderer>())
            {
                var mats = new Material[r.sharedMaterials.Length];
                for (int i = 0; i < mats.Length; i++) mats[i] = skin;
                r.sharedMaterials = mats;
                r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            }
            foreach (var c in hand.GetComponentsInChildren<Collider>()) Object.DestroyImmediate(c);
            hand.AddComponent<HandVisibility>().node = side == "Left" ? UnityEngine.XR.XRNode.LeftHand : UnityEngine.XR.XRNode.RightHand;   // hide the glove when hand tracking is in use
        }
    }

    static Interviewer SetupInterviewer(GameObject rootGo = null, AudioSource sharedVoice = null)
    {
        var iv = new Interviewer { root = rootGo != null ? rootGo : GameObject.Find("Avatar") };
        iv.customization = iv.root.GetComponent<Sunbox.Avatars.AvatarCustomization>();
        foreach (var a in iv.root.GetComponentsInChildren<Animator>(false))
            if (a.avatar != null && a.avatar.isHuman) { iv.animator = a; break; }
        if (iv.animator == null) throw new System.Exception("No active humanoid Animator under 'Avatar'");

        // Face the candidate and put the hips at seat height over the interviewer chair.
        // (characters from different tools face different ways, so find which way this one faces from its leg bones)
        var legL = iv.animator.GetBoneTransform(HumanBodyBones.LeftUpperLeg);
        var legR = iv.animator.GetBoneTransform(HumanBodyBones.RightUpperLeg);
        Vector3 facing = Vector3.Cross(legR.position - legL.position, Vector3.up);
        facing.y = 0f;
        float turn = Vector3.SignedAngle(facing, Vector3.back, Vector3.up);   // about the vertical axis only (a plain FromToRotation flips her upside down when she faces exactly away)
        iv.root.transform.rotation = Quaternion.AngleAxis(turn, Vector3.up) * iv.root.transform.rotation;
        var hips = iv.animator.GetBoneTransform(HumanBodyBones.Hips);
        iv.root.transform.position += new Vector3(0f - hips.position.x, SeatedHipsY - hips.position.y, SeatedHipsZ - hips.position.z);

        Debug.Log($"[ConferenceInterviewSceneBuilder] seated {iv.root.name}: root {iv.root.transform.position:F2} rot {iv.root.transform.eulerAngles:F0}, hips {hips.position:F2}, animator {iv.animator.name} at {iv.animator.transform.position:F2}");
        // Solve the seated pose, then put the skeleton back exactly as it was: the pose is applied at runtime.
        var saved = Snapshot(iv.animator.transform);
        var solved = InterviewerSeatSolver.Solve(iv.animator, TableTop - SeatedHipsY, SeatedHipsZ - TableEdgeZ, 0.14f);
        Restore(saved);
        Debug.Log("[ConferenceInterviewSceneBuilder] Seat solve:\n" + solved.report);

        iv.body = GetOrAdd<InterviewerBody>(iv.root);
        iv.face = GetOrAdd<InterviewerFace>(iv.root);
        iv.gaze = GetOrAdd<InterviewerGaze>(iv.root);
        iv.controller = GetOrAdd<AvatarController>(iv.root);

        iv.body.Animator = iv.animator;
        iv.body.SetSeatedPose(solved.names, solved.values);

        // Voice comes out of the mouth, not the avatar's feet. This is the AudioSource AudioManager plays on.
        var audio = sharedVoice != null ? sharedVoice : iv.root.GetComponentInChildren<AudioSource>(true);
        var head = iv.animator.GetBoneTransform(HumanBodyBones.Head);
        if (audio != null && head != null)
        {
            var eyeL = head.Find("Eye_L"); var eyeR = head.Find("Eye_R");
            Vector3 eyeMid = eyeL != null && eyeR != null ? (eyeL.position + eyeR.position) * 0.5f : head.position + Vector3.up * 0.08f;
            Vector3 fwd = iv.root.transform.forward; fwd.y = 0f;
            audio.transform.position = eyeMid - Vector3.up * 0.065f + fwd.normalized * 0.07f;
            audio.transform.SetParent(head, true);
            audio.playOnAwake = false;
            audio.spatialBlend = 1f;
            audio.dopplerLevel = 0f;
            audio.minDistance = 0.8f;
            audio.maxDistance = 12f;
            audio.rolloffMode = AudioRolloffMode.Logarithmic;
        }

        var notes = GameObject.Find("InterviewerNotes");
        if (notes == null) notes = new GameObject("InterviewerNotes");
        notes.transform.position = new Vector3(0f, TableTop + 0.01f, 0.5f);   // the interviewer's notepad

        var gazeRoot = iv.root.transform.Find("GazeTarget");
        if (gazeRoot == null)
        {
            var gt = new GameObject("GazeTarget");
            gt.transform.SetParent(iv.root.transform, false);
            gazeRoot = gt.transform;
        }

        var cso = SO(iv.controller);
        cso.FindProperty("animator").objectReferenceValue = iv.animator;
        cso.FindProperty("audioSource").objectReferenceValue = audio;
        cso.FindProperty("headBone").objectReferenceValue = head;
        cso.FindProperty("body").objectReferenceValue = iv.body;
        cso.FindProperty("face").objectReferenceValue = iv.face;
        cso.FindProperty("gaze").objectReferenceValue = iv.gaze;
        cso.ApplyModifiedProperties();

        var fso = SO(iv.face);
        fso.FindProperty("voice").objectReferenceValue = audio;
        fso.FindProperty("body").objectReferenceValue = iv.body;
        fso.ApplyModifiedProperties();

        var gso = SO(iv.gaze);
        gso.FindProperty("animator").objectReferenceValue = iv.animator;
        gso.FindProperty("face").objectReferenceValue = iv.face;
        gso.FindProperty("notesTarget").objectReferenceValue = notes.transform;
        gso.FindProperty("gazeTargetRoot").objectReferenceValue = gazeRoot;
        gso.ApplyModifiedProperties();

        return iv;
    }

    /// Solid hit boxes on the interviewer's body so rays and physics objects stop at her instead of passing through.
    /// The colliders sit on the animated bones; a kinematic Rigidbody on the root lets them move without PhysX rebuilds.
    static void AddAvatarHitboxes(Interviewer iv)
    {
        var rb = GetOrAdd<Rigidbody>(iv.root);
        rb.isKinematic = true;
        rb.useGravity = false;

        void Capsule(HumanBodyBones from, HumanBodyBones to, float radius)
        {
            var a = iv.animator.GetBoneTransform(from);
            var b = iv.animator.GetBoneTransform(to);
            if (a == null || b == null || a.GetComponent<Collider>() != null) return;
            Vector3 local = a.InverseTransformPoint(b.position);
            var col = a.gameObject.AddComponent<CapsuleCollider>();
            float ax = Mathf.Abs(local.x), ay = Mathf.Abs(local.y), az = Mathf.Abs(local.z);
            col.direction = ax >= ay && ax >= az ? 0 : (ay >= az ? 1 : 2);
            col.radius = radius / Mathf.Max(0.01f, a.lossyScale.x);
            col.height = local.magnitude + col.radius * 2f;
            col.center = local * 0.5f;
        }

        Capsule(HumanBodyBones.Hips, HumanBodyBones.Spine, 0.15f);
        Capsule(HumanBodyBones.Spine, HumanBodyBones.Chest, 0.15f);
        Capsule(HumanBodyBones.Chest, HumanBodyBones.Neck, 0.16f);
        Capsule(HumanBodyBones.Neck, HumanBodyBones.Head, 0.06f);
        Capsule(HumanBodyBones.LeftUpperArm, HumanBodyBones.LeftLowerArm, 0.05f);
        Capsule(HumanBodyBones.RightUpperArm, HumanBodyBones.RightLowerArm, 0.05f);
        Capsule(HumanBodyBones.LeftLowerArm, HumanBodyBones.LeftHand, 0.045f);
        Capsule(HumanBodyBones.RightLowerArm, HumanBodyBones.RightHand, 0.045f);
        Capsule(HumanBodyBones.LeftUpperLeg, HumanBodyBones.LeftLowerLeg, 0.08f);
        Capsule(HumanBodyBones.RightUpperLeg, HumanBodyBones.RightLowerLeg, 0.08f);
        Capsule(HumanBodyBones.LeftLowerLeg, HumanBodyBones.LeftFoot, 0.06f);
        Capsule(HumanBodyBones.RightLowerLeg, HumanBodyBones.RightFoot, 0.06f);

        var head = iv.animator.GetBoneTransform(HumanBodyBones.Head);
        if (head != null && head.GetComponent<Collider>() == null)
        {
            var eyeL = head.Find("Eye_L"); var eyeR = head.Find("Eye_R");
            var sphere = head.gameObject.AddComponent<SphereCollider>();
            sphere.radius = 0.11f;
            sphere.center = eyeL != null && eyeR != null ? head.InverseTransformPoint((eyeL.position + eyeR.position) * 0.5f) : Vector3.up * 0.1f;
        }
    }

    static void WireManagers(Interviewer iv, AudioSource voice)
    {
        foreach (var o in new Object[] { Object.FindObjectOfType<SessionManager>(), Object.FindObjectOfType<AudioManager>() })
        {
            if (o == null) continue;
            var so = SO(o);
            var p = so.FindProperty("avatarController");
            if (p != null) { p.objectReferenceValue = iv.controller; so.ApplyModifiedProperties(); }
        }
        // every interviewer speaks through the one shared voice source
        var audioManager = Object.FindObjectOfType<AudioManager>();
        if (audioManager != null && voice != null)
        {
            var so = SO(audioManager);
            var p = so.FindProperty("audioSource");
            if (p != null) { p.objectReferenceValue = voice; so.ApplyModifiedProperties(); }
        }
    }

    // ---------------------------------------------------------------- interviewer cast (Microsoft Rocketbox business characters)

    static Material RocketboxSkin(string name, Texture2D color, Texture2D normal, float smoothness)
    {
        var m = new Material(Shader.Find("Standard")) { color = Color.white };
        if (color != null) m.mainTexture = color;
        if (normal != null) { m.SetTexture("_BumpMap", normal); m.SetFloat("_BumpScale", 0.8f); m.EnableKeyword("_NORMALMAP"); }
        m.SetFloat("_Metallic", 0f);
        m.SetFloat("_Glossiness", smoothness);
        AssetDatabase.CreateAsset(m, $"Assets/Rocketbox/Materials/{name}.mat");
        return m;
    }

    static Material RocketboxCutout(string name, Texture2D colorWithAlpha)
    {
        var m = new Material(Shader.Find("Standard")) { color = Color.white };
        if (colorWithAlpha != null) m.mainTexture = colorWithAlpha;
        m.SetFloat("_Mode", 1f);   // cutout
        m.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.One);
        m.SetInt("_DstBlend", (int)UnityEngine.Rendering.BlendMode.Zero);
        m.SetInt("_ZWrite", 1);
        m.EnableKeyword("_ALPHATEST_ON");
        m.SetFloat("_Cutoff", 0.45f);
        m.renderQueue = 2450;
        m.SetFloat("_Metallic", 0f);
        m.SetFloat("_Glossiness", 0.15f);
        AssetDatabase.CreateAsset(m, $"Assets/Rocketbox/Materials/{name}.mat");
        return m;
    }

    public static void ApplyRocketboxMaterials(GameObject go, string model)
    {
        Directory.CreateDirectory("Assets/Rocketbox/Materials");
        string dir = $"Assets/Rocketbox/{model}/Textures";
        Texture2D Find(string endsWith, string notContaining = null)
        {
            foreach (var f in Directory.GetFiles(dir, "*.png"))
            {
                string n = Path.GetFileName(f);
                if (n.EndsWith(endsWith) && (notContaining == null || !n.Contains(notContaining)))
                    return AssetDatabase.LoadAssetAtPath<Texture2D>(f.Replace('\\', '/'));
            }
            return null;
        }
        var body = RocketboxSkin(model + "_body", Find("_body_color.png"), Find("_body_normal.png"), 0.2f);
        var head = RocketboxSkin(model + "_head", Find("_head_color.png"), Find("_head_normal.png"), 0.28f);
        var hair = RocketboxCutout(model + "_opacity", Find("_opacity_color.png", "glasses"));
        var glasses = RocketboxCutout(model + "_glasses", Find("glasses_opacity_color.png"));

        foreach (var r in go.GetComponentsInChildren<Renderer>(true))
        {
            var mats = r.sharedMaterials;
            for (int i = 0; i < mats.Length; i++)
            {
                if (mats[i] == null) continue;
                string n = mats[i].name;
                if (n.EndsWith("_body")) mats[i] = body;
                else if (n.EndsWith("_head")) mats[i] = head;
                else if (n.EndsWith("_glasses")) mats[i] = glasses;
                else if (n.EndsWith("_opacity")) mats[i] = hair;
            }
            r.sharedMaterials = mats;
            if (r is SkinnedMeshRenderer smr0) smr0.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;   // casting shadows crashes Quest 1 (SIGSEGV in the shadow pass, found Oct 6)
            if (r is SkinnedMeshRenderer smr) smr.updateWhenOffscreen = true;   // the pose is procedural, so the bounds can lag
        }
    }

    /// Every roster character, fully set up and seated; only one is active at a time (InterviewerCast switches them).
    static InterviewerCast BuildCast(out Interviewer first, out AudioSource voice)
    {
        first = null;
        var castRoot = new GameObject("InterviewerCast");
        var voiceGo = new GameObject("InterviewerVoice");
        voice = voiceGo.AddComponent<AudioSource>();
        voice.playOnAwake = false;
        voice.spatialBlend = 1f;
        voice.dopplerLevel = 0f;
        voice.minDistance = 0.8f;
        voice.maxDistance = 12f;
        voice.rolloffMode = AudioRolloffMode.Logarithmic;
        voiceGo.transform.SetParent(castRoot.transform, false);

        var built = new System.Collections.Generic.List<(string name, string voice, Interviewer iv, Transform head)>();
        int made = 0;
        foreach (var e in InterviewerRoster.All)
        {
            if (made >= castLimit) break;
            made++;
            var src = AssetDatabase.LoadAssetAtPath<GameObject>($"Assets/Rocketbox/{e.Model}/Export/{e.Model}_facial.fbx");
            if (src == null) { Debug.LogWarning("[ConferenceInterviewSceneBuilder] Missing character " + e.Model); continue; }
            var go = (GameObject)PrefabUtility.InstantiatePrefab(src);
            go.name = "Interviewer_" + e.Model;
            go.transform.SetParent(castRoot.transform, false);
            ApplyRocketboxMaterials(go, e.Model);

            var iv = SetupInterviewer(go, voice);
            AddAvatarHitboxes(iv);
            var headBone = iv.animator.GetBoneTransform(HumanBodyBones.Head);
            var feet = iv.animator.GetBoneTransform(HumanBodyBones.LeftFoot);
            Debug.Log($"[ConferenceInterviewSceneBuilder] {e.Model}: head {headBone.position.y:F2} m, left foot {feet.position.y:F2} m, face mesh " +
                      (iv.face != null ? "ok" : "none"));
            if (built.Count == 0)
                foreach (var smr in go.GetComponentsInChildren<SkinnedMeshRenderer>(true))
                {
                    var mesh = smr.sharedMesh;
                    if (mesh == null || mesh.blendShapeCount == 0) continue;
                    var names = new System.Text.StringBuilder();
                    for (int k = 0; k < Mathf.Min(mesh.blendShapeCount, 20); k++) names.Append(mesh.GetBlendShapeName(k)).Append(" | ");
                    Debug.Log($"[ConferenceInterviewSceneBuilder] {smr.name}: {mesh.blendShapeCount} blend shapes: {names}");
                }
            built.Add((e.Name, e.Voice, iv, headBone));
        }
        if (built.Count == 0) throw new System.Exception("No Rocketbox characters found in Assets/Rocketbox");
        first = built[0].iv;

        // the old pack avatar stays in the scene file but out of play
        var sunbox = GameObject.Find("Avatar");
        if (sunbox != null) sunbox.SetActive(false);

        var cast = castRoot.AddComponent<InterviewerCast>();
        var so = SO(cast);
        var arr = so.FindProperty("members");
        arr.arraySize = built.Count;
        for (int i = 0; i < built.Count; i++)
        {
            var el = arr.GetArrayElementAtIndex(i);
            el.FindPropertyRelative("displayName").stringValue = built[i].name;
            el.FindPropertyRelative("voice").stringValue = built[i].voice;
            el.FindPropertyRelative("controller").objectReferenceValue = built[i].iv.controller;
            el.FindPropertyRelative("head").objectReferenceValue = built[i].head;
        }
        so.FindProperty("voiceSource").objectReferenceValue = voice;
        so.ApplyModifiedProperties();

        // the voice starts at the first character's mouth; the others wait, inactive, until it is their turn
        voiceGo.transform.SetParent(built[0].head, false);
        voiceGo.transform.position = built[0].head.position + built[0].iv.root.transform.forward * 0.09f + Vector3.up * 0.04f;
        for (int i = 1; i < built.Count; i++) built[i].iv.root.SetActive(false);
        return cast;
    }

    /// The scene's EventSystem used the mouse/keyboard module, which ignores VR controller rays, so buttons never reacted
    /// to the pointer. XR rays need the XR UI input module and a tracked-device raycaster on each canvas.
    static void FixUiInput()
    {
        var es = Object.FindObjectOfType<EventSystem>();
        if (es != null)
        {
            var standalone = es.GetComponent<StandaloneInputModule>();
            if (standalone != null) Object.DestroyImmediate(standalone);
            if (es.GetComponent<XRUIInputModule>() == null) es.gameObject.AddComponent<XRUIInputModule>();
        }
        foreach (var canvas in Object.FindObjectsOfType<Canvas>(true))
            if (canvas.renderMode == RenderMode.WorldSpace && canvas.GetComponent<TrackedDeviceGraphicRaycaster>() == null)
                canvas.gameObject.AddComponent<TrackedDeviceGraphicRaycaster>();
    }

    /// Start / Stop / Test were the old manual-recording buttons. Hold-to-talk replaces them, and the new title screen
    /// and control panel replace the rest, so they are hidden (not deleted).
    static void HideOldButtons()
    {
        // the original world-space status text sat on top of the new company sign
        var oldCanvas = GameObject.Find("Canvas");
        if (oldCanvas != null && oldCanvas.GetComponent<Canvas>() != null) oldCanvas.GetComponent<Canvas>().enabled = false;

        var canvas = GameObject.Find("Canvas");
        if (canvas == null) return;
        foreach (var name in new[] { "Start", "Stop", "Test button" })
        {
            var t = canvas.transform.Find(name);
            if (t != null) t.gameObject.SetActive(false);
        }
    }

    // ---------------------------------------------------------------- title screen, control panel, fade

    static GameObject titleCanvasGo, controlCanvasGo;

    static GameObject MakeCanvas(string name, Vector3 position, Quaternion rotation, Vector2 size, float scale)
    {
        var go = new GameObject(name, typeof(RectTransform));
        var canvas = go.AddComponent<Canvas>();
        canvas.renderMode = RenderMode.WorldSpace;
        canvas.worldCamera = Camera.main;
        go.AddComponent<CanvasScaler>().dynamicPixelsPerUnit = 3f;
        go.AddComponent<GraphicRaycaster>();
        go.AddComponent<TrackedDeviceGraphicRaycaster>();
        var rt = go.GetComponent<RectTransform>();
        rt.sizeDelta = size;
        rt.localScale = Vector3.one * scale;
        rt.position = position;
        rt.rotation = rotation;
        return go;
    }

    static TextMeshProUGUI MakeText(Transform parent, string name, string text, float fontSize, Color color, Vector2 anchoredPosition, Vector2 box)
    {
        var go = new GameObject(name, typeof(RectTransform));
        go.transform.SetParent(parent, false);
        var t = go.AddComponent<TextMeshProUGUI>();
        t.text = text;
        t.fontSize = fontSize;
        t.color = color;
        t.alignment = TextAlignmentOptions.Center;
        t.enableWordWrapping = true;
        t.raycastTarget = false;
        t.rectTransform.sizeDelta = box;
        t.rectTransform.anchoredPosition = anchoredPosition;
        return t;
    }

    static Button MakeButton(Transform parent, string name, string label, float labelSize, Vector2 anchoredPosition, Vector2 size, Color normal, out TextMeshProUGUI labelText)
    {
        var go = new GameObject(name, typeof(RectTransform));
        go.transform.SetParent(parent, false);
        var image = go.AddComponent<Image>();
        image.color = Color.white;
        var button = go.AddComponent<Button>();
        button.targetGraphic = image;
        var colors = button.colors;
        colors.normalColor = normal;
        colors.highlightedColor = Color.Lerp(normal, Color.white, 0.4f);   // lights up when the pointer is on it
        colors.pressedColor = Color.Lerp(normal, Color.black, 0.35f);
        colors.selectedColor = normal;
        colors.disabledColor = new Color(0.35f, 0.35f, 0.38f, 0.8f);
        colors.colorMultiplier = 1f;
        colors.fadeDuration = 0.08f;
        button.colors = colors;
        var rt = go.GetComponent<RectTransform>();
        rt.sizeDelta = size;
        rt.anchoredPosition = anchoredPosition;
        labelText = MakeText(go.transform, "Label", label, labelSize, Color.white, Vector2.zero, size);
        labelText.fontStyle = FontStyles.Bold;
        return button;
    }

    static void BuildFlowUi()
    {
        var cam = Camera.main;

        // Fade: an inside-out sphere around the head with an unlit shader that ignores depth.
        var fade = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        fade.name = "FadeSphere";
        Object.DestroyImmediate(fade.GetComponent<Collider>());
        fade.transform.SetParent(cam.transform, false);
        fade.transform.localPosition = Vector3.zero;
        fade.transform.localScale = Vector3.one * 1.5f;
        var fadeMat = new Material(Shader.Find("VRInterview/FadeOverlay")) { color = new Color(0f, 0f, 0f, 0f) };
        AssetDatabase.CreateAsset(fadeMat, "Assets/ConferenceRoom/Materials/FadeOverlay.mat");
        var fadeRenderer = fade.GetComponent<MeshRenderer>();
        fadeRenderer.sharedMaterial = fadeMat;
        fadeRenderer.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        fadeRenderer.receiveShadows = false;
        fadeRenderer.enabled = false;

        // Title screen: in front of the candidate, shown against the dark void.
        titleCanvasGo = MakeCanvas("TitleCanvas", new Vector3(0f, 1.42f, 0.35f), Quaternion.identity, new Vector2(1000f, 640f), 0.0016f);
        var tr = titleCanvasGo.transform;
        var bg = new GameObject("Background", typeof(RectTransform));
        bg.transform.SetParent(tr, false);
        bg.AddComponent<Image>().color = new Color(0.07f, 0.09f, 0.13f, 0.95f);
        bg.GetComponent<Image>().raycastTarget = false;
        bg.GetComponent<RectTransform>().sizeDelta = new Vector2(1000f, 640f);
        MakeText(tr, "Title", "VR Interview Practice", 72f, Color.white, new Vector2(0f, 255f), new Vector2(940f, 100f)).fontStyle = FontStyles.Bold;
        var subtitle = MakeText(tr, "Subtitle", "Software Engineer interview  |  Nimbus Labs", 34f, new Color(0.6f, 0.75f, 0.85f), new Vector2(0f, 190f), new Vector2(940f, 56f));
        MakeText(tr, "ChooseJob", "Step 1: point at a job and pull the trigger (you will hear and feel a click)", 24f, new Color(0.75f, 0.82f, 0.9f), new Vector2(0f, 135f), new Vector2(960f, 40f));
        var jobButtons = new Button[InterviewJobs.All.Length];
        for (int i = 0; i < jobButtons.Length; i++)
        {
            TextMeshProUGUI jobLabel;
            float x = (i % 4 - 1.5f) * 240f;
            float y = 70f - (i / 4) * 95f;
            jobButtons[i] = MakeButton(tr, "Job_" + InterviewJobs.All[i].Id, InterviewJobs.All[i].Label, 25f, new Vector2(x, y), new Vector2(228f, 80f), new Color(0.16f, 0.2f, 0.28f), out jobLabel);
        }
        var message = MakeText(tr, "Message", "Hold the trigger or grip to speak. Release to send.\nPress Y or B for the menu.", 26f, new Color(0.82f, 0.85f, 0.9f), new Vector2(0f, -120f), new Vector2(860f, 90f));
        TextMeshProUGUI startLabel;
        var startButton = MakeButton(tr, "StartInterview", "Step 2: Start Interview", 30f, new Vector2(-170f, -235f), new Vector2(460f, 100f), new Color(0.1f, 0.55f, 0.62f), out startLabel);
        TextMeshProUGUI coachLabel;
        var coachButton = MakeButton(tr, "CoachReview", "Job Coach Review", 28f, new Vector2(265f, -235f), new Vector2(350f, 100f), new Color(0.45f, 0.32f, 0.72f), out coachLabel);
        coachButton.interactable = false;   // available once an interview has been finished

        // Job coach screen: a summary page, then one page per question (Prev / Next / Close)
        var coachCanvasGo = MakeCanvas("CoachCanvas", new Vector3(0f, 1.42f, 0.35f), Quaternion.identity, new Vector2(1000f, 640f), 0.0016f);
        var cc = coachCanvasGo.transform;
        var coachBg = new GameObject("Background", typeof(RectTransform));
        coachBg.transform.SetParent(cc, false);
        coachBg.AddComponent<Image>().color = new Color(0.07f, 0.09f, 0.13f, 0.97f);
        coachBg.GetComponent<Image>().raycastTarget = false;
        coachBg.GetComponent<RectTransform>().sizeDelta = new Vector2(1000f, 640f);
        var coachHeading = MakeText(cc, "Heading", "Job Coach", 38f, Color.white, new Vector2(0f, 282f), new Vector2(940f, 60f));
        coachHeading.fontStyle = FontStyles.Bold;
        var coachBody = MakeText(cc, "Body", "", 28f, new Color(0.9f, 0.92f, 0.95f), new Vector2(0f, 20f), new Vector2(920f, 440f));
        coachBody.alignment = TextAlignmentOptions.TopLeft;
        coachBody.enableWordWrapping = true;
        coachBody.enableAutoSizing = true;
        coachBody.fontSizeMin = 16f;
        coachBody.fontSizeMax = 28f;
        var coachPage = MakeText(cc, "Page", "", 20f, new Color(0.62f, 0.68f, 0.76f), new Vector2(0f, -246f), new Vector2(940f, 34f));
        TextMeshProUGUI prevLabel, nextLabel, closeLabel;
        var prevButton = MakeButton(cc, "CoachPrev", "< Previous", 28f, new Vector2(-330f, -292f), new Vector2(280f, 56f), new Color(0.16f, 0.2f, 0.28f), out prevLabel);
        var closeCoach = MakeButton(cc, "CoachClose", "Close", 28f, new Vector2(0f, -292f), new Vector2(280f, 56f), new Color(0.72f, 0.2f, 0.2f), out closeLabel);
        var nextButton = MakeButton(cc, "CoachNext", "Next >", 28f, new Vector2(330f, -292f), new Vector2(280f, 56f), new Color(0.1f, 0.55f, 0.62f), out nextLabel);
        var coachPanel = coachCanvasGo.AddComponent<CoachPanel>();
        var coachSo = SO(coachPanel);
        coachSo.FindProperty("heading").objectReferenceValue = coachHeading;
        coachSo.FindProperty("body").objectReferenceValue = coachBody;
        coachSo.FindProperty("pageLabel").objectReferenceValue = coachPage;
        coachSo.FindProperty("prevButton").objectReferenceValue = prevButton;
        coachSo.FindProperty("nextButton").objectReferenceValue = nextButton;
        coachSo.FindProperty("closeButton").objectReferenceValue = closeCoach;
        coachSo.ApplyModifiedProperties();
        coachCanvasGo.SetActive(false);

        // Menu panel (opened with Y or B; the flow places it in front of the user): Resume / Restart / End.
        controlCanvasGo = MakeCanvas("ControlCanvas", new Vector3(0f, 1.05f, -0.2f), Quaternion.identity, new Vector2(1100f, 140f), 0.0007f);
        var cr = controlCanvasGo.transform;
        // Backdrop and heading so it clearly reads as a menu (the panel is 1100 x 140 units; extend it up for the heading).
        var panelRt = controlCanvasGo.GetComponent<RectTransform>();
        panelRt.sizeDelta = new Vector2(1100f, 260f);
        var menuBg = new GameObject("MenuBackdrop", typeof(RectTransform));
        menuBg.transform.SetParent(cr, false);
        var bgImage = menuBg.AddComponent<Image>();
        bgImage.color = new Color(0.06f, 0.08f, 0.12f, 0.93f);
        bgImage.raycastTarget = false;
        menuBg.GetComponent<RectTransform>().sizeDelta = new Vector2(1180f, 300f);
        var menuEdge = new GameObject("MenuEdge", typeof(RectTransform));
        menuEdge.transform.SetParent(cr, false);
        var edgeImage = menuEdge.AddComponent<Image>();
        edgeImage.color = new Color(0.1f, 0.55f, 0.62f, 1f);
        edgeImage.raycastTarget = false;
        var edgeRt = menuEdge.GetComponent<RectTransform>();
        edgeRt.sizeDelta = new Vector2(1180f, 8f);
        edgeRt.anchoredPosition = new Vector2(0f, 146f);
        MakeText(cr, "MenuTitle", "Interview Menu", 46f, Color.white, new Vector2(0f, 95f), new Vector2(700f, 70f)).fontStyle = FontStyles.Bold;
        TextMeshProUGUI resumeLabel, restartLabel, endLabel;
        var resumeButton = MakeButton(cr, "ResumeInterview", "Resume", 40f, new Vector2(-370f, -40f), new Vector2(330f, 110f), new Color(0.1f, 0.55f, 0.62f), out resumeLabel);
        var restartButton = MakeButton(cr, "RestartInterview", "Restart Interview", 34f, new Vector2(0f, -40f), new Vector2(330f, 110f), new Color(0.82f, 0.52f, 0.12f), out restartLabel);
        var endButton = MakeButton(cr, "EndInterview", "End Interview", 34f, new Vector2(370f, -40f), new Vector2(330f, 110f), new Color(0.72f, 0.2f, 0.2f), out endLabel);
        controlCanvasGo.SetActive(false);

        // The flow controller wires everything together at runtime.
        var flowGo = GameObject.Find("InterviewFlow");
        if (flowGo == null) flowGo = new GameObject("InterviewFlow");
        var flow = GetOrAdd<InterviewFlow>(flowGo);
        GetOrAdd<XRUIClicker>(flowGo);   // trigger pull = click the button under the pointer
        var so = SO(flow);
        so.FindProperty("titlePanel").objectReferenceValue = titleCanvasGo;
        so.FindProperty("controlPanel").objectReferenceValue = controlCanvasGo;
        so.FindProperty("titleMessage").objectReferenceValue = message;
        so.FindProperty("startLabel").objectReferenceValue = startLabel;
        so.FindProperty("startButton").objectReferenceValue = startButton;
        so.FindProperty("subtitle").objectReferenceValue = subtitle;
        so.FindProperty("cast").objectReferenceValue = Object.FindObjectOfType<InterviewerCast>();
        so.FindProperty("coachButton").objectReferenceValue = coachButton;
        so.FindProperty("coachPanel").objectReferenceValue = coachPanel;
        var jobProp = so.FindProperty("jobButtons");
        jobProp.arraySize = jobButtons.Length;
        for (int i = 0; i < jobButtons.Length; i++) jobProp.GetArrayElementAtIndex(i).objectReferenceValue = jobButtons[i];
        so.FindProperty("resumeButton").objectReferenceValue = resumeButton;
        so.FindProperty("restartButton").objectReferenceValue = restartButton;
        so.FindProperty("endButton").objectReferenceValue = endButton;
        so.FindProperty("fadeRenderer").objectReferenceValue = fadeRenderer;
        so.ApplyModifiedProperties();
    }

    static void AddPushToTalk()
    {
        var go = GameObject.Find("PushToTalk");
        if (go == null) go = new GameObject("PushToTalk");
        GetOrAdd<PushToTalk>(go);
    }

    static void SetServerUrl()
    {
        var ws = Object.FindObjectOfType<WebSocketManager>();
        if (ws == null) return;
        var so = SO(ws);
        var p = so.FindProperty("serverUrl");
        if (p == null) return;
        p.stringValue = ServerUrl;
        so.ApplyModifiedProperties();
    }

    static T GetOrAdd<T>(GameObject go) where T : Component
    {
        var c = go.GetComponent<T>();
        return c != null ? c : go.AddComponent<T>();
    }

    // ---------------------------------------------------------------- transform snapshot (used around the solver)

    struct TState { public Transform t; public Vector3 p, s; public Quaternion r; }

    static List<TState> Snapshot(Transform root)
    {
        var list = new List<TState>();
        foreach (var t in root.GetComponentsInChildren<Transform>(true))
            list.Add(new TState { t = t, p = t.localPosition, r = t.localRotation, s = t.localScale });
        return list;
    }

    static void Restore(List<TState> list)
    {
        foreach (var s in list) { s.t.localPosition = s.p; s.t.localRotation = s.r; s.t.localScale = s.s; }
    }

    // ---------------------------------------------------------------- previews

    static void RenderPreviews(GameObject prefab, Interviewer iv)
    {
        try
        {
            // what AvatarCustomization.Start does at runtime: skin/eye/hair materials and clothing
            if (iv.customization != null)
            {
                iv.customization.UpdateCustomization();
                iv.customization.UpdateClothing();
            }
        }
        catch (System.Exception e) { Debug.LogWarning("Preview: customization update failed: " + e.Message); }

        // Edit mode has no player loop, so force skinning to follow the bones on every render.
        foreach (var smr in iv.root.GetComponentsInChildren<SkinnedMeshRenderer>(true)) smr.forceMatrixRecalculationPerRender = true;

        var eyes = new GameObject("PreviewCandidateEyes");
        eyes.transform.position = new Vector3(0f, 1.25f, -1.0f);
        iv.gaze.SetTarget(eyes.transform);

        iv.body.Initialise(); iv.face.Initialise(); iv.gaze.Initialise();
        Random.InitState(5);

        void Step(int frames)
        {
            for (int i = 0; i < frames; i++) { iv.body.Tick(1f / 60f); iv.gaze.Tick(1f / 60f); iv.face.Tick(1f / 60f); }
        }

        var head = iv.animator.GetBoneTransform(HumanBodyBones.Head);
        Vector3 candidateEye = eyes.transform.position;
        Vector3 chest = new Vector3(0f, 1.05f, 0.9f);
        void Views(string tag)
        {
            ConferenceRoomBuilder.Shot($"{PreviewDir}/{tag}_candidate_view.png", candidateEye, chest + Vector3.up * 0.1f, 58f);
            ConferenceRoomBuilder.Shot($"{PreviewDir}/{tag}_side_view.png", new Vector3(2.0f, 1.2f, 1.0f), new Vector3(0f, 0.95f, 0.9f), 48f);
        }

        InterviewerBody.DebugArms = true;
        titleCanvasGo.SetActive(false);   // keep the title panel out of the body shots
        foreach (var t in Object.FindObjectsOfType<Transform>()) if (t.name == "CandidateHand") t.gameObject.SetActive(false);   // editor-only; hands sit at the controller origins here

        // 1. waiting for the candidate
        iv.controller.SetAttentiveState();
        Step(150);
        Debug.Log($"[ConferenceInterviewSceneBuilder] after pose: root {iv.root.transform.position:F2} rot {iv.root.transform.eulerAngles:F0}, hips {iv.animator.GetBoneTransform(HumanBodyBones.Hips).position:F2}, " +
                  $"head {iv.animator.GetBoneTransform(HumanBodyBones.Head).position:F2}, leftHand {iv.animator.GetBoneTransform(HumanBodyBones.LeftHand).position:F2}, " +
                  $"animator pos {iv.animator.transform.position:F2} rot {iv.animator.transform.eulerAngles:F0}");
        Views("1_attentive");
        ConferenceRoomBuilder.Shot($"{PreviewDir}/1_hands_closeup.png", new Vector3(0f, 1.2f, -0.35f), new Vector3(0f, 0.8f, 0.6f), 40f);
        ConferenceRoomBuilder.Shot($"{PreviewDir}/1_hands_side.png", new Vector3(1.3f, 1.0f, 0.65f), new Vector3(0f, 0.8f, 0.65f), 36f);

        // 2. listening
        iv.controller.SetListeningState();
        Step(100);
        iv.body.Nod(1f);
        Step(26);   // mid-nod
        ConferenceRoomBuilder.Shot($"{PreviewDir}/2_listening_nod_closeup.png", candidateEye, head.position, 28f);

        // 3. thinking
        iv.controller.SetThinkingState();
        Step(180);
        Views("3_thinking");

        // 4. speaking with gestures (open palm, beat, two hands)
        iv.controller.SetSpeakingState();
        iv.body.SetTalking(true);
        iv.face.SetTalking(true);
        for (int g = 0; g < 3; g++)
        {
            iv.body.Gesture(g);
            Step(40);
            ConferenceRoomBuilder.Shot($"{PreviewDir}/4_gesture{g}_side_view.png", new Vector3(2.0f, 1.2f, 1.0f), new Vector3(0f, 0.95f, 0.9f), 48f);
            ConferenceRoomBuilder.Shot($"{PreviewDir}/4_gesture{g}_candidate_view.png", candidateEye, chest + Vector3.up * 0.1f, 58f);
            ConferenceRoomBuilder.Shot($"{PreviewDir}/4_gesture{g}_hands.png", new Vector3(0f, 1.2f, -0.35f), new Vector3(0f, 0.8f, 0.6f), 40f);
            Step(80);
        }
        iv.body.SetTalking(false);
        iv.face.SetTalking(false);

        // 5. mouth shapes
        iv.controller.SetSpeakingState();
        Step(60);
        foreach (var v in new[] { "Viseme_AA", "Viseme_O", "Viseme_E", "Viseme_SS", "Viseme_PP" })
        {
            iv.face.ClearVisemeOverride();
            iv.face.SetViseme(v, 1f);
            Step(20);
            ConferenceRoomBuilder.Shot($"{PreviewDir}/5_{v}.png", candidateEye + new Vector3(0f, 0.05f, 0.2f), head.position + new Vector3(0f, -0.04f, 0f), 18f);
        }
        iv.face.ClearVisemeOverride();

        // 6. wide establishing shot
        iv.controller.SetAttentiveState();
        Step(120);
        ConferenceRoomBuilder.Shot($"{PreviewDir}/6_room_overview.png", new Vector3(-3.7f, 2.3f, -2.7f), new Vector3(0.3f, 0.9f, 0.6f), 72f);
        ConferenceRoomBuilder.Shot($"{PreviewDir}/6_window_side.png", new Vector3(-3.6f, 1.6f, 0f), new Vector3(2f, 1.1f, 0.4f), 80f);

        // 7. the new screens
        ConferenceRoomBuilder.Shot($"{PreviewDir}/9_north_wall.png", candidateEye, new Vector3(0f, 1.4f, 3f), 75f);
        ConferenceRoomBuilder.Shot($"{PreviewDir}/9_west_wall.png", candidateEye, new Vector3(-4f, 1.3f, 0f), 75f);
        ConferenceRoomBuilder.Shot($"{PreviewDir}/9_window_wall.png", candidateEye, new Vector3(4f, 1.3f, 0.5f), 75f);
        titleCanvasGo.SetActive(true);
        ConferenceRoomBuilder.Shot($"{PreviewDir}/7_title_screen.png", candidateEye, new Vector3(0f, 1.42f, 0.35f), 62f);
        controlCanvasGo.SetActive(true);
        ConferenceRoomBuilder.Shot($"{PreviewDir}/8_control_panel.png", candidateEye, new Vector3(0f, 0.97f, -0.55f), 62f);
        controlCanvasGo.SetActive(false);

        Object.DestroyImmediate(eyes);
    }
}
