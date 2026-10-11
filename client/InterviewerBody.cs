using UnityEngine;

/// <summary>
/// Procedural body animation for a seated interviewer on a Humanoid rig.
/// Drives the whole body through humanoid muscles (HumanPoseHandler), so it needs no animation clips and works with
/// any humanoid avatar. Layers on top of a solved seated pose: breathing, posture per interview state,
/// listening nods, speech-driven emphasis nods and hand gestures.
///
/// Hooks (called by AvatarController, or call them yourself):
///   SetPosture(Posture), SetTalking(bool), Nod(strength), Gesture(index), SetSpeechLevel(0..1)
/// </summary>
[DefaultExecutionOrder(100)]
public class InterviewerBody : MonoBehaviour
{
    public enum Posture { Neutral, Attentive, Listening, Thinking, Speaking, Confused }

    [Header("Rig (auto-found if empty)")]
    [SerializeField] private Animator animator;

    [Header("Seated pose (solved in the editor by InterviewerSeatSolver)")]
    [SerializeField] private string[] seatedMuscleNames;
    [SerializeField] private float[] seatedMuscleValues;
    [Tooltip("Finger relaxation: 0 = flat hand, 1 = fist.")]
    [SerializeField, Range(0f, 1f)] private float fingerCurl = 0.3f;
    [SerializeField, Range(-1f, 1f)] private float restingFingerOpen = 0.35f;   // positive = fingers extended

    [Header("Motion")]
    [SerializeField] private float breathsPerMinute = 14f;
    [SerializeField] private float breathDepth = 1f;
    [SerializeField] private float swayAmount = 1f;
    [SerializeField] private float postureBlendSpeed = 2.5f;
    [SerializeField] private float gestureAmount = 1f;
    [Tooltip("Seconds between speech gestures (random in this range) while talking.")]
    [SerializeField] private Vector2 gestureInterval = new Vector2(2.2f, 4.5f);
    [Tooltip("Seconds between backchannel nods while listening.")]
    [SerializeField] private Vector2 listenNodInterval = new Vector2(3.5f, 7f);

    // One set of offsets per posture. Muscle units: +-1 is the full range of the muscle.
    // Signs (probed on this rig): chest/upper-chest negative = lean forward; neck/head nod negative = look down;
    // tilt/turn positive = toward the avatar's right.
    struct PostureOffsets
    {
        public float lean;        // forward lean
        public float headNod;     // + up / - down
        public float headTilt;    // + right
        public float headTurn;
        public float shoulders;   // + raised
        public float armLift;     // raises both forearms off the table a little
        public float animation;   // 0..1 how lively the idle motion is
    }

    static PostureOffsets Offsets(Posture p)
    {
        switch (p)
        {
            case Posture.Attentive: return new PostureOffsets { lean = 0.35f, headNod = 0.00f, headTilt = 0.03f, animation = 0.7f };
            case Posture.Listening: return new PostureOffsets { lean = 0.45f, headNod = -0.03f, headTilt = 0.07f, animation = 0.5f };
            case Posture.Thinking: return new PostureOffsets { lean = -0.10f, headNod = 0.05f, headTilt = -0.12f, headTurn = -0.04f, armLift = 0.15f, animation = 0.6f };
            case Posture.Speaking: return new PostureOffsets { lean = 0.30f, headNod = 0.00f, headTilt = 0.00f, animation = 1.0f };
            case Posture.Confused: return new PostureOffsets { lean = -0.35f, headNod = 0.02f, headTilt = 0.20f, shoulders = 0.30f, animation = 0.5f };
            default: return new PostureOffsets { animation = 0.6f };
        }
    }

    private static string[] s_muscleNames;
    private HumanPoseHandler handler;
    private HumanPose pose;
    private float[] baseMuscles, muscles;
    private bool ready;

    private Posture posture = Posture.Neutral;
    private PostureOffsets current, target;
    private bool talking;
    private float speechLevel;

