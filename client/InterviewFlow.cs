using System.Collections;
using TMPro;
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.XR;

/// <summary>
/// The shape of one interview session: Title screen -> Start Interview -> the interviewer introduces themselves ->
/// conversation -> the interviewer's closing reply -> fade to black -> back to the Title screen.
/// Also owns the Restart and End buttons.
///
/// The room and the avatar live on a hidden layer; on the title screen the camera simply does not render that layer,
/// so the main screen is a clean dark void with the menu in front of you.
/// </summary>
public class InterviewFlow : MonoBehaviour
{
    public enum Phase { Title, Starting, Active, Ending }

    [Header("Screens")]
    [SerializeField] private GameObject titlePanel;
    [SerializeField] private GameObject controlPanel;
    [SerializeField] private TMP_Text titleMessage;
    [SerializeField] private TMP_Text startLabel;

    [Header("Job choice")]
    [SerializeField] private Button[] jobButtons;
    [SerializeField] private TMP_Text subtitle;

    [Header("Interviewers")]
    [SerializeField] private InterviewerCast cast;

    [Header("Walk-in")]
    [Tooltip("The candidate starts at the door, walks to the chair and sits while the interviewer's opening line is prepared.")]
    [SerializeField] private bool walkInEnabled = true;
    [SerializeField] private float walkSpeed = 1.0f;

    [Header("Job coach")]
    [SerializeField] private Button coachButton;
    [SerializeField] private CoachPanel coachPanel;

    [Header("Buttons")]
    [SerializeField] private Button startButton;
    [SerializeField] private Button resumeButton;
    [SerializeField] private Button restartButton;
    [SerializeField] private Button endButton;

    [Header("Fade")]
    [SerializeField] private Renderer fadeRenderer;
    [SerializeField] private float fadeOutSeconds = 0.6f;
    [SerializeField] private float fadeInSeconds = 1.4f;

    [Header("Behaviour")]
    [Tooltip("After the interviewer's closing line finishes, wait this long before fading out.")]
    [SerializeField] private float closingPauseSeconds = 3f;
    [SerializeField] private int hiddenLayer = 8;
    [SerializeField] private Color voidColor = new Color(0.02f, 0.03f, 0.05f);

    private const string DefaultMessage = "Hold the trigger or grip to speak. Release to send.\nPress Y or B for the menu.";

    private AudioManager audioManager;
    private WebSocketManager webSocket;
    private AvatarController avatar;
    private SessionManager sessionManager;
    private PushToTalk pushToTalk;
    private UIManager uiManager;
    private Camera cam;
    private int originalMask;
    private CameraClearFlags originalFlags;
    private Color originalBackground;
    private Material fadeMaterial;
    private Coroutine running;
    private bool closingPending;
    private int sessionsCompleted;

    public Phase CurrentPhase { get; private set; } = Phase.Title;

    // remembered across interviews within a run of the app
    private static int selectedJob;
    private static readonly Color JobNormal = new Color(0.16f, 0.2f, 0.28f);
    private static readonly Color JobSelected = new Color(0.1f, 0.55f, 0.62f);

    // --- lifecycle ---------------------------------------------------------------------------------------------

