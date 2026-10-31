"""
Blind model comparison for the interviewer (and the coach). Local only: it talks to Ollama on this PC and nothing else.

    1) generate replies   .venv\\Scripts\\python.exe tools\\model_compare.py generate --models qwen2.5:7b-instruct qwen3.5:9b gemma4:12b
       (resumable: finished model/turn pairs are kept in model_compare\\results\\<model>.json; add --coach for the coach section)
    2) build the page     .venv\\Scripts\\python.exe tools\\model_compare.py page
       -> model_compare\\rate.html (anonymous, shuffled A/B/C... per turn) and model_compare\\key.json (which model is which; do not open before rating)
    3) rate in the browser, press "Download ratings", then press "Reveal" and pick key.json to see the result table.
    4) layout check without any model:   .venv\\Scripts\\python.exe tools\\model_compare.py page --dry-run

Method: "teacher forcing". For every candidate answer in three real interviews (customer service 2026-10-04, speech therapist and a
one-word-answers run 2026-10-07) every model gets the SAME conversation so far and writes the next interviewer reply with the full
production logic (prompt, persona, topic rules). So the replies are directly comparable. Speed numbers are only meaningful for models
that fit in VRAM; a CPU-offloaded big model is judged on quality only.
"""
import argparse
import html
import json
import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
OUT = os.path.join(ROOT, "model_compare")
RES = os.path.join(OUT, "results")

SCENARIOS = [
    {"id": "cs", "title": "Customer service (real interview, 2026-10-04)", "job": "customer_service", "who": "Taylor Wilson",
     "file": "exports/2026-10-04_18-46_customer_service_9fbd6a83.json"},
    {"id": "st", "title": "Speech therapist (real interview, 2026-10-07)", "job": "speech_therapist", "who": "Samuel Hughes",
     "file": "exports/2026-10-07_12-17_speech_therapist_1148167c.json"},
    {"id": "sw", "title": "Software engineer, one-word answers (real interview, 2026-10-07)", "job": "software_engineer", "who": "Gregory Jensen",
     "file": "exports/2026-10-07_13-32_software_engineer_ebd3e995.json"},
]
THINK_OFF_PREFIXES = ("qwen3", "gemma4", "granite4", "deepseek", "gpt-oss")   # reasoning-capable families: ask Ollama not to think (think=false)


def load_scenario(sc):
    rec = json.load(open(os.path.join(ROOT, sc["file"]), encoding="utf-8"))
    ex = rec["exchanges"]
    turns = []
    for i, e in enumerate(ex):
        turns.append({"n": i + 1, "question": e["question"], "answer": e["answer"],
                      "next": ex[i + 1]["question"] if i + 1 < len(ex) else rec.get("closing", "")})
    return rec, turns


def make_client(model):
    from services.llm.Ollama_client import OllamaClient
    cfg = json.load(open(os.path.join(ROOT, "config", "config.json"), encoding="utf-8"))["ollama"]
    cfg = json.loads(json.dumps(cfg))
    cfg["prompt_layout"] = "usertail"
    cfg["url"] = cfg["url"].replace("localhost", "127.0.0.1")
    cfg.setdefault("options", {})["num_ctx"] = 4096
    if model.lower().startswith(THINK_OFF_PREFIXES):
        cfg["think"] = False
    cfg["keep_alive"] = "10m"
    cfg["collect_stats"] = True      # read the stream to the end so Ollama's timing numbers are available
    return OllamaClient(cfg["url"], model, 4096, config=cfg)


def port_up(port):
    import socket
    s = socket.socket()
    s.settimeout(0.5)
    try:
        return s.connect_ex(("127.0.0.1", port)) == 0
    finally:
        s.close()


def first_audio_seconds(sentences):
    """Time the Kokoro worker needs for the first chunk (sentences joined to at least 8 characters), or None if the worker is not running."""
    if not port_up(8771) or not sentences:
        return None
    import requests
    chunk = ""
    for s in sentences:
        chunk = f"{chunk} {s}".strip()
        if len(chunk) >= 8:
            break
    t = time.time()
    try:
        requests.post("http://127.0.0.1:8771/synthesize", json={"text": chunk, "voice": "am_adam"}, timeout=30)
    except Exception:
        return None
    return time.time() - t


def run_info():
    import requests
    try:
        version = requests.get("http://127.0.0.1:11434/api/version", timeout=3).json().get("version")
    except Exception:
        version = None
    return {"ollama_version": version, "stt_worker_running": port_up(8770), "kokoro_worker_running": port_up(8771), "alltalk_running": port_up(7851)}


