using UnityEngine;

/// <summary>
/// Lip-sync and blinking for the interviewer, driven by the AudioSource that plays the server's voice.
///
/// The server sends audio only, so visemes are estimated from the signal itself: loudness opens the mouth, the
/// spectral centroid picks the vowel shape (O/U low, AA mid, E/I high), strong high-frequency energy picks a
/// fricative (SS), and a sudden drop in level fires a lip-closed (PP) pulse. If you later get real phoneme data
/// from the server, call SetViseme / ClearVisemeOverride and the audio analysis steps aside.
/// </summary>
[DefaultExecutionOrder(120)]
public class InterviewerFace : MonoBehaviour
{
    [Header("References (auto-found if empty)")]
    [SerializeField] private SkinnedMeshRenderer faceMesh;
    [SerializeField] private AudioSource voice;
    [SerializeField] private InterviewerBody body;

    [Header("Lip sync")]
    [SerializeField, Range(0f, 2f)] private float intensity = 1f;
    [SerializeField] private float attackTime = 0.035f;
    [SerializeField] private float releaseTime = 0.07f;
    [Tooltip("Loudness below this (0..1, normalised to a running peak) keeps the mouth closed.")]
    [SerializeField] private float openThreshold = 0.06f;

    [Header("Blinking")]
    [SerializeField] private Vector2 blinkInterval = new Vector2(2.2f, 5.5f);
    [SerializeField, Range(0f, 40f)] private float restingLidClosure = 8f;

    static readonly string[] VisemeNames =
        { "Viseme_AA", "Viseme_O", "Viseme_CH", "Viseme_PP", "Viseme_FF", "Viseme_TH", "Viseme_DD",
          "Viseme_KK", "Viseme_SS", "Viseme_NN", "Viseme_RR", "Viseme_E", "Viseme_I", "Viseme_U", "Viseme_SIL" };

    enum V { AA, O, CH, PP, FF, TH, DD, KK, SS, NN, RR, E, I, U, SIL }

    // same order as VisemeNames
    static readonly string[] RocketboxVisemes =
        { "AA_VI_10_aa", "AA_VI_13_O", "AA_VI_06_CH", "AA_VI_01_PP", "AA_VI_02_FF", "AA_VI_03_TH", "AA_VI_04_DD",
          "AA_VI_05_KK", "AA_VI_07_SS", "AA_VI_08_nn", "AA_VI_09_RR", "AA_VI_11_E", "AA_VI_12_I", "AA_VI_14_U", "AA_VI_00_Sil" };

    private int[] visemeIdx = new int[VisemeNames.Length];
    private float[] w = new float[VisemeNames.Length];        // smoothed weights 0..1
    private float[] tgt = new float[VisemeNames.Length];
    private float[] overrideW;
    private bool overrideActive;

    private int blinkIdx = -1, blinkLIdx = -1, blinkRIdx = -1, browUpIdx = -1;
    private float browUp, browUpTarget;
    private float browBase;

    private float[] wave = new float[512];
    private float[] spec = new float[1024];
    private float peak = 0.02f;
    private float prevLoud;
    private float ppUntil;

    private bool talking;
    private float nextBlinkAt, blinkStart = -10f, blinkLen = 0.2f;
    private bool doubleBlink;
    private float time;

    public float SpeechLevel { get; private set; }

    // --- server lip-sync (Rhubarb mouth shapes) -------------------------------------------------------------

    private MouthCue[] cueTrack;
    private AudioClip cueClip;
    [Header("Server lip-sync")]
    [SerializeField, Tooltip("Seconds the mouth leads the sound, so closures land on the consonant.")] private float cueLead = 0.05f;

    /// <summary>Follow this timeline while <paramref name="clip"/> plays. Until it arrives (or if it never does) the loudness-based mouth is used.</summary>
    public void SetMouthCues(MouthCue[] cues, AudioClip clip)
    {
        cueTrack = cues;
        cueClip = clip;
    }

