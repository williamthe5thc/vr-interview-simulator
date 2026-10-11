using UnityEngine;

/// <summary>
/// Eye contact for the interviewer: eyes and head follow the candidate's headset camera, with small saccades,
/// glances away while thinking or speaking, and glances down at the notes. Replaces the avatar pack's static
/// EyeController (same eye-bone convention, but with a clamp, smoothing and behaviour on top).
///
/// Hooks: SetMode(GazeMode), SetTalking(bool), GlanceAway(), GlanceAtNotes(), SetTarget(Transform)
/// </summary>
[DefaultExecutionOrder(110)]
public class InterviewerGaze : MonoBehaviour
{
    public enum GazeMode { Contact, Thinking, Notes }

    [Header("References (auto-found if empty)")]
    [SerializeField] private Animator animator;
    [Tooltip("Who to look at. Defaults to the main camera (the candidate's eyes).")]
    [SerializeField] private Transform lookTarget;
    [Tooltip("Where the notepad is, for glances down.")]
    [SerializeField] private Transform notesTarget;
    [SerializeField] private Transform head;
    [SerializeField] private Transform eyeLeft;
    [SerializeField] private Transform eyeRight;
    [SerializeField] private Transform gazeTargetRoot;     // the avatar pack's GazeTarget object (moved to where we look)
    [SerializeField] private InterviewerFace face;

    [Header("Behaviour")]
    [SerializeField, Range(0f, 1f)] private float headFollow = 0.5f;
    [SerializeField] private float maxHeadAngle = 38f;
    [SerializeField] private float maxEyeAngle = 32f;
    [SerializeField] private float eyeSpeed = 0.06f;       // smoothing time of the eye point (small = snappy)
    [SerializeField] private float headSpeed = 0.35f;
    [Tooltip("Seconds between small eye micro-movements.")]
    [SerializeField] private Vector2 saccadeInterval = new Vector2(0.5f, 2.2f);
    [SerializeField] private float saccadeSize = 0.03f;    // metres at the candidate
    [Tooltip("Seconds between glances away while talking / listening.")]
    [SerializeField] private Vector2 glanceInterval = new Vector2(3.5f, 8f);

    private GazeMode mode = GazeMode.Contact;
    private bool talking;
    private Vector3 gazePoint, gazeVel;
    private Vector3 saccade;
    private float nextSaccadeAt, nextGlanceAt, glanceUntil;
    private Vector3 glanceOffset;
    private bool glanceNotes;
    private Quaternion headDelta = Quaternion.identity;
    private Vector3 headFwdLocal;
    private bool calibrated;
    private float time, lookSearchAt, lastShiftBlink = -10f;
    private Vector3 lastDesired;

    /// Blink at the start of a large gaze shift (not more often than once a second).
    private void BlinkOnShift()
    {
        if (face == null || time - lastShiftBlink < 1f) return;
        lastShiftBlink = time;
        face.Blink();
    }

    // --- hooks ---------------------------------------------------------------------------------------------

    public void SetMode(GazeMode m)
    {
        if (m == mode) return;
        mode = m;
        if (m != GazeMode.Contact) glanceUntil = 0f;
        if (m == GazeMode.Thinking) BlinkOnShift();     // a blink as the eyes go off to think
    }

    public void SetTalking(bool value)
    {
        if (talking == value) return;
        talking = value;
        // people look away as they start a sentence and come back to the listener towards its end
        if (talking && mode == GazeMode.Contact && Random.value < 0.55f) { GlanceAway(Random.Range(0.7f, 1.5f)); nextGlanceAt = time + Random.Range(glanceInterval.x, glanceInterval.y); }
        else if (!talking && mode == GazeMode.Contact) glanceUntil = 0f;
    }
    public void SetTarget(Transform t) { lookTarget = t; }

    public void GlanceAway(float seconds = 1f)
    {
        glanceNotes = false;
        glanceOffset = RootRight() * (Random.value < 0.5f ? -0.5f : 0.5f) + Vector3.up * Random.Range(-0.1f, 0.3f);
        glanceUntil = time + seconds;
        if (face != null) face.Blink();
    }

