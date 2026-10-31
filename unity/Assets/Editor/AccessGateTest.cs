using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

/// <summary>
/// Plays the access-code panel against a local mock server (Tools/mock_auth_server.py) in an empty scene.
/// Batch (no -quit): -executeMethod AccessGateTest.Run -agtPort 8791 -agtLegacyPort 8792
/// Prints "[AGT] PASS/FAIL ..." lines and exits with 0 when every check passes.
/// </summary>
[InitializeOnLoad]
public static class AccessGateTest
{
    const string Key = "AGT_running";

    static AccessGateTest()
    {
        if (!SessionState.GetBool(Key, false)) return;
        EditorApplication.playModeStateChanged += state =>
        {
            if (state == PlayModeStateChange.EnteredPlayMode)
                new GameObject("AGT_Driver").AddComponent<Driver>();
        };
    }

    public static void Run()
    {
        int port = Arg("-agtPort", 8791), legacy = Arg("-agtLegacyPort", 8792);
        SessionState.SetBool(Key, true);
        SessionState.SetInt("AGT_port", port);
        SessionState.SetInt("AGT_legacy", legacy);
        EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        new GameObject("Main Camera") { tag = "MainCamera" }.AddComponent<Camera>();
        new GameObject("WebSocketManager").AddComponent<WebSocketManager>();
        EditorApplication.EnterPlaymode();
    }

    static int Arg(string name, int fallback)
    {
        var args = System.Environment.GetCommandLineArgs();
        for (int i = 0; i < args.Length - 1; i++)
            if (args[i] == name && int.TryParse(args[i + 1], out int v)) return v;
        return fallback;
    }

    class Driver : MonoBehaviour
    {
        int failures;

        void Check(bool ok, string what)
        {
            if (!ok) failures++;
            Debug.Log("[AGT] " + (ok ? "PASS " : "FAIL ") + what);
        }

        IEnumerator Start()
        {
            int port = SessionState.GetInt("AGT_port", 8791), legacy = SessionState.GetInt("AGT_legacy", 8792);
            string url = "ws://127.0.0.1:" + port;
            yield return new WaitForSecondsRealtime(1f);
            var gate = AccessGate.Instance;
            Check(gate != null && AccessGate.Showing, "panel is shown at start and the socket did not connect on its own");
            if (gate == null) { Finish(); yield break; }

            Check(AccessGate.AddressesFor(AccessGate.DefaultServer) == string.Join(",", new[] { AccessGate.DefaultServer }.Concat(AccessGate.FallbackServers)), "default address list (public address, then the fallbacks)");
            Check(AccessGate.NormalizeAddress("10.0.0.5:8765") == "ws://10.0.0.5:8765", "address without scheme gets ws://");
            Check(AccessGate.AddressesFor("wss://my.server/ws") == "wss://my.server/ws", "own address is used alone");

            var cases = new List<(string code, string expectStatus, string expectRemaining, bool expectShowing)>
            {
                ("BADCODE", "isn't valid", "", true),
                ("RATECODE", "Too many tries", "", true),
                ("BUSYCODE", "Someone else is practising", "", true),
                ("LIMITCODE", "No interviews left", "", true),
                ("NOLIMIT", "Signed in.", "", false),
                ("GOODCODE", "3 interviews left today", "3 interviews left today", false),
            };
            foreach (var c in cases)
            {
                gate.Submit(c.code, url);
                yield return new WaitForSecondsRealtime(3f);
                string status = gate.StatusText;
                Check(status.Contains(c.expectStatus), c.code + ": status \"" + status.Replace("\n", " | ") + "\"");
                Check(gate.RemainingText == c.expectRemaining, c.code + ": remaining \"" + gate.RemainingText + "\"");
                Check(AccessGate.Showing == c.expectShowing, c.code + ": panel " + (AccessGate.Showing ? "shown" : "hidden"));
                if (c.expectShowing)
                {
                    // no automatic retry: wait as long as several reconnect delays; the mock counts the connections
                    yield return new WaitForSecondsRealtime(c.code == "BADCODE" ? 9f : 1f);
                }
            }
            Check(PlayerPrefs.GetString("vrsim.access_code") == "GOODCODE" && PlayerPrefs.GetString("vrsim.server_address") == url, "code and address saved in PlayerPrefs");

            // old server: never answers auth -> used anyway after 5 s
            gate.Submit("ANYCODE", "127.0.0.1:" + legacy);
            yield return new WaitForSecondsRealtime(3f);
            Check(!FindObjectOfType<WebSocketManager>().IsConnected(), "legacy: still waiting for auth_result at 3 s");
            yield return new WaitForSecondsRealtime(5f);
            Check(!AccessGate.Showing && gate.StatusText == "Signed in.", "legacy: proceeds after the 5 s timeout");
            Check(FindObjectOfType<WebSocketManager>().IsConnected(), "legacy: socket counts as connected");

            PlayerPrefs.DeleteKey("vrsim.access_code");
            PlayerPrefs.DeleteKey("vrsim.server_address");
            Finish();
        }

        void Finish()
        {
            Debug.Log("[AGT] DONE failures=" + failures);
            SessionState.SetBool(Key, false);
            EditorApplication.Exit(failures == 0 ? 0 : 1);
        }
    }
}
