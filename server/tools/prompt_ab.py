"""
Replay real candidate answers against the interviewer LLM (no server, no voice) and score how well it follows the rules.

    .venv\\Scripts\\python.exe tools\\prompt_ab.py --model qwen2.5:7b-instruct --layout tail --runs 2 --who "Marcus Reed"

Scenarios use the real answers saved in exports\\ (customer service and software engineer). Printed per run:
  followed    forced new topics where the reply really asks that bank question (word overlap >= 0.4)
  invited     the "do you have questions for me" turn happened
  stock       replies that open with a stock phrase the prompt bans ("That's ...", "That sounds ...", "impressive", "quite a")
  loops       consecutive questions that are near-identical
  first/total average seconds until the first sentence / the whole reply (streamed)
Transcripts go to the --out folder so they can be read.
"""
import argparse
import json
import os
import re
import statistics
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from services.llm.Ollama_client import OllamaClient  # noqa: E402

SCENARIOS = {
    "cs": ("customer_service", "exports/2026-10-04_18-46_customer_service_9fbd6a83.json"),
    "sw": ("software_engineer", "exports/2026-10-04_18-29_software_engineer_9fbd6a83.json"),
    "st": ("speech_therapist", "exports/2026-10-07_12-17_speech_therapist_1148167c.json"),
    "sw13": ("software_engineer", "exports/2026-10-07_13-32_software_engineer_ebd3e995.json"),
}
STOCK = re.compile(r"^(that'?s|that sounds|thank you for sharing)\b|impressive|\bquite an?\b", re.I)
INVITE = re.compile(r"questions? (for me|you (have|may have|might have))|anything (you'?d|you would) like to ask|do you have any", re.I)


def run_once(cfg, model, layout, who, scenario, think_off):
    job, path = SCENARIOS[scenario]
    answers = [e["answer"] for e in json.load(open(path, encoding="utf-8"))["exchanges"]]
    cfg = json.loads(json.dumps(cfg))
    cfg["prompt_layout"] = layout
    cfg["url"] = cfg["url"].replace("localhost", "127.0.0.1")
    client = OllamaClient(cfg["url"], model, cfg.get("context_length", 4096), config=cfg)
    client.set_job(job)
    client.interviewer_name = who
    ctx, rows = [], []
    for user in ["Hello."] + answers:
        t0, first, sentences = time.time(), None, []
        for s in client.stream_response(user, ctx):
            first = first if first is not None else time.time() - t0
            sentences.append(s)
        reply = " ".join(sentences)
        rows.append({"user": user, "reply": reply, "stage": client.last_stage, "topic": client.forced_question,
                     "first": first or 0.0, "total": time.time() - t0})
        ctx += [{"role": "user", "content": user}, {"role": "assistant", "content": reply}]
    return rows, client


def score(rows, client):
    words = client._content_words
    forced = [r for r in rows if r["topic"]]
    followed = sum(1 for r in forced if len(words(r["topic"]) & words(r["reply"])) / max(1, len(words(r["topic"]))) >= 0.4)
    invited = any(r["stage"] == "candidate_questions" and INVITE.search(r["reply"]) for r in rows)
    stock = sum(1 for r in rows[1:-1] if STOCK.search(r["reply"]))
    qs = [client._content_words(client._last_question_of(r["reply"])) for r in rows[:-1]]
    loops = sum(1 for a, b in zip(qs, qs[1:]) if a and b and len(a & b) / len(a | b) >= 0.5)
    mid = rows[1:-1] or rows
    return {"followed": f"{followed}/{len(forced)}", "invited": invited, "stock": f"{stock}/{len(rows) - 2}", "loops": loops,
            "first": statistics.mean(r["first"] for r in mid), "total": statistics.mean(r["total"] for r in mid)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=None)
    ap.add_argument("--layout", default="tail", choices=["single", "tail", "usertail"])
    ap.add_argument("--who", default="Marcus Reed")
    ap.add_argument("--scenario", default="cs", choices=list(SCENARIOS))
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--out", default=os.path.join(ROOT, "logs", "prompt_ab"))
    a = ap.parse_args()
    cfg = json.load(open("config/config.json", encoding="utf-8"))["ollama"]
    model = a.model or cfg["model"]
    os.makedirs(a.out, exist_ok=True)
    for i in range(a.runs):
        rows, client = run_once(cfg, model, a.layout, a.who, a.scenario, True)
        sc = score(rows, client)
        tag = f"{model.replace(':', '_')}_{a.layout}_{a.scenario}_{a.who.split()[0]}_{i + 1}"
        with open(os.path.join(a.out, tag + ".txt"), "w", encoding="utf-8") as f:
            for r in rows:
                f.write(f"[{r['stage']}{' | forced: ' + r['topic'] if r['topic'] else ''}]\nCANDIDATE: {r['user'][:200]}\nINTERVIEWER: {r['reply']}\n\n")
        print(f"{model:24s} {a.layout:8s} {a.scenario} {a.who.split()[0]:8s} run{i + 1}: " + "  ".join(f"{k}={v:.2f}" if isinstance(v, float) else f"{k}={v}" for k, v in sc.items()))


if __name__ == "__main__":
    main()