    public void GlanceAtNotes(float seconds = 1.2f)
    {
        glanceNotes = true;
        glanceUntil = time + seconds;
        if (face != null) face.Blink();
    }

    // --- lifecycle ---------------------------------------------------------------------------------------------

    private void Start() => Initialise();

    public bool Initialise()
    {
        if (head != null) return true;
        if (animator == null)
            foreach (var a in GetComponentsInChildren<Animator>(false))
                if (a.avatar != null && a.avatar.isHuman) { animator = a; break; }
        if (animator == null) { enabled = false; return false; }

        head = animator.GetBoneTransform(HumanBodyBones.Head);
        if (head == null) { enabled = false; return false; }
        if (eyeLeft == null) eyeLeft = head.Find("Eye_L");
        if (eyeRight == null) eyeRight = head.Find("Eye_R");
        if (eyeLeft == null) eyeLeft = animator.GetBoneTransform(HumanBodyBones.LeftEye);     // Rocketbox and other humanoid rigs
        if (eyeRight == null) eyeRight = animator.GetBoneTransform(HumanBodyBones.RightEye);
        if (face == null) face = GetComponent<InterviewerFace>();
        if (gazeTargetRoot == null)
        {
            var g = transform.Find("GazeTarget");
            if (g != null) gazeTargetRoot = g;
        }

        // the pack's own eye script would fight ours
        foreach (var ec in GetComponentsInChildren<Sunbox.Avatars.EyeController>(true)) ec.enabled = false;

        nextSaccadeAt = Random.Range(saccadeInterval.x, saccadeInterval.y);
        nextGlanceAt = Random.Range(glanceInterval.x, glanceInterval.y);
        return true;
    }

    private Vector3 RootForward() { var f = animator.transform.forward; f.y = 0; return f.normalized; }
    private Vector3 RootRight() => Vector3.Cross(Vector3.up, RootForward());

    private void LateUpdate()
    {
        if (head == null && !Initialise()) return;
        Tick(Time.deltaTime);
    }

    private Vector3 Candidate()
    {
        if (lookTarget == null && Time.unscaledTime >= lookSearchAt)
        {
            lookSearchAt = Time.unscaledTime + 1f;
            var cam = Camera.main;
            if (cam != null) lookTarget = cam.transform;
        }
        // no candidate yet: look straight across the table
        return lookTarget != null ? lookTarget.position : head.position + RootForward() * 1.2f - Vector3.up * 0.05f;
    }

