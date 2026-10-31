# Downloads the Microsoft Rocketbox avatars this project uses (11 "Business" characters, about 944 MB)
# into unity/Assets/Rocketbox. Run it BEFORE the first time you open the project in Unity: the .meta files
# for these avatars are already in the repository, and Unity deletes a .meta file whose asset is missing.
# (If that happened, run `git checkout -- unity/Assets/Rocketbox` and then this script.)
#
# Rocketbox is MIT licensed: see unity/Assets/Rocketbox/LICENSE.md and third_party/Microsoft-Rocketbox-LICENSE.
# Usage:  powershell -ExecutionPolicy Bypass -File tools\get_rocketbox.ps1

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'   # Invoke-WebRequest is very slow with the progress bar on
$commit = '0943055db6ec570bcef9f2c8b41c9e5467c808f9'   # pinned upstream commit
$base = "https://raw.githubusercontent.com/microsoft/Microsoft-Rocketbox/$commit/Assets/Avatars/Professions"
$repo = Split-Path -Parent $PSScriptRoot
$dest = Join-Path $repo 'unity\Assets\Rocketbox'
$list = Join-Path $PSScriptRoot 'rocketbox_files.txt'

$failed = 0
foreach ($line in Get-Content $list) {
    if ($line -match '^\s*(#|$)') { continue }
    $parts = $line -split '\s+'
    $rel = $parts[0]; $size = [int64]$parts[1]
    $out = Join-Path $dest ($rel -replace '/', '\')
    if ((Test-Path $out) -and (Get-Item $out).Length -eq $size) { Write-Host "ok    $rel"; continue }
    New-Item -ItemType Directory -Force (Split-Path -Parent $out) | Out-Null
    Write-Host "get   $rel"
    try {
        Invoke-WebRequest -Uri "$base/$rel" -OutFile $out -UseBasicParsing
        if ((Get-Item $out).Length -ne $size) { Write-Warning "size mismatch: $rel"; $failed++ }
    } catch { Write-Warning "failed: $rel ($_)"; $failed++ }
}
if ($failed -gt 0) { Write-Error "$failed file(s) failed. Run the script again to retry." }
Write-Host 'Rocketbox avatars are in place.'
