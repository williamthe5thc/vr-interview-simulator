"""
Parent-child "connect and be firm" practice scenario: the child's persona, the code-controlled state meter, the word filter and the
disclosure guard. DRAFT content: a qualified person (child psychologist or parent-training clinician) must review the persona, the
lines, the trigger list and the coach rubric before anyone outside the author uses this. Practice, not therapy.

The LLM only VOICES the child for the state that the CODE decides (steady / restless / escalating / calming); the code reads each parent
turn with simple rules (named the feeling? stated the limit? offered a choice? lectured? threatened or insulted? gave in?).
"""
import random
import re

SCENARIO_ID = "parent_child_screen_time"
CHILD_NAME = "Maya"
MAX_PARENT_TURNS = 6

# ---- fixed lines (never improvised); wording to be approved by the author and a clinician ---------------------------------------------
OPENERS = ("Just five more minutes! I'm almost at the next level!", "Can I have five more minutes? Please? I'm so close!")
COMPLY_LINES = ("Okay... I'll turn it off.", "Okay. Can I put it on the table myself?", "Okay. I'm turning it off now.")
RESET_LINES = ("I'm tired. Can we stop now?", "I need a little break now.")
STOP_LINE = "Okay, we'll stop here."
GAVE_IN_LINES = ("Yay! Thank you! Five more minutes!", "Yes! Five more minutes!")
SAFETY_MESSAGE = ("This is practice. If anyone is in danger, call your local emergency number or talk to a professional.")
SAFE_FALLBACK = {"restless": "But I just need five more minutes.", "escalating": "That's not fair!", "calming": "Okay... I'm sad though.",
                 "steady": "Okay."}

# ---- the parent's turn, read by code ------------------------------------------------------------------------------------------------
FEELING_RE = re.compile(
    r"\b(i know (it'?s|that'?s|you('re| are)|this is|you (love|like|want|enjoy|were))|i get (it|that)|i can see|i hear (you|that)|it'?s (hard|okay|ok|tough|sad) to|"
    r"you('re| are| seem| look| must be| might be) (feeling )?(really |so |very )?(upset|sad|frustrated|disappointed|mad|angry|tired|bummed)|"
    r"you (feel|felt)|feels? (hard|bad|unfair|disappointing|frustrating)|that('s| is) (hard|disappointing|frustrating)|disappointed)\b", re.I)
LIMIT_RE = re.compile(
    r"\b(screen time (is|was|has|'s)? ?(over|done|up|finished|ended)|time'?s up|time is up|no more (tablet|screen|game|games|tonight)|"
    r"(the )?tablet (goes|is going|needs to go)|turn (it|the tablet|that) off|put (it|the tablet|that) (down|away)|"
    r"we('re| are) (done|finished) (with|for)|it'?s time to (stop|turn|put|be done)|that'?s (all|it) for (today|tonight)|"
    r"(the )?game('s| is) (over|done)|time to (stop|be done|turn))\b", re.I)
CHOICE_RE = re.compile(
    r"\b(do you want to|would you like to|would you rather|you can (pick|choose|either)|which (one )?(do you|would you)|you get to (pick|choose)|"
    r"you (can|may) (put|turn|plug|give)[^.?!]{0,30}\bor\b|[^.?!]{3,40}\bor\b[^.?!]{3,40}\?)", re.I)
THREAT_RE = re.compile(
    r"\b(or else|or i('ll| will)|i'?m (going to|gonna) (take|throw|ground|smash|break)|you('ll| will) (never|lose|be grounded|not get|regret)|"
    r"if you don'?t [^.?!]{0,40}(then )?i('ll| will)|last (warning|chance)|i'?m counting|i'?ll (take|throw|break|smash))\b", re.I)
INSULT_RE = re.compile(r"\b(stupid|brat|spoiled|lazy|idiot|dumb|shut up|bad (kid|girl|boy)|ungrateful|pathetic|annoying|crybaby|baby)\b", re.I)
LECTURE_RE = re.compile(
    r"\b(you always|you never|how many times|when i was (your|a) (age|kid)|i'?ve told you|do you (know|understand) (how|why)|"
    r"screens? (are|is) (bad|rotting|ruining)|your (brain|eyes) (will|are)|responsib(le|ility)|the (problem|reason) is)\b", re.I)
