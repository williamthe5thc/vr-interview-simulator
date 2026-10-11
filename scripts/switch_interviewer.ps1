# Switch how the interviewer is written while the hosted model (Claude Haiku 5.5) is on. Takes effect at the NEXT interview (the next `begin`);
# an interview that is running keeps the mode it started with. No server restart needed.
#   .\switch_interviewer.ps1 judgement   # the new prompt: warm opening, real follow-ups, human reactions, next steps at the close
#   .\switch_interviewer.ps1 scripted    # the earlier scripted behaviour (forced topics, fixed lines), also what the local model always uses
#   .\switch_interviewer.ps1             # show the current setting
param([ValidateSet("judgement", "scripted", "")][string]$Mode = "")
$srv = Join-Path (Split-Path $PSScriptRoot -Parent) "server"   # paths are relative to this repo
$file = "$srv\config\interviewer_mode.txt"
if ($Mode) { Set-Content -Path $file -Value $Mode -Encoding ascii }
$now = if (Test-Path $file) { (Get-Content $file -Raw).Trim() } else { "scripted (no file)" }
Write-Host "Interviewer mode: $now"
$be = (Get-Content "$srv\config\llm_backend.txt" -Raw -ErrorAction SilentlyContinue)
Write-Host "LLM backend: $($be.Trim())  (judgement only applies while the backend is anthropic; the local model always uses the scripted prompt)"
