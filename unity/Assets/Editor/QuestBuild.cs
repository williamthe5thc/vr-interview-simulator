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
        EditorApplication.Exit(report.summary.result == BuildResult.Succeeded ? 0 : 1);
    }

    /// On the very first import of a fresh clone, the XR settings registered in ProjectSettings/EditorBuildSettings.asset are not
    /// resolved yet when a batch build starts. The Oculus plugin then silently skips its manifest step (Quest device list,
    /// vr_only mode, removing the BLUETOOTH permission that Unity adds for the Microphone). Re-register the settings from the assets.
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
