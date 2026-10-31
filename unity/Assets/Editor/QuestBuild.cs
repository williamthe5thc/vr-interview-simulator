using System.Linq;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.XR.Management;
using UnityEngine;
using UnityEngine.XR.Management;

/// <summary>Builds the conference-room scene to an Android APK without touching the saved Build Settings scene list.
/// Batch: -executeMethod QuestBuild.BuildConference</summary>
public static class QuestBuild
{
    public const string Output = "Builds/VRInterviewSim_Conference.apk";

    public static void BuildConference()
    {
        if (!EnsureOculusXr())
        {
            Debug.LogError("[QuestBuild] the Oculus XR loader is not active for Android: not building (the APK would miss the Quest manifest entries)");
            EditorApplication.Exit(1);
            return;
        }
        var options = new BuildPlayerOptions
        {
            scenes = new[] { "Assets/Scenes/VRInterviewScene_Conference.unity" },
            locationPathName = Output,
            target = BuildTarget.Android,
            targetGroup = BuildTargetGroup.Android,
            options = BuildOptions.None
        };
        var report = BuildPipeline.BuildPlayer(options);
        Debug.Log($"[QuestBuild] result={report.summary.result} size={report.summary.totalSize / (1024 * 1024)} MB errors={report.summary.totalErrors} time={report.summary.totalTime}");
        bool ok = report.summary.result == BuildResult.Succeeded && ManifestLooksRight(Output);
        EditorApplication.Exit(ok ? 0 : 1);
    }

    /// Make sure the XR settings registered in ProjectSettings/EditorBuildSettings.asset resolve (re-register them from the assets
    /// if not) and that the Oculus loader is active for Android; without it the APK would not start in VR.
    static bool EnsureOculusXr()
    {
        Register<XRGeneralSettingsPerBuildTarget>(XRGeneralSettings.k_SettingsKey);
        Register<Unity.XR.Oculus.OculusSettings>("Unity.XR.Oculus.Settings");
        var general = XRGeneralSettingsPerBuildTarget.XRGeneralSettingsForBuildTarget(BuildTargetGroup.Android);
        bool ok = general != null && general.AssignedSettings != null
            && general.AssignedSettings.activeLoaders.Any(l => l is Unity.XR.Oculus.OculusLoader);
        Debug.Log("[QuestBuild] Oculus XR loader for Android: " + (ok ? "active" : "MISSING"));
        return ok;
    }

    /// The very first build after a fresh clone (Library created in the same run) comes out without the Oculus plugin's
    /// manifest step: no Quest device list or vr_only mode, and Unity's BLUETOOTH permission (added for the Microphone) stays in.
    /// The cause is inside Unity; the next build of the same project is fine. So check the APK and refuse a wrong one.
    static bool ManifestLooksRight(string apk)
    {
        try
        {
            string text;
            using (var file = System.IO.File.OpenRead(apk))
            using (var zip = new System.IO.Compression.ZipArchive(file))
            using (var stream = zip.GetEntry("AndroidManifest.xml").Open())
            using (var memory = new System.IO.MemoryStream())
            {
                stream.CopyTo(memory);
                byte[] bytes = memory.ToArray();   // binary XML: its strings are UTF-16 (or UTF-8), so look in both decodings
                text = System.Text.Encoding.Unicode.GetString(bytes) + System.Text.Encoding.UTF8.GetString(bytes);
            }
            bool bluetooth = text.Contains("android.permission.BLUETOOTH");
            bool oculusStep = text.Contains("com.samsung.android.vr.application.mode");
            if (!bluetooth && oculusStep)
            {
                Debug.Log("[QuestBuild] manifest check passed (Oculus entries present, no BLUETOOTH permission)");
                return true;
            }
            Debug.LogError("[QuestBuild] manifest check FAILED (bluetooth=" + bluetooth + ", oculus entries=" + oculusStep + "). " +
                           "This happens on the first build after a fresh clone: run the same command again. The APK was deleted.");
            System.IO.File.Delete(apk);
            return false;
        }
        catch (System.Exception e)
        {
            Debug.LogError("[QuestBuild] could not check the APK manifest: " + e.Message);
            return false;
        }
    }

    static void Register<T>(string key) where T : Object
    {
        if (EditorBuildSettings.TryGetConfigObject(key, out T existing) && existing != null) return;
        string guid = AssetDatabase.FindAssets("t:" + typeof(T).Name).FirstOrDefault();
        if (guid == null) return;
        var asset = AssetDatabase.LoadAssetAtPath<T>(AssetDatabase.GUIDToAssetPath(guid));
        if (asset == null) return;
        EditorBuildSettings.AddConfigObject(key, asset, true);
        Debug.Log("[QuestBuild] re-registered XR settings " + key + " -> " + AssetDatabase.GUIDToAssetPath(guid));
    }
}
