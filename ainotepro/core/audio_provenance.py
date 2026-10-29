"""Conservative, versioned ownership index for generated Anki sound references."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
import threading
from datetime import datetime, timezone

from ..config.manager import USER_FILES_DIR

PATH = os.path.join(USER_FILES_DIR, "audio_provenance_v1.json")
_LOCK = threading.RLock()


def _key(note_id, field, sound_tag):
    return json.dumps([int(note_id), str(field), str(sound_tag)], ensure_ascii=False)


def read_index():
    if not os.path.exists(PATH):
        return {"schema_version": 1, "entries": {}}
    with open(PATH, "r", encoding="utf-8") as stream:
        data = json.load(stream)
    if data.get("schema_version") != 1 or not isinstance(data.get("entries"), dict):
        raise ValueError("Unsupported audio provenance index; Replace disabled")
    return data


def record(note_id, field, filename, data, provider):
    """Atomic index update after Anki note commit. Never changes the note."""
    tag = f"[sound:{filename}]"
    entry = {
        "schema_version": 1, "note_id": int(note_id),
        "destination_field": field, "media_filename": filename,
        "media_sha256": hashlib.sha256(data).hexdigest(),
        "sound_tag": tag, "provider": provider,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with _LOCK:
        index = read_index()
        index["entries"][_key(note_id, field, tag)] = entry
        os.makedirs(USER_FILES_DIR, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".provenance-", suffix=".json", dir=USER_FILES_DIR)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(index, stream, indent=2, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp, PATH)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    return entry


def owned_tag(note_id, field, html, media_dir):
    """Return an exactly verified managed tag, otherwise None (never infer ownership)."""
    with _LOCK:
        try:
            entries = copy.deepcopy(read_index()["entries"])
        except (OSError, ValueError, json.JSONDecodeError):
            return None
    candidates = []
    for entry in entries.values():
        if not isinstance(entry, dict):
            continue
        if entry.get("note_id") != int(note_id) or entry.get("destination_field") != field:
            continue
        tag, filename = entry.get("sound_tag"), entry.get("media_filename")
        if not isinstance(tag, str) or not isinstance(filename, str):
            continue
        if tag != f"[sound:{filename}]" or html.count(tag) != 1:
            continue
        if os.path.basename(filename) != filename:
            continue
        path = os.path.join(media_dir, filename)
        try:
            with open(path, "rb") as stream:
                digest = hashlib.sha256(stream.read()).hexdigest()
        except OSError:
            continue
        if digest == entry.get("media_sha256"):
            candidates.append(tag)
    return candidates[0] if len(candidates) == 1 else None
