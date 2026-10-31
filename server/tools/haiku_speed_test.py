"""
Tiny speed test: claude-haiku-4-5 vs claude-haiku-5-5 on the same real interview prompts (production messages from the export).
Both get the cached system prompt; 5.5 runs at effort "low" with thinking disabled; 4.5 has no effort setting and does not think unless asked.
Measures time to first token, time to the first complete sentence, and total, and adds up the cost. The key is read from the user
environment (VRSIM_ANTHROPIC_API_KEY) and only goes in the x-api-key header.

    .venv\\Scripts\\python.exe tools\\haiku_speed_test.py [--n 8]
"""
import argparse
import json
import os
import re
import statistics
import sys
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "services", "llm"))
import anthropic_backend as ab  # noqa: E402

PRICES = {"claude-haiku-4-5": (1.00, 5.00), "claude-haiku-5-5": (0.20, 1.00)}     # $/1M in/out (5.5 at the safe estimate used by the cap)
LIST = {"claude-haiku-4-5": (1.00, 5.00), "claude-haiku-5-5": (0.10, 0.50)}        # list prices


def call(http, key, model, system, msgs, max_tokens):
    body = {"model": model, "max_tokens": max_tokens, "stream": True, "messages": msgs,
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]}
    if model == "claude-haiku-5-5":        # 5.5 rejects `temperature` ("deprecated for this model"); 4.5 gets 0.8
        body["output_config"] = {"effort": "low"}
        body["thinking"] = {"type": "disabled"}
    if model != "claude-haiku-5-5":
        body["temperature"] = 0.8
    t0 = time.time()
    first = sentence = None
    text, usage = "", {}
    r = http.post("https://api.anthropic.com/v1/messages", json=body, stream=True, timeout=(5, 30),
                  headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    if r.status_code != 200:
        raise SystemExit(f"{model}: HTTP {r.status_code} {r.text[:200].replace(key, '***')}")
    with r:
        for line in r.iter_lines():
            if not line.startswith(b"data:"):
                continue
            j = json.loads(line[5:].strip())
            if j.get("type") == "message_start":
                usage.update(j["message"].get("usage") or {})
            elif j.get("type") == "message_delta":
                usage.update(j.get("usage") or {})
            elif j.get("type") == "content_block_delta":
                piece = (j.get("delta") or {}).get("text") or ""
                if piece and first is None:
                    first = time.time() - t0
                text += piece
                if sentence is None and re.search(r"[.!?]\s", text + " ") and re.search(r"[.!?](\s|$)", text) and len(text) > 8:
                    # the first sentence is complete once a terminator is followed by more text (as stream_response requires) or the reply ends
                    if re.search(r"[.!?]\s+\S", text):
                        sentence = time.time() - t0
    total = time.time() - t0
    return first or 0, sentence or total, total, usage, text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=8)
    a = ap.parse_args()
    key = ab._key()
    if not key:
        raise SystemExit("VRSIM_ANTHROPIC_API_KEY is not set")
    moments = json.load(open(os.path.join(ROOT, "model_compare", "export", "moments.json"), encoding="utf-8"))
    pool = [m for m in moments if m["needs_model"] and not m["meta"]["forced_question"] and m["meta"]["last_stage"] != "conclusion"][:a.n]
    http = requests.Session()
    res = {m: {"first": [], "sentence": [], "total": [], "cost": 0.0, "list": 0.0, "cache_read": 0, "out": []} for m in PRICES}
    for model in PRICES:                                     # one throw-away call each: opens the connection and writes the cache
        system = "\n\n".join(x["content"] for x in pool[0]["messages"] if x["role"] == "system")
        call(http, key, model, system, [x for x in pool[0]["messages"] if x["role"] != "system"], 40)
    for m in pool:
        system = "\n\n".join(x["content"] for x in m["messages"] if x["role"] == "system")
        msgs = [x for x in m["messages"] if x["role"] != "system"]
        for model in PRICES:                                 # alternate models so network weather hits both equally
            first, sent, total, u, text = call(http, key, model, system, msgs, m["max_tokens"])
            r = res[model]
            r["first"].append(first); r["sentence"].append(sent); r["total"].append(total); r["out"].append(u.get("output_tokens") or 0)
            for table, k in ((PRICES, "cost"), (LIST, "list")):
                pin, pout = table[model]
                r[k] += ((u.get("input_tokens") or 0) * pin + (u.get("cache_creation_input_tokens") or 0) * pin * 1.25
                         + (u.get("cache_read_input_tokens") or 0) * pin * 0.1 + (u.get("output_tokens") or 0) * pout) / 1e6
            r["cache_read"] += u.get("cache_read_input_tokens") or 0
            print(f"{m['id']:6s} {model}: first {first:.2f}s first-sentence {sent:.2f}s total {total:.2f}s out={u.get('output_tokens')} {text[:60]!r}", flush=True)

    def q(v, p):
        v = sorted(v)
        return v[min(len(v) - 1, int(round(p * (len(v) - 1))))]
    print()
    for model, r in res.items():
        print(f"{model}: first token median {statistics.median(r['first']):.2f}s p90 {q(r['first'], .9):.2f}s | first sentence median "
              f"{statistics.median(r['sentence']):.2f}s p90 {q(r['sentence'], .9):.2f}s | total median {statistics.median(r['total']):.2f}s | "
              f"avg output {statistics.mean(r['out']):.0f} tokens | cache-read tokens {r['cache_read']} | cost ${r['list']:.4f} at list price "
              f"(${r['cost']:.4f} at the cap estimate)")


if __name__ == "__main__":
    main()
