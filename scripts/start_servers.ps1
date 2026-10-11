# Starts everything the headset app needs: Ollama (language model), AllTalk (voice) and the interview server (port 8765).
# Run:  powershell -ExecutionPolicy Bypass -File scripts\start_servers.ps1
# Stop: powershell -ExecutionPolicy Bypass -File scripts\stop_servers.ps1
$srv = Join-Path (Split-Path $PSScriptRoot -Parent) "server"   # paths are relative to this repo
$allTalk = if ($env:ALLTALK_DIR) { $env:ALLTALK_DIR } else { "PATH_TO_ALLTALK\alltalk_tts" }   # set ALLTALK_DIR per install; only needed for the XTTS engine
$ErrorActionPreference = "Continue"
$log = Join-Path $env:TEMP "vr_interview_logs"
New-Item -ItemType Directory -Force $log | Out-Null

function Port-Open($port) { [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) }

# Ollama's model folder: use the OLLAMA_MODELS user variable if set, else a default under the home folder.
$env:OLLAMA_MODELS = [Environment]::GetEnvironmentVariable("OLLAMA_MODELS", "User")
if (-not $env:OLLAMA_MODELS) { $env:OLLAMA_MODELS = "$HOME\.ollama\models" }
if (-not (Port-Open 11434)) {
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden -RedirectStandardOutput "$log\ollama.out.log" -RedirectStandardError "$log\ollama.err.log"
    "starting Ollama..."
}
# Voice engine from $srv\config\config.json: "alltalk" (XTTS, default) or "kokoro" (faster, uses much less GPU memory;
# AllTalk is then NOT started, and gTTS is the emergency fallback)
$engine = try { (Get-Content "$srv\config\config.json" -Raw | ConvertFrom-Json).engine } catch { "alltalk" }
if ($engine -ne "kokoro") {
    if (-not (Port-Open 7851)) {
        Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "$allTalk\start_alltalk.bat" -WorkingDirectory "$allTalk" -WindowStyle Hidden -RedirectStandardOutput "$log\alltalk.out.log" -RedirectStandardError "$log\alltalk.err.log"
        "starting AllTalk voice..."
    }
}
foreach ($t in 1..60) { if ((Port-Open 11434) -and (($engine -eq "kokoro") -or (Port-Open 7851))) { break }; Start-Sleep 2 }

# faster-whisper speech-to-text worker (about 4x faster than the built-in Whisper; the interview server falls back if it is down)
if (-not (Port-Open 8770)) {
    Start-Process -FilePath "$srv\.venv_fw\Scripts\python.exe" -ArgumentList "tools\stt_worker.py", "--port", "8770" -WorkingDirectory "$srv" -WindowStyle Hidden -RedirectStandardOutput "$log\stt_worker.out.log" -RedirectStandardError "$log\stt_worker.err.log"
    "starting faster-whisper worker..."
}
foreach ($t in 1..45) { if (Port-Open 8770) { break }; Start-Sleep 2 }

# Kokoro voice worker, only in "kokoro" mode
if ($engine -eq "kokoro") {
    if (-not (Port-Open 8771)) {
        Start-Process -FilePath "$srv\.venv_tts\Scripts\python.exe" -ArgumentList "tools\tts_worker.py", "--port", "8771" -WorkingDirectory "$srv" -WindowStyle Hidden -RedirectStandardOutput "$log\tts_worker.out.log" -RedirectStandardError "$log\tts_worker.err.log"
        "starting Kokoro voice worker..."
    }
    foreach ($t in 1..45) { if (Port-Open 8771) { break }; Start-Sleep 2 }
}

if (-not (Port-Open 8765)) {
    Start-Process -FilePath "$srv\.venv\Scripts\python.exe" -ArgumentList "server.py" -WorkingDirectory "$srv" -WindowStyle Hidden -RedirectStandardOutput "$log\server.out.log" -RedirectStandardError "$log\server.err.log"
    "starting interview server..."
}
foreach ($t in 1..60) { if (Port-Open 8765) { break }; Start-Sleep 2 }

"Ollama   : " + $(if (Port-Open 11434) { "up" } else { "NOT up" })
"AllTalk  : " + $(if ($engine -eq "kokoro") { "not started (Kokoro mode)" } elseif (Port-Open 7851) { "up" } else { "NOT up" })
"Voice    : " + $(if ($engine -eq "kokoro") { if (Port-Open 8771) { "up (Kokoro worker, AllTalk is the fallback)" } else { "Kokoro NOT up (AllTalk will be used)" } } else { "AllTalk (XTTS)" })
"Whisper  : " + $(if (Port-Open 8770) { "up (faster-whisper worker)" } else { "NOT up (built-in Whisper will be used)" })
"Interview: " + $(if (Port-Open 8765) { "up (ws://YOUR_PC_LAN_IP:8765, set per install)" } else { "NOT up" })
"Logs in $log . The first spoken reply is slow (about 10 s) while the voice warms up."
