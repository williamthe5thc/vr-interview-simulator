# Switch the interviewer's brain between the hosted Claude Haiku 5.5 (Anthropic API) and the local Ollama model.
# Takes effect on the NEXT reply; no server restart needed. Nothing here touches the API key.
#
#   .\switch_llm.ps1 anthropic    # hosted Claude Haiku 5.5 (costs cents per interview)
#   .\switch_llm.ps1 local        # back to the local model (qwen2.5:7b-instruct on this PC)
#   .\switch_llm.ps1              # show the current setting
param([ValidateSet("anthropic", "local", "")][string]$Backend = "")
$srv = Join-Path (Split-Path $PSScriptRoot -Parent) "server"   # paths are relative to this repo
$file = "$srv\config\llm_backend.txt"
if ($Backend) { Set-Content -Path $file -Value $Backend -Encoding ascii }
$now = if (Test-Path $file) { (Get-Content $file -Raw).Trim() } else { "local (no file)" }
Write-Host "LLM backend: $now"
if ($now -eq "anthropic") {
    $has = [bool][Environment]::GetEnvironmentVariable("VRSIM_ANTHROPIC_API_KEY", "User")
    Write-Host "API key present in user environment: $has  (if False, replies silently stay on the local model)"
}