    private void Start()
    {
        audioManager = FindObjectOfType<AudioManager>();
        webSocket = FindObjectOfType<WebSocketManager>();
        avatar = FindObjectOfType<AvatarController>();
        sessionManager = FindObjectOfType<SessionManager>();
        pushToTalk = FindObjectOfType<PushToTalk>();
        uiManager = FindObjectOfType<UIManager>();
        cam = Camera.main;
        var rigGo = GameObject.Find("XR Origin (XR Rig)");
        if (rigGo != null)
        {
            rig = rigGo.transform;
            seatPosition = rig.position;
            seatRotation = rig.rotation;
        }
        walkAudio = gameObject.AddComponent<AudioSource>();
        walkAudio.playOnAwake = false;
        walkAudio.spatialBlend = 0f;
        walkAudio.volume = 0.7f;
        stepClip = MakeStep();
        sitClip = MakeSit();
        if (cam != null)
        {
            originalMask = cam.cullingMask;
            originalFlags = cam.clearFlags;
            originalBackground = cam.backgroundColor;
        }
        if (fadeRenderer != null) fadeMaterial = fadeRenderer.material;

        if (jobButtons != null)
            for (int i = 0; i < jobButtons.Length; i++)
            {
                int index = i;
                if (jobButtons[i] != null) jobButtons[i].onClick.AddListener(() => SelectJob(index));
            }
        SelectJob(Mathf.Clamp(selectedJob, 0, InterviewJobs.All.Length - 1));

        if (startButton != null) startButton.onClick.AddListener(OnStartPressed);
        if (resumeButton != null) resumeButton.onClick.AddListener(CloseMenu);
        if (restartButton != null) restartButton.onClick.AddListener(OnRestartPressed);
        if (endButton != null) endButton.onClick.AddListener(OnEndPressed);
        if (webSocket != null) webSocket.OnInterviewComplete += OnInterviewComplete;
        if (webSocket != null)
        {
            webSocket.OnExportSaved += OnExportSaved;
            webSocket.OnCoachProgress += OnCoachProgress;
            webSocket.OnCoachReport += OnCoachReport;
            webSocket.OnServerStatus += OnServerStatus;
        }
        if (coachButton != null) coachButton.onClick.AddListener(OnCoachPressed);
        if (coachPanel != null) coachPanel.OnClosed += OnCoachClosed;
        if (audioManager != null) audioManager.OnPlaybackCompleted += OnPlaybackCompleted;

        StartCoroutine(PutWorldOnHiddenLayer());
        SetAlpha(0f);
        EnterTitle(null);
    }

    private void OnDestroy()
    {
        if (webSocket != null) webSocket.OnInterviewComplete -= OnInterviewComplete;
        if (webSocket != null)
        {
            webSocket.OnExportSaved -= OnExportSaved;
            webSocket.OnCoachProgress -= OnCoachProgress;
            webSocket.OnCoachReport -= OnCoachReport;
            webSocket.OnServerStatus -= OnServerStatus;
        }
        if (audioManager != null) audioManager.OnPlaybackCompleted -= OnPlaybackCompleted;
        SetWorldVisible(true);
    }

    // --- menu (Y or B) ---------------------------------------------------------------------------------------

    private bool menuHeld;

    private void Update()
    {
        bool down = ButtonDown(XRNode.LeftHand) || ButtonDown(XRNode.RightHand);
        if (down && !menuHeld && CurrentPhase == Phase.Active) ToggleMenu();
        menuHeld = down;
    }

    private static bool ButtonDown(XRNode node)
    {
        var device = InputDevices.GetDeviceAtXRNode(node);
        if (!device.isValid) return false;
        bool value;
        // Y on the left controller, B on the right (secondary buttons), or the menu button
        return (device.TryGetFeatureValue(CommonUsages.secondaryButton, out value) && value)
            || (device.TryGetFeatureValue(CommonUsages.menuButton, out value) && value);
    }

    private void ToggleMenu()
    {
        if (controlPanel == null) return;
        if (controlPanel.activeSelf) { CloseMenu(); return; }

        if (cam != null)
        {
            Vector3 forward = Vector3.ProjectOnPlane(cam.transform.forward, Vector3.up);
            if (forward.sqrMagnitude < 0.01f) forward = cam.transform.forward;
            Vector3 position = cam.transform.position + forward.normalized * 0.8f + Vector3.down * 0.2f;
            controlPanel.transform.position = position;
            controlPanel.transform.rotation = Quaternion.LookRotation(position - cam.transform.position);
        }
        controlPanel.SetActive(true);
    }

    private void CloseMenu()
    {
        if (controlPanel != null) controlPanel.SetActive(false);
    }

    // --- events ---------------------------------------------------------------------------------------------

    private void OnInterviewComplete() => closingPending = true;

    private void OnPlaybackCompleted()
    {
        if (CurrentPhase == Phase.Active && closingPending) Run(EndRoutine(true));
    }

