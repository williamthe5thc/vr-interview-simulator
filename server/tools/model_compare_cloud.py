"""
Extra sources for the blind comparison: replies written OUTSIDE this PC's Ollama, run through the SAME production post-processing.

    export   .venv\\Scripts\\python.exe tools\\model_compare_cloud.py export
             -> model_compare\\export\\moments.json   (26 moments: the exact messages a model gets, plus the per-turn state)
             -> model_compare\\export\\coach.json     (the coach calls: system + user for each of the 9 answers)
    ingest   .venv\\Scripts\\python.exe tools\\model_compare_cloud.py ingest --model NAME --raw replies.json [--coach-raw coach.json]
             replies.json  = {"cs|1": "raw reply text", ...}   (only the moments with "needs_model": true are needed)
             coach.json    = {"coach|1": "WENT WELL: ...\\nIMPROVE: ...\\nTRY SAYING: ...\\nSCORE: 3", ...}
             -> cleaned like production output and stored as model_compare\\results\\NAME.json (a new blind letter on the next `page`)
    cloud    .venv\\Scripts\\python.exe tools\\model_compare_cloud.py cloud --models mistralai/Mistral-Nemo-Instruct-2407 ... [--coach] [--cap 0.60]
             DeepInfra (OpenAI-compatible, streaming). The key is read from the user environment variable DEEPINFRA_API_KEY; it is
             never printed, logged or written anywhere. Records time to first token, and stops when the estimated spend reaches --cap.
Then:  .venv\\Scripts\\python.exe tools\\model_compare.py page      (letters of earlier models stay, new models are appended)
"""
import argparse
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.chdir(ROOT)
import model_compare as mc  # noqa: E402

EXPORT = os.path.join(mc.OUT, "export")
# DeepInfra prices per 1M tokens (checked 2026-10-07, DeepInfra pricing page); used only for the spend estimate / cap
PRICES = {"mistral-nemo": (0.019, 0.03), "gemma-4-26b": (0.07, 0.34), "gemma-4-31b": (0.20, 0.40),
          "llama-3.3-70b": (0.10, 0.32), "gpt-oss-120b": (0.15, 0.60),
          "qwen3-235b-a22b-instruct": (0.09, 0.55), "deepseek-v3.2": (0.26, 0.38), "kimi-k2-instruct-0905": (0.40, 2.00),
          "mistral-small-3.2": (0.075, 0.20), "deepseek-v4-flash": (0.09, 0.18), "llama-4-maverick": (0.20, 0.80),
          "glm-5.3-flash": (0.15, 0.50), "qwen3.5-397b": (0.45, 3.00)}


def price_for(model_id):
    m = model_id.lower()
    for k, v in PRICES.items():
        if k in m:
            return v
    return (0.60, 3.00)   # unknown model: assume expensive so the cap protects us


def base_client(sc):
    client = mc.make_client("qwen2.5:7b-instruct")    # only used to build prompts and to post-process; no model is called
    client.set_job(sc["job"])
    client.interviewer_name = sc["who"]
    return client


