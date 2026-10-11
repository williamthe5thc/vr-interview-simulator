"""
The redesigned job coach (v2). Needs the hosted model (Claude); app/interview_review.py falls back to the original coach otherwise.

One call reads the WHOLE interview and gives every score, an exact quote, what worked, the single fix, and how it came across, plus the
patterns across the interview (top fixes, attitude, summary). Short parallel calls then rewrite the weaker answers in the candidate's own
voice. Same report shape as the original coach (extra keys: quote, tone, attitude, coach, left_early), so the headset keeps working.

config/coach_mode.txt (written by scripts/switch_coach.ps1): legacy | v2 (Claude Haiku 5.5) | v2-sonnet (Claude Sonnet 5.5).
"""
import json
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("coach_v2")

COACH_MODE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "coach_mode.txt")


def coach_mode(llm_client):
    """legacy, v2 or v2-sonnet. The v2 modes need the hosted model; without it the original coach is used."""
    try:
        with open(COACH_MODE_FILE, encoding="utf-8") as f:
            mode = f.read().strip().lower()
    except OSError:
        mode = "legacy"
    if mode not in ("v2", "v2-sonnet"):
        return "legacy"
    anth = getattr(llm_client, "_anth", None)
    return mode if anth is not None and anth.active() else "legacy"


COACH_SYSTEM = """You are an experienced interview coach giving a candidate private, honest feedback after a practice interview for a {job_label} role at {company}. You see the whole transcript. The answers come from speech recognition, so ignore small transcription mistakes and filler words. Speak directly to the candidate as "you"; never use anyone's name, and refer to the interviewer as "the interviewer" (no he or she). Write plain spoken-style sentences inside the JSON strings (no markdown, no lists inside a string).

What strong answers contain for this job: {tips}.
What interviewers treat as weak: {flags}.

HOW TO JUDGE
- Judge ONLY what was said, and quote it. Never invent facts, tools, methods, numbers or employers the candidate did not state.
- Look at three things: content (did they answer the question that was actually asked? a specific situation, what THEY did, the result), delivery (length, rambling, hedging such as "it depends" and "I think", getting to the point), and attitude (energy, confidence, honesty, engagement). Say plainly and kindly when something came across as disengaged, evasive, dismissive, joking or off-topic; for example "I just don't do anything" tells the interviewer nothing.
- Score honestly, never to be nice: 5 = a specific example with the situation, what YOU did and a clear result; 4 = relevant and clear but missing one of those; 3 = relevant but general, or rambling; 2 = vague, beside the point, or too long to follow; 1 = not an answer (a joke, a refusal, nonsense). A long answer that never reaches a result is a 2 or 3. A short answer can still score well if it is specific.
- Your overall summary must match the scores: do not call the interview strong when most answers scored 2 or 3, and do not call it weak when most scored 4 or 5. If the interview ended early or the candidate said they were not interested or not a fit for the role, say so honestly and kindly.
- Never praise for greeting, stating their name, answering at all, or being brief. If nothing specific worked in an answer, "worked" is an empty string.
- Do not repeat the same advice for every answer: find the patterns across the whole interview and put them in "top_fixes".

For EVERY scored answer give:
- "n": the question number
- "score": 1 to 5
- "quote": 3 to 12 words copied exactly from their answer that your feedback is about ("" if the answer was too short)
- "worked": one specific thing that genuinely worked, citing what they said, or ""
- "fix": the single most useful change, concrete, one or two sentences, tied to what they said and what the interviewer actually asked
- "tone": a short note on how it came across (confidence, energy, hedging, rambling), or "" if unremarkable
Overall:
- "summary": three sentences, honest, consistent with the scores
- "strengths": up to 2 items, each tied to something they actually said (may be empty)
- "top_fixes": the 2 or 3 most important things to change across the whole interview, most important first, each one an action with a small example
- "attitude": one or two sentences on their overall tone and engagement

Reply with ONE JSON object only, no other text:
{{"answers": [{{"n": 1, "score": 3, "quote": "...", "worked": "...", "fix": "...", "tone": "..."}}], "summary": "...", "strengths": ["..."], "top_fixes": ["...", "..."], "attitude": "..."}}"""

REWRITE_SYSTEM = """You rewrite a candidate's interview answer so that it is stronger, in the candidate's OWN voice: first person, their vocabulary and level of formality, spoken English (not written), 2 to 4 sentences.

The rewrite may contain ONLY three kinds of content: (1) things the candidate actually said, kept close to their own words and put in a better order (situation, what they did, result); (2) bracketed placeholders for the facts they should add, such as [the method I used] or [what happened next], at most three; (3) plain connecting words. It must NOT contain any specific method, program, tool, name, number, example, quote, conversation, action or outcome that is not in the candidate's answer, even if the coach advice mentions one: that is advice for them, not something they said. If their answer has little in it, the rewrite is short and mostly placeholders. Where the question asked what they would do and they only said they would hand it to someone else, keep what they said and add a placeholder for their own first step. Reply with the rewritten answer only."""


