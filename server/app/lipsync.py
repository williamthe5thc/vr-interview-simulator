"""Mouth-shape timelines for the interviewer's voice, using Rhubarb Lip Sync (MIT licence).

analyze_wav() runs Rhubarb in its fast "phonetic" mode (about 4x faster than real time on this PC; the default
pocketSphinx mode needs 2-3x the clip length) and returns a compact cue list:
    [{"s": start_seconds, "e": end_seconds, "v": "A".."H" | "X"}, ...]
Shapes: A closed lips (P B M), B teeth together (K S T, EE), C open (EH), D wide open (AA), E rounded (AO ER),
F puckered (OO W), G teeth on lip (F V), H tongue up (L), X rest.
"""
import json
import logging
import os
import subprocess
import tempfile

logger = logging.getLogger("lipsync")

RHUBARB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "tools", "rhubarb", "Rhubarb-Lip-Sync-1.14.0-Windows", "rhubarb.exe")


def available() -> bool:
    return os.path.exists(RHUBARB)


def analyze_wav(wav_bytes: bytes, timeout: float = 20.0):
    """Blocking (run it in a thread). Returns the cue list, or None if analysis is unavailable or failed."""
    if not available() or not wav_bytes:
        return None
    path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(wav_bytes)
            path = f.name
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        out_path = path + ".json"   # Rhubarb prints nothing to the console with --quiet, so ask for a file
        result = subprocess.run(
            [RHUBARB, path, "-r", "phonetic", "-f", "json", "--extendedShapes", "GHX", "--quiet", "-o", out_path],
            capture_output=True, timeout=timeout, creationflags=flags)
        if result.returncode != 0:
            logger.warning(f"Rhubarb failed ({result.returncode}): {result.stderr[:200]!r}")
            return None
        with open(out_path, encoding="utf-8") as f:
            cues = json.load(f).get("mouthCues", [])
        return [{"s": round(c["start"], 3), "e": round(c["end"], 3), "v": c["value"]} for c in cues]
    except Exception as e:
        logger.warning(f"Lip-sync analysis failed: {e}")
        return None
    finally:
        for leftover in ([path, path + ".json"] if path else []):
            try:
                os.remove(leftover)
            except OSError:
                pass