    private float time;
    private float nodStart = -10f, nodStrength;
    private float gestureStart = -10f, gestureDuration = 1.2f, gestureSide = 1f, gestureKind;
    private float nextGestureAt, nextListenNodAt;
    private float seed;

    public Posture CurrentPosture => posture;
    public bool IsReady => ready;

    // --- public hooks ---------------------------------------------------------------------------------------

    public void SetPosture(Posture p)
    {
        posture = p;
        target = Offsets(p);
        if (p == Posture.Listening) nextListenNodAt = time + Random.Range(1.5f, 3f);
    }

    public void SetTalking(bool value)
    {
        if (talking == value) return;
        talking = value;
        if (talking) nextGestureAt = time + Random.Range(0.4f, 1.2f);
    }

    /// <summary>0..1 loudness of the current speech; emphasises nods on onsets. Fed by InterviewerFace.</summary>
    public void SetSpeechLevel(float level)
    {
        if (level > 0.65f && speechLevel < 0.45f && talking && time - nodStart > 0.9f) Nod(0.35f);
        speechLevel = level;
    }

    /// <summary>A single head nod. strength 1 = clear acknowledging nod.</summary>
    public void Nod(float strength = 1f)
    {
        nodStart = time;
        nodStrength = strength;
        // acknowledging nods are sometimes a quick double nod
        if (strength >= 0.5f && Random.value < 0.25f) pendingNodAt = time + 0.6f;
    }

    private float pendingNodAt = -1f;
    private float shiftStartAt, shiftEndAt, nextShiftAt = 20f;
    private float shiftLean, shiftLeanFrom, shiftSide, shiftSideFrom, shiftLeanTo, shiftSideTo, breathPhase;

    /// <summary>Hand gesture: 0 = open palm lift, 1 = emphasis beat, 2 = two-handed explain. -1 = random.</summary>
    public void Gesture(int index = -1)
    {
        gestureKind = index < 0 ? Random.Range(0, 3) : index % 3;
        gestureSide = Random.value < 0.5f ? 1f : -1f;
        gestureStart = time;
        gestureDuration = Random.Range(1.1f, 1.8f);
    }

    // --- lifecycle ---------------------------------------------------------------------------------------------

    private void Awake()
    {
        seed = Random.value * 100f;
        target = current = Offsets(Posture.Neutral);
    }

    private void Start() => Initialise();

    public bool Initialise()
    {
        if (ready) return true;
        if (animator == null)
        {
            foreach (var a in GetComponentsInChildren<Animator>(false))
                if (a.avatar != null && a.avatar.isHuman) { animator = a; break; }
        }
        if (animator == null || animator.avatar == null || !animator.avatar.isHuman)
        {
            Debug.LogWarning("[InterviewerBody] No humanoid Animator found; body animation disabled.");
            enabled = false;
            return false;
        }

        // We pose the skeleton directly; make sure the Animator is not also writing to it.
        animator.applyRootMotion = false;
        animator.enabled = false;

        if (s_muscleNames == null) s_muscleNames = HumanTrait.MuscleName;
        handler = new HumanPoseHandler(animator.avatar, animator.transform);
        pose = new HumanPose();
        handler.GetHumanPose(ref pose);   // keeps the avatar's own body position/rotation
        // For some rigs GetHumanPose reports the body position/rotation in world terms (in human-scale units) while SetHumanPose reads
        // them relative to the character, so a character that is not at the world origin jumps when a pose is applied (Rocketbox);
        // other rigs round-trip fine (the original pack avatar). Test with a no-op write and convert only if the hips move.
        var hipsT = animator.GetBoneTransform(HumanBodyBones.Hips);
        Vector3 hipsBefore = hipsT.position;
        handler.SetHumanPose(ref pose);
        if ((hipsT.position - hipsBefore).sqrMagnitude > 1e-4f)
        {
            var rootT = animator.transform;
            float humanScale = animator.humanScale;
            pose.bodyPosition = rootT.InverseTransformPoint(pose.bodyPosition * humanScale) / humanScale;
            pose.bodyRotation = Quaternion.Inverse(rootT.rotation) * pose.bodyRotation;
            handler.SetHumanPose(ref pose);   // back to where it was
        }

        baseMuscles = new float[HumanTrait.MuscleCount];
        muscles = new float[HumanTrait.MuscleCount];
        if (seatedMuscleNames != null)
            for (int i = 0; i < seatedMuscleNames.Length && i < seatedMuscleValues.Length; i++)
                Add(baseMuscles, seatedMuscleNames[i], seatedMuscleValues[i]);
        for (int i = 0; i < s_muscleNames.Length; i++)
            if (s_muscleNames[i].EndsWith(" Stretched"))
                // resting hands lie relaxed and nearly flat (curled fingers looked like she was gripping a controller)
                baseMuscles[i] = s_muscleNames[i].Contains("Thumb") ? 0f : restingFingerOpen;

        nextGestureAt = nextListenNodAt = 2f;
        ready = true;
        return true;
    }

