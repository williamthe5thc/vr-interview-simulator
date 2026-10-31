#!/usr/bin/env bash
# Downloads the Microsoft Rocketbox avatars this project uses (11 "Business" characters, about 944 MB)
# into unity/Assets/Rocketbox. Run it BEFORE the first time you open the project in Unity: the .meta files
# for these avatars are already in the repository, and Unity deletes a .meta file whose asset is missing.
# (If that happened, run `git checkout -- unity/Assets/Rocketbox` and then this script.)
#
# Rocketbox is MIT licensed: see unity/Assets/Rocketbox/LICENSE.md and third_party/Microsoft-Rocketbox-LICENSE.
# Usage:  bash tools/get_rocketbox.sh
set -euo pipefail

commit=0943055db6ec570bcef9f2c8b41c9e5467c808f9   # pinned upstream commit
base="https://raw.githubusercontent.com/microsoft/Microsoft-Rocketbox/$commit/Assets/Avatars/Professions"
here="$(cd "$(dirname "$0")" && pwd)"
dest="$here/../unity/Assets/Rocketbox"

filesize() { wc -c < "$1" | tr -d ' '; }

failed=0
while read -r rel size; do
  size="${size%$'\r'}"   # the list may have Windows line endings
  case "$rel" in ''|'#'*) continue ;; esac
  out="$dest/$rel"
  if [ -f "$out" ] && [ "$(filesize "$out")" = "$size" ]; then echo "ok    $rel"; continue; fi
  mkdir -p "$(dirname "$out")"
  echo "get   $rel"
  if ! curl -fsSL --retry 3 -o "$out" "$base/$rel" || [ "$(filesize "$out")" != "$size" ]; then
    echo "FAILED: $rel" >&2; failed=$((failed + 1))
  fi
done < "$here/rocketbox_files.txt"

if [ "$failed" -gt 0 ]; then echo "$failed file(s) failed. Run the script again to retry." >&2; exit 1; fi
echo "Rocketbox avatars are in place."
