using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;

/// <summary>Builds the conference-room scene to an Android APK without touching the saved Build Settings scene list.
/// Batch: -executeMethod QuestBuild.BuildConference</summary>
public static class QuestBuild
{
    public const string Output = "Builds/VRInterviewSim_Conference.apk";

    public static void BuildConference()
    {
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
}
