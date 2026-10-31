using System;
using System.Collections.Generic;
using System.Text;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

/// The job-coach screen: a summary page, then one page per question with what went well, what to improve and a
/// sentence structure to try. Prev / Next / Close buttons; Close returns to the title screen.
public class CoachPanel : MonoBehaviour
{
    [SerializeField] private TMP_Text heading;
    [SerializeField] private TMP_Text body;
    [SerializeField] private TMP_Text pageLabel;
    [SerializeField] private Button prevButton;
    [SerializeField] private Button nextButton;
    [SerializeField] private Button closeButton;

    public event Action OnClosed;

    private readonly List<string> titles = new List<string>();
    private readonly List<string> pages = new List<string>();
    private int page;

    private void Awake()
    {
        if (prevButton != null) prevButton.onClick.AddListener(() => Go(-1));
        if (nextButton != null) nextButton.onClick.AddListener(() => Go(1));
        if (closeButton != null) closeButton.onClick.AddListener(() => { gameObject.SetActive(false); OnClosed?.Invoke(); });
    }

    private bool waiting;
    private string waitText;

    public void ShowProgress(int done, int total)
    {
        gameObject.SetActive(true);
        titles.Clear(); pages.Clear();
        SetNav(false);
        if (heading != null) heading.text = "Job Coach";
        waitText = total > 0
            ? "Your job coach is reading your answers{0}\n\nReviewed " + done + " of " + total + "."
            : "Your job coach is reading your answers{0}";
        waiting = true;
        UpdateWaitText();
        if (pageLabel != null) pageLabel.text = "";
    }

    // moving dots so the wait (up to ~20 s) never looks frozen
    private void UpdateWaitText()
    {
        if (!waiting || body == null) return;
        body.text = string.Format(waitText, new string('.', 1 + (int)(Time.unscaledTime * 2f) % 3));
    }

    private void Update() { if (waiting) UpdateWaitText(); }

    public void ShowMessage(string message)
    {
        waiting = false;
        gameObject.SetActive(true);
        titles.Clear(); pages.Clear();
        SetNav(false);
        if (heading != null) heading.text = "Job Coach";
        if (body != null) body.text = message;
        if (pageLabel != null) pageLabel.text = "";
    }

    public void Show(CoachReport report)
    {
        waiting = false;
        gameObject.SetActive(true);
        titles.Clear(); pages.Clear();
        if (report == null || !string.IsNullOrEmpty(report.error) || report.items == null || report.items.Length == 0)
        {
            ShowMessage(report != null && !string.IsNullOrEmpty(report.error) ? report.error : "The coach has nothing to review yet.");
            return;
        }

        var sb = new StringBuilder();
        sb.Append(report.summary).Append("\n\n");
        sb.Append("<b>Average score:</b> ").Append(report.average_score.ToString("0.0")).Append(" / 5");
        if (!string.IsNullOrEmpty(report.attitude)) sb.Append("\n\n<b>Attitude:</b> ").Append(report.attitude);
        if (report.left_early) sb.Append("\n\n<i>You ended the interview early; the last answer wasn't scored.</i>");
        titles.Add("Job Coach: summary");
        pages.Add(sb.ToString());

        sb.Clear();
        if (report.strengths != null && report.strengths.Length > 0)
        {
            sb.Append("<b>Strengths</b>\n");
            foreach (var s in report.strengths) sb.Append("- ").Append(s).Append('\n');
            sb.Append('\n');
        }
        if (report.focus != null && report.focus.Length > 0)
        {
            sb.Append("<b>Work on next</b>\n");
            foreach (var s in report.focus) sb.Append("- ").Append(s).Append('\n');
        }
        if (sb.Length > 0) { titles.Add("Job Coach: strengths and next steps"); pages.Add(sb.ToString()); }

        foreach (var item in report.items)
        {
            // two pages per question so longer coach texts never spill out of the box
            string head = $"Question {item.number} of {report.items.Length}   |   Score {item.score} / 5";
            var q = new StringBuilder();
            q.Append("<b>Question:</b> ").Append(item.question).Append("\n\n");
            q.Append("<b>You said:</b> ").Append(Trim(item.answer, 150));
            if (!string.IsNullOrEmpty(item.quote)) q.Append("\n\n<b>Key phrase:</b> \"").Append(Trim(item.quote, 120)).Append('"');
            if (!string.IsNullOrEmpty(item.tone)) q.Append("\n\n<b>Tone:</b> ").Append(item.tone);
            if (!string.IsNullOrEmpty(item.went_well)) q.Append("\n\n<b>Went well:</b> ").Append(item.went_well);
            titles.Add(head + "   |   1/2");
            pages.Add(q.ToString());

            var r = new StringBuilder();
            if (!string.IsNullOrEmpty(item.improve)) r.Append("<b>To improve:</b> ").Append(item.improve);
            if (!string.IsNullOrEmpty(item.stronger)) { if (r.Length > 0) r.Append("\n\n"); r.Append("<b>Try saying:</b> ").Append(item.stronger); }
            if (r.Length == 0) r.Append("No further suggestions for this answer.");
            titles.Add(head + "   |   2/2");
            pages.Add(r.ToString());
        }
        page = 0;
        SetNav(true);
        Render(report.filename);
        lastFile = report.filename;
    }

    private string lastFile;

    private void Go(int delta)
    {
        if (pages.Count == 0) return;
        page = Mathf.Clamp(page + delta, 0, pages.Count - 1);
        Render(lastFile);
    }

    private void Render(string file)
    {
        if (heading != null) heading.text = titles[page];
        if (body != null) body.text = pages[page];
        if (pageLabel != null) pageLabel.text = $"Page {page + 1} of {pages.Count}" + (string.IsNullOrEmpty(file) ? "" : "   |   saved on the server as " + file);
        if (prevButton != null) prevButton.interactable = page > 0;
        if (nextButton != null) nextButton.interactable = page < pages.Count - 1;
    }

    private void SetNav(bool on)
    {
        if (prevButton != null) prevButton.gameObject.SetActive(on);
        if (nextButton != null) nextButton.gameObject.SetActive(on);
    }

    private static string Trim(string s, int max)
    {
        if (string.IsNullOrEmpty(s)) return "";
        return s.Length <= max ? s : s.Substring(0, max).TrimEnd() + "...";
    }
}