    private void LateUpdate()
    {
        if (!ready) return;
        Tick(Time.deltaTime);
    }

    /// <summary>Advance and apply the pose. Public so editor tooling can step it without play mode.</summary>
    public void Tick(float dt)
    {
        if (!ready && !Initialise()) return;
        time += dt;

        // blend posture offsets
        float k = 1f - Mathf.Exp(-dt * postureBlendSpeed);
        current.lean = Mathf.Lerp(current.lean, target.lean, k);
        current.headNod = Mathf.Lerp(current.headNod, target.headNod, k);
        current.headTilt = Mathf.Lerp(current.headTilt, target.headTilt, k);
        current.headTurn = Mathf.Lerp(current.headTurn, target.headTurn, k);
        current.shoulders = Mathf.Lerp(current.shoulders, target.shoulders, k);
        current.armLift = Mathf.Lerp(current.armLift, target.armLift, k);
        current.animation = Mathf.Lerp(current.animation, target.animation, k);

        // schedule automatic behaviours
        if (talking && time >= nextGestureAt)
        {
            if (time - gestureStart > gestureDuration) Gesture();
            nextGestureAt = time + Random.Range(gestureInterval.x, gestureInterval.y);
        }
        if (!talking && posture == Posture.Listening && time >= nextListenNodAt)
        {
            Nod(Random.Range(0.5f, 0.9f));
            nextListenNodAt = time + Random.Range(listenNodInterval.x, listenNodInterval.y);
        }

        if (pendingNodAt > 0f && time >= pendingNodAt) { pendingNodAt = -1f; nodStart = time; nodStrength *= 0.6f; }

        // an occasional shift of weight: lean and side move slowly to a new resting value every 20-45 s
        if (time >= nextShiftAt)
        {
            shiftStartAt = time; shiftEndAt = time + Random.Range(1.5f, 2.5f);
            shiftLeanFrom = shiftLean; shiftSideFrom = shiftSide;
            shiftLeanTo = Random.Range(-0.08f, 0.10f); shiftSideTo = Random.Range(-0.12f, 0.12f);
            nextShiftAt = time + Random.Range(20f, 45f);
        }
        float shiftT = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(shiftStartAt, shiftEndAt, time));
        shiftLean = Mathf.Lerp(shiftLeanFrom, shiftLeanTo, shiftT);
        shiftSide = Mathf.Lerp(shiftSideFrom, shiftSideTo, shiftT);

        System.Array.Copy(baseMuscles, muscles, muscles.Length);
        Add(muscles, "Chest Front-Back", -shiftLean);
        Add(muscles, "Spine Left-Right", shiftSide * 0.5f);

