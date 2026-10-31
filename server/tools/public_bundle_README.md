# Blind rating page: public copy

Rate reply options to real interview moments. Models are hidden; this folder contains no model names and no key.

## Files
- `server.py`: the server. Python 3 standard library only (the Mac's built-in `python3` works). No installs.
- `rate.html`: the page (names of the people in the interviews are replaced with neutral ones).
- `allowed_ids.json`: the ids/letters the server will accept. No model information.
- `passcode.txt`: the passcode raters type once. Change it by editing the file (one line) and restarting.
- `ratings/`: created on first use, one `<name>.json` per rater.

## Run it
```bash
cd public_bundle
python3 server.py            # passcode ON, listens on 127.0.0.1:8780 only
```
`--no-passcode` turns the passcode off; `--port N` changes the port. It listens on localhost only, so nothing is
reachable until you expose it deliberately:

## Put it on the internet (Tailscale Funnel)
```bash
tailscale funnel 8780        # prints a public https://<mac-name>.<tailnet>.ts.net URL
tailscale funnel status
```
While the funnel is on, **anyone with the URL can load the page**; only people with the passcode can save or read ratings.
Share the URL and the passcode separately.

## Stop it
- `Ctrl+C` in the terminal running `server.py`
- `tailscale funnel reset`   (turns the public URL off)

## Limits built in
Rater name 1-40 chars of letters, digits, space, `_`, `-`; at most 50 raters; only the known rating ids; scores 1-5;
best-pick letters only from that moment's letters; body at most 20 KB; 90 requests/min per address; an address that gives
the wrong passcode 10 times is locked out for a minute.

## Getting the ratings back
Zip the `ratings/` folder and send it to the PC (AirDrop / Taildrop / email), then on the PC:
```
.venv\Scripts\python.exe tools\model_compare.py merge-folder --dir <the unzipped ratings folder>
```
Each rater lands in `model_compare\ratings\web_<name>.json`. Models are revealed only on the PC, with `results`.
Do not copy `key.json` to the Mac.

## Note
The candidate answers in the page are real interview answers (names replaced, wording otherwise unchanged).
