"""
Run the coach on real interviews (exports/*.json) and write the reports side by side, with timing and the real token counts.
Costs real (small) money through the Anthropic API.

    .venv\Scripts\python.exe tools\coach_replay.py EXPORT.json [...] --coach legacy|v2|v2-sonnet [--out FILE.md]

legacy = the original coach on Claude Haiku 5.5 (this is what the headset ran on 2026-10-10), v2 = the redesigned coach on Haiku 5.5,
v2-sonnet = the redesigned coach on Claude Sonnet 5.5.
"""
import argparse
import json
import logging
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.chdir(ROOT)
logging.disable(logging.CRITICAL)
import model_compare as mc  # noqa: E402
from app import coach_v2, interview_review as rv  # noqa: E402
from services.llm import anthropic_backend  # noqa: E402
from services.llm.scenarios import job_interview  # noqa: E402


def run(path, coach):
    d = json.load(open(path, encoding="utf-8"))
    c = mc.make_client("qwen2.5:7b-instruct")
    job = job_interview.get_job_info(d["job_id"])
    calls_before, spent_before = c._anth.calls, c._anth.spent
    t0 = time.time()
    if coach == "legacy":
        report = rv.generate_coach_report_legacy(c, d, job)
    else:
        report = coach_v2.generate(c, d, job, sonnet=(coach == "v2-sonnet"))
    secs = time.time() - t0
    return d, report, secs, c._anth.calls - calls_before, c._anth.spent - spent_before


def render(d, report, secs, calls, spent, coach):
    out = [f"## {d['job_label']} with {d['interviewer']}: coach {coach} ({secs:.1f} s, {calls} calls, about ${spent:.4f})\n"]
    for it in report["items"]:
        out.append(f"**Q{it['number']}** {it['question']}\n\n**Answer:** {it['answer']}\n")
        out.append(f"*Score {it['score']}/5*")
        if it.get("quote"):
            out.append(f"- About: \"{it['quote']}\"")
        for label, key in (("Went well", "went_well"), ("To improve", "improve"), ("How it came across", "tone"), ("Try saying", "stronger")):
            if it.get(key):
                out.append(f"- {label}: {it[key]}")
        out.append("")
    out.append(f"**Summary (average {report['average_score']}):** {report['summary']}\n")
    if report.get("attitude"):
        out.append(f"**Attitude:** {report['attitude']}\n")
    if report.get("strengths"):
        out.append("**Strengths:** " + " | ".join(report["strengths"]) + "\n")
    if report.get("focus"):
        out.append("**Focus:**\n" + "\n".join(f"{i + 1}. {x}" for i, x in enumerate(report["focus"])) + "\n")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("exports", nargs="+")
    ap.add_argument("--coach", default="v2")
    ap.add_argument("--out", default=os.path.join(ROOT, "model_compare", "coach_replay.md"))
    a = ap.parse_args()
    if not anthropic_backend.wanted():
        raise SystemExit('config\\llm_backend.txt must say "anthropic"')
    text, total = [], 0.0
    for p in a.exports:
        d, report, secs, calls, spent = run(p, a.coach)
        total += spent
        text.append(render(d, report, secs, calls, spent, a.coach))
        text.append("\n---\n")
        print(f"{os.path.basename(p)}: {secs:.1f} s, {calls} calls, about ${spent:.4f}, average {report['average_score']}", flush=True)
    open(a.out, "w", encoding="utf-8").write("\n".join(text))
    print(f"written {a.out}; total about ${total:.4f}")


if __name__ == "__main__":
    main()
