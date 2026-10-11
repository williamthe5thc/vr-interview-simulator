# Choose the language model for the parent-child server (port 8766) ONLY; the interview server (8765) has its own switch (switch_llm.ps1).
# Takes effect on the next reply, no restart. The coach follows it: local = qwen2.5:7b on this PC, anthropic = Claude (Haiku, or Sonnet if coach_mode says v2-sonnet).
#   .\switch_pc_llm.ps1 local        # default while prototyping
#   .\switch_pc_llm.ps1 anthropic
#   .\switch_pc_llm.ps1              # show the current setting
param([ValidateSet("local", "anthropic", "")][string]$Backend = "")
$srv = Join-Path (Split-Path $PSScriptRoot -Parent) "server"   # paths are relative to this repo
$file = "$srv\config\pc_llm_backend.txt"
if ($Backend) { Set-Content -Path $file -Value $Backend -Encoding ascii }
$now = if (Test-Path $file) { (Get-Content $file -Raw).Trim() } else { "local (no file)" }
Write-Host "Parent-child LLM backend: $now"
