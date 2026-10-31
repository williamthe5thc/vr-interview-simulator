"""
Replay real interviews (exports\\*.json) through the interviewer with the hosted model, to compare designs. Uses the candidate's real
answers; costs real (small) money through the Anthropic API.

    .venv\\Scripts\\python.exe tools\\naturalness_replay.py EXPORT.json [EXPORT2.json ...] [--mode judgement|scripted] [--forced] [--out FILE.md]

  default (free run): the candidate's answers are fed in order and the interviewer writes its own questions, so the whole arc
                      (opening, transitions, questions, close) comes from the design under test. Some answers will not fit the
                      new questions exactly; that is a limit of replaying a fixed script of answers.
  --forced:           teacher forcing: every turn sees the ORIGINAL interview so far and writes only the next reply.
"""
import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.chdir(ROOT)
import logging  # noqa: E402

logging.disable(logging.CRITICAL)
import model_compare as mc  # noqa: E402
from services.llm import anthropic_backend  # noqa: E402


def reply(client, text, history):
    """One interviewer reply, as the live server would speak it (chunks joined)."""
    t0 = time.time()
    parts = list(client.stream_response(text, history, None))
    return " ".join(p.strip() for p in parts if p and p.strip()), time.time() - t0


def run(path, mode, forced, out, client_cache):
    d = json.load(open(path, encoding="utf-8"))
    c = mc.make_client("qwen2.5:7b-instruct")
    c.config["interviewer_mode_override"] = mode
    c.set_job(d["job_id"])
    c.interviewer_name = d["interviewer"]
    ex = d["exchanges"]
    before = c._anth.spent
    out.append(f"## {d['job_label']} with {d['interviewer']} ({mode}, {'teacher-forced' if forced else 'free run'})\n")
    history = []
    opening, secs = reply(c, "Hello.", [])
    if forced:
        out.append(f"**Interviewer (opening, new):** {opening}\n\n*(original opening: {ex[0]['question']})*\n")
        history = [{"role": "user", "content": "Hello."}, {"role": "assistant", "content": ex[0]["question"]}]
    else:
        out.append(f"**Interviewer:** {opening}\n")
        history = [{"role": "user", "content": "Hello."}, {"role": "assistant", "content": opening}]
    for i, e in enumerate(ex):
        out.append(f"**Candidate:** {e['answer']}\n")
        text, secs = reply(c, e["answer"], history)
        if forced:
            nxt = ex[i + 1]["question"] if i + 1 < len(ex) else d.get("closing", "")
            out.append(f"**Interviewer (new):** {text}\n\n*(original: {nxt})*\n")
            history = history + [{"role": "user", "content": e["answer"]}, {"role": "assistant", "content": nxt}]
        else:
            out.append(f"**Interviewer:** {text}\n")
            history = history + [{"role": "user", "content": e["answer"]}, {"role": "assistant", "content": text}]
    cost = c._anth.spent - before
    out.append(f"*API cost for this interview about ${cost:.4f} (estimate at $0.20/$1.00 per 1M tokens; list price is half), {c._anth.calls} calls*\n")
    return cost


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("exports", nargs="+")
    ap.add_argument("--mode", default="judgement")
    ap.add_argument("--forced", action="store_true")
    ap.add_argument("--out", default=os.path.join(ROOT, "model_compare", "naturalness_replay.md"))
    a = ap.parse_args()
    if not anthropic_backend.wanted():
        raise SystemExit('config\\llm_backend.txt must say "anthropic" for this replay')
    out, total = [], 0.0
    for p in a.exports:
        total += run(p, a.mode, a.forced, out, {})
        out.append("\n---\n")
    out.append(f"Total about ${total:.4f}\n")
    open(a.out, "w", encoding="utf-8").write("\n".join(out))
    print(f"written {a.out}; total about ${total:.4f}")


if __name__ == "__main__":
    main()