def generate(models, coach, tag=""):
    os.makedirs(RES, exist_ok=True)
    for model in models:
        path = os.path.join(RES, model.replace(":", "_").replace("/", "_") + (f"__{tag}" if tag else "") + ".json")
        data = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {"model": model, "tag": tag, "replies": {}, "coach": None}
        data["run_info"] = run_info()    # which workers were running, which Ollama; the report must say it
        print(f"{model}: {data['run_info']}", flush=True)
        for sc in SCENARIOS:
            rec, turns = load_scenario(sc)
            client = make_client(model)
            client.set_job(sc["job"])
            client.interviewer_name = sc["who"]
            ctx = [{"role": "user", "content": "Hello."}]
            ctx_q = [{"role": "assistant", "content": turns[0]["question"]}]
            history = ctx + ctx_q
            for t in turns:
                key = f"{sc['id']}|{t['n']}"
                if key not in data["replies"]:
                    started, first, sentences = time.time(), None, []
                    for s in client.stream_response(t["answer"], history):
                        first = first if first is not None else time.time() - started
                        sentences.append(s)
                    total = time.time() - started
                    tts = first_audio_seconds(sentences)
                    st = client.last_stats or {}
                    ns = lambda k: round((st.get(k) or 0) / 1e9, 3)
                    data["replies"][key] = {
                        "reply": " ".join(sentences), "first": round(first or 0, 2), "total": round(total, 2),
                        # candidate's last word -> first audio, as the live server would do it (speech-to-text excluded): first sentence + Kokoro for chunk 1
                        "first_audio": round((first or 0) + tts, 2) if tts is not None else None,
                        "ollama": {"prompt_tokens": st.get("prompt_eval_count"), "prompt_eval_s": ns("prompt_eval_duration"),
                                   "gen_tokens": st.get("eval_count"), "gen_s": ns("eval_duration"), "load_s": ns("load_duration"),
                                   "tokens_per_s": round((st.get("eval_count") or 0) / max(ns("eval_duration"), 1e-6), 1) if st.get("eval_count") else None}}
                    json.dump(data, open(path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
                    r = data["replies"][key]
                    print(f"{model:22s} {key:6s} first {r['first']:5.2f}s audio {str(r['first_audio']):>5}s  gen {r['ollama']['gen_tokens']}tok @ {r['ollama']['tokens_per_s']}/s  {r['reply'][:80]}", flush=True)
                # the conversation continues with the REAL next question, the same for every model
                history = history + [{"role": "user", "content": t["answer"]}]
                if t["next"] and t is not turns[-1]:
                    history.append({"role": "assistant", "content": t["next"]})
        if coach and not data.get("coach"):
            from app import interview_review as rv
            from services.llm.scenarios import job_interview
            sc = SCENARIOS[1]
            rec, _ = load_scenario(sc)
            client = make_client(model)
            client.config["coach_workers"] = 1
            t0 = time.time()
            rep = rv.generate_coach_report(client, rec, job_interview.get_job_info(sc["job"]))
            data["coach"] = {"seconds": round(time.time() - t0, 1), "summary": rep["summary"], "items": rep["items"]}
            json.dump(data, open(path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
            print(f"{model} coach done in {data['coach']['seconds']}s", flush=True)


def build_page(dry):
    rnd = random.Random(20261007)
    if dry:
        models = ["model-x", "model-y", "model-z"]
        results = {m: {"replies": {}, "coach": {"seconds": 1, "summary": f"{m} summary", "items": []}} for m in models}
        for sc in SCENARIOS:
            _, turns = load_scenario(sc)
            for t in turns:
                for m in models:
                    results[m]["replies"][f"{sc['id']}|{t['n']}"] = {"reply": f"[{m}] sample reply to turn {t['n']}.", "first": 0.5, "total": 1.0}
    else:
        results = {}
        for fn in sorted(os.listdir(RES)):
            d = json.load(open(os.path.join(RES, fn), encoding="utf-8"))
            if d.get("tag"):
                continue          # control runs (before/after the Ollama upgrade) are not rated
            results[d["model"]] = d
        models = list(results)
    key, cards = {}, []
    old_key = {}
    if not dry and os.path.exists(os.path.join(OUT, "key.json")):
        old_key = json.load(open(os.path.join(OUT, "key.json"), encoding="utf-8")).get("key", {})   # letters already shown to the rater stay
    for sc in SCENARIOS:
        _, turns = load_scenario(sc)
        cards.append(f"<h2>{html.escape(sc['title'])}</h2>")
        for t in turns:
            k = f"{sc['id']}|{t['n']}"
            have = [m for m in models if k in results[m]["replies"]]
            if len(have) < 2:
                continue
            labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            kept = {lab: m for lab, m in old_key.get(k, {}).items() if m in have}
            new = [m for m in have if m not in kept.values()]
            rnd.shuffle(new)
            free = [lab for lab in labels if lab not in kept]
            mapping = dict(kept)
            mapping.update({free[i]: m for i, m in enumerate(new)})
            key[k] = dict(sorted(mapping.items()))
            order = [key[k][lab] for lab in sorted(key[k])]
            boxes = []
            for i, m in enumerate(order):
                lab = sorted(key[k])[i]
                boxes.append(
                    f'<div class="reply"><b>Reply {lab}</b><p>{html.escape(results[m]["replies"][k]["reply"])}</p>'
                    f'<span class="stars" data-id="{k}|{lab}">' + "".join(f'<button data-v="{v}">{v}</button>' for v in range(1, 6)) + "</span></div>")
            cards.append(
                f'<div class="card"><div class="hdr"><div class="ctx"><small>Interviewer asked:</small> {html.escape(t["question"])}</div>'
                f'<div class="ans"><small>Candidate said:</small> <b>{html.escape(t["answer"][:400])}</b></div></div>{"".join(boxes)}'
                f'<div class="best">Best reply: ' + "".join(f'<label><input type="radio" name="best-{k}" value="{sorted(key[k])[i]}"> {sorted(key[k])[i]}</label> ' for i in range(len(order))) + "</div></div>")
    coach_models = [m for m in models if results[m].get("coach") and results[m]["coach"].get("items")]
    if len(coach_models) >= 2:
        cards.append("<h2>Coach feedback on the speech-therapist interview</h2>")
        kept = {lab: m for lab, m in old_key.get("coach", {}).items() if m in coach_models}
        new = [m for m in coach_models if m not in kept.values()]
        rnd.shuffle(new)
        free = [lab for lab in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if lab not in kept]
        mapping = dict(kept)
        mapping.update({free[i]: m for i, m in enumerate(new)})
        key["coach"] = dict(sorted(mapping.items()))
        order = [key["coach"][lab] for lab in sorted(key["coach"])]
        for idx in range(len(results[order[0]]["coach"]["items"])):
            it0 = results[order[0]]["coach"]["items"][idx]
            boxes = []
            for i, m in enumerate(order):
                items = results[m]["coach"]["items"]
                if idx >= len(items):
                    continue
                it = items[idx]
                lab = sorted(key["coach"])[i]
                boxes.append(f'<div class="reply"><b>Coach {lab}</b> (score {it["score"]}/5)<p>Went well: {html.escape(it["went_well"])}<br>Improve: {html.escape(it["improve"])}<br>Try saying: {html.escape(it["stronger"])}</p>'
                             f'<span class="stars" data-id="coach|{it["number"]}|{lab}">' + "".join(f'<button data-v="{v}">{v}</button>' for v in range(1, 6)) + "</span></div>")
            cards.append(f'<div class="card"><div class="hdr"><div class="ans"><small>Candidate answer {it0["number"]}:</small> {html.escape(it0["answer"][:300])}</div></div>{"".join(boxes)}</div>')
    def _avg(m, f):
        vals = [r[f] for r in results[m]["replies"].values() if r.get(f) is not None and r.get("timed", True)]
        return round(sum(vals) / len(vals), 2) if vals else None
    timing = {m: {"avg_first": _avg(m, "first"), "avg_total": _avg(m, "total")} for m in models}
    os.makedirs(OUT, exist_ok=True)
    json.dump({"key": key, "timing": timing}, open(os.path.join(OUT, "key.json"), "w", encoding="utf-8"), indent=1)
    template = open(os.path.join(ROOT, "tools", "rate_template.html"), encoding="utf-8").read()
    page = template.replace("__BODY__", "\n".join(cards))
    open(os.path.join(OUT, "rate.html"), "w", encoding="utf-8").write(page)
    os.makedirs(os.path.join(OUT, "public"), exist_ok=True)   # the only folder the tailnet-only rating server shows (key.json stays out)
    open(os.path.join(OUT, "public", "rate.html"), "w", encoding="utf-8").write(page)
    print(f"wrote {os.path.join(OUT, 'rate.html')} ({len(models)} models, {len(key)} items) and key.json")


PAGE = """<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Blind reply rating</title>
<style>
body{font-family:Segoe UI,Arial,sans-serif;margin:0 auto;max-width:900px;padding:16px 16px 80px;background:#fafafa;color:#222}
h1{font-size:22px}h2{margin-top:36px;border-bottom:2px solid #ddd;padding-bottom:4px}
.card{background:#fff;border:1px solid #ddd;border-radius:8px;padding:12px;margin:14px 0}
.ctx,.ans{margin:4px 0;font-size:14px}.ctx{color:#555}small{color:#777}
.reply{border-left:4px solid #8ab;margin:10px 0;padding:4px 10px;background:#f6f9fc}.reply p{margin:4px 0}
.stars button{width:34px;height:30px;margin-right:4px;border:1px solid #999;background:#fff;border-radius:4px;cursor:pointer}
.stars button.on{background:#2a7;color:#fff;border-color:#2a7}.best{font-size:14px;margin-top:6px}
#bar{position:fixed;bottom:0;left:0;right:0;background:#fff;border-top:1px solid #ccc;padding:10px 16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
button.act{padding:8px 14px;border:0;border-radius:6px;background:#246;color:#fff;cursor:pointer}pre{background:#fff;border:1px solid #ddd;padding:10px;overflow:auto}
@media (prefers-color-scheme:dark){body{background:#181a1b;color:#ddd}.card,#bar,pre{background:#222;border-color:#444}.reply{background:#1d2630}.stars button{background:#222;color:#ddd}}
</style>
<h1>Which reply sounds like a good human interviewer?</h1>
<p>For each moment, read the candidate's answer and rate every reply from 1 (poor, stiff, wrong or off-topic) to 5 (natural, relevant, what a good interviewer would say). Then tick the best one. The models are hidden and shuffled. Your ratings are saved in this browser as you go.</p>
__BODY__
<div id="bar"><span id="count"></span><button class="act" id="dl">Download ratings</button>
<label>Reveal: <input type="file" id="keyfile" accept=".json"> (choose key.json after you finish)</label></div><pre id="out" hidden></pre>
<script>
const S='blind-ratings-v1';let R={};try{R=JSON.parse(localStorage.getItem(S)||'{}')}catch(e){}
let tmr;function save(){try{localStorage.setItem(S,JSON.stringify(R))}catch(e){}document.getElementById('count').textContent=Object.keys(R).length+' ratings';clearTimeout(tmr);tmr=setTimeout(()=>{try{fetch('/ratings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(R)}).catch(()=>{})}catch(e){}},800)}
function paint(){document.querySelectorAll('.stars').forEach(s=>{const id=s.dataset.id;s.querySelectorAll('button').forEach(b=>b.classList.toggle('on',R[id]==b.dataset.v))});document.querySelectorAll('input[type=radio]').forEach(r=>{r.checked=(R['best:'+r.name]==r.value)})}
document.querySelectorAll('.stars').forEach(s=>{const id=s.dataset.id;s.querySelectorAll('button').forEach(b=>{b.onclick=()=>{R[id]=+b.dataset.v;paint();save()}})});
document.querySelectorAll('input[type=radio]').forEach(r=>{r.onchange=()=>{R['best:'+r.name]=r.value;save()}});paint();save();
fetch('/ratings').then(r=>r.ok?r.json():{}).then(S=>{let n=0;for(const k in S){if(!(k in R)){R[k]=S[k];n++}}if(n){paint();save()}}).catch(()=>{});
document.getElementById('dl').onclick=()=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(R,null,1)],{type:'application/json'}));a.download='ratings.json';a.click()};
document.getElementById('keyfile').onchange=async e=>{const K=JSON.parse(await e.target.files[0].text());const sum={},cnt={},wins={};
for(const id in R){if(id.startsWith('best:')){const k=id.slice(10);const m=(K.key[k]||{})[R[id]];if(m)wins[m]=(wins[m]||0)+1;continue}
const p=id.split('|');const lab=p.pop();const k=p.join('|');const m=(K.key[k]||K.key[p[0]]||{})[lab];if(!m)continue;sum[m]=(sum[m]||0)+R[id];cnt[m]=(cnt[m]||0)+1}
let t='model                      avg rating   rated   best-picks   avg first sentence / whole reply (s)\\n';
for(const m of Object.keys(K.timing))t+=m.padEnd(27)+((sum[m]||0)/(cnt[m]||1)).toFixed(2).padEnd(13)+String(cnt[m]||0).padEnd(8)+String(wins[m]||0).padEnd(13)+K.timing[m].avg_first+' / '+K.timing[m].avg_total+'\\n';
const o=document.getElementById('out');o.textContent=t;o.hidden=false;o.scrollIntoView()};
</script>"""


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--models", nargs="+", required=True)
    g.add_argument("--coach", action="store_true")
    g.add_argument("--tag", default="", help="label for a control run, e.g. old_ollama; tagged results are kept out of the rating page")
    sub.add_parser("results")
    mg = sub.add_parser("merge-ratings")
    mg.add_argument("--file", required=True)
    mf = sub.add_parser("merge-folder")
    mf.add_argument("--dir", required=True, help="the ratings folder returned from the public copy")
    p = sub.add_parser("page")
    p.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.cmd == "results":
        return results()
    if a.cmd == "merge-ratings":
        return merge_ratings(a.file)
    if a.cmd == "merge-folder":
        return merge_folder(a.dir)
    if a.cmd == "generate":
        generate(a.models, a.coach, a.tag)
    else:
        build_page(a.dry_run)


RATERS = os.path.join(OUT, "ratings")


def safe_rater(name):
    return "".join(c for c in (name or "") if c.isalnum() or c in " _-").strip()[:30]


def merge_ratings(path):
    """A downloaded ratings file from a static copy of the page ({"rater": name, "ratings": {...}}) -> ratings/<name>.json (merged)."""
    d = json.load(open(path, encoding="utf-8"))
    name = safe_rater(d.get("rater"))
    if not name:
        raise SystemExit("the file has no rater name")
    os.makedirs(RATERS, exist_ok=True)
    f = os.path.join(RATERS, name + ".json")
    cur = json.load(open(f, encoding="utf-8")) if os.path.exists(f) else {}
    n_before = len(cur)
    cur.update(d.get("ratings", {}))
    json.dump(cur, open(f, "w", encoding="utf-8"), indent=1)
    print(f"{name}: {n_before} -> {len(cur)} entries")


def merge_folder(folder):
    """The ratings/ folder of the public copy (one <name>.json per rater) -> ratings/web_<name>.json here.
    The web_ prefix keeps a public rater called e.g. "owner" from mixing into the owner's file."""
    os.makedirs(RATERS, exist_ok=True)
    for fn in sorted(os.listdir(folder)):
        if not fn.endswith(".json"):
            continue
        d = json.load(open(os.path.join(folder, fn), encoding="utf-8"))
        if not isinstance(d, dict):
            continue
        f = os.path.join(RATERS, "web_" + safe_rater(fn[:-5]) + ".json")
        cur = json.load(open(f, encoding="utf-8")) if os.path.exists(f) else {}
        n_before = len(cur)
        cur.update(d)
        json.dump(cur, open(f, "w", encoding="utf-8"), indent=1)
        print(f"web_{fn[:-5]}: {n_before} -> {len(cur)} entries")


def results():
    """Per-rater and combined averages per model (needs key.json: run it only on this PC, never serve it)."""
    key = json.load(open(os.path.join(OUT, "key.json"), encoding="utf-8"))
    files = sorted(os.listdir(RATERS)) if os.path.isdir(RATERS) else []
    table = {}
    for fn in files:
        who = fn[:-5]
        R = json.load(open(os.path.join(RATERS, fn), encoding="utf-8"))
        for rid, v in R.items():
            if rid.startswith("best:"):
                k = rid[len("best:best-"):]
                m = key["key"].get(k, {}).get(v)
                if m:
                    table.setdefault(m, {}).setdefault(who, {"sum": 0, "n": 0, "wins": 0})["wins"] += 1
                continue
            parts = rid.split("|")
            lab, k = parts[-1], "|".join(parts[:-1])
            m = (key["key"].get(k) or key["key"].get(parts[0]) or {}).get(lab)
            if m:
                t = table.setdefault(m, {}).setdefault(who, {"sum": 0, "n": 0, "wins": 0})
                t["sum"] += v
                t["n"] += 1
    print(f"raters: {', '.join(f[:-5] for f in files) or 'none'}")
    print(f"{'model':34s} " + "".join(f"{f[:-5][:10]:>12s}" for f in files) + f"{'ALL avg':>10s}{'rated':>7s}{'best':>6s}")
    rows = []
    for m, per in table.items():
        tot_n = sum(x["n"] for x in per.values())
        tot = sum(x["sum"] for x in per.values()) / tot_n if tot_n else 0
        rows.append((tot, m, per, tot_n, sum(x["wins"] for x in per.values())))
    for tot, m, per, tot_n, wins in sorted(rows, reverse=True):
        cells = "".join(f"{(per[f[:-5]]['sum'] / per[f[:-5]]['n']):12.2f}" if f[:-5] in per and per[f[:-5]]["n"] else f"{'-':>12s}" for f in files)
        print(f"{m:34s} {cells}{tot:10.2f}{tot_n:7d}{wins:6d}")


if __name__ == "__main__":
    main()