    /// Choose the job for the next interview: updates the title screen and the company name on the office sign.
    private void SelectJob(int index)
    {
        if (CurrentPhase != Phase.Title) return;
        selectedJob = index;
        var job = InterviewJobs.All[index];
        if (subtitle != null) subtitle.text = job.Label + " interview  |  " + job.Company;
        if (jobButtons != null)
            for (int i = 0; i < jobButtons.Length; i++)
            {
                if (jobButtons[i] == null) continue;
                bool on = i == index;
                if (jobButtons[i].image != null) jobButtons[i].image.color = on ? JobSelected : JobNormal;
                var label = jobButtons[i].GetComponentInChildren<TMP_Text>();
                if (label != null) label.text = on ? "> " + InterviewJobs.All[i].Label + " <" : InterviewJobs.All[i].Label;
                jobButtons[i].transform.localScale = Vector3.one * (on ? 1.06f : 1f);
            }
        ApplySign(job);
    }

    private TMP_Text signText;

    // --- export + job coach ----------------------------------------------------------------------------------
    private bool coachAvailable;
    private string lastExportName;
    private int lastQuestionCount;

    private void OnExportSaved(string filename, int questions)
    {
        coachAvailable = true;
        lastExportName = filename;
        lastQuestionCount = questions;
        if (CurrentPhase == Phase.Title)
        {
            if (coachButton != null) coachButton.interactable = true;
            if (titleMessage != null)
                titleMessage.text = "Your interview was saved on the server (exports/" + filename + ").\nPress Job Coach Review for feedback on your answers.";
        }
    }

    private void OnCoachPressed()
    {
        if (CurrentPhase != Phase.Title || !coachAvailable || webSocket == null || coachPanel == null) return;
        if (titlePanel != null) titlePanel.SetActive(false);
        coachPanel.ShowProgress(0, lastQuestionCount);
        webSocket.SendControlMessage("coach");
    }

    private void OnCoachProgress(int done, int total)
    {
        if (coachPanel != null && coachPanel.gameObject.activeSelf) coachPanel.ShowProgress(done, total);
    }

    private void OnCoachReport(CoachReport report)
    {
        if (coachPanel != null && coachPanel.gameObject.activeSelf) coachPanel.Show(report);
    }

    private string serverNotice = "";

    /// The server reports a problem with its language model or voice engine (or that it is fine again).
    private void OnServerStatus(string text)
    {
        serverNotice = text ?? "";
        if (CurrentPhase == Phase.Title && titleMessage != null)
            titleMessage.text = string.IsNullOrEmpty(serverNotice) ? DefaultMessage : "Notice: " + serverNotice;
        else if (uiManager != null && !string.IsNullOrEmpty(serverNotice))
            uiManager.UpdateStatus(serverNotice);
    }

    private void OnCoachClosed()
    {
        if (titlePanel != null) titlePanel.SetActive(true);
    }

    private void ApplySign(InterviewJobs.Job job)
    {
        if (signText == null)
        {
            var sign = GameObject.Find("CompanySign");
            if (sign != null) signText = sign.GetComponent<TMP_Text>();
        }
        if (signText != null) signText.text = job.Company.ToUpperInvariant();
    }

    private void OnStartPressed() { if (CurrentPhase == Phase.Title) Run(StartRoutine()); }
    private void OnRestartPressed() { if (CurrentPhase == Phase.Active) Run(RestartRoutine()); }
    private void OnEndPressed() { if (CurrentPhase == Phase.Active) Run(EndRoutine(false)); }

    private void Run(IEnumerator routine)
    {
        if (running != null) StopCoroutine(running);
        running = StartCoroutine(routine);
    }

    // --- screens ---------------------------------------------------------------------------------------------

    private void EnterTitle(string message)
    {
        StopWalk();
        CurrentPhase = Phase.Title;
        closingPending = false;
        if (pushToTalk != null) pushToTalk.enabled = false;
        if (controlPanel != null) controlPanel.SetActive(false);
        if (titlePanel != null) titlePanel.SetActive(true);
        if (titleMessage != null) titleMessage.text = message ?? (string.IsNullOrEmpty(serverNotice) ? DefaultMessage : "Notice: " + serverNotice);
        if (startLabel != null) startLabel.text = sessionsCompleted > 0 ? "Step 2: Start New Interview" : "Step 2: Start Interview";
        if (coachButton != null) coachButton.interactable = coachAvailable;
        if (coachPanel != null) coachPanel.gameObject.SetActive(false);
        if (startButton != null) startButton.interactable = true;
        if (jobButtons != null) foreach (var b in jobButtons) if (b != null) b.interactable = true;
        SetWorldVisible(false);
    }

