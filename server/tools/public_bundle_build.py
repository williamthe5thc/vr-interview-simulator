"""
Build the PUBLIC bundle (model_compare\\public_bundle\\) from the live rating page. Nothing is deployed or sent anywhere.

    .venv\\Scripts\\python.exe tools\\public_bundle_build.py

The bundle holds: rate.html (anonymised copy), server.py (stdlib only), allowed_ids.json (ids and letters only, no model names),
passcode.txt (a fresh random passcode), README.md. It never contains key.json or anything that maps a letter to a model.
"""
import json
import os
import re
import secrets
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "model_compare")
BUNDLE = os.path.join(OUT, "public_bundle")
# real names that appear in the candidates' answers -> neutral stand-ins (body text only, never the script)
NAMES = []   # fill in per run, e.g. [("Real Name", "Casey Morgan")]; real names are never committed


def anonymise(html):
    head, sep, tail = html.partition("<script>")
    script, sep2, rest = tail.partition("</script>")
    for old, new in NAMES:
        head = re.sub(r"\b%s\b" % re.escape(old), new, head)
        rest = re.sub(r"\b%s\b" % re.escape(old), new, rest)
    # the live copy has a file picker that reveals models from key.json; the public copy does not
    head = re.sub(r'<label>Reveal \(only with the key file\).*?</label>', "", head, flags=re.S)
    script = re.sub(r"document\.getElementById\('keyfile'\)\.onchange = async e => \{.*?\n\};\n", "", script, flags=re.S)
    script = re.sub(r"  if \(NAME\.toLowerCase\(\) === 'jordan'\) \{.*?\n  \}\n", "", script, flags=re.S)
    return head + sep + script + sep2 + rest


def main():
    html = open(os.path.join(OUT, "public", "rate.html"), encoding="utf-8").read()
    page = anonymise(html)
    ids = sorted(set(re.findall(r'data-id="([^"]+)"', page)))
    best = {}
    for name in re.findall(r'name="best-([^"]+)"', page):
        best.setdefault(name, None)
    for moment in best:
        best[moment] = sorted({i.split("|")[-1] for i in ids if i.rsplit("|", 1)[0] == moment})
    os.makedirs(BUNDLE, exist_ok=True)
    open(os.path.join(BUNDLE, "rate.html"), "w", encoding="utf-8").write(page)
    json.dump({"rating_ids": ids, "best": best}, open(os.path.join(BUNDLE, "allowed_ids.json"), "w"), indent=0)
    shutil.copy2(os.path.join(ROOT, "tools", "public_bundle_server.py"), os.path.join(BUNDLE, "server.py"))
    pc = os.path.join(BUNDLE, "passcode.txt")
    if not os.path.exists(pc):
        open(pc, "w").write(secrets.token_urlsafe(6) + "\n")
    print(f"bundle written to {BUNDLE}: {len(ids)} rating ids, {len(best)} best-pick moments")


if __name__ == "__main__":
    main()