def export():
    os.makedirs(EXPORT, exist_ok=True)
    moments = []
    for sc in mc.SCENARIOS:
        rec, turns = mc.load_scenario(sc)
        client = base_client(sc)
        history = [{"role": "user", "content": "Hello."}, {"role": "assistant", "content": turns[0]["question"]}]
        for t in turns:
            meta = {"forced_question": None, "forced_fixed_ack": None, "fixed_reply": None, "reply_prefix": None, "last_stage": None}
            repeated = client._repeat_request(t["answer"], history)
            if repeated:
                meta["fixed_reply"] = repeated
                msgs = []
            else:
                msgs = client._build_messages(t["answer"], history, None)
                meta.update({"forced_question": client.forced_question, "forced_fixed_ack": client.forced_fixed_ack,
                             "fixed_reply": client.fixed_reply, "reply_prefix": client.reply_prefix, "last_stage": client.last_stage})
            needs = not (meta["fixed_reply"] or (meta["forced_question"] and meta["forced_fixed_ack"]))   # fixed lines need no model
            moments.append({
                "id": f"{sc['id']}|{t['n']}", "scenario": sc["title"], "candidate_answer": t["answer"], "needs_model": needs,
                "max_tokens": 48 if meta["forced_question"] else 160, "temperature": 0.8,
                "how_to_answer": ("Reply with ONLY what the interviewer says out loud, as plain spoken text, following the system "
                                  "message and the private note at the end of the last user message. No preamble, no markdown."),
                "messages": msgs, "meta": meta})
            history = history + [{"role": "user", "content": t["answer"]}]
            if t["next"] and t is not turns[-1]:
                history.append({"role": "assistant", "content": t["next"]})
    json.dump(moments, open(os.path.join(EXPORT, "moments.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)

    # coach calls: run the real coach code against a stub that records what it would send
    from app import interview_review as rv
    from services.llm.scenarios import job_interview
    sc = mc.SCENARIOS[1]
    rec, _ = mc.load_scenario(sc)
    calls = []

    class Stub:
        config = {"coach_workers": 1}
        wants_to_end = staticmethod(mc.make_client("qwen2.5:7b-instruct").wants_to_end)

        def coach_completion(self, system, user, max_tokens=230, timeout=90.0):
            calls.append({"system": system, "user": user, "max_tokens": max_tokens})
            return ""
    rv.generate_coach_report(Stub(), rec, job_interview.get_job_info(sc["job"]))
    items = [{"id": f"coach|{i + 1}", **c} for i, c in enumerate(calls[:-1])]       # the last call is the overall summary (not rated)
    json.dump(items, open(os.path.join(EXPORT, "coach.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"{len(moments)} moments ({sum(m['needs_model'] for m in moments)} need a model reply), {len(items)} coach calls -> {EXPORT}")


def load_export():
    return (json.load(open(os.path.join(EXPORT, "moments.json"), encoding="utf-8")),
            json.load(open(os.path.join(EXPORT, "coach.json"), encoding="utf-8")))


def finalize(model, raw_replies, raw_coach=None, timings=None, info=None):
    """Raw replies -> production post-processing -> results\\<model>.json (same layout as the Ollama runs)."""
    moments, coach_calls = load_export()
    os.makedirs(mc.RES, exist_ok=True)
    clients = {}
    replies = {}
    for m in moments:
        sid = m["id"].split("|")[0]
        sc = next(s for s in mc.SCENARIOS if s["id"] == sid)
        client = clients.setdefault(sid, base_client(sc))
        meta = m["meta"]
        if not m["needs_model"]:
            text = meta["fixed_reply"] or client.finalize_raw("", meta)   # fixed acknowledgement + the code-chosen question
        elif m["id"] in raw_replies:
            text = client.finalize_raw(raw_replies[m["id"]], meta)
        else:
            continue
        tm = (timings or {}).get(m["id"], {})
        replies[m["id"]] = {"reply": text, "first": tm.get("first") or 0.0, "total": tm.get("total") or 0.0, "first_audio": None,
                            "timed": bool(tm), "ollama": {}}
    data = {"model": model, "tag": "", "replies": replies, "coach": None, "run_info": info or {"source": "outside Ollama"}}
    if raw_coach:
        from app import interview_review as rv
        from services.llm.scenarios import job_interview
        sc = mc.SCENARIOS[1]
        rec, _ = mc.load_scenario(sc)
        order = [c["id"] for c in coach_calls]

        class Replay:
            config = {"coach_workers": 1}
            wants_to_end = staticmethod(mc.make_client("qwen2.5:7b-instruct").wants_to_end)
            n = 0

            def coach_completion(self, system, user, max_tokens=230, timeout=90.0):
                i = Replay.n
                Replay.n += 1
                return raw_coach.get(order[i], "") if i < len(order) else ""
        rep = rv.generate_coach_report(Replay(), rec, job_interview.get_job_info(sc["job"]))
        data["coach"] = {"seconds": 0, "summary": "", "items": rep["items"]}
    path = os.path.join(mc.RES, model.replace(":", "_").replace("/", "_") + ".json")
    json.dump(data, open(path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"stored {len(replies)} replies" + (f" and {len(data['coach']['items'])} coach items" if data["coach"] else "") + f" for {model} -> {path}")


def ingest(a):
    raw = json.load(open(a.raw, encoding="utf-8"))
    coach = json.load(open(a.coach_raw, encoding="utf-8")) if a.coach_raw else None
    finalize(a.model, raw, coach)


# ---- DeepInfra ------------------------------------------------------------------------------------------------------

def api_key():
    key = os.environ.get("DEEPINFRA_API_KEY") or subprocess.run(
        ["powershell", "-NoProfile", "-Command", "[Environment]::GetEnvironmentVariable('DEEPINFRA_API_KEY','User')"],
        capture_output=True, text=True).stdout.strip()
    if not key:
        raise SystemExit("DEEPINFRA_API_KEY is not set (user environment variable); nothing was sent")
    return key


def stream_chat(key, model_id, messages, max_tokens, temperature, variant):
    """stream_chat_once with a patient retry for "model busy" (429) and server errors (5xx): 3 retries, 4 / 8 / 16 s apart."""
    for attempt in range(4):
        try:
            return stream_chat_once(key, model_id, messages, max_tokens, temperature, variant)
        except RuntimeError as e:
            if attempt < 3 and (str(e).startswith("HTTP 429") or str(e).startswith("HTTP 5")):
                wait = 4 * 2 ** attempt
                print(f"  host busy ({str(e)[:40]}); waiting {wait}s", flush=True)
                time.sleep(wait)
                continue
            raise


def stream_chat_once(key, model_id, messages, max_tokens, temperature, variant):
    """One streamed chat call. Returns (text, first_token_s, total_s, usage). The key only goes into the Authorization header."""
    import requests
    body = {"model": model_id, "messages": messages, "temperature": temperature, "top_p": 0.9, "max_tokens": max_tokens,
            "stream": True, "stream_options": {"include_usage": True}}
    body.update(variant)
    t0 = time.time()
    first, text, usage, reasoning = None, "", {}, False
    with requests.post("https://api.deepinfra.com/v1/openai/chat/completions", json=body, stream=True, timeout=(10, 90),
                       headers={"Authorization": f"Bearer {key}"}) as r:
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200].replace(key, '***')}")
        for line in r.iter_lines():
            if not line or not line.startswith(b"data:"):
                continue
            payload = line[5:].strip()
            if payload == b"[DONE]":
                break
            j = json.loads(payload)
            if j.get("usage"):
                usage = j["usage"]
            for ch in j.get("choices") or []:
                d = ch.get("delta") or {}
                if d.get("reasoning_content") or d.get("reasoning"):
                    reasoning = True
                piece = d.get("content") or ""
                if piece and first is None:
                    first = time.time() - t0
                text += piece
    return text, first, time.time() - t0, usage, reasoning


def boost(model_id, n):
    """Reasoning-only models (gpt-oss) spend part of max_tokens on hidden reasoning; give them room (our post-processing still trims the reply)."""
    return max(n, 700) if "gpt-oss" in model_id.lower() else n


VARIANTS = [{}, {"reasoning_effort": "none"}, {"chat_template_kwargs": {"enable_thinking": False}}, {"reasoning_effort": "low"}]


def cost_of(usage, pin, pout):
    """DeepInfra puts the real cost of a call in usage.estimated_cost (dollars); otherwise price x tokens."""
    if usage.get("estimated_cost") is not None:
        return float(usage["estimated_cost"])
    return ((usage.get("prompt_tokens") or 0) * pin + (usage.get("completion_tokens") or 0) * pout) / 1e6


def smoke(a, key, moments):
    """2 moments per model (one acknowledgement-only turn, one full reply); prints the raw and the post-processed text. Nothing is stored."""
    sample = [next(m for m in moments if m["needs_model"] and m["meta"]["forced_question"]),
              next(m for m in moments if m["needs_model"] and not m["meta"]["forced_question"] and m["meta"]["last_stage"] != "conclusion")]
    spent = 0.0
    for model_id in a.models:
        pin, pout = price_for(model_id)
        print(f"--- {model_id}", flush=True)
        for m in sample:
            for v in VARIANTS:
                try:
                    text, first, total, usage, reasoning = stream_chat(key, model_id, m["messages"], boost(model_id, m["max_tokens"]), m["temperature"], v)
                except RuntimeError as e:
                    print(f"    variant {list(v)} rejected: {str(e)[:70]}", flush=True)
                    continue
                spent += cost_of(usage, pin, pout)
                print(f"    {m['id']} variant={list(v)} reasoning_seen={reasoning} first={first or 0:.2f}s total={total:.2f}s tokens={usage.get('completion_tokens')}", flush=True)
                print(f"      raw: {text.strip()[:160]!r}", flush=True)
                if text.strip() and not reasoning:
                    break
    print(f"smoke spend: ${spent:.4f}", flush=True)


def cloud(a):
    key = api_key()
    moments, coach_calls = load_export()
    if a.smoke:
        return smoke(a, key, moments)
    spent = 0.0
    for model_id in a.models:
        pin, pout = price_for(model_id)
        short = "deepinfra/" + model_id.split("/")[-1]
        variant, raw, timings, raw_coach = None, {}, {}, {}
        todo = [m for m in moments if m["needs_model"]]
        spent_before = spent
        for m in todo:
            msgs = m["messages"]
            for v in ([variant] if variant is not None else VARIANTS):
                try:
                    text, first, total, usage, reasoning = stream_chat(key, model_id, msgs, boost(model_id, m["max_tokens"]), m["temperature"], v)
                except RuntimeError as e:          # the host rejected this switch for this model: try the next one
                    print(f"  {short}: variant {list(v)} rejected ({str(e)[:80]})", flush=True)
                    continue
                spent += cost_of(usage, pin, pout)
                if text.strip() and (not reasoning or v.get("reasoning_effort") == "low"):   # "low" is the lowest a reasoning-only model allows
                    variant = v
                    break
                print(f"  {short}: variant {list(v)} gave no clean reply (reasoning={reasoning}); trying the next", flush=True)
            else:
                raise SystemExit(f"{model_id}: no variant gave a clean reply; stopping (spent about ${spent:.4f})")
            raw[m["id"]] = text
            timings[m["id"]] = {"first": round(first or 0, 2), "total": round(total, 2)}
            print(f"{short:34s} {m['id']:6s} first token {first or 0:5.2f}s total {total:5.2f}s  {text[:70]!r}", flush=True)
            if spent > a.cap:
                raise SystemExit(f"spend cap reached (about ${spent:.4f} > ${a.cap}); stopped")
            if a.model_cap and spent - spent_before > a.model_cap:
                raise SystemExit(f"{model_id} passed its own cap (${spent - spent_before:.4f} > ${a.model_cap}); stopped")
        if a.coach:
            for c in coach_calls:
                msgs = [{"role": "system", "content": c["system"]}, {"role": "user", "content": c["user"]}]
                text, first, total, usage, reasoning = stream_chat(key, model_id, msgs, boost(model_id, c["max_tokens"]), 0.5, variant or {})
                spent += cost_of(usage, pin, pout)
                raw_coach[c["id"]] = text
            print(f"{short} coach calls done", flush=True)
        firsts = sorted(t["first"] for t in timings.values())
        info = {"source": "DeepInfra", "model_id": model_id, "variant": list(variant or {}), "median_first_token_s": firsts[len(firsts) // 2],
                "run_from": "this PC over home internet"}
        finalize(short, raw, raw_coach or None, timings, info)
        print(f"{short}: spent ${spent - spent_before:.4f}; run total so far ${spent:.4f}", flush=True)


# ---- Anthropic API (Claude Haiku 5.5, lowest effort, no thinking) ----------------------------------------------------

ANTHROPIC_PRICE = (0.10, 0.50)        # $/1M tokens, "from" price on the models page; the cap uses these (cache reads 10% of input)


def anthropic_key():
    key = os.environ.get("VRSIM_ANTHROPIC_API_KEY") or subprocess.run(
        ["powershell", "-NoProfile", "-Command", "[Environment]::GetEnvironmentVariable('VRSIM_ANTHROPIC_API_KEY','User')"],
        capture_output=True, text=True).stdout.strip()
    if not key:
        raise SystemExit("VRSIM_ANTHROPIC_API_KEY is not set (user environment variable); nothing was sent")
    return key


def anthropic_cost(u):
    pin, pout = ANTHROPIC_PRICE
    return ((u.get("input_tokens") or 0) * pin + (u.get("cache_creation_input_tokens") or 0) * pin * 1.25
            + (u.get("cache_read_input_tokens") or 0) * pin * 0.1 + (u.get("output_tokens") or 0) * pout) / 1e6


def anthropic_chat(key, model, system, messages, max_tokens, temperature, effort="low", thinking_off=True):
    """One streamed Messages call. Returns (text, first_token_s, total_s, usage, thinking_seen). The key only goes in the x-api-key header."""
    import requests
    body = {"model": model, "max_tokens": max_tokens, "stream": True, "output_config": {"effort": effort},
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}], "messages": messages}
    if temperature is not None:
        body["temperature"] = temperature
    if thinking_off:
        body["thinking"] = {"type": "disabled"}
    t0 = time.time()
    first, text, usage, thinking = None, "", {}, False
    with requests.post("https://api.anthropic.com/v1/messages", json=body, stream=True, timeout=(10, 90),
                       headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}) as r:
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300].replace(key, '***')}")
        for line in r.iter_lines():
            if not line or not line.startswith(b"data:"):
                continue
            j = json.loads(line[5:].strip())
            t = j.get("type")
            if t == "message_start":
                usage.update(j["message"].get("usage") or {})
            elif t == "message_delta":
                usage.update(j.get("usage") or {})
            elif t == "content_block_start" and (j.get("content_block") or {}).get("type") in ("thinking", "redacted_thinking"):
                thinking = True
            elif t == "content_block_delta":
                piece = (j.get("delta") or {}).get("text") or ""
                if piece and first is None:
                    first = time.time() - t0
                text += piece
            elif t == "error":
                raise RuntimeError("stream error: " + json.dumps(j)[:200].replace(key, "***"))
    return text, first, time.time() - t0, usage, thinking


def split_system(msgs):
    system = "\n\n".join(m["content"] for m in msgs if m["role"] == "system")
    return system, [m for m in msgs if m["role"] != "system"]


def anthropic_run(a):
    key = anthropic_key()
    moments, coach_calls = load_export()
    short = a.name
    todo = [m for m in moments if m["needs_model"]]
    if a.smoke:
        todo = [next(m for m in todo if m["meta"]["forced_question"]),
                next(m for m in todo if not m["meta"]["forced_question"] and m["meta"]["last_stage"] != "conclusion")]
    spent, raw, timings, raw_coach, usages = 0.0, {}, {}, {}, []
    temp = 0.8
    for m in todo:
        system, msgs = split_system(m["messages"])
        try:
            text, first, total, usage, thinking = anthropic_chat(key, a.model, system, msgs, m["max_tokens"], temp)
        except RuntimeError as e:
            if temp is not None and "temperature" in str(e).lower():
                print(f"  temperature rejected ({str(e)[:90]}); retrying without it", flush=True)
                temp = None
                text, first, total, usage, thinking = anthropic_chat(key, a.model, system, msgs, m["max_tokens"], temp)
            else:
                raise
        spent += anthropic_cost(usage)
        usages.append(usage)
        raw[m["id"]] = text
        timings[m["id"]] = {"first": round(first or 0, 2), "total": round(total, 2)}
        print(f"{short:18s} {m['id']:6s} first {first or 0:5.2f}s total {total:5.2f}s thinking_seen={thinking} in={usage.get('input_tokens')} "
              f"out={usage.get('output_tokens')} cache_w={usage.get('cache_creation_input_tokens')} cache_r={usage.get('cache_read_input_tokens')}  {text[:70]!r}", flush=True)
        if a.smoke:
            print(f"      raw: {text.strip()!r}", flush=True)
        if spent > a.cap:
            raise SystemExit(f"spend cap reached (about ${spent:.4f} > ${a.cap}); stopped")
    if a.smoke:
        print(f"smoke spend about ${spent:.4f}")
        return
    if a.coach:
        for c in coach_calls:
            text, first, total, usage, thinking = anthropic_chat(key, a.model, c["system"], [{"role": "user", "content": c["user"]}], c["max_tokens"], 0.5 if temp is not None else None)
            spent += anthropic_cost(usage)
            usages.append(usage)
            raw_coach[c["id"]] = text
            if spent > a.cap:
                raise SystemExit(f"spend cap reached (about ${spent:.4f} > ${a.cap}); stopped")
        print(f"{short} coach calls done", flush=True)
    firsts = sorted(t["first"] for t in timings.values())
    totals = sorted(t["total"] for t in timings.values())
    info = {"source": "Anthropic API", "model_id": a.model, "effort": "low", "thinking": "disabled", "median_first_token_s": firsts[len(firsts) // 2],
            "p90_first_token_s": firsts[int(len(firsts) * 0.9) - 1], "median_total_s": totals[len(totals) // 2],
            "estimated_cost_usd": round(spent, 4), "cache_read_tokens": sum(u.get("cache_read_input_tokens") or 0 for u in usages),
            "run_from": "this PC over home internet"}
    finalize(short, raw, raw_coach or None, timings, info)
    print(f"{short}: spent about ${spent:.4f}; first token median {info['median_first_token_s']}s p90 {info['p90_first_token_s']}s; "
          f"cache read tokens {info['cache_read_tokens']}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    an = sub.add_parser("anthropic")
    an.add_argument("--model", default="claude-haiku-5-5")
    an.add_argument("--name", default="claude-haiku-api")
    an.add_argument("--coach", action="store_true")
    an.add_argument("--cap", type=float, default=1.0)
    an.add_argument("--smoke", action="store_true")
    sub.add_parser("export")
    i = sub.add_parser("ingest")
    i.add_argument("--model", required=True)
    i.add_argument("--raw", required=True)
    i.add_argument("--coach-raw")
    c = sub.add_parser("cloud")
    c.add_argument("--models", nargs="+", required=True)
    c.add_argument("--coach", action="store_true")
    c.add_argument("--cap", type=float, default=0.60)
    c.add_argument("--model-cap", type=float, default=0.0, help="stop a model that spends more than this on its own")
    c.add_argument("--smoke", action="store_true", help="2 moments per model, nothing stored")
    a = ap.parse_args()
    {"anthropic": lambda: anthropic_run(a), "export": lambda: export(), "ingest": lambda: ingest(a), "cloud": lambda: cloud(a)}[a.cmd]()


if __name__ == "__main__":
    main()
