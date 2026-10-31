# CLAUDE.md: working on the VR Interview Simulator

Instructions for Claude Code (and people) working in this repository.

## What this is

- `unity/`: the Meta Quest app (Unity 2022.3.7f1, Built-in render pipeline, Oculus XR plugin, XR Interaction Toolkit 2.4.3).
  It's a VR job-interview practice room: an AI interviewer asks spoken questions, and a job coach reviews the answers.
- `server/`: the Python interview server (WebSocket, port 8765). It handles speech-to-text, the interviewer LLM, text-to-speech, lip-sync cues, interview export and the job coach.
- `scripts/`: PowerShell start, stop and switch scripts for the server.
- `tools/`: the Rocketbox download scripts and the Blender scripts that made the room props.
- `docs/PROTOCOL.md`: every WebSocket message. `docs/INSTALL_QUEST.md`: installing on a headset.

## Rules (read first)

1. **No secrets in builds or commits.** API keys live only in user environment variables (`VRSIM_ANTHROPIC_API_KEY`, optionally `DEEPINFRA_API_KEY`).
   Never print them, log them, put them in `config.json`, in Unity assets or in git.
   Access codes are typed by each player on the headset and saved on that device. Never build a code into the APK.
   Before any commit, search the diff for `sk-ant`, `api_key`, `passcode`, real IP addresses and e-mail addresses.
   Before you share an APK, search its strings too (unzip it and grep `assets/bin/Data/Managed/Metadata/global-metadata.dat` and the `.so` files).
2. **Never delete anything in `server/exports/`.** Saved interviews are real people's practice sessions. Tests must write to a temporary folder (`VR_EXPORT_DIR`).
3. **Adults only.** Interviewer avatars must be adults (the Rocketbox "Business" characters). Don't add child or teen avatars to this app.
4. **Practice, not therapy.** This is interview practice. Don't make clinical, therapeutic or hiring-outcome claims in the app, the prompts or the docs.
5. Don't commit third-party assets you aren't allowed to redistribute (Unity Asset Store packs, Rocketbox payload). See "Avatars and store assets".
6. Only one Unity process may use the project at a time. Close the Editor before running a batch build.

## Set up (first time)

1. Install **Unity 2022.3.7f1** with **Android Build Support** (including OpenJDK and Android SDK & NDK) from Unity Hub.
2. Install **Git LFS** (`git lfs install`). Then clone, or run `git lfs pull` in an existing clone.
3. **Download the avatars before you open Unity:**
   - Windows: `powershell -ExecutionPolicy Bypass -File tools\get_rocketbox.ps1`
   - macOS or Linux: `bash tools/get_rocketbox.sh`
   This puts about 944 MB of Microsoft Rocketbox files (MIT) into `unity/Assets/Rocketbox`, next to the `.meta` files that are already committed.
   If Unity was opened first, it deleted those `.meta` files. Fix it with `git checkout -- unity/Assets/Rocketbox`, then run the script again.
4. Open `unity/` in Unity Hub. The first import takes a while.

### Avatars and store assets

- **Rocketbox** (MIT) is downloaded by the script above. The licence is in `unity/Assets/Rocketbox/LICENSE.md` and `third_party/`.
- The scene also refers to two **Unity Asset Store** packs that the licence doesn't let us redistribute: *Stylized Customizable Avatar* (Sunbox Games, folder `Assets/SunboxGames`) and *Office Props Softpack* (nappin, folder `Assets/nappin`, one mug).
  The app builds and runs without them. They only appear as missing references on an old hidden placeholder avatar and one prop.
  The code finds the Sunbox components by name, so it compiles either way. If you own the packs, import them from the Package Manager ("My Assets") and the references come back.

## Build the Quest APK

The baked conference scene is committed (`unity/Assets/Scenes/VRInterviewScene_Conference.unity` plus its lightmaps), so a build doesn't need a re-bake.

Batch build (Windows, Editor closed):

```powershell
& "C:\Program Files\Unity\Hub\Editor\2022.3.7f1\Editor\Unity.exe" -batchmode -quit -projectPath unity `
  -executeMethod QuestBuild.BuildConference -logFile "$env:TEMP\questbuild.log"
