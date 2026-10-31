# WebSocket protocol

The headset (and the web client) talk to the interview server over one WebSocket.
Every message is a JSON text frame with a `type` field. Audio travels inside JSON as base64.

- Headset address: whatever the player sets on the sign-in screen. The app's default is in
  `unity/Assets/AccessGate.cs` (`DefaultServer`); a self-hosted server is usually `ws://<pc-address>:8765`.
- Server code: `server/app/websocket/server_enhanced_fixed.py` (routing) and `server/app/access_codes.py` (sign-in).
- Client code: `unity/Assets/WebSocketManager.cs`.

## 1. Sign-in (access codes)

The first message after the socket opens must be `auth`. The server handles nothing else until it has answered.

Client → server:

```json
{"type": "auth", "code": "ABCD-EFGH", "client": "quest", "app_version": "0.1"}
```

- `code` is the player's own access code, typed on the sign-in screen and saved on the device (PlayerPrefs).
  It is never built into the app. The server ignores case, spaces and dashes.
- `client` is `"quest"` for the headset.

Server → client, accepted:

```json
{"type": "auth_result", "ok": true, "label": "friend name", "limits": {"interviews_per_day": 5, "remaining_today": 3}}
```

`limits` can be `null` (no daily limit, or a repeated `auth` on a connection that already signed in).

Server → client, refused (the server then closes the socket):

```json
{"type": "auth_result", "ok": false, "reason": "invalid", "message": "Plain text for the player."}
```

| reason          | close code | meaning                                                      |
|-----------------|-----------:|--------------------------------------------------------------|
| `invalid`       | 4401 | unknown code                                                         |
| `revoked`       | 4401 | the code was switched off                                            |
| `expired`       | 4401 | the code's end date has passed                                       |
| `limit_reached` | 4429 | no interviews left today for this code                               |
| `rate_limited`  | 4429 | too many wrong codes from this address; wait before trying again    |
| `busy`          | 4503 | someone else is practising (one headset session at a time for now)   |

Client rules:

- Show `message` as it is and let the player re-enter the code.
- Never retry automatically after a refusal. The player presses Connect again.
- An older server that never sends `auth_result` is used anyway after 5 seconds.
- NativeWebSocket reports the 44xx close codes as "Undefined", so the client goes by the `auth_result` message rather than the close code.
- `auth_result` arrives before `session_init`.

If the day's interviews run out during a connection, `begin` is answered with `{"type": "error", "code": 429, "message": "..."}`.
The headset shows "No interviews left today".

## 2. Session messages

### Server → client

| type | fields | notes |
|---|---|---|
| `session_init` | `session_id`, `timestamp`, `capabilities` | The client adopts this `session_id`. For an access-code session the server pins the id and ignores the one the client sends. |
| `state_update` | `previous`, `current`, `metadata` | States: `IDLE`, `LISTENING`, `PROCESSING`, `RESPONDING`, `WAITING`, `ERROR`. |
| `audio_response` | `data` (base64 WAV), `format`, `seq`, `more`, `interview_complete` | One reply can come in several chunks: `more: true` means another chunk of the same reply follows. `interview_complete: true` marks the interviewer's closing reply. |
| `visemes` | `seq`, `cues` [{`start`, `end`, `value`}] | Rhubarb mouth cues for the `audio_response` with the same `seq`. |
| `text_response` | `text` | The interviewer's reply as text (web client). |
| `server_status` | `text`, `llm`, `voice`, `restarting` | A notice about the language model or voice engine. Empty `text` means everything is fine. |
| `heartbeat` | `progress`, `message` | Sent while a reply is being prepared. The headset ignores it. |
| `export_saved` | `filename`, `questions`, `saved` | The finished interview was saved on the server (`exports/`). |
| `coach_progress` | `done`, `total` | The job-coach review is running. |
| `coach_report` | `job_label`, `company`, `summary`, `average_score`, `strengths[]`, `focus[]`, `items[]`, `attitude`, `left_early`, `coach`, `error` | `items[]` has `number`, `question`, `answer`, `went_well`, `improve`, `stronger`, `score`, `quote`, `tone`. See `unity/Assets/CoachData.cs`. |
| `pong` | | Reply to `ping`. |
| `error` | `code`, `message` | 400 = bad message, 429 = limit (see above), 503 = busy. |
| `auth_result` | see section 1 | |

### Client → server

| type | fields | notes |
|---|---|---|
| `auth` | `code`, `client`, `app_version` | Always first. See section 1. |
| `control` | `action`, `session_id`, plus `job`, `interviewer`, `voice` with `begin` | Actions below. |
| `audio_data` | `data` (base64 WAV, 16 kHz mono), `session_id` | One spoken answer, sent when push-to-talk is released. |
| `text_data` | `text` | A typed answer instead of speech (web client; same limits as speech). |
| `playback_complete` | `session_id` | The client finished playing a reply. |
| `client_capabilities` | free-form object | Optional feature flags from the client. |
| `ping` | `session_id` | Keep-alive, every 5 seconds from the headset. |

`control` actions:

| action | what it does |
|---|---|
| `start` | Announces the session after connecting (sent by SessionManager). |
| `begin` | Starts an interview: the interviewer introduces themselves and asks the first question. `job` = job id (`unity/Assets/InterviewJobs.cs`), `interviewer` = the character's name, `voice` = that character's voice. Counts one interview against the access code. |
| `reset` | Ends the current conversation. An interview that actually happened is saved to `exports/` first (`export_saved`). |
| `stop` | Stops the reply being generated. |
| `coach` | Runs the job-coach review of the last finished interview (`coach_progress`, then `coach_report`). |
| `timeout` | The client went idle. The server only logs it. |
| `say` | Dev and test only: one candidate turn from `text`. It's ignored for web sessions, and the headset never sends it. |
| `ping` | Same as the `ping` message. |

## 3. A normal headset session

```
open socket
→ auth                         ← auth_result ok        (or refused + close)
                               ← session_init
→ control start
→ control begin (job, interviewer, voice)
                               ← state_update ... ← audio_response (seq 0, more) ← visemes (seq 0) ...
→ playback_complete
→ audio_data (answer)          ← state_update PROCESSING ← heartbeat ... ← audio_response ...
   ... repeat ...
                               ← audio_response (interview_complete: true)
→ control reset                ← export_saved
→ control coach                ← coach_progress ... ← coach_report
```