    private void SetWorldVisible(bool visible)
    {
        if (cam == null) return;
        if (visible)
        {
            cam.cullingMask = originalMask;
            cam.clearFlags = originalFlags;
            cam.backgroundColor = originalBackground;
        }
        else
        {
            cam.cullingMask = originalMask & ~(1 << hiddenLayer);
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = voidColor;
        }
    }

    /// The room is spawned a moment after start by EnvironmentManager; move it (and the avatar) onto the hidden layer.
    private IEnumerator PutWorldOnHiddenLayer()
    {
        if (avatar != null) SetLayerRecursively(avatar.gameObject, hiddenLayer);
        if (cast != null && cast.Members != null) foreach (var m in cast.Members)
                if (m != null && m.controller != null) SetLayerRecursively(m.controller.gameObject, hiddenLayer);
        var oldCanvas = GameObject.Find("Canvas");   // the original status / state text
        if (oldCanvas != null) SetLayerRecursively(oldCanvas, hiddenLayer);

        float waited = 0f;
        while (waited < 30f)
        {
            var room = GameObject.Find("ConferenceRoomEnvironment") ?? GameObject.Find("ConferenceRoomEnvironment(Clone)");
            if (room != null)
            {
                SetLayerRecursively(room, hiddenLayer);
                yield break;
            }
            waited += 0.25f;
            yield return new WaitForSeconds(0.25f);
        }
    }

    private static void SetLayerRecursively(GameObject go, int layer)
    {
        foreach (var t in go.GetComponentsInChildren<Transform>(true)) t.gameObject.layer = layer;
    }

    // --- fade ---------------------------------------------------------------------------------------------

    private float alpha;

    private void SetAlpha(float a)
    {
        alpha = a;
        if (fadeMaterial != null)
        {
            var c = fadeMaterial.color;
            c.a = a;
            fadeMaterial.color = c;
        }
        if (fadeRenderer != null) fadeRenderer.enabled = a > 0.001f;
    }

    private IEnumerator Fade(float to, float seconds)
    {
        float from = alpha, t = 0f;
        while (t < seconds)
        {
            t += Time.unscaledDeltaTime;
            SetAlpha(Mathf.Lerp(from, to, Mathf.SmoothStep(0f, 1f, t / seconds)));
            yield return null;
        }
        SetAlpha(to);
    }

    // --- flow ---------------------------------------------------------------------------------------------

    private IEnumerator StartRoutine()
    {
        CurrentPhase = Phase.Starting;
        if (startButton != null) startButton.interactable = false;
        if (titleMessage != null) titleMessage.text = "Connecting to the interview server...";

        float waited = 0f;
        while (webSocket != null && !webSocket.IsConnected() && waited < 15f)
        {
            waited += Time.unscaledDeltaTime;
            yield return null;
        }
        if (webSocket == null || !webSocket.IsConnected())
        {
            EnterTitle("Can't reach the interview server. Check that it is running, then try again.");
            yield break;
        }

        if (titlePanel != null) titlePanel.SetActive(false);
        yield return Fade(1f, 0.4f);
        SetWorldVisible(true);
        if (avatar != null) avatar.SetIdleState();
        webSocket.SendControlMessage("reset");
        yield return new WaitForSecondsRealtime(0.4f);
        yield return EnterRoom(fadeInSeconds);
    }

    private IEnumerator RestartRoutine()
    {
        CurrentPhase = Phase.Starting;
        CloseMenu();
        StopWalk();
        if (pushToTalk != null) pushToTalk.enabled = false;
        StopAudio();
        yield return Fade(1f, 0.4f);
        yield return WaitUntilSettled(25f);   // a reset sent while she is still processing would be ignored
        if (avatar != null) avatar.SetIdleState();
        webSocket.SendControlMessage("reset");
        yield return new WaitForSecondsRealtime(0.6f);
        yield return EnterRoom(1.0f);
    }

