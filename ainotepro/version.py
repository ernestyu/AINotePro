"""Read the add-on version from Anki's authoritative manifest.json."""
from __future__ import annotations

import json
from pathlib import Path


def addon_version() -> str:
    """Return the packaged add-on version without a second hard-coded value."""
    manifest = Path(__file__).resolve().parent.parent / "manifest.json"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        version = data["version"]
        if not isinstance(version, str) or not version.strip():
            raise ValueError("Missing version")
        return version
    except (OSError, ValueError, KeyError, TypeError):
        # A broken package must not cause the settings window to crash.
        return "unknown"
