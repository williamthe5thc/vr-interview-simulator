# Choose the coach that reviews a finished interview. Takes effect at the next coach review; no restart needed.
#   .\switch_coach.ps1 legacy      # the original coach (one call per answer, template "try saying", local model or Haiku)
#   .\switch_coach.ps1 v2          # the redesigned coach on Claude Haiku 5.5
#   .\switch_coach.ps1 v2-sonnet   # the redesigned coach on Claude Sonnet 5.5 (higher quality, a few cents more)
#   .\switch_coach.ps1             # show the current setting
param([ValidateSet("legacy", "v2", "v2-sonnet", "")][string]$Mode = "")
$srv = Join-Path (Split-Path $PSScriptRoot -Parent) "server"   # paths are relative to this repo
$file = "$srv\config\coach_mode.txt"
if ($Mode) { Set-Content -Path $file -Value $Mode -Encoding ascii }
$now = if (Test-Path $file) { (Get-Content $file -Raw).Trim() } else { "legacy (no file)" }
Write-Host "Coach mode: $now  (v2 modes need the anthropic backend and fall back to legacy otherwise)"