    private IEnumerator EndRoutine(bool natural)
    {
        CurrentPhase = Phase.Ending;
        CloseMenu();
        StopWalk();
        if (pushToTalk != null) pushToTalk.enabled = false;
        if (natural)
            yield return new WaitForSecondsRealtime(closingPauseSeconds);   // let the goodbye land
        else
            StopAudio();

        yield return Fade(1f, 1.2f);
        StopAudio();
        yield return WaitUntilSettled(25f);
        if (avatar != null) avatar.SetIdleState();
        if (webSocket != null) webSocket.SendControlMessage("reset");   // clear the conversation on the server
        sessionsCompleted++;
        EnterTitle(natural ? "Interview complete. Thanks for practising!" : "Interview ended.");
        yield return Fade(0f, 1.2f);

        Resources.UnloadUnusedAssets();   // release the last reply's audio and anything else no longer needed
        System.GC.Collect();
    }

    // --- walk-in ----------------------------------------------------------------------------------------------

    private Transform rig;
    private Vector3 seatPosition;
    private Quaternion seatRotation;
    private AudioSource walkAudio;
    private AudioClip stepClip, sitClip;
    private Coroutine walkRoutine;

    private const float StandingLift = 0.35f;                         // eyes at about standing height while walking
    private static readonly Vector3 DoorSpot = new Vector3(-3.55f, 0f, -1.8f);   // just inside the door in the west wall
    private const float AisleX = 0f;                                  // walk the south aisle, then turn to the chair

    /// Fade in and bring the candidate to the chair (walking in from the door), asking the server to start the
    /// interview at once so her opening line is being prepared during the walk.
    private IEnumerator EnterRoom(float fadeSeconds)
    {
        if (walkInEnabled && rig != null && audioManager != null)
        {
            audioManager.HoldPlayback = true;   // she speaks once we are seated
            rig.SetPositionAndRotation(DoorPosition(), Quaternion.Euler(0f, 90f, 0f));
            BeginTurn(false);
            walkRoutine = StartCoroutine(WalkToSeat());
            yield return Fade(0f, fadeSeconds);
            yield return walkRoutine;
            if (pushToTalk != null) pushToTalk.enabled = true;
        }
        else
        {
            yield return Fade(0f, fadeSeconds);
            BeginTurn();
        }
    }

    private Vector3 DoorPosition() => new Vector3(DoorSpot.x, seatPosition.y + StandingLift, DoorSpot.z);

    private IEnumerator WalkToSeat()
    {
        Vector3 door = DoorPosition();
        Vector3 corner = new Vector3(AisleX, door.y, DoorSpot.z);
        Vector3 chair = new Vector3(seatPosition.x, seatPosition.y + StandingLift, seatPosition.z);
        float yawEnd = seatRotation.eulerAngles.y;
        float legA = Vector3.Distance(door, corner);
        float legB = Vector3.Distance(corner, chair);
        float timeA = legA / walkSpeed, timeB = legB / (walkSpeed * 0.7f);
        float stepTimer = 0f, t = 0f, total = timeA + timeB;

        while (t < total)
        {
            t += Time.unscaledDeltaTime;
            Vector3 pos;
            float yaw;
            if (t < timeA)
            {
                float u = Mathf.SmoothStep(0f, 1f, Mathf.Min(1f, t / 0.6f)) * 0.0f + t / timeA;   // steady walk
                pos = Vector3.Lerp(door, corner, u);
                yaw = 90f;
            }
            else
            {
                float u = Mathf.Clamp01((t - timeA) / timeB);
                pos = Vector3.Lerp(corner, chair, Mathf.SmoothStep(0f, 1f, u));
                yaw = Mathf.LerpAngle(90f, yawEnd, Mathf.SmoothStep(0f, 1f, u));
            }
            // gentle head bob while walking
            stepTimer += Time.unscaledDeltaTime;
            float bobPhase = t * walkSpeed * 3.6f;
            pos.y += Mathf.Sin(bobPhase * Mathf.PI) * 0.012f;
            if (stepTimer >= 0.55f / walkSpeed) { stepTimer = 0f; if (walkAudio != null && stepClip != null) walkAudio.PlayOneShot(stepClip, 0.8f); }
            rig.SetPositionAndRotation(pos, Quaternion.Euler(0f, yaw, 0f));
            yield return null;
        }

        // sit down: lower to the seated height
        if (walkAudio != null && sitClip != null) walkAudio.PlayOneShot(sitClip);
        Vector3 from = rig.position, to = seatPosition;
        for (float s = 0f; s < 0.9f; s += Time.unscaledDeltaTime)
        {
            rig.SetPositionAndRotation(Vector3.Lerp(from, to, Mathf.SmoothStep(0f, 1f, s / 0.9f)), seatRotation);
            yield return null;
        }
        rig.SetPositionAndRotation(seatPosition, seatRotation);
        if (audioManager != null) audioManager.HoldPlayback = false;   // now she can start talking
        walkRoutine = null;
    }

