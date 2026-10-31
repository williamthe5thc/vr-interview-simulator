using System.Collections.Generic;
using UnityEditor;
using UnityEngine;

/// <summary>
/// Editor-time solver that finds humanoid muscle values for a seated pose (thighs forward, shins down,
/// forearms resting on a table) for whichever humanoid avatar it is pointed at. The result is stored on the
/// InterviewerBody component so the runtime needs no per-rig knowledge.
/// </summary>
public static class InterviewerSeatSolver
{
    public class Result
    {
        public string[] names;
        public float[] values;
        public float hipsHeight;      // hips height above the avatar root in the neutral pose
        public string report;
    }

    static readonly string[] Muscles = HumanTrait.MuscleName;

    static int Idx(string n)
    {
        int i = System.Array.IndexOf(Muscles, n);
        if (i < 0) throw new System.Exception("Unknown muscle: " + n);
        return i;
    }

    class Frame
    {
        public Vector3 right, up = Vector3.up, fwd;
        public Vector3 ToLocal(Vector3 v) => new Vector3(Vector3.Dot(v, right), Vector3.Dot(v, up), Vector3.Dot(v, fwd));
    }

    /// tableTopRel: table surface height above the hips; edgeF: table edge distance in front of the hips.
    public static Result Solve(Animator anim, float tableTopRel, float edgeF, float handsPastEdge)
    {
        var handler = new HumanPoseHandler(anim.avatar, anim.transform);
        var basePose = new HumanPose();
        handler.GetHumanPose(ref basePose);

        Transform B(HumanBodyBones b) => anim.GetBoneTransform(b);
        var hips = B(HumanBodyBones.Hips);

        // Reset to the neutral (all-zero muscles) pose so the solve is deterministic.
        var pose = new HumanPose { bodyPosition = basePose.bodyPosition, bodyRotation = basePose.bodyRotation, muscles = new float[HumanTrait.MuscleCount] };
        handler.SetHumanPose(ref pose);

        Vector3 toesDir = (B(HumanBodyBones.LeftToes).position - B(HumanBodyBones.LeftFoot).position)
                        + (B(HumanBodyBones.RightToes).position - B(HumanBodyBones.RightFoot).position);
        toesDir.y = 0;
        var fr = new Frame { fwd = toesDir.normalized };
        fr.right = Vector3.Cross(Vector3.up, fr.fwd);

        Vector3 Rel(HumanBodyBones b) => fr.ToLocal(B(b).position - hips.position);
        float L1 = (Rel(HumanBodyBones.LeftLowerLeg) - Rel(HumanBodyBones.LeftUpperLeg)).magnitude;
        float L2 = (Rel(HumanBodyBones.LeftFoot) - Rel(HumanBodyBones.LeftLowerLeg)).magnitude;
        float Ua = (Rel(HumanBodyBones.LeftLowerArm) - Rel(HumanBodyBones.LeftUpperArm)).magnitude;
        float Fa = (Rel(HumanBodyBones.LeftHand) - Rel(HumanBodyBones.LeftLowerArm)).magnitude;
        Vector3 shoulderL = Rel(HumanBodyBones.LeftUpperArm);
        Vector3 hipL = Rel(HumanBodyBones.LeftUpperLeg);
        float sL = Mathf.Sign(hipL.x);   // which side of the hips the avatar's left limbs are on

        // Targets for the left chain (the right chain mirrors in x).
        Vector3 kneeT = hipL + L1 * new Vector3(sL * 0.06f, -0.05f, 1f).normalized;
        Vector3 ankleT = kneeT + L2 * new Vector3(0f, -1f, -0.06f).normalized;
        Vector3 elbowT = shoulderL + Ua * new Vector3(sL * 0.10f, -0.86f, 0.50f).normalized;
        Vector3 wristT = new Vector3(sL * 0.13f, tableTopRel + 0.04f, edgeF + handsPastEdge);

        string[] varNames =
        {
            "Upper Leg Front-Back", "Upper Leg In-Out", "Upper Leg Twist In-Out", "Lower Leg Stretch",
            "Arm Down-Up", "Arm Front-Back", "Arm Twist In-Out", "Forearm Stretch", "Forearm Twist In-Out"
        };
        int n = varNames.Length;
        int[] li = new int[n], ri = new int[n];
        for (int i = 0; i < n; i++) { li[i] = Idx("Left " + varNames[i]); ri[i] = Idx("Right " + varNames[i]); }

        float[] v = new float[n];
        float[] muscles = new float[HumanTrait.MuscleCount];

        float Eval(float[] x)
        {
            for (int i = 0; i < n; i++) { muscles[li[i]] = x[i]; muscles[ri[i]] = x[i]; }
            pose.muscles = muscles;
            handler.SetHumanPose(ref pose);
            float e = 0;
            for (int side = 0; side < 2; side++)
            {
                float m = side == 0 ? 1f : -1f;   // mirror targets for the right side
                Vector3 Mir(Vector3 t) => new Vector3(t.x * m, t.y, t.z);
                var kn = Rel(side == 0 ? HumanBodyBones.LeftLowerLeg : HumanBodyBones.RightLowerLeg);
                var an = Rel(side == 0 ? HumanBodyBones.LeftFoot : HumanBodyBones.RightFoot);
                var el = Rel(side == 0 ? HumanBodyBones.LeftLowerArm : HumanBodyBones.RightLowerArm);
                var wr = Rel(side == 0 ? HumanBodyBones.LeftHand : HumanBodyBones.RightHand);
                e += (kn - Mir(kneeT)).sqrMagnitude * 4f + (an - Mir(ankleT)).sqrMagnitude * 2f
                   + (el - Mir(elbowT)).sqrMagnitude * 1f + (wr - Mir(wristT)).sqrMagnitude * 3f;
            }
            return e;
        }

        // Coordinate descent with a shrinking step.
        float best = Eval(v);
        float step = 0.4f;
        for (int pass = 0; pass < 120 && step > 0.002f; pass++)
        {
            bool improved = false;
            for (int i = 0; i < n; i++)
            {
                foreach (float d in new[] { step, -step })
                {
                    float old = v[i];
                    v[i] = Mathf.Clamp(old + d, -1f, 1f);
                    float e = Eval(v);
                    if (e < best - 1e-9f) { best = e; improved = true; break; }
                    v[i] = old;
                }
            }
            if (!improved) step *= 0.6f;
        }
        Eval(v);

        var names = new List<string>(); var vals = new List<float>();
        for (int i = 0; i < n; i++)
        {
            names.Add("Left " + varNames[i]); vals.Add(v[i]);
            names.Add("Right " + varNames[i]); vals.Add(v[i]);
        }

        string P(string label, Vector3 got, Vector3 want) => $"  {label}: got {got.ToString("F3")} want {want.ToString("F3")} err {(got - want).magnitude:F3}\n";
        string rep = $"limb lengths thigh {L1:F2} shin {L2:F2} upperArm {Ua:F2} forearm {Fa:F2}  total error {best:F5}\n"
            + P("knee", Rel(HumanBodyBones.LeftLowerLeg), kneeT) + P("ankle", Rel(HumanBodyBones.LeftFoot), ankleT)
            + P("elbow", Rel(HumanBodyBones.LeftLowerArm), elbowT) + P("wrist", Rel(HumanBodyBones.LeftHand), wristT);
        for (int i = 0; i < n; i++) rep += $"  {varNames[i]} = {v[i]:F3}\n";

        return new Result { names = names.ToArray(), values = vals.ToArray(), hipsHeight = hips.position.y - anim.transform.position.y, report = rep };
    }
}