        // --- posture ---
        float a = current.animation;
        Add(muscles, "Chest Front-Back", -current.lean * 0.8f);
        Add(muscles, "UpperChest Front-Back", -current.lean * 0.6f);
        Add(muscles, "Neck Nod Down-Up", current.headNod * 0.5f);
        Add(muscles, "Head Nod Down-Up", current.headNod * 0.5f);
        Add(muscles, "Neck Tilt Left-Right", current.headTilt * 0.5f);
        Add(muscles, "Head Tilt Left-Right", current.headTilt * 0.5f);
        Add(muscles, "Neck Turn Left-Right", current.headTurn * 0.5f);
        Add(muscles, "Head Turn Left-Right", current.headTurn * 0.5f);
        Add(muscles, "Left Shoulder Down-Up", current.shoulders);
        Add(muscles, "Right Shoulder Down-Up", current.shoulders);
        Add(muscles, "Left Arm Down-Up", current.armLift * 0.4f);
        Add(muscles, "Right Arm Down-Up", current.armLift * 0.4f);

        // --- breathing + sway ---
        // breathing: a little faster while talking, with a slowly wandering rate so it is never a perfect sine
        float bpm = breathsPerMinute * (talking ? 1.25f : 1f) * (1f + 0.12f * Noise(0.05f, 41f));
        breathPhase += dt * Mathf.PI * 2f * bpm / 60f;
        float breathe = Mathf.Sin(breathPhase);
        Add(muscles, "Chest Front-Back", breathe * 0.07f * breathDepth);
        Add(muscles, "UpperChest Front-Back", breathe * 0.09f * breathDepth);
        Add(muscles, "Left Shoulder Down-Up", breathe * 0.04f * breathDepth);
        Add(muscles, "Right Shoulder Down-Up", breathe * 0.04f * breathDepth);

        float n1 = Noise(0.13f, 0f), n2 = Noise(0.11f, 7f), n3 = Noise(0.17f, 13f), n4 = Noise(0.2f, 21f);
        Add(muscles, "Spine Left-Right", n1 * 0.10f * swayAmount * a);
        Add(muscles, "Spine Twist Left-Right", n2 * 0.08f * swayAmount * a);
        Add(muscles, "Head Tilt Left-Right", n3 * 0.07f * swayAmount * a);
        Add(muscles, "Head Turn Left-Right", n4 * 0.05f * swayAmount * a);
        Add(muscles, "Head Nod Down-Up", Noise(0.23f, 31f) * 0.04f * swayAmount * a);

        // --- talking: gentle head motion that follows the voice ---
        if (talking)
        {
            float lively = 0.4f + speechLevel * 0.6f;
            Add(muscles, "Head Nod Down-Up", Mathf.Sin(time * 3.1f) * 0.06f * lively);
            Add(muscles, "Neck Nod Down-Up", Mathf.Sin(time * 3.1f + 0.4f) * 0.04f * lively);
            Add(muscles, "Head Turn Left-Right", Mathf.Sin(time * 1.7f + 1f) * 0.06f * lively);
            Add(muscles, "Head Tilt Left-Right", Mathf.Sin(time * 1.3f + 2f) * 0.05f * lively);
        }

        // --- nod (down then back up) ---
        float nt = (time - nodStart) / 0.9f;
        if (nt >= 0f && nt < 1f)
        {
            float env = Mathf.Sin(nt * Mathf.PI);
            float dip = Mathf.Sin(nt * Mathf.PI * 2f);   // down, up
            Add(muscles, "Head Nod Down-Up", -0.30f * nodStrength * dip * env);
            Add(muscles, "Neck Nod Down-Up", -0.16f * nodStrength * dip * env);
            Add(muscles, "Chest Front-Back", -0.05f * nodStrength * env);
        }