    /// Abort a walk in progress and put the candidate back in the chair (restart / end / title).
    private void StopWalk()
    {
        if (walkRoutine != null) { StopCoroutine(walkRoutine); walkRoutine = null; }
        if (rig != null) rig.SetPositionAndRotation(seatPosition, seatRotation);
        if (audioManager != null) audioManager.HoldPlayback = false;
    }

    /// A soft footstep on carpet: low-passed noise burst with a quick decay.
    private static AudioClip MakeStep()
    {
        const int rate = 44100;
        int count = (int)(rate * 0.16f);
        var samples = new float[count];
        var rnd = new System.Random(3);
        float lp = 0f;
        for (int i = 0; i < count; i++)
        {
            float noise = (float)(rnd.NextDouble() * 2.0 - 1.0);
            lp += 0.12f * (noise - lp);
            samples[i] = lp * Mathf.Exp(-i / (rate * 0.03f)) * 2.2f;
        }
        var clip = AudioClip.Create("Footstep", count, 1, rate, false);
        clip.SetData(samples, 0);
        return clip;
    }

    /// Sitting into an office chair: a low thump with a little rustle.
    private static AudioClip MakeSit()
    {
        const int rate = 44100;
        int count = (int)(rate * 0.45f);
        var samples = new float[count];
        var rnd = new System.Random(9);
        float lp = 0f;
        for (int i = 0; i < count; i++)
        {
            float t = i / (float)rate;
            float noise = (float)(rnd.NextDouble() * 2.0 - 1.0);
            lp += 0.08f * (noise - lp);
            samples[i] = (Mathf.Sin(2f * Mathf.PI * 62f * t) * Mathf.Exp(-t * 12f) * 0.8f + lp * Mathf.Exp(-t * 7f) * 1.6f) * 0.9f;
        }
        var clip = AudioClip.Create("ChairSit", count, 1, rate, false);
        clip.SetData(samples, 0);
        return clip;
    }

    /// Ask the server for the interviewer's opening: she introduces herself and asks the first question.
    private InterviewerCast.Member currentInterviewer;

    private void BeginTurn(bool enablePushToTalk = true)
    {
        closingPending = false;
        if (cast != null && cast.Count > 0)
        {
            currentInterviewer = cast.SelectNext();   // a different interviewer for every interview
            if (currentInterviewer != null && currentInterviewer.controller != null) avatar = currentInterviewer.controller;
        }
        CurrentPhase = Phase.Active;
        if (pushToTalk != null) pushToTalk.enabled = enablePushToTalk;
        if (uiManager != null) uiManager.UpdateStatus("The interviewer is joining... (Y or B = menu)");
        if (avatar != null) avatar.SetAttentiveState();
        var chosen = InterviewJobs.All[Mathf.Clamp(selectedJob, 0, InterviewJobs.All.Length - 1)];
        ApplySign(chosen);
        webSocket.SendControlMessage("begin", chosen.Id,
            currentInterviewer != null ? currentInterviewer.displayName : null,
            currentInterviewer != null ? currentInterviewer.voice : null);
    }

    /// Wait (up to maxSeconds) until the server session is idle or waiting, i.e. not mid-reply.
    private IEnumerator WaitUntilSettled(float maxSeconds)
    {
        float waited = 0f;
        while (sessionManager != null && waited < maxSeconds)
        {
            string state = sessionManager.GetCurrentState();
            if (state == "IDLE" || state == "WAITING" || state == "ERROR") yield break;
            waited += Time.unscaledDeltaTime;
            yield return null;
        }
    }

    private void StopAudio()
    {
        if (audioManager == null) return;
        if (audioManager.IsRecording) audioManager.CancelRecording();
        audioManager.StopPlayback();
    }
}