    /// Rhubarb shape -> (viseme, weight) pairs. A closed, B teeth together, C open, D wide, E rounded, F puckered, G teeth on lip, H tongue up.
    private static readonly System.Collections.Generic.Dictionary<string, (V viseme, float weight)[]> ShapeMap =
        new System.Collections.Generic.Dictionary<string, (V viseme, float weight)[]>
        {
            ["X"] = new (V, float)[0],
            ["A"] = new[] { (V.PP, 0.95f) },
            ["B"] = new[] { (V.I, 0.5f), (V.SS, 0.25f) },
            ["C"] = new[] { (V.E, 0.7f), (V.AA, 0.3f) },
            ["D"] = new[] { (V.AA, 0.95f) },
            ["E"] = new[] { (V.O, 0.7f), (V.AA, 0.15f) },
            ["F"] = new[] { (V.U, 0.85f), (V.O, 0.2f) },
            ["G"] = new[] { (V.FF, 0.9f) },
            ["H"] = new[] { (V.DD, 0.4f), (V.AA, 0.3f) },
        };

    /// <summary>Drive the visemes from the cue timeline. False when there is none for the clip that is playing.</summary>
    private bool ApplyCues()
    {
        if (cueTrack == null || cueTrack.Length == 0 || voice == null || !voice.isPlaying || voice.clip != cueClip) return false;
        float t = voice.time + cueLead;
        System.Array.Clear(tgt, 0, tgt.Length);
        // coarticulation: in the last moments of a mouth shape the next one starts to come in
        string shape = "X", next = null;
        float toEnd = 1f;
        for (int i = 0; i < cueTrack.Length; i++)
            if (t >= cueTrack[i].s && t < cueTrack[i].e)
            {
                shape = cueTrack[i].v;
                toEnd = cueTrack[i].e - t;
                if (i + 1 < cueTrack.Length) next = cueTrack[i + 1].v;
                break;
            }
        // jaw by loudness: loud syllables open a little wider, quiet ones less (the cues alone are all-or-nothing)
        float jaw = Mathf.Lerp(0.8f, 1.1f, VoiceLoudness(Time.deltaTime));
        float blend = next != null && toEnd < 0.05f ? 0.35f * (1f - toEnd / 0.05f) : 0f;
        if (ShapeMap.TryGetValue(shape, out var parts))
            foreach (var (viseme, weight) in parts)
                tgt[(int)viseme] = Mathf.Max(tgt[(int)viseme], Mathf.Min(1f, weight * jaw) * (1f - blend));
        if (blend > 0f && ShapeMap.TryGetValue(next, out var nextParts))
            foreach (var (viseme, weight) in nextParts)
                tgt[(int)viseme] = Mathf.Max(tgt[(int)viseme], weight * blend);
        float level = 0f;
        for (int i = 0; i < tgt.Length; i++) if (i != (int)V.SIL) level = Mathf.Max(level, tgt[i]);
        SpeechLevel = level;
        return true;
    }

    private float loudSmooth;

    /// 0..1 loudness of the voice, normalised to a running peak and smoothed (used to scale the mouth opening).
    private float VoiceLoudness(float dt)
    {
        if (voice == null || !voice.isPlaying) { loudSmooth = 0f; return 0f; }
        voice.GetOutputData(wave, 0);
        float sum = 0f;
        for (int i = 0; i < wave.Length; i++) sum += wave[i] * wave[i];
        float rms = Mathf.Sqrt(sum / wave.Length);
        peak = Mathf.Max(rms, Mathf.Lerp(peak, 0.02f, dt * 0.25f));
        float loud = Mathf.Clamp01(rms / Mathf.Max(peak, 0.01f));
        loudSmooth = Mathf.Lerp(loudSmooth, loud, 1f - Mathf.Exp(-dt * 18f));
        return loudSmooth;
    }

