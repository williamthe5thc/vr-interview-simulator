"""
Small output guards for the hosted-model ("judgement") interviewer. Kept in its own module so it can be reloaded at the start of every
interview without restarting the server (Ollama_client reloads it, and the judgement prompt, in `begin`).

- Third-person narration about the candidate ("The candidate hasn't told me anything yet...") or any mention of the private note must
  never be spoken: such sentences are dropped.
- Verdicts on an answer ("Good, that's helpful to know.", "Three years is a solid run.", "That makes sense.", "Thank you for being
  direct.") are dropped when the reply has another sentence to carry it (a question).
- The close always carries the next steps.
"""
import re

META_RE = re.compile(r"\b(?:the candidate|candidate's|private note|reply number|progress:|for my next reply|the interviewer(?:'s)? (?:note|prompt))\b", re.I)

VERDICT_RE = re.compile(
    r"^(?:(?:good|great|nice|excellent|perfect|wonderful|fine|fair enough|okay|alright|right)[,.!]\s*)?"
    r"(?:that'?s|that is|this is|it'?s)\s+(?:a\s+|an\s+|very\s+|really\s+|quite\s+|pretty\s+|truly\s+)*"
    r"(?:good|great|fair|helpful|useful|solid|nice|fine|valid|reasonable|sensible|interesting|wonderful|excellent|impressive)\b"
    r"|\bis (?:a|an) (?:solid|good|great|strong|impressive) (?:run|start|answer|example|way|foundation|background)\b"
    r"|^that makes (?:complete |perfect |total )?sense\b"
    r"|^(?:good|great|nice|excellent|perfect|wonderful)[,.!]\s*$"
    r"|^(?:thank you|thanks) for (?:being|walking|sharing|explaining|that|clarifying|your honesty|the)\b",
    re.I)

NEXT_STEPS_RE = re.compile(r"hear back|next steps|within (?:a|about a|the next) week|reviews? (?:all |the )?(?:other )?candidates|be in touch|get back to you", re.I)
NEXT_STEPS = "The team will review all candidates, and you'll hear back within about a week."
_FAREWELL_RE = re.compile(r"\b(?:goodbye|good bye|take care|best of luck|all the best|have a (?:good|great|nice))\b", re.I)


def is_meta(sentence):
    return bool(META_RE.search(sentence or ""))


def is_verdict(sentence):
    s = (sentence or "").strip()
    return (not s.endswith("?")) and bool(VERDICT_RE.search(s))


def drop_bad(sentences):
    """Sentences without the leaked narration; verdicts are dropped too unless the sentence is the last one. Never returns fewer than
    the meta-free sentences, and a lone verdict is kept (something has to be said)."""
    out = [s for s in sentences if not is_meta(s)]
    if len(out) >= 2:
        last = out[-1]
        out = [s for s in out[:-1] if not is_verdict(s)] + [last]
    return out


def ensure_next_steps(text):
    """The closing must say what happens next: insert the line before the farewell when the model left it out."""
    text = (text or "").strip()
    if not text or NEXT_STEPS_RE.search(text):
        return text
    sentences = re.split(r"(?<=[.!?])\s+", text)
    if len(sentences) > 1 and _FAREWELL_RE.search(sentences[-1]):
        return " ".join(sentences[:-1] + [NEXT_STEPS, sentences[-1]])
    return f"{text} {NEXT_STEPS}"