def _json_object(text):
    text = text or ""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in the coach reply")
    return json.loads(text[start:end + 1])


def generate(llm_client, record, job_info=None, progress=None, sonnet=False):
    """Blocking (call it from a thread). Returns the coach report (same shape as the original coach, plus quote/tone/attitude)."""
    from services.llm import anthropic_backend
    model = anthropic_backend.SONNET if sonnet else None
    job_label, company = record.get("job_label", "this role"), record.get("company", "the company")
    tips = "; ".join((job_info or {}).get("good_answer_tips", [])) or "specific examples, clear outcomes, and honest reflection"
    flags = "; ".join((job_info or {}).get("red_flags", [])) or "vague answers, no concrete example, blaming others"
    wants_to_end = getattr(llm_client, "wants_to_end", lambda text: False)
    exchanges = [ex for ex in record.get("exchanges", []) if not wants_to_end(ex["answer"])]
    left_early = len(exchanges) < len(record.get("exchanges", []))

    lines = []
    for ex in record.get("exchanges", []):
        lines.append(f"Question {ex['number']} (interviewer): {ex['question']}")
        note = "  [the candidate asked to end the interview here; do not score this one]" if wants_to_end(ex["answer"]) else ""
        lines.append(f"Answer {ex['number']} (candidate, {len(ex['answer'].split())} words): {ex['answer'][:1500]}{note}")
    if record.get("closing"):
        lines.append(f"Closing (interviewer): {record['closing']}")
    system = COACH_SYSTEM.format(job_label=job_label, company=company, tips=tips, flags=flags)
    total = 1 + len(exchanges)          # the analysis call plus one step per scored answer (answers with no rewrite count as done at once)
    if progress:
        try:
            progress(0, total)          # at once: the analysis call below takes most of the wait
        except Exception:
            pass
    raw = llm_client.coach_completion(system, "\n".join(lines), max_tokens=2400, timeout=90.0, model=model)
    data = _json_object(raw)
    by_n = {}
    for a in data.get("answers", []):
        try:
            by_n[int(a.get("n"))] = a
        except (TypeError, ValueError):
            continue

    def score_of(a):
        try:
            return max(1, min(5, int(a.get("score"))))
        except (TypeError, ValueError):
            return 3

    items = []
    for ex in exchanges:
        a = by_n.get(ex["number"], {})
        items.append({
            "number": ex["number"], "question": ex["question"], "answer": ex["answer"],
            "quote": (a.get("quote") or "").strip(), "went_well": (a.get("worked") or "").strip(),
            "improve": (a.get("fix") or "").strip(), "tone": (a.get("tone") or "").strip(), "stronger": "", "score": score_of(a),
        })

    todo = [it for it in items if it["score"] <= 4 and len(it["answer"].split()) >= 8]
    done = [1 + len(items) - len(todo)]
    lock = threading.Lock()
    if progress:
        try:
            progress(done[0], total)
        except Exception:
            pass

    def rewrite(it):
        user = (f"Interviewer question: {it['question']}\n\nCandidate's answer: {it['answer'][:1500]}\n\n"
                f"What the coach says is missing: {it['improve']}")
        try:
            it["stronger"] = llm_client.coach_completion(REWRITE_SYSTEM, user, max_tokens=260, timeout=60.0, model=model).strip()
        except Exception as e:
            logger.warning(f"Coach rewrite failed for question {it['number']}: {e}")
        with lock:
            done[0] += 1
            if progress:
                try:
                    progress(done[0], total)
                except Exception:
                    pass

    workers = max(1, int(getattr(llm_client, "config", {}).get("coach_workers", 5)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(rewrite, todo))

    average = round(sum(i["score"] for i in items) / len(items), 1) if items else 0
    return {
        "job_label": job_label, "company": company, "average_score": average, "coach": "v2-sonnet" if sonnet else "v2",
        "left_early": left_early,
        "summary": (data.get("summary") or "").strip() or f"You answered {len(items)} questions with an average coach score of {average} out of 5.",
        "strengths": [str(x).strip() for x in (data.get("strengths") or []) if str(x).strip()][:2],
        "focus": [str(x).strip() for x in (data.get("top_fixes") or []) if str(x).strip()][:3],
        "attitude": (data.get("attitude") or "").strip(),
        "items": items,
    }
