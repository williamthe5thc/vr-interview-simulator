using System;

/// Shapes of the job-coach report the server sends (type "coach_report"); JsonUtility needs plain serializable classes.
[Serializable]
public class CoachItem
{
    public int number;
    public string question;
    public string answer;
    public string went_well;
    public string improve;
    public string stronger;   // "Try saying": a sentence structure with [blanks]
    public int score;
    public string quote;      // coach v2: the phrase from the answer the feedback refers to (may be missing)
    public string tone;       // coach v2: how the answer sounded (may be missing)
}

[Serializable]
public class CoachReport
{
    public string error;
    public string job_label;
    public string company;
    public string summary;
    public bool left_early;   // coach v2: the candidate ended the interview and the last answer was not scored
    public string attitude;   // coach v2: overall attitude comment (may be missing)
    public string filename;
    public float average_score;
    public string[] strengths;
    public string[] focus;
    public CoachItem[] items;
}