    /// <summary>Advance and apply. Public so editor tooling can step it without play mode.</summary>
    public void Tick(float dt)
    {
        if (head == null && !Initialise()) return;
        time += dt;

        if (!calibrated)
        {
            // Body has already posed the skeleton this frame; the head faces the root's forward in the seated pose.
            headFwdLocal = Quaternion.Inverse(head.rotation) * RootForward();
            eyeAxisLeft = EyeForwardAxis(eyeLeft);
            eyeAxisRight = EyeForwardAxis(eyeRight);
            calibrated = true;
            gazePoint = Candidate();
        }

        // ---- decide where to look ----
        Vector3 cand = Candidate();
        if (time >= nextSaccadeAt)
        {
            // thinking: the eyes wander more
            float wander = mode == GazeMode.Thinking ? 3f : 1f;
            saccade = (RootRight() * Random.Range(-1f, 1f) + Vector3.up * Random.Range(-0.6f, 0.6f)) * saccadeSize * wander;
            nextSaccadeAt = time + Random.Range(saccadeInterval.x, saccadeInterval.y);
        }

        if (mode == GazeMode.Contact && time >= nextGlanceAt && time > glanceUntil)
        {
            // fewer glances in the first moments of an answer; notes glances while listening
            if (!talking && Random.value < 0.4f) GlanceAtNotes(Random.Range(0.8f, 1.5f));
            else GlanceAway(Random.Range(0.6f, 1.3f));
            // a listener keeps more eye contact than a speaker
            nextGlanceAt = time + Random.Range(glanceInterval.x, glanceInterval.y) * (talking ? 1f : 1.6f);
        }

        Vector3 desired;
        Vector3 headDesired;
        if (mode == GazeMode.Thinking)
        {
            desired = head.position + RootForward() * 1.0f - RootRight() * 0.55f + Vector3.up * 0.30f;
            headDesired = desired;
        }
        else if (mode == GazeMode.Notes || (time < glanceUntil && glanceNotes))
        {
            desired = notesTarget != null ? notesTarget.position : head.position + RootForward() * 0.45f - Vector3.up * 0.45f;
            headDesired = desired;
        }
        else if (time < glanceUntil)
        {
            desired = cand + glanceOffset;
            headDesired = Vector3.Lerp(cand, desired, 0.6f);
        }
        else
        {
            desired = cand + saccade;
            headDesired = cand;
        }

        // eyes move fast, head slower
        // blink when the thing we look at jumps far (glance, notes), not on the small saccades
        if ((desired - lastDesired).magnitude > 0.35f && Random.value < 0.7f) BlinkOnShift();
        lastDesired = desired;
        gazePoint = Vector3.SmoothDamp(gazePoint, desired, ref gazeVel, eyeSpeed, 20f, dt);

        // ---- head ----
        Vector3 headFwd = head.rotation * headFwdLocal;
        Vector3 toTarget = (headDesired - head.position).normalized;
        Quaternion full = Quaternion.FromToRotation(headFwd, toTarget);
        full.ToAngleAxis(out float ang, out Vector3 axis);
        if (ang > 180f) ang -= 360f;
        float limited = Mathf.Clamp(ang * headFollow, -maxHeadAngle, maxHeadAngle);
        Quaternion wanted = Quaternion.AngleAxis(limited, axis);
        headDelta = Quaternion.Slerp(headDelta, wanted, 1f - Mathf.Exp(-dt / Mathf.Max(headSpeed * 0.5f, 0.01f)));
        head.rotation = headDelta * head.rotation;

        // ---- eyes ----
        if (gazeTargetRoot != null) gazeTargetRoot.position = gazePoint;
        headFwd = head.rotation * headFwdLocal;
        AimEye(eyeLeft, gazePoint, headFwd, eyeAxisLeft);
        AimEye(eyeRight, gazePoint, headFwd, eyeAxisRight);
    }

    private Vector3 eyeAxisLeft = Vector3.up, eyeAxisRight = Vector3.up;

    /// The eye bone's local axis that points where the head looks (Y for the original pack, another axis for other rigs).
    private Vector3 EyeForwardAxis(Transform eye)
    {
        if (eye == null) return Vector3.up;
        Vector3 d = eye.InverseTransformDirection(head.rotation * headFwdLocal);
        float ax = Mathf.Abs(d.x), ay = Mathf.Abs(d.y), az = Mathf.Abs(d.z);
        if (ax >= ay && ax >= az) return new Vector3(Mathf.Sign(d.x), 0f, 0f);
        return ay >= az ? new Vector3(0f, Mathf.Sign(d.y), 0f) : new Vector3(0f, 0f, Mathf.Sign(d.z));
    }

    private void AimEye(Transform eye, Vector3 point, Vector3 headFwd, Vector3 localForward)
    {
        if (eye == null) return;
        Vector3 dir = (point - eye.position).normalized;
        float a = Vector3.Angle(headFwd, dir);
        if (a > maxEyeAngle) dir = Vector3.Slerp(headFwd, dir, maxEyeAngle / a);
        // turn the eye so that its own forward axis (found at start) points along dir
        eye.rotation = Quaternion.LookRotation(dir, Vector3.up) * Quaternion.FromToRotation(localForward, Vector3.forward);
    }

    public Transform NotesTarget { get => notesTarget; set => notesTarget = value; }
}