        // --- hand gesture ---
        float gt = (time - gestureStart) / gestureDuration;
        if (!handsInLap && gt >= 0f && gt < 1f)
        {
            float env = Mathf.SmoothStep(0f, 1f, Mathf.Min(gt * 3f, 1f)) * Mathf.SmoothStep(0f, 1f, Mathf.Min((1f - gt) * 3f, 1f));
            float beat = gestureKind == 1f ? Mathf.Abs(Mathf.Sin(gt * Mathf.PI * 3f)) : 1f;
            float g = env * gestureAmount;
            bool both = gestureKind == 2f;
            ApplyArmGesture("Right", gestureSide > 0 || both ? g : g * 0.0f, beat);
            ApplyArmGesture("Left", gestureSide < 0 || both ? g : g * 0.0f, beat);
        }

        pose.muscles = muscles;
        handler.SetHumanPose(ref pose);
        if (handsInLap) PlaceHandsInLap(); else KeepArmsAboveTable();
    }

    private void ApplyArmGesture(string side, float g, float beat)
    {
        if (g <= 0.001f) return;
        // lift the arm off the table, open the forearm out and tilt the hand up; fingers relax
        Add(muscles, side + " Arm Down-Up", 0.30f * g * (0.7f + 0.3f * beat));
        Add(muscles, side + " Arm Front-Back", 0.05f * g);
        Add(muscles, side + " Forearm Stretch", -0.35f * g);
        Add(muscles, side + " Forearm Twist In-Out", 0.20f * g);
        Add(muscles, side + " Hand Down-Up", 0.25f * g * beat);
        for (int i = 0; i < s_muscleNames.Length; i++)
            if (s_muscleNames[i].StartsWith(side) && s_muscleNames[i].EndsWith(" Stretched")) muscles[i] += 0.2f * g;
    }

    [Header("Table clearance")]
    [SerializeField] private float tableTopHeight = 0.775f;
    [Tooltip("Half size of the table area in world x and z, around the origin.")]
    [SerializeField] private Vector2 tableHalfExtent = new Vector2(2.2f, 0.7f);
    [SerializeField] private float tableClearance = 0.045f;
    [SerializeField] private float fingerClearance = 0.018f;

    private static readonly HumanBodyBones[] LeftFingers =
    {
        HumanBodyBones.LeftThumbIntermediate, HumanBodyBones.LeftThumbDistal,
        HumanBodyBones.LeftIndexProximal, HumanBodyBones.LeftIndexIntermediate, HumanBodyBones.LeftIndexDistal,
        HumanBodyBones.LeftMiddleProximal, HumanBodyBones.LeftMiddleIntermediate, HumanBodyBones.LeftMiddleDistal,
        HumanBodyBones.LeftRingProximal, HumanBodyBones.LeftRingIntermediate, HumanBodyBones.LeftRingDistal,
        HumanBodyBones.LeftLittleProximal, HumanBodyBones.LeftLittleIntermediate, HumanBodyBones.LeftLittleDistal,
    };
    private static readonly HumanBodyBones[] RightFingers =
    {
        HumanBodyBones.RightThumbIntermediate, HumanBodyBones.RightThumbDistal,
        HumanBodyBones.RightIndexProximal, HumanBodyBones.RightIndexIntermediate, HumanBodyBones.RightIndexDistal,
        HumanBodyBones.RightMiddleProximal, HumanBodyBones.RightMiddleIntermediate, HumanBodyBones.RightMiddleDistal,
        HumanBodyBones.RightRingProximal, HumanBodyBones.RightRingIntermediate, HumanBodyBones.RightRingDistal,
        HumanBodyBones.RightLittleProximal, HumanBodyBones.RightLittleIntermediate, HumanBodyBones.RightLittleDistal,
    };

    /// Leaning, gestures and breathing can push a wrist or finger below the tabletop (the palm and fingers sank into the
    /// wood when only the wrist was checked). Raising the arm with a muscle swings it sideways, so instead each arm is
    /// re-solved with a two-bone IK that lifts the wrist straight up by exactly the deficit and keeps the elbow bend.
    private void KeepArmsAboveTable()
    {
        LiftArm(HumanBodyBones.LeftUpperArm, HumanBodyBones.LeftLowerArm, HumanBodyBones.LeftHand, LeftFingers);
        LiftArm(HumanBodyBones.RightUpperArm, HumanBodyBones.RightLowerArm, HumanBodyBones.RightHand, RightFingers);
    }

    public static bool DebugArms;

    [Header("Hands")]
    [Tooltip("Rest the hands in her lap, below the desk. (Resting them on the table made the fingers sink into it.)")]
    [SerializeField] private bool handsInLap = true;
    [SerializeField] private Vector3 lapLeftWrist = new Vector3(0.15f, 0.66f, 0.80f);
    [SerializeField] private Vector3 lapRightWrist = new Vector3(-0.15f, 0.66f, 0.80f);

    private void PlaceHandsInLap()
    {
        SolveArmTo(HumanBodyBones.LeftUpperArm, HumanBodyBones.LeftLowerArm, HumanBodyBones.LeftHand, HumanBodyBones.LeftMiddleProximal, lapLeftWrist);
        SolveArmTo(HumanBodyBones.RightUpperArm, HumanBodyBones.RightLowerArm, HumanBodyBones.RightHand, HumanBodyBones.RightMiddleProximal, lapRightWrist);
    }

    /// Two-bone IK: put the wrist at a world position (keeping the elbow bend direction) and lay the hand flat.
    private void SolveArmTo(HumanBodyBones upper, HumanBodyBones lower, HumanBodyBones hand, HumanBodyBones knuckleBone, Vector3 target)
    {
        Transform u = animator.GetBoneTransform(upper), l = animator.GetBoneTransform(lower), h = animator.GetBoneTransform(hand);
        if (u == null || l == null || h == null) return;
        Vector3 s0 = u.position, e0 = l.position, w0 = h.position;
        float l1 = (e0 - s0).magnitude, l2 = (w0 - e0).magnitude;

        Vector3 toTarget = target - s0;
        float d = Mathf.Clamp(toTarget.magnitude, 0.05f, l1 + l2 - 0.002f);
        Vector3 dir = toTarget.normalized;
        float along = (l1 * l1 - l2 * l2 + d * d) / (2f * d);
        float height = Mathf.Sqrt(Mathf.Max(0f, l1 * l1 - along * along));
        Vector3 pole = Vector3.ProjectOnPlane(e0 - s0, dir);
        pole = pole.sqrMagnitude < 1e-8f ? Vector3.ProjectOnPlane(Vector3.down, dir).normalized : pole.normalized;
        Vector3 e1 = s0 + dir * along + pole * height;

        u.rotation = Quaternion.FromToRotation(e0 - s0, e1 - s0) * u.rotation;
        l.rotation = Quaternion.FromToRotation(h.position - l.position, (s0 + dir * d) - l.position) * l.rotation;

        Transform knuckle = animator.GetBoneTransform(knuckleBone);
        if (knuckle != null)
        {
            Vector3 handDir = knuckle.position - h.position;
            Vector3 flat = new Vector3(handDir.x, handDir.y * 0.1f, handDir.z);
            if (handDir.sqrMagnitude > 1e-6f && flat.sqrMagnitude > 1e-6f)
                h.rotation = Quaternion.FromToRotation(handDir, flat) * h.rotation;
        }
    }

    private void LiftArm(HumanBodyBones upper, HumanBodyBones lower, HumanBodyBones hand, HumanBodyBones[] fingers)
    {
        Transform u = animator.GetBoneTransform(upper), l = animator.GetBoneTransform(lower), h = animator.GetBoneTransform(hand);
        if (u == null || l == null || h == null) return;
        float need = Mathf.Max(BelowTable(h), FingerDeficit(fingers));
        if (DebugArms) Debug.Log($"[Arms] {hand}: wrist={h.position:F3} wristDeficit={BelowTable(h):F3} fingerDeficit={FingerDeficit(fingers):F3} need={need:F3}");
        if (need <= 0.002f) return;
        need = Mathf.Min(need, 0.22f);

        Vector3 s0 = u.position, e0 = l.position, w0 = h.position;
        float l1 = (e0 - s0).magnitude, l2 = (w0 - e0).magnitude;
        Vector3 target = w0 + Vector3.up * need;

        // wrist target at distance d from the shoulder; elbow on the circle that keeps the current bend direction
        Vector3 toTarget = target - s0;
        float d = Mathf.Clamp(toTarget.magnitude, 0.05f, l1 + l2 - 0.002f);
        Vector3 dir = toTarget.normalized;
        float along = (l1 * l1 - l2 * l2 + d * d) / (2f * d);
        float height = Mathf.Sqrt(Mathf.Max(0f, l1 * l1 - along * along));
        Vector3 pole = Vector3.ProjectOnPlane(e0 - s0, dir);
        pole = pole.sqrMagnitude < 1e-8f ? Vector3.ProjectOnPlane(Vector3.down, dir).normalized : pole.normalized;
        Vector3 e1 = s0 + dir * along + pole * height;

        u.rotation = Quaternion.FromToRotation(e0 - s0, e1 - s0) * u.rotation;
        Vector3 wAfter = h.position;                       // the wrist moved with the upper arm
        l.rotation = Quaternion.FromToRotation(wAfter - l.position, (s0 + dir * d) - l.position) * l.rotation;

        // lifting tilts the forearm up and the hand with it; lay the hand flat on the table again (palm down)
        Transform knuckle = animator.GetBoneTransform(hand == HumanBodyBones.LeftHand ? HumanBodyBones.LeftMiddleProximal : HumanBodyBones.RightMiddleProximal);
        if (knuckle != null)
        {
            Vector3 handDir = knuckle.position - h.position;
            Vector3 flat = new Vector3(handDir.x, Mathf.Min(0f, handDir.y * 0.2f), handDir.z);
            if (handDir.sqrMagnitude > 1e-6f && flat.sqrMagnitude > 1e-6f)
                h.rotation = Quaternion.FromToRotation(handDir, flat) * h.rotation;
        }
    }

    private float FingerDeficit(HumanBodyBones[] bones)
    {
        float worst = 0f;
        foreach (var bone in bones)
        {
            var t = animator.GetBoneTransform(bone);
            if (t == null) continue;
            Vector3 p = t.position;
            if (Mathf.Abs(p.x) > tableHalfExtent.x || Mathf.Abs(p.z) > tableHalfExtent.y) continue;
            // finger joints are skin-deep centre points: leave a bit more than the joint radius above the surface
            worst = Mathf.Max(worst, tableTopHeight + fingerClearance - p.y);
        }
        return worst;
    }

    private float BelowTable(Transform t)
    {
        if (t == null) return 0f;
        Vector3 p = t.position;
        if (Mathf.Abs(p.x) > tableHalfExtent.x || Mathf.Abs(p.z) > tableHalfExtent.y) return 0f;
        return Mathf.Max(0f, tableTopHeight + tableClearance - p.y);
    }

    private float Noise(float freq, float offset) => Mathf.PerlinNoise(seed + offset, time * freq) * 2f - 1f;

    private static void Add(float[] arr, string muscle, float v)
    {
        if (s_muscleNames == null) s_muscleNames = HumanTrait.MuscleName;
        int i = System.Array.IndexOf(s_muscleNames, muscle);
        if (i >= 0) arr[i] = Mathf.Clamp(arr[i] + v, -1f, 1f);
    }

    // --- editor support ---------------------------------------------------------------------------------------

    public void SetSeatedPose(string[] names, float[] values)
    {
        seatedMuscleNames = names;
        seatedMuscleValues = values;
    }

    public Animator Animator { get => animator; set => animator = value; }
}
