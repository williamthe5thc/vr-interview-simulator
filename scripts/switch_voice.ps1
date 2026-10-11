# Switches the interviewer voice engine: Kokoro (fast, light on the GPU) or XTTS via AllTalk (the original voices).
#   powershell -ExecutionPolicy Bypass -File scripts\switch_voice.ps1 kokoro
#   powershell -ExecutionPolicy Bypass -File scripts\switch_voice.ps1 xtts     (AllTalk needs about 1.5-5.5 minutes to start)
# Refuses while a headset is connected, because the interview server restarts (add -Force to restart anyway).
param([Parameter(Mandatory=$true)][ValidateSet("kokoro","xtts")][string]$Engine, [switch]$Force)
$srv = Join-Path (Split-Path $PSScriptRoot -Parent) "server"   # paths are relative to this repo
$allTalk = if ($env:ALLTALK_DIR) { $env:ALLTALK_DIR } else { "PATH_TO_ALLTALK\alltalk_tts" }   # set ALLTALK_DIR per install; only needed for the XTTS engine
$ErrorActionPreference = "Continue"
$cfg = "$srv\config\config.json"
$log = Join-Path $env:TEMP "vr_interview_logs"
New-Item -ItemType Directory -Force $log | Out-Null
function Port-Open($port) { [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) }
function Stop-ByPattern($pattern, $label) {
    Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.ProcessId -ne $PID -and $_.CommandLine -match $pattern } |
        ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force; "stopped $label ($($_.ProcessId))" } catch {} }
}

if (-not $Force -and (Get-NetTCPConnection -LocalPort 8765 -State Established -ErrorAction SilentlyContinue)) {
    "A headset is connected to the interview server. Finish the interview first, or run again with -Force."; exit 1
}

# 1. config
$json = Get-Content $cfg -Raw | ConvertFrom-Json
$json | Add-Member -NotePropertyName engine -NotePropertyValue $(if ($Engine -eq "kokoro") { "kokoro" } else { "alltalk" }) -Force
$json | ConvertTo-Json -Depth 20 | Set-Content $cfg -Encoding UTF8
"engine set to $($json.engine)"

# 2. voice processes
if ($Engine -eq "kokoro") {
    if (-not (Port-Open 8771)) {
        Start-Process -FilePath "$srv\.venv_tts\Scripts\python.exe" -ArgumentList "tools\tts_worker.py", "--port", "8771" -WorkingDirectory "$srv" -WindowStyle Hidden -RedirectStandardOutput "$log\tts_worker.out.log" -RedirectStandardError "$log\tts_worker.err.log"
        "starting Kokoro worker..."
    }
    foreach ($t in 1..45) { if (Port-Open 8771) { break }; Start-Sleep 2 }
    Stop-ByPattern 'alltalk_tts.*(script|tts_server)\.py|^python\s+script\.py' "AllTalk (frees several GB of GPU memory)"
} else {
    Stop-ByPattern 'tts_worker\.py' "Kokoro worker"
    if (-not (Port-Open 7851)) {
        Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "$allTalk\start_alltalk.bat" -WorkingDirectory "$allTalk" -WindowStyle Hidden -RedirectStandardOutput "$log\alltalk.out.log" -RedirectStandardError "$log\alltalk.err.log"
        "starting AllTalk (this takes 1.5-5.5 minutes) ..."
    }
    foreach ($t in 1..200) { if (Port-Open 7851) { break }; Start-Sleep 2 }
}

# 3. restart the interview server so it picks the engine up
Stop-ByPattern 'vr_interview_system.*server\.py|\bserver\.py' "interview server"
Start-Sleep 2
Start-Process -FilePath "$srv\.venv\Scripts\python.exe" -ArgumentList "server.py" -WorkingDirectory "$srv" -WindowStyle Hidden -RedirectStandardOutput "$log\server.out.log" -RedirectStandardError "$log\server.err.log"
foreach ($t in 1..60) { if (Port-Open 8765) { break }; Start-Sleep 2 }
"Interview server : " + $(if (Port-Open 8765) { "up" } else { "NOT up" })
"Voice            : $Engine  (" + $(if ($Engine -eq "kokoro") { if (Port-Open 8771) { "worker up" } else { "worker NOT up" } } else { if (Port-Open 7851) { "AllTalk up" } else { "AllTalk NOT up" } }) + ")"