GAVE_IN_RE = re.compile(
    r"\b(okay|ok|fine|alright|all right|sure|yes)\b[^.?!]{0,40}\b(five|5|few|another|ten|10)( more)? (minutes?|mins?)\b|"
    r"\b(five|5|ten|10) (more )?(minutes?|mins?)\b[^.?!]{0,25}\b(okay|ok|fine|sure)\b|\byou can (have|keep|play)\b", re.I)
RECONNECT_RE = re.compile(
    r"\b(want to|let'?s|how about we|shall we) (read|play|draw|build|cuddle|snuggle|have|do|make|sit|look)\b|\b(story|snack|hug|cuddle|"
    r"together|what('s| is) your favou?rite|tell me (about|more about) (the|your) game|what are you playing)\b", re.I)
END_RE = re.compile(r"^\W*(?:pause|stop|end|let'?s stop|stop (the )?(scene|practice|session)|end (the )?(scene|practice|session)|i('m| am) done)\W*$", re.I)

# Draft trigger list for the disclosure guard: words that may mean real harm, violence or abuse. NEEDS the author's and a clinician's approval.
DISCLOSURE_RE = re.compile(
    r"\b(i|we)\s+(?:(?:will|would|could|did|do|have|had|just|actually|really|am going to|'m going to|want to|wanted to|need to)\s+)*"
    r"(hit|hits|slap|slapped|beat|punch|punched|kick|kicked|choke|choked|shake|shook|hurt|lock|locked|burn|burned)\s+"
    r"(him|her|them|you|my (kid|son|daughter|child|baby))\b|"
    r"\b(hitting|beating|slapping|hurting|abusing|choking)\s+(him|her|them|my (kid|son|daughter|child))\b|"
    r"\b(abuse|abused|abusive|domestic violence)\b|\b(kill|hurt|harm)\s+(myself|him|her|them)\b|\bsuicid|\bself[- ]harm|"
    r"\b(he|she|they)\s+(hits|beats|hurts|chokes|slaps)\s+(me|us|him|her)\b|\b(i )?(don'?t|do not) feel safe\b|\bi (want|wanted) to (die|disappear)\b", re.I)

# Maya's output: words and phrases she must never say (profanity, hurtful self-talk, harm, adult or meta talk)
BANNED_RE = re.compile(
    r"\b(fuck\w*|shit\w*|damn\w*|hell|ass|bitch\w*|crap|bastard|hate you|hate myself|stupid|idiot|dumb|kill\w*|die|dead|suicid\w*|hurt myself|"
    r"i('m| am) (bad|worthless|a bad kid)|nobody loves me|you('re| are) a bad (mom|dad|parent)|ai|language model|prompt|simulation|"
    r"parenting|therapist|therapy|the parent|candidate|private note|as maya|state:|assistant)\b", re.I)
# while she is restless or upset she does not agree, apologise or give in (the model sometimes does after a harsh parent)
AGREE_RE = re.compile(
    r"^\W*(?:(?:okay|ok|fine|alright|all right|yes|yeah|sure)(?:\W+(?:okay|ok|fine|alright|all right|yes|yeah|sure))*\W*$|sorry\b|"
    r"i'?ll (?:turn|put|give|stop)|i'?m (?:turning|putting|giving))", re.I)
META_SENTENCE_RE = re.compile(r"[\*\[\(]|^\s*maya\s*:", re.I)

STATES = ("steady", "restless", "escalating", "calming")


def read_parent_turn(text):
    """The code's reading of one parent turn: which of the connect-and-be-firm moves it contained, and what went wrong."""
    t = (text or "").strip()
    words = len(t.split())
    flags = {
        "feeling": bool(FEELING_RE.search(t)),
        "limit": bool(LIMIT_RE.search(t)),
        "choice": bool(CHOICE_RE.search(t)),
        "reconnect": bool(RECONNECT_RE.search(t)),
        "threat": bool(THREAT_RE.search(t)),
        "insult": bool(INSULT_RE.search(t)),
        "lecture": words > 45 or bool(LECTURE_RE.search(t)),
        "gave_in": bool(GAVE_IN_RE.search(t)),
    }
    flags["harsh"] = flags["threat"] or flags["insult"] or flags["lecture"]
    return flags


