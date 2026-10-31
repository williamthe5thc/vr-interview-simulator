# Access codes for the headset app

Friends use the Quest app from anywhere through `quest.alearningmind.org`. That hostname is **not** behind Cloudflare Access, so a
personal access code is the only thing that stops strangers from using the interview server (and the API key's money). The website,
`interview.alearningmind.org`, stays behind Cloudflare Access (e-mail PIN) as before.

The code check lives in `app/access_codes.py` and covers the interview server on port 8765.

## Everyday use

Run these on the PC in `server`:

```
.venv\Scripts\python.exe tools\access_codes.py add "Sam"
.venv\Scripts\python.exe tools\access_codes.py add "Sam" --per-day 5 --expires 2026-12-31
.venv\Scripts\python.exe tools\access_codes.py list
.venv\Scripts\python.exe tools\access_codes.py revoke "Sam"
.venv\Scripts\python.exe tools\access_codes.py usage
.venv\Scripts\python.exe tools\access_codes.py disable
.venv\Scripts\python.exe tools\access_codes.py enable
```

- **add** makes a code like `H64A-GGA2` (8 letters/digits, no look-alikes such as O/0 or I/1/L) and prints it **once**. Only a salted
  hash is saved, so it can't be shown again. If someone loses theirs, revoke it and add a new one.
  Defaults: 3 interviews a day, one headset at a time, never expires. `--expires` is the last day it works.
- **list** shows every code's name, status (active / revoked / expired), limits and dates. Never the codes themselves.
- **revoke** turns a code off. A headset already in an interview finishes it; the next connection is refused.
- **usage** shows interviews started per code for the last 7 days (`--days N` for more), today's estimated API spend per code and in
  total, whether the kill switch is on, and any lockouts right now.
- **disable** is the kill switch: it creates `config/quest_disabled`. From then on every headset is refused (`busy`, 4503, "switched
  off right now"), and a headset already in an interview gets no more turns or new interviews. **enable** deletes the file.
  Creating or deleting that file by hand does the same.

The running server notices all of this by itself. The codes file is checked on every connection and re-read whenever it has changed.
The kill switch is checked on every connection and every turn. No restart is needed after add, revoke, disable or enable.

**Your own headset needs a code too.** Add one for yourself (for example `add "Owner" --per-day 50`). There are no address-based
exemptions. If the codes file is empty, every headset is refused.

Typed codes are forgiving: upper/lower case, spaces and the dash don't matter.

## What counts and what is limited

| Limit | Default | Where |
|---|---|---|
| Interviews per day, per code | 3 | per code (`--per-day`); counted when an interview starts (the "begin" message), not per connection, so a dropped connection doesn't use one up |
| Headsets at once, per code | 1 | per code (`--max-concurrent`) |
| Headset sessions at once, all codes together | 1 | `access.max_quest_sessions` (they share one language-model client, so keep this at 1 unless that changes) |
| Wrong codes | 5 in 10 minutes from one address | then that address is locked out for 15 minutes |
| Wrong codes, all addresses together | 50 in 10 minutes | then every code attempt is paused for 15 minutes (`rate_limited`), friends included: a brake on guessing spread over many addresses |
| Estimated API spend, per code | $0.25 a day | `access.code_usd_per_day`, or per code with `add --usd-per-day` |
| Estimated API spend, all code sessions together | $1.00 a day | `access.quest_daily_usd_cap` |

Spend is the hosted model's own estimate (it errs on the high side) for each turn and coach report of a code session. A spend cap that
is reached gives `limit_reached` (4429) at connect, or the usual 429 error on a turn or `begin`. With the local model the spend is 0.
The website has its own, separate spend caps (`web` in config.json, `app/web_guard.py`); they don't count headset sessions.

The daily counts, spend and lockouts are kept in `data/access_state.json` and survive restarts. Days are counted in the PC's local time.

## Files (all git-ignored)

- `config/access_codes.json`: one entry per code with `label`, `salt`, `hash` (PBKDF2-SHA256), `created`, `expires`, `revoked`,
  `interviews_per_day`, `max_concurrent`, `usd_per_day`. Edit it with the tool, not by hand.
- `data/access_state.json`: interviews and spend per code per day, recent failed attempts and lockouts.
- `config/quest_disabled`: the kill switch, only while it's on.

## Settings

All optional, under `"access"` in `config/config.json`. Shown with their defaults:

```json
"access": {
  "require_access_code": true,
  "web_sessions_need_code": false,
  "trusted_proxies": ["YOUR_PROXY_IP", "127.0.0.1", "::1"],
  "max_quest_sessions": 1,
  "auth_timeout_seconds": 10,
  "fail_limit": 5,
  "fail_window_minutes": 10,
  "lockout_minutes": 15,
  "cf_team_domain": "",
  "cf_access_aud": [],
  "global_fail_limit": 50,
  "quest_daily_usd_cap": 1.0,
  "code_usd_per_day": 0.25,
  "kill_switch_file": "config/quest_disabled"
}
```

config.json currently sets `cf_team_domain` to `YOUR_TEAM.cloudflareaccess.com`. `cf_access_aud` stays empty until the AUD tag
is read from the Cloudflare dashboard.

- `require_access_code: false` goes back to the old open server (an `auth` message is still answered `ok`, so new headset builds
  still work). Settings are read at server start.
- `trusted_proxies`: only connections from these addresses (your tunnel or proxy host, e.g. its Tailscale address, and localhost) may tell the server the real
  client address. `CF-Connecting-IP` comes first (Cloudflare sets it). Otherwise it's the right-most `X-Forwarded-For` entry that
  isn't one of these proxies, so a single value and an appended `127.0.0.1` from cloudflared both work. From anyone else those headers are ignored, so a stranger can't dodge
  the lockout by making up addresses.
- Browser sessions from the website skip the code only when they carry an allowed `Origin`, no `X-VRSim-Entry: quest` header,
  and a `Cf-Access-Jwt-Assertion` token that checks out (`app/cf_access.py`):
  - its RS256 signature against Cloudflare's keys from `https://<team>.cloudflareaccess.com/cdn-cgi/access/certs` (cached for an
    hour, re-fetched at most once a minute when a token names a key we don't have);
  - `aud` is one of `cf_access_aud`, `iss` is `https://<team>.cloudflareaccess.com`, and it hasn't expired (60 s leeway).

  `cf_team_domain` (for example `myteam.cloudflareaccess.com`, or just `myteam`) and `cf_access_aud` (the Access application's AUD
  tag; a list, or comma-separated) can also come from the environment variables `VRSIM_CF_TEAM_DOMAIN` and `VRSIM_CF_ACCESS_AUD`,
  which win over config.json. **While either is empty, no token is trusted and every connection, website included, needs a code.**
  The same happens if Cloudflare's keys can't be fetched. Set `web_sessions_need_code: true` to make website visitors always use codes.

## What the logs show

One line per attempt: `access: ok label='Sam' addr=203.0.113.7 client=quest app=1.4 session=...` or
`access: refused label='-' reason=invalid addr=...`. The code itself and keys are never logged.

## Mac nginx (quest hostname)

The quest server block must forward the real address and mark the connection as coming from the quest hostname, and it must
**clear** any Cloudflare Access headers so a caller can't pretend to be a website visitor:

```nginx
location / {
    proxy_pass http://<PC tailscale address>:8765;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header CF-Connecting-IP $http_cf_connecting_ip;
    proxy_set_header X-Forwarded-For $http_cf_connecting_ip;
    proxy_set_header X-VRSim-Entry quest;
    proxy_set_header Cf-Access-Jwt-Assertion "";
    proxy_set_header Cf-Access-Authenticated-User-Email "";
    proxy_set_header Origin "";
    proxy_read_timeout 600s;
}
```

(nginx doesn't send a header whose value is empty, so the last three lines remove them.)

## Protocol (for the headset app)

1. After the WebSocket connects, the client's **first** message must arrive within 10 seconds:
   `{"type":"auth","code":"<code>","client":"quest","app_version":"<x>"}`
2. Success: `{"type":"auth_result","ok":true,"label":"<friend name>","limits":{"interviews_per_day":N,"remaining_today":M}}`.
   Then the normal protocol continues unchanged (`session_init` and the rest come after this).
3. Failure: `{"type":"auth_result","ok":false,"reason":"<reason>","message":"<plain words for the player>"}`, then the server closes
   the socket with:

   | reason | close code |
   |---|---|
   | `invalid`, `revoked`, `expired` | 4401 |
   | `limit_reached`, `rate_limited` | 4429 |
   | `busy` | 4503 |

   No auth message within 10 seconds gives `invalid` with a "no access code was sent" message. A spend cap gives `limit_reached`,
   the kill switch and a code already in use give `busy`, and the all-addresses brake gives `rate_limited`, each with its own message.
4. Until auth succeeds every other message is ignored, and no speech-to-text, language-model or voice work happens.
5. If the daily limit runs out during a connection, the next `begin` gets the usual error message with code 429.
6. Sending `auth` again later, or to a server with codes switched off, just gets `{"type":"auth_result","ok":true,"label":"","limits":null}`.
7. A connection that used a code can only act on its own session: a `session_id` in its messages is ignored.

## Tests

```
.venv\Scripts\python.exe -m unittest -v test_scripts.test_access_codes test_scripts.test_cf_access
```

They use temporary files, a throwaway signing key and throwaway servers on 127.0.0.1 ports 18791-18793.
