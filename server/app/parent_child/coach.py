"""
"Connect and be firm" coach for the parent-child practice. Same shape as the interview coach v2 (one whole-conversation analysis call, then
short parallel rewrites in the parent's own voice) with a different rubric. DRAFT: the rubric wording and tone need review by a qualified
person before anyone outside the author uses it. Practice, not therapy: never labels the parent good or bad, never diagnoses the child.
"""
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("parent_child_coach")

RUBRIC = [
    ("calm", "Stayed calm", "tone and words stayed steady and kind even when Maya pushed back"),
    ("feeling", "Named the feeling", "said out loud what Maya might feel (for example \"you're sad the game is over\")"),
    ("limit", "Stated the limit once, briefly", "said the limit in a short, clear sentence, without repeating it again and again or explaining at length"),
    ("choice", "Offered a choice inside the limit", "gave Maya a small real choice (for example where to put the tablet, or what comes next)"),
    ("nolecture", "No lecture, no threat", "no long explanations, no \"you always/never\", no threats, no insults, no bargaining that gave the limit away"),
    ("reconnect", "Reconnected", "turned toward Maya warmly (an offer to do something together, curiosity about her game, a hug)"),
]

COACH_SYSTEM = """You are a warm, practical parent coach giving private feedback after a short PRACTICE conversation in which a parent spoke aloud to "Maya", an 8-year-old (played by a computer) who did not want to stop her tablet game. This is practice, not therapy. Speak directly to the parent as "you", never use anyone's name for them, and keep a warm, no-blame tone: never say or imply that they are a good or bad parent, never diagnose or label Maya, and never say there is a "right" way to feel. The parent's words come from speech recognition, so ignore small transcription mistakes. Plain spoken-style sentences inside the JSON strings.

THE SKILL BEING PRACTISED, "connect and be firm": stay calm; name the feeling; state the limit once, briefly; offer a small choice inside the limit; no lecture, no threat; reconnect warmly.

HOW TO JUDGE
- Judge ONLY what the parent said, and quote them. Never invent words they did not say.
- For each of the six skills give a rating: "yes" (clearly done), "partly", or "not yet", and one short, specific note that quotes or points to what they said. If they never had the chance, say so kindly.
- If Maya ended the conversation (the notes below say how it ended) say what happened in plain words: she calmed and turned it off; the six turns passed; they gave in; or they stopped.
- The "tone" of an answer says how it likely landed (calm, rushed, sharp, warm, tangled), kindly.
- Never praise just for talking. If nothing specific worked in a turn, "worked" is an empty string.
- "stronger" is NOT written by you here (a later step does it).

For EVERY parent turn give: "n" (the turn number), "score" (1 to 5: 5 = calm, warm and firm in the same turn; 3 = partly; 1 = harsh or gave the limit away), "quote" (3 to 12 words copied exactly, or ""), "worked", "fix" (the single most useful change, concrete, one or two sentences), "tone".
Overall: "summary" (three kind, honest sentences consistent with the ratings), "strengths" (up to 2, tied to something they actually said), "to_try_next" (the 2 or 3 most useful things to try next time, each a small action with a short example sentence in a parent's own words), "attitude" (one or two sentences on how the whole conversation felt: warm, hurried, tense), and "rubric": a list of exactly these six keys in this order, each {{"key": ..., "rating": "yes|partly|not yet", "note": "..."}}: calm, feeling, limit, choice, nolecture, reconnect.

Reply with ONE JSON object only:
{{"answers": [{{"n": 1, "score": 3, "quote": "...", "worked": "...", "fix": "...", "tone": "..."}}], "summary": "...", "strengths": ["..."], "to_try_next": ["..."], "attitude": "...", "rubric": [{{"key": "calm", "rating": "partly", "note": "..."}}]}}"""

REWRITE_SYSTEM = """You rewrite a parent's sentence(s) to a young child so that it connects and is firm, in the parent's OWN voice: first person, their vocabulary and warmth, spoken English, 1 to 3 short sentences. Use only what the parent said, organised better, plus at most two bracketed placeholders for things they should choose themselves, such as [a feeling you think she has] or [a choice you are happy with]. Add no new facts, names, threats, promises or consequences that they did not say. Reply with the rewritten words only."""

