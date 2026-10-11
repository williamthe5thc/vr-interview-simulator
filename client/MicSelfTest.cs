using System.Collections;
using UnityEngine;

/// <summary>
/// One-shot microphone self-test, for headsets nobody is wearing. It only runs when a flag file named "mic_selftest" exists
/// in Application.persistentDataPath (create it with adb; it is deleted as it starts, so normal launches are unaffected).
///
/// It plays a loud tone through the headset speakers and records at the same time. If a microphone path works it hears the
/// tone. It tries Unity's Microphone class, then Android's AudioRecord directly with each audio source, and logs the peak
/// level of each under the tag [MicSelfTest]. If every path reads exactly zero, the microphone itself is not delivering audio.
/// </summary>
public class MicSelfTest : MonoBehaviour
{
#if UNITY_ANDROID && !UNITY_EDITOR
    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    private static void Boot()
    {
        string flag = System.IO.Path.Combine(Application.persistentDataPath, "mic_selftest");
        if (!System.IO.File.Exists(flag)) return;
        try { System.IO.File.Delete(flag); } catch { }
        new GameObject("MicSelfTest").AddComponent<MicSelfTest>();
    }

    private volatile bool nativeDone;

    private static void Log(string message) => Debug.Log("[MicSelfTest] " + message);

    private static AudioClip MakeTone()
    {
        const int rate = 24000;
        var data = new float[rate * 3];
        var rng = new System.Random(1);
        for (int i = 0; i < data.Length; i++)
        {
            float t = i / (float)rate;
            float burst = (Mathf.Sin(t * Mathf.PI * 4f) > 0f) ? 1f : 0.35f;   // loud / louder pulses
            float v = 0.5f * Mathf.Sin(2 * Mathf.PI * 440f * t) + 0.3f * Mathf.Sin(2 * Mathf.PI * 880f * t) + 0.2f * Mathf.Sin(2 * Mathf.PI * 1760f * t);
            v += 0.15f * ((float)rng.NextDouble() * 2f - 1f);
            data[i] = Mathf.Clamp(v * burst * 0.95f, -1f, 1f);
        }
        var clip = AudioClip.Create("MicSelfTestTone", data.Length, 1, rate, false);
        clip.SetData(data, 0);
        return clip;
    }

    private IEnumerator Start()
    {
        yield return new WaitForSeconds(8f);   // let the scene, XR and audio settle
        Log("begin; devices = [" + string.Join(", ", Microphone.devices) + "]");

        var speaker = gameObject.AddComponent<AudioSource>();
        speaker.spatialBlend = 0f;
        speaker.volume = 1f;
        speaker.loop = true;
        speaker.clip = MakeTone();
        speaker.Play();
        Log("tone playing: " + speaker.isPlaying + ", system audio listener volume " + AudioListener.volume);
        yield return new WaitForSeconds(1.0f);

        // ---- 1. Unity's Microphone class (what the app uses)
        string device = Microphone.devices.Length > 0 ? Microphone.devices[0] : null;
        Microphone.GetDeviceCaps(device, out int minFreq, out int maxFreq);
        Log($"Unity Microphone '{device}' caps {minFreq}..{maxFreq} Hz");
        var clip = Microphone.Start(device, false, 3, 16000);
        yield return new WaitForSeconds(3.1f);
        int pos = Microphone.GetPosition(device);
        var data = new float[clip.samples];
        clip.GetData(data, 0);
        Microphone.End(device);
        Report("Unity Microphone", data, pos > 0 ? pos : data.Length);

        // ---- 2. Android AudioRecord directly, per audio source (background thread, JNI attached)
        var worker = new System.Threading.Thread(NativeTest);
        worker.Start();
        while (!nativeDone) yield return null;

        speaker.Stop();
        Log("finished");
    }

    private static void Report(string label, float[] data, int count)
    {
        float peak = 0f; double sum = 0;
        int n = Mathf.Min(count, data.Length);
        for (int i = 0; i < n; i++) { float a = Mathf.Abs(data[i]); if (a > peak) peak = a; sum += data[i] * data[i]; }
        float rms = n > 0 ? Mathf.Sqrt((float)(sum / n)) : 0f;
        Log($"{label}: samples={n} peak={peak:F4} rms={rms:F4} -> " + (peak < 0.0005f ? "SILENT" : "HEARS SOUND"));
    }

    private void NativeTest()
    {
        AndroidJNI.AttachCurrentThread();
        try
        {
            var sources = new[] { (1, "MIC"), (5, "CAMCORDER"), (6, "VOICE_RECOGNITION"), (7, "VOICE_COMMUNICATION"), (9, "UNPROCESSED") };
            int minBuf;
            using (var cls = new AndroidJavaClass("android.media.AudioRecord"))
                minBuf = cls.CallStatic<int>("getMinBufferSize", 16000, 16, 2);
            Log("AudioRecord min buffer " + minBuf + " bytes");

            foreach (var (source, name) in sources)
            {
                try
                {
                    using (var rec = new AndroidJavaObject("android.media.AudioRecord", source, 16000, 16, 2, Mathf.Max(minBuf, 32000)))
                    {
                        int state = rec.Call<int>("getState");
                        if (state != 1) { Log($"AudioRecord source {name}: not initialised (state {state})"); continue; }
                        rec.Call("startRecording");
                        int recState = rec.Call<int>("getRecordingState");
                        var buf = new short[1600];
                        float peak = 0f; double sum = 0; long n = 0;
                        var clock = System.Diagnostics.Stopwatch.StartNew();
                        while (clock.ElapsedMilliseconds < 1600)
                        {
                            int read = rec.Call<int>("read", buf, 0, buf.Length);
                            if (read <= 0) { Log($"AudioRecord source {name}: read returned {read}"); break; }
                            for (int i = 0; i < read; i++) { float a = Mathf.Abs(buf[i] / 32768f); if (a > peak) peak = a; sum += (buf[i] / 32768.0) * (buf[i] / 32768.0); n++; }
                        }
                        rec.Call("stop");
                        rec.Call("release");
                        float rms = n > 0 ? Mathf.Sqrt((float)(sum / n)) : 0f;
                        Log($"AudioRecord source {name} ({source}): recordingState={recState} samples={n} peak={peak:F4} rms={rms:F4} -> " + (peak < 0.0005f ? "SILENT" : "HEARS SOUND"));
                    }
                }
                catch (System.Exception e) { Log($"AudioRecord source {name}: exception {e.GetType().Name}: {e.Message}"); }
            }
        }
        finally
        {
            AndroidJNI.DetachCurrentThread();
            nativeDone = true;
        }
    }
#endif
}
