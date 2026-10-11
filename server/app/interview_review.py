"""Interview export and job-coach review.

- build_exchanges(): pairs every interviewer question with the candidate's answer from a Session history.
- export_interview(): writes the whole interview (and the coach feedback, when there is some) to exports/ as Markdown + JSON,
  so it can be sent to a job coach or anyone else for review.
- generate_coach_report(): asks the local LLM for feedback on each answer plus an overall summary.
"""
import json
import logging
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

logger = logging.getLogger("interview_review")

EXPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exports")


def build_exchanges(history):
    """history: [{user_input, system_response, timestamp}]. The first user_input is the canned "Hello." that starts the
    interview, so question i is history[i].system_response and its answer is history[i + 1].user_input. The last
    system_response is the closing remark and has no answer."""
    exchanges = []
    for i in range(len(history) - 1):
        question = (history[i].get("system_response") or "").strip()
        answer = (history[i + 1].get("user_input") or "").strip()
        if question and answer:
            exchanges.append({"number": len(exchanges) + 1, "question": question, "answer": answer})
    return exchanges


def _safe(text):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", text or "")[:40]


def export_interview(record, coach_report=None):
    """record: {session_id, job_id, job_label, company, interviewer, started, exchanges, closing}. Returns the base path."""
    os.makedirs(EXPORT_DIR, exist_ok=True)
    stamp = record.get("saved_at") or datetime.now().strftime("%Y-%m-%d_%H-%M")
    record["saved_at"] = stamp
    base = os.path.join(EXPORT_DIR, f"{stamp}_{_safe(record.get('job_id'))}_{_safe(record.get('session_id'))[:8]}")

    data = dict(record)
    if coach_report:
        data["coach_report"] = coach_report
    with open(base + ".json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    lines = [
        f"# Mock interview: {record.get('job_label', '')} at {record.get('company', '')}",
        "",
        f"- Date: {stamp.replace('_', ' ')}",
        f"- Interviewer: {record.get('interviewer', '')}",
        f"- Questions answered: {len(record.get('exchanges', []))}",
        "",
        "## Transcript",
        "",
    ]
    coach_items = {it.get("number"): it for it in (coach_report or {}).get("items", [])}
    for ex in record.get("exchanges", []):
        lines += [f"### Question {ex['number']}", f"**Interviewer:** {ex['question']}", "", f"**Candidate:** {ex['answer']}", ""]
        item = coach_items.get(ex["number"])
        if item:
            lines += [f"*Coach ({item.get('score', '?')}/5)*", ""]
            if item.get("quote"):
                lines.append(f"- About: \"{item['quote']}\"")
            for label, key in (("Went well", "went_well"), ("To improve", "improve"), ("How it came across", "tone"), ("Try saying", "stronger")):
                if item.get(key):
                    lines.append(f"- {label}: {item[key]}")
            lines.append("")
    if record.get("closing"):
        lines += ["**Interviewer (closing):** " + record["closing"], ""]
    if coach_report:
        lines += ["## Coach summary", "", coach_report.get("summary", ""), ""]
        if coach_report.get("attitude"):
            lines += [f"Attitude: {coach_report['attitude']}", ""]
        if coach_report.get("strengths"):
            lines += ["Strengths:"] + [f"- {s}" for s in coach_report["strengths"]] + [""]
        if coach_report.get("focus"):
            lines += ["Focus for next time:"] + [f"- {s}" for s in coach_report["focus"]] + [""]
    with open(base + ".md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    logger.info(f"Interview exported to {base}.md")
    return base


_SECTION = re.compile(r"(?:^|(?<=\s))(WENT WELL|IMPROVE|TRY SAYING|SCORE|OVERALL|STRENGTHS|FOCUS NEXT)\s*:\s*", re.I)


def _parse_sections(text):
    """Split 'LABEL: value' blocks into a dict (labels upper-cased)."""
    out = {}
    matches = list(_SECTION.finditer(text or ""))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out[m.group(1).upper()] = text[m.end():end].strip()
    return out


def _bullets(text):
    items = [re.sub(r"^[\-\*•\d\.\)\s]+", "", ln).strip() for ln in (text or "").splitlines()]
    return [x for x in items if x]


def generate_coach_report(llm_client, record, job_info=None, progress=None):
    """Blocking (call it from a thread). Uses the redesigned coach (app/coach_v2.py) when config/coach_mode.txt says so, and the
    original coach otherwise or when the new one fails."""
    from app import coach_v2
    mode = coach_v2.coach_mode(llm_client)
    if mode != "legacy":
        try:
            return coach_v2.generate(llm_client, record, job_info, progress, sonnet=(mode == "v2-sonnet"))
        except Exception as e:
            logger.warning(f"Coach v2 failed ({type(e).__name__}: {str(e)[:160]}); using the original coach")
    return generate_coach_report_legacy(llm_client, record, job_info, progress)


def generate_coach_report_legacy(llm_client, record, job_info=None, progress=None):
    """The original coach: one call per answer plus a summary call. job_info: the question bank entry (good_answer_tips, red_flags)."""
    job_label, company = record.get("job_label", "this role"), record.get("company", "the company")
    tips = "; ".join((job_info or {}).get("good_answer_tips", [])) or "specific examples, clear outcomes, and honest reflection"
    flags = "; ".join((job_info or {}).get("red_flags", [])) or "vague answers, no concrete example, blaming others"

    coach_system = (
        f"You are a warm, honest job coach reviewing a practice interview for a {job_label} role at {company}. "
        "Be specific and brief. Speak directly to the candidate as 'you' and never use anyone's name. Plain text only, no markdown. "
        f"What strong answers contain for this job: {tips}. What interviewers treat as weak: {flags}. "
        "The answers come from speech recognition, so ignore small transcription mistakes. "
        "Never invent facts, tools, methods, programs, numbers or employers that the candidate did not state. "
        "TRY SAYING is a short sentence STRUCTURE for a stronger answer on this topic, with the missing details left as blanks in "
        "square brackets, for example: 'In my role at [place], I [what you did], which led to [the result].' Never fill the blanks yourself.\n"
        "Score honestly with this guide: 5 = a specific example with the situation, what YOU did and a clear result; 4 = relevant and "
        "clear but missing one of those; 3 = relevant but general, or rambling; 2 = vague, beside the point, or too long to follow; "
        "1 = not an answer (a joke, a refusal, nonsense). A long answer that never reaches a result is a 2 or 3, not a 4. "
        "If the answer does not respond to the question that was asked, say so politely in IMPROVE. Judge only what was said.\n"
        "Reply in exactly this format:\n"
        "WENT WELL: <one sentence that refers to something specific they said>\n"
        "IMPROVE: <one or two sentences of concrete advice>\n"
        "TRY SAYING: <one or two sentences: a structure with [blanks] they can fill in, using their own topic>\n"
        "SCORE: <a whole number from 1 to 5>"
    )
    # A final "I'm done, let's wrap up" is the candidate leaving, not an answer to be scored.
    wants_to_end = getattr(llm_client, "wants_to_end", lambda text: False)
    exchanges = [ex for ex in record.get("exchanges", []) if not wants_to_end(ex["answer"])]
    total = len(exchanges)
    done = [0]
    lock = threading.Lock()

    def coach_one(ex):
        words = len(ex["answer"].split())
        user = (f"Interviewer question: {ex['question']}\n\nCandidate's answer ({words} words): {ex['answer'][:1500]}")
        try:
            raw = llm_client.coach_completion(coach_system, user, max_tokens=230)
        except Exception as e:
            logger.warning(f"Coach call failed for question {ex['number']}: {e}")
            raw = ""
        sec = _parse_sections(raw)
        try:
            score = int(re.search(r"[1-5]", sec.get("SCORE", "")).group(0))
        except Exception:
            score = 3
        with lock:
            done[0] += 1
            if progress:
                try:
                    progress(done[0], total)
                except Exception:
                    pass
        return {
            "number": ex["number"], "question": ex["question"], "answer": ex["answer"],
            "went_well": sec.get("WENT WELL") or "You answered the question.",
            "improve": sec.get("IMPROVE") or "Add a concrete example with a clear outcome.",
            "stronger": sec.get("TRY SAYING") or "",
            "score": score,
        }

    workers = max(1, int(getattr(llm_client, "config", {}).get("coach_workers", 3)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        items = list(pool.map(coach_one, exchanges))   # keeps the question order

    average = round(sum(i["score"] for i in items) / len(items), 1) if items else 0
    recap = "\n".join(f"Q{i['number']} ({i['score']}/5): {i['question']} | Answer: {i['answer'][:220]}" for i in items)
    summary_system = (
        f"You are a warm, honest job coach who just reviewed a practice interview for a {job_label} role. "
        "Speak directly to the candidate as 'you' and never use anyone's name. Plain text only, no markdown. Reply in exactly this format:\n"
        "OVERALL: <three sentences: how the interview went and the single most important thing to work on>\n"
        "STRENGTHS: <two short lines, one per line>\n"
        "FOCUS NEXT: <two short, actionable lines, one per line>"
    )
    try:
        raw = llm_client.coach_completion(summary_system, recap, max_tokens=260)
    except Exception as e:
        logger.warning(f"Coach summary failed: {e}")
        raw = ""
    sec = _parse_sections(raw)
    return {
        "job_label": job_label, "company": company, "average_score": average,
        "summary": sec.get("OVERALL") or f"You answered {len(items)} questions with an average coach score of {average} out of 5.",
        "strengths": _bullets(sec.get("STRENGTHS"))[:3],
        "focus": _bullets(sec.get("FOCUS NEXT"))[:3],
        "items": items,
    }