OUTCOMES = {"complied": "Maya calmed down and turned the tablet off.", "turns": "The six turns passed and the practice ended gently.",
            "gave_in": "The parent agreed to more time, so Maya kept the tablet.", "stopped": "The parent stopped the practice.",
            None: "The practice ended."}


def _json_object(text):
    start, end = (text or "").find("{"), (text or "").rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in the coach reply")
    return json.loads(text[start:end + 1])


def generate(llm_client, record, progress=None, sonnet=False):
    """record: {"exchanges": [{"number", "question" (Maya's line), "answer" (the parent's words)}], "ended": why, "turn_log": [...]}."""
    from services.llm import anthropic_backend
    model = anthropic_backend.SONNET if sonnet else None
    exchanges = record.get("exchanges", [])
    total = 1 + len(exchanges)
    if progress:
        try:
            progress(0, total)
        except Exception:
            pass
    lines = [f"How it ended: {OUTCOMES.get(record.get('ended'), OUTCOMES[None])}"]
    for ex in exchanges:
        lines.append(f"Maya (before turn {ex['number']}): {ex['question']}")
        lines.append(f"Parent, turn {ex['number']} ({len(ex['answer'].split())} words): {ex['answer'][:1200]}")
    trail = [f"turn {t['turn']}: {', '.join(t['flags']) or 'nothing notable'} -> Maya {t['state']}" for t in record.get("turn_log", [])]
    if trail:
        lines.append("A simple rule-based reading of each turn (a hint only, it can be wrong): " + "; ".join(trail))
    if record.get("closing"):
        lines.append(f"Maya's last line: {record['closing']}")
    raw = llm_client.coach_completion(COACH_SYSTEM, "\n".join(lines), max_tokens=2600, timeout=90.0, model=model)
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
        items.append({"number": ex["number"], "question": ex["question"], "answer": ex["answer"], "quote": (a.get("quote") or "").strip(),
                      "went_well": (a.get("worked") or "").strip(), "improve": (a.get("fix") or "").strip(), "tone": (a.get("tone") or "").strip(),
                      "stronger": "", "score": score_of(a)})
    todo = [it for it in items if it["score"] <= 4 and len(it["answer"].split()) >= 4]
    done = [1 + len(items) - len(todo)]
    lock = threading.Lock()
    if progress:
        try:
            progress(done[0], total)
        except Exception:
            pass

    def rewrite(it):
        user = f"What Maya said before: {it['question']}\n\nThe parent said: {it['answer'][:800]}\n\nWhat the coach says would help: {it['improve']}"
        try:
            it["stronger"] = llm_client.coach_completion(REWRITE_SYSTEM, user, max_tokens=200, timeout=60.0, model=model).strip()
        except Exception as e:
            logger.warning(f"Coach rewrite failed for turn {it['number']}: {e}")
        with lock:
            done[0] += 1
            if progress:
                try:
                    progress(done[0], total)
                except Exception:
                    pass

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(rewrite, todo))
    rubric = []
    given = {r.get("key"): r for r in data.get("rubric", []) if isinstance(r, dict)}
    for key, label, _ in RUBRIC:
        r = given.get(key, {})
        rating = r.get("rating") if r.get("rating") in ("yes", "partly", "not yet") else "not yet"
        rubric.append({"key": key, "label": label, "rating": rating, "note": (r.get("note") or "").strip()})
    average = round(sum(i["score"] for i in items) / len(items), 1) if items else 0
    return {
        "scenario": "parent_child_screen_time", "average_score": average, "coach": "pc-v2-sonnet" if sonnet else "pc-v2",
        "ended": record.get("ended"), "outcome": OUTCOMES.get(record.get("ended"), OUTCOMES[None]),
        "summary": (data.get("summary") or "").strip(), "strengths": [str(x).strip() for x in (data.get("strengths") or []) if str(x).strip()][:2],
        "focus": [str(x).strip() for x in (data.get("to_try_next") or []) if str(x).strip()][:3], "attitude": (data.get("attitude") or "").strip(),
        "rubric": rubric, "items": items,
    }
