# Installing the app on a Meta Quest

There are two ways to use the headset app:

- **Easy:** use the project owner's server. You get the APK and a personal access code from the project owner.
- **Run it yourself:** run your own server on a Windows PC, with your own Anthropic API key or a local Ollama model, and point the app at it.

The app is for adults practising job interviews. It's practice, not therapy or career counselling.
On the project owner's server, interviews are saved there so the project can be improved; the sign-in screen and the project owner tell you this.

## Easy: the project owner's server

You need a Quest (Quest 1, 2, 3 or 3S), a USB-C cable and a computer.

1. **Get the APK and your access code** from the project owner. The code is yours only, so don't share it.
   The APK name ends in `.apk`. Check its SHA-256 checksum against the one you were sent:
   - Windows: `certutil -hashfile <file>.apk SHA256`
   - macOS or Linux: `shasum -a 256 <file>.apk`
2. **Turn on developer mode** on the headset. This needs a free Meta developer account:
   Meta Horizon app on your phone → Devices → your headset → Headset settings → Developer mode → on. Restart the headset.
3. **Sideload the APK.** Use one of these:
   - **SideQuest** (https://sidequestvr.com, the "Advanced Installer"). Connect the headset by USB and accept "Allow USB debugging" inside the headset.
     Then drag the APK onto SideQuest's "Install APK file from folder on computer" button.
   - **adb** (Android platform-tools). With the headset on USB:
     ```bash
     adb devices
     adb install -r <file>.apk
     ```
4. **Open it.** In the headset: App Library → filter "Unknown Sources" → *VRInterviewSim*. Allow the microphone when asked.
5. **Sign in.** On the first screen, point at the keys with a controller and pull the trigger to type your **access code**, then press **Connect**.
   It shows how many interviews you have left today. The code is saved on the headset, so next time you only press Connect.

If sign-in fails, the app shows why:

- the code is wrong, switched off or expired;
- no interviews are left today;
- too many wrong tries (wait about 15 minutes);
- someone else is practising right now (try again in a few minutes).

## Run it yourself: your own server

You need a Windows PC with an NVIDIA GPU (about 8 GB of video memory or more for local voice and speech-to-text) and Python 3.11 or newer.

1. Get the code and set up the server: see [`../CLAUDE.md`](../CLAUDE.md) ("Run the server") and `server/README` notes.
   For the AI interviewer, choose one:
   - **Your own Anthropic API key:** put it in the user environment variable `VRSIM_ANTHROPIC_API_KEY`. Never put it in a file in the repository.
   - **Ollama only (free, local):** install Ollama and pull a model, for example `ollama pull qwen2.5:7b-instruct`. Then switch the backend to local with `scripts\switch_llm.ps1 local`.
2. Start the server with `powershell -ExecutionPolicy Bypass -File scripts\start_servers.ps1`. It listens on port 8765.
3. Let the headset reach it:
   - **Same Wi-Fi:** use the PC's LAN address, for example `ws://192.168.0.20:8765`. You may need to allow Python through Windows Firewall on private networks.
   - **From anywhere:** use a VPN such as Tailscale, or a tunnel that gives you a `wss://` address.
4. Access codes: your server can switch them off (`"access": {"require_access_code": false}` in `server/config/config.json`), or you can make codes with `server/tools/access_codes.py`.
5. Install the APK (as above, or build it yourself, see `CLAUDE.md`). On the sign-in screen, press **Advanced** and type your server's address in the **Server address** field.
   Then type your code (any text if codes are off) and press **Connect**. Use **Default** to go back to the project owner's server.

## Uninstall

Settings → Apps → Installed apps → VRInterviewSim → Uninstall. Or run `adb uninstall com.vrforgoodofzion.vrinterviewsim`.