```

- Output: `unity/Builds/VRInterviewSim_Conference.apk`, about 200 MB, package `com.vrforgoodofzion.vrinterviewsim`.
- Success line in the log: `[QuestBuild] result=Succeeded`. The script is `unity/Assets/Editor/QuestBuild.cs`.
- **First build after a fresh clone:** Unity skips the Oculus plugin's manifest step on the very first build of a new `Library/`, so the APK would lack the Quest entries and keep a BLUETOOTH permission.
  `QuestBuild` checks the finished APK, deletes a wrong one and exits with code 1 ("manifest check FAILED ... run the same command again").
  Run the same command a second time; it then passes ("manifest check passed").
- Check the APK: `<Unity>\Editor\Data\PlaybackEngines\AndroidPlayer\SDK\build-tools\<ver>\aapt.exe dump badging <apk>`. It must list INTERNET and RECORD_AUDIO.
- The APK is signed with your machine's Android debug key. A headset that has an APK from another machine must uninstall it first (`adb uninstall com.vrforgoodofzion.vrinterviewsim`).
- After adding or deleting `.cs` files, delete `unity/Library/Bee` and `unity/Library/ScriptAssemblies` if the compile shows bogus CS0103 or CS0246 errors.

Rebuilding the scene (only after changing the room, cast or UI builder) runs `-executeMethod ConferenceInterviewSceneBuilder.Build` (it bakes the lighting, about 10 minutes), then the build above.
The builder copies `Assets/VRInterviewScene.unity` and adds everything in code: `ConferenceRoomBuilder`, the Rocketbox cast, and the UI.

Test the sign-in screen without a headset:
- Start a mock or real server on `127.0.0.1`.
- Run `-batchmode -projectPath unity -executeMethod AccessGateTest.Run -agtPort <port> -agtLegacyPort <port2>`, without `-quit`.
- The mock must answer the codes listed in `Assets/Editor/AccessGateTest.cs`.

### Where things are in the client

- `AccessGate.cs`: the first screen (access code, server address behind "Advanced", Connect). `DefaultServer` is the one place the default address lives.
- `WebSocketManager.cs`: the socket, sign-in, reconnects and message routing. `InterviewFlow.cs`: title screen, interview, ending, coach.
- `PushToTalk.cs` / `AudioManager.cs`: microphone and playback. `InterviewerFace/Gaze/Body.cs`: lip-sync, eyes and body. `CoachPanel.cs`: coach report pages.

## Run the server

Windows PC, Python 3.11 or newer, an NVIDIA GPU for local speech-to-text and voice. From `server/`:

1. `python -m venv .venv` then `.venv\Scripts\pip install -r requirements.txt`. The optional workers have their own venvs:
   - `.venv_fw` with `requirements-stt-worker.txt` (faster-whisper);
   - `.venv_tts` with `requirements-tts-worker.txt` (Kokoro).
2. `copy config\config_example.json config\config.json` and edit it. `config.json` is git-ignored: keep local values there, never keys.
3. Choose the interviewer model:
   - **Hosted (Anthropic):** set your own key as a *user* environment variable `VRSIM_ANTHROPIC_API_KEY`, then `scripts\switch_llm.ps1 anthropic`.
   - **Local (Ollama):** install Ollama, `ollama pull qwen2.5:7b-instruct`, then `scripts\switch_llm.ps1 local`. This is free and needs no key.
   The switch scripts write small git-ignored files in `server/config/` (`llm_backend.txt`, `interviewer_mode.txt`, `coach_mode.txt`). The server reads them at each interview, with no restart.
4. Start everything: `powershell -ExecutionPolicy Bypass -File scripts\start_servers.ps1`. Stop: `scripts\stop_servers.ps1`. Logs go to `%TEMP%\vr_interview_logs`.
5. **Access codes** (full guide: [`server/docs/ACCESS_CODES.md`](server/docs/ACCESS_CODES.md)). Running your own server means
   `"access": {"require_access_code": true}` in `config.json` **plus your own codes**. With an empty codes file every headset is refused, your own included.
   - Make a code: `.venv\Scripts\python.exe tools\access_codes.py add "Name" --per-day 5`. It's printed once; only a salted hash is stored in `config/access_codes.json` (git-ignored).
   - `list`, `revoke "Name"`, `usage`, and `disable` / `enable` (kill switch: the file `config/quest_disabled`). No restart is needed.
   - Daily limits, spend caps per code and overall, and wrong-code lockouts live in `data/access_state.json` (git-ignored).
   - Behind a tunnel or reverse proxy, add that host's address to `access.trusted_proxies` so the server sees the real client address.
     `cf_team_domain` / `cf_access_aud` let Cloudflare Access web sessions skip the code; leave them empty if you don't use Access.
   - `require_access_code: false` is the old open behaviour. Use it only on a private network.
6. **Restart rule:** before restarting a live server, check that port 8765 has no open connections, and tell the people using it.

Server tests: `python -m pytest test_scripts -q` (set `VR_EXPORT_DIR` to a temporary folder first).

## Before you commit or share

- [ ] `git diff --cached` has no keys, codes, real IP addresses, e-mail addresses or personal paths.
- [ ] Nothing from `server/exports`, `server/data`, `server/logs` or `server/config/*.json` (except `config_example.json`).
- [ ] The APK was built from a clean tree, and its SHA-256 is written down next to it.
- [ ] Pushing, publishing a release, or installing on someone's headset needs the project owner's explicit OK.