    // --- public hooks ---------------------------------------------------------------------------------------

    public void SetTalking(bool value) => talking = value;
    public void SetAudioSource(AudioSource source) => voice = source;

    public void Blink()
    {
        blinkStart = time;
        blinkLen = Random.Range(0.16f, 0.24f);
        doubleBlink = Random.value < 0.15f;
    }

    /// <summary>Raise (+) the brows 0..1 for attentive / surprised / confused looks.</summary>
    public void SetBrowRaise(float amount) => browUpTarget = Mathf.Clamp01(amount);

    /// <summary>Force a single viseme (e.g. from server phoneme data). Weight 0..1.</summary>
    public void SetViseme(string visemeName, float weight)
    {
        int i = System.Array.IndexOf(VisemeNames, visemeName);
        if (i < 0) return;
        if (overrideW == null) overrideW = new float[VisemeNames.Length];
        overrideW[i] = Mathf.Clamp01(weight);
        overrideActive = true;
    }

    public void ClearVisemeOverride()
    {
        overrideActive = false;
        if (overrideW != null) System.Array.Clear(overrideW, 0, overrideW.Length);
    }

    // --- lifecycle ---------------------------------------------------------------------------------------------

    private void Start() => Initialise();

    private bool initialised;

    /// Blend shape index by name. Models from some tools name shapes with a prefix ("blendShape1.AA_VI_00_Sil"), so a name also
    /// matches when it only ends with ".name".
    private static int ShapeIndex(Mesh mesh, string name)
    {
        if (mesh == null) return -1;
        int exact = mesh.GetBlendShapeIndex(name);
        if (exact >= 0) return exact;
        string suffix = "." + name;
        for (int i = 0; i < mesh.blendShapeCount; i++)
            if (mesh.GetBlendShapeName(i).EndsWith(suffix)) return i;
        return -1;
    }


    public bool Initialise()
    {
        if (initialised) return true;

        if (body == null) body = GetComponent<InterviewerBody>();
        if (faceMesh == null)
        {
            foreach (var smr in GetComponentsInChildren<SkinnedMeshRenderer>(false))
            {
                if (smr.sharedMesh != null && (ShapeIndex(smr.sharedMesh, "Viseme_AA") >= 0 || ShapeIndex(smr.sharedMesh, "AA_VI_01_PP") >= 0)) { faceMesh = smr; break; }
            }
        }
        if (faceMesh == null)
        {
            Debug.LogWarning("[InterviewerFace] No mesh with Viseme_* blend shapes found; lip sync disabled.");
            enabled = false;
            return false;
        }

        var mesh = faceMesh.sharedMesh;
        for (int i = 0; i < VisemeNames.Length; i++)
        {
            int idx = ShapeIndex(mesh, VisemeNames[i]);
            // the male mesh calls the E viseme "Viseme_EE"
            if (idx < 0 && VisemeNames[i] == "Viseme_E") idx = ShapeIndex(mesh, "Viseme_EE");
            // Microsoft Rocketbox characters: the 15 standard visemes are called AA_VI_00_Sil ... AA_VI_14_U
            if (idx < 0) idx = ShapeIndex(mesh, RocketboxVisemes[i]);
            visemeIdx[i] = idx;
        }
        blinkIdx = ShapeIndex(mesh, "Expression_Blink");
        blinkLIdx = ShapeIndex(mesh, "Expression_Blink_L");
        blinkRIdx = ShapeIndex(mesh, "Expression_Blink_R");
        browUpIdx = ShapeIndex(mesh, "Face_BrowHeight_Max");
        if (blinkLIdx < 0) blinkLIdx = ShapeIndex(mesh, "AK_09_EyeBlinkLeft");     // Rocketbox / ARKit names
        if (blinkRIdx < 0) blinkRIdx = ShapeIndex(mesh, "AK_10_EyeBlinkRight");
        if (browUpIdx < 0) browUpIdx = ShapeIndex(mesh, "AK_03_BrowInnerUp");
        if (browUpIdx >= 0) browBase = faceMesh.GetBlendShapeWeight(browUpIdx);
        nextBlinkAt = Random.Range(blinkInterval.x, blinkInterval.y);
        MakeEyesGlossy();
        initialised = true;
        return true;
    }