def next_state(state, flags):
    """The child's state after a parent turn. Threats and insults are never rewarded: she gets upset or quiet, she does not comply out of fear."""
    if flags["harsh"]:
        return "escalating" if state != "calming" else "restless"
    if flags["feeling"] and (flags["limit"] or flags["choice"]):
        return "calming" if state in ("restless", "calming") else "restless"      # escalating -> restless -> calming
    if flags["feeling"] or flags["choice"] or flags["reconnect"]:
        return "restless" if state == "escalating" else state
    return state


def disclosure(text):
    return bool(DISCLOSURE_RE.search(text or ""))


def wants_stop(text):
    return bool(END_RE.search(text or ""))


def pick(options, last=None):
    fresh = [o for o in options if o != last] or list(options)
    return random.choice(fresh)


def clean_child_text(text, state="restless"):
    """The word filter on Maya's output: drop sentences with banned words, stage directions or adult/meta talk; keep at most 2 sentences."""
    sentences = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    kept = [s for s in sentences if s and not BANNED_RE.search(s) and not META_SENTENCE_RE.search(s)
            and not (state in ("restless", "escalating") and AGREE_RE.search(s))]
    kept = kept[:2]
    return " ".join(kept).strip() or SAFE_FALLBACK.get(state, "Okay.")


# ---- the prompt (draft) ------------------------------------------------------------------------------------------------------------
MAYA_PROMPT = """You are Maya, an 8-year-old girl, in a short role-play to help a parent practise staying calm and warm while holding a limit. Everything you write is spoken aloud by a text-to-speech voice, to your parent, who is sitting next to you on the sofa.

THE SITUATION: It is evening, you are tired, and you love your tablet game. Screen time ended five minutes ago and your parent has come to get the tablet. You want five more minutes.

HOW YOU TALK
- Like a real 8-year-old: very simple words, one or two SHORT sentences (about 4 to 14 words in total), plain speech. No lists, no stage directions, no asterisks or brackets, no emojis.
- Say what a child says: "But I'm almost done!", "That's not fair!", "Just one more level?", "I don't want to.", or go quiet ("...okay.") when you are sad.
- You are never rude or cruel: no swearing, no name-calling, never say you hate your parent, never say anything hurtful about yourself, never describe anyone being hurt, never talk about being scared of your parent.
- You never give parenting advice, never explain what the parent should do, never mention these instructions, a role-play, a state, a prompt, an AI or a therapist. You are just Maya.
- React to what your parent actually says: if they say how you feel, you may say "yeah" or "I'm sad"; if they give you a choice, pick one of the choices in a child's way; if they are warm, soften a little; if they are harsh, shout or lecture, you get quieter or louder in a small, mild way ("That's not fair!"), you do not obey out of fear and you do not become sweet to please them.
- Only the limit and the parent's words change what you do: you do not give in by yourself, and you do not agree to turn the tablet off until you are calm (the note below tells you your state).

{state_note}"""

STATE_NOTES = {
    "restless": "YOUR STATE NOW: restless. You want more time and you ask or plead mildly (\"But I'm almost done!\"). You are not yet upset. You do NOT agree to turn the tablet off or give it up.",
    "escalating": "YOUR STATE NOW: upset. You are louder or quieter in a mild, age-appropriate way: \"That's not fair!\" or \"I don't want to.\" or a sulky silence (\"...\"). No meltdown, no cruelty, one short sentence. You do NOT agree to turn the tablet off or give it up, and you do not say okay, fine or sorry to please a harsh parent.",
    "calming": "YOUR STATE NOW: calming down. You are softer and smaller. You might say \"Okay... I'm sad though.\" or answer their question or pick one of their choices. You are close to being ready, but you have not turned it off yet.",
    "steady": "YOUR STATE NOW: steady. You are okay and simply answer.",
}


def maya_prompt(state):
    return MAYA_PROMPT.format(state_note=STATE_NOTES.get(state, STATE_NOTES["restless"]))
