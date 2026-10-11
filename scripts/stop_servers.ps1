# Stops the interview server, the AllTalk voice and Ollama, freeing the GPU (about 9-10 GB) and CPU for other work.
# Run:  powershell -ExecutionPolicy Bypass -File scripts\stop_servers.ps1
$srv = Join-Path (Split-Path $PSScriptRoot -Parent) "server"   # paths are relative to this repo
function Stop-Matching($pattern, $label) {
    $procs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -match $pattern }
    foreach ($p in $procs) { try { Stop-Process -Id $p.ProcessId -Force; "stopped $label ($($p.ProcessId))" } catch {} }
}
Stop-Matching 'vr_interview_system.*server\.py|\bserver\.py' "interview server"
Stop-Matching 'stt_worker\.py' "faster-whisper worker"
Stop-Matching 'rating_server\.py' "blind rating page server"
Stop-Matching 'tts_worker\.py|kokoro_server\.py' "extra voice engine (Kokoro/Piper worker)"
Stop-Matching 'alltalk_tts.*(script|tts_server)\.py|^python\s+script\.py' "AllTalk"
foreach ($n in "ollama", "ollama_llama_server", "ollama app") {
    Get-Process -Name $n -ErrorAction SilentlyContinue | ForEach-Object { try { Stop-Process -Id $_.Id -Force; "stopped $n ($($_.Id))" } catch {} }
}
Start-Sleep 2
foreach ($port in 8765, 8770, 8771, 8780, 7851, 7852, 11434) {
    "port $port : " + $(if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) { "STILL LISTENING" } else { "free" })
}