    [Header("Eyes")]
    [SerializeField, Range(0f, 1f), Tooltip("Smoothness of the eyeball material: the sun and room lights then show as a small catch-light that makes the eyes look wet. 0 = leave as imported.")]
    private float eyeGloss = 0.92f;

    /// Gives the eyeball materials (not the lashes or the skin) a high smoothness so they pick up a highlight.
    private void MakeEyesGlossy()
    {
        if (eyeGloss <= 0f) return;
        foreach (var smr in GetComponentsInChildren<SkinnedMeshRenderer>(false))
            foreach (var m in smr.materials)   // instance copies, so shared assets are not touched
            {
                if (m == null) continue;
                string n = m.name.ToLowerInvariant();
                if (!n.Contains("eye") || n.Contains("lash") || n.Contains("brow")) continue;
                if (m.HasProperty("_Glossiness")) m.SetFloat("_Glossiness", eyeGloss);
                if (m.HasProperty("_Smoothness")) m.SetFloat("_Smoothness", eyeGloss);
            }
    }

    private void LateUpdate()
    {
        if (faceMesh == null && !Initialise()) return;
        Tick(Time.deltaTime);
    }

    /// <summary>Advance and apply. Public so editor tooling can step it without play mode.</summary>
    public void Tick(float dt)
    {
        time += dt;
        if (overrideActive) UseOverride(); else if (!ApplyCues()) AnalyseAudio(dt);
        SmoothAndApply(dt);
        UpdateBlink();
        UpdateBrows(dt);
        if (body != null) body.SetSpeechLevel(SpeechLevel);
    }

    // --- audio analysis ---------------------------------------------------------------------------------------

    private void UseOverride()
    {
        for (int i = 0; i < tgt.Length; i++) tgt[i] = overrideW != null ? overrideW[i] : 0f;
        SpeechLevel = 0f;
        for (int i = 0; i < tgt.Length; i++) if (i != (int)V.SIL) SpeechLevel = Mathf.Max(SpeechLevel, tgt[i]);
    }

    private void AnalyseAudio(float dt)
    {
        System.Array.Clear(tgt, 0, tgt.Length);
        if (voice == null || !voice.isPlaying)
        {
            SpeechLevel = Mathf.MoveTowards(SpeechLevel, 0f, dt * 6f);
            prevLoud = 0f;
            return;
        }

        voice.GetOutputData(wave, 0);
        float sum = 0f;
        for (int i = 0; i < wave.Length; i++) sum += wave[i] * wave[i];
        float rms = Mathf.Sqrt(sum / wave.Length);

        // normalise to a slowly decaying peak so it works at any playback volume
        peak = Mathf.Max(rms, Mathf.Lerp(peak, 0.02f, dt * 0.25f));
        float loud = Mathf.Clamp01(rms / Mathf.Max(peak, 0.01f));

        voice.GetSpectrumData(spec, 0, FFTWindow.Hanning);
        float binHz = AudioSettings.outputSampleRate * 0.5f / spec.Length;
        float total = 0f, weighted = 0f, high = 0f;
        for (int i = 2; i < spec.Length; i++)
        {
            float f = i * binHz;
            if (f < 150f) continue;
            if (f > 9000f) break;
            float e = spec[i];
            if (f <= 5000f) { total += e; weighted += e * f; }
            if (f >= 3500f) high += e;
        }
        float centroid = total > 1e-9f ? weighted / total : 1000f;
        float hfRatio = (total + high) > 1e-9f ? high / (total + high) : 0f;

        float open = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(openThreshold, 0.75f, loud));
        SpeechLevel = open;

