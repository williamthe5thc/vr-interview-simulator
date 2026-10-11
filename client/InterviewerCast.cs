using System;
using UnityEngine;

/// The interviewers the candidate can meet. Each is a fully set-up character (seat, face, gaze, lip-sync); only one is
/// active at a time. Every new or restarted interview moves on to the next one, so a run of practice interviews
/// rotates through different people. The name and voice are sent to the server so the voice matches the character.
public static class InterviewerRoster
{
    public readonly struct Entry
    {
        public readonly string Model, Name, Voice;
        public Entry(string model, string name, string voice) { Model = model; Name = name; Voice = voice; }
    }

    // Model folder names under Assets/Rocketbox (Microsoft Rocketbox, MIT licence) with a first name and an AllTalk voice file.
    public static readonly Entry[] All =
    {
        new Entry("Business_Female_01", "Dana Whitfield", "female_06.wav"),
        new Entry("Business_Female_02", "Margaret Ellis", "female_03.wav"),
        new Entry("Business_Female_03", "Linda Foster", "female_01.wav"),
        new Entry("Business_Female_04", "Rachel Grant", "female_05.wav"),
        new Entry("Business_Male_01", "Daniel Hayes", "male_01.wav"),
        new Entry("Business_Male_02", "Marcus Reed", "male_02.wav"),
        new Entry("Business_Male_03", "Eric Carter", "male_03.wav"),
        new Entry("Business_Male_04", "Victor Brooks", "male_04.wav"),
        new Entry("Business_Male_05", "Samuel Hughes", "male_05.wav"),
        new Entry("Business_Male_06", "Thomas Irwin", "male_02.wav"),
        new Entry("Business_Male_07", "Gregory Jensen", "male_01.wav"),
    };
}

public class InterviewerCast : MonoBehaviour
{
    [Serializable]
    public class Member
    {
        public string displayName;
        public string voice;
        public AvatarController controller;
        public Transform head;
    }

    [SerializeField] private Member[] members = new Member[0];
    [SerializeField] private AudioSource voiceSource;

    private int index = -1;

    public Member[] Members => members;
    public int Count => members != null ? members.Length : 0;
    public Member Current => index >= 0 && index < Count ? members[index] : null;
    public AudioSource VoiceSource => voiceSource;

    /// Start the next interview with the next character (the first time: a random one).
    public Member SelectNext()
    {
        if (Count == 0) return null;
        // Crash hunt: step through the characters in a fixed order and remember where we are across app restarts. The next index is
        // saved BEFORE activating, so after a crash the next launch tries the following character. adb log: "[Cast] activating ..."
        int next = PlayerPrefs.GetInt("castNext", 0) % Count;
        PlayerPrefs.SetInt("castNext", (next + 1) % Count);
        PlayerPrefs.Save();
        index = next;
        Debug.Log($"[Cast] activating {index} of {Count}: {members[index].displayName}");
        Activate(index);
        Invoke(nameof(LogSurvived), 5f);
        return members[index];
    }

    private void LogSurvived() => Debug.Log($"[Cast] survived 5 s with character {index}");

    private void Activate(int active)
    {
        for (int i = 0; i < members.Length; i++)
            if (members[i].controller != null) members[i].controller.gameObject.SetActive(i == active);

        var m = members[active];
        if (voiceSource != null && m.head != null)
        {
            // the voice comes out of this character's mouth
            voiceSource.transform.SetParent(m.head, false);
            var t = m.controller.transform;
            voiceSource.transform.position = m.head.position + t.forward * 0.09f + Vector3.up * 0.04f;
        }
        var audio = FindObjectOfType<AudioManager>();
        if (audio != null) audio.SetAvatar(m.controller);
        var session = FindObjectOfType<SessionManager>();
        if (session != null) session.SetAvatar(m.controller);
    }
}