        // plosive-ish closure: a sharp drop in level right after speech
        if (prevLoud > 0.45f && loud < 0.18f) ppUntil = time + 0.07f;
        prevLoud = loud;
        if (time < ppUntil) { tgt[(int)V.PP] = 0.9f; return; }
        if (open < 0.02f) { tgt[(int)V.SIL] = 0f; return; }

        if (hfRatio > 0.42f)
        {
            tgt[(int)V.SS] = Mathf.Clamp01(hfRatio * 1.1f) * open * 0.8f;
            tgt[(int)V.E] = 0.25f * open;
        }
        else
        {
            float t = Mathf.InverseLerp(450f, 2300f, centroid);   // 0 = dark vowel, 1 = bright vowel
            tgt[(int)V.AA] = Mathf.Clamp01(1.2f - Mathf.Abs(t - 0.38f) * 2.6f) * open;
            tgt[(int)V.O] = Mathf.Clamp01(0.9f - t * 2.4f) * open;
            tgt[(int)V.U] = Mathf.Clamp01(0.45f - t * 1.6f) * open;
            tgt[(int)V.E] = Mathf.Clamp01(1.1f - Mathf.Abs(t - 0.72f) * 3.2f) * open;
            tgt[(int)V.I] = Mathf.Clamp01((t - 0.62f) * 3f) * open;
            // very quiet voiced sound still shows a little movement
            tgt[(int)V.NN] = (1f - open) * 0.15f;
        }
    }

    private void SmoothAndApply(float dt)
    {
        for (int i = 0; i < w.Length; i++)
        {
            float tau = tgt[i] > w[i] ? attackTime : releaseTime;
            w[i] = Mathf.Lerp(w[i], tgt[i], 1f - Mathf.Exp(-dt / Mathf.Max(tau, 0.001f)));
            if (visemeIdx[i] >= 0) faceMesh.SetBlendShapeWeight(visemeIdx[i], Mathf.Clamp01(w[i] * intensity) * 100f);
        }
    }

    // --- blinking & brows -------------------------------------------------------------------------------------

    private void UpdateBlink()
    {
        if (time >= nextBlinkAt)
        {
            Blink();
            float rate = talking ? 0.8f : 1f;
            nextBlinkAt = time + Random.Range(blinkInterval.x, blinkInterval.y) * rate;
        }

        float closure = 0f;
        float t = (time - blinkStart) / blinkLen;
        if (t >= 0f && t < 1f) closure = t < 0.35f ? t / 0.35f : 1f - (t - 0.35f) / 0.65f;
        else if (doubleBlink)
        {
            float t2 = (time - blinkStart - blinkLen * 0.9f) / blinkLen;
            if (t2 >= 0f && t2 < 1f) closure = t2 < 0.35f ? t2 / 0.35f : 1f - (t2 - 0.35f) / 0.65f;
        }

        float weight = Mathf.Lerp(restingLidClosure, 100f, Mathf.Clamp01(closure));
        if (blinkIdx >= 0) faceMesh.SetBlendShapeWeight(blinkIdx, weight);
        // keep the per-eye shapes at zero so they never stack on the combined blink
        if (blinkLIdx >= 0) faceMesh.SetBlendShapeWeight(blinkLIdx, 0f);
        if (blinkRIdx >= 0) faceMesh.SetBlendShapeWeight(blinkRIdx, 0f);
    }

    private void UpdateBrows(float dt)
    {
        if (browUpIdx < 0) return;
        browUp = Mathf.Lerp(browUp, browUpTarget, 1f - Mathf.Exp(-dt * 4f));
        // additive on top of whatever the avatar customisation set; limited so the face stays natural
        faceMesh.SetBlendShapeWeight(browUpIdx, Mathf.Clamp(browBase + browUp * 35f, 0f, 100f));
    }
}
