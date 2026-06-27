from __future__ import annotations

from typing import Optional
from aqt import mw


def add_binary_to_media_collection(data: bytes, filename_hint: str) -> str:
    """Write binary data into Anki media and return the stored filename.

    Uses Anki's media manager to avoid duplicates and ensure correct hashing.
    """
    if not data:
        raise ValueError("No data to save to media collection")
    media = mw.col.media
    if hasattr(media, "write_data"):
        stored_name = media.write_data(filename_hint, data)
    else:
        stored_name = media.writeData(filename_hint, data)
    return stored_name


def add_image_to_media_collection(image_data: bytes, filename_hint: str = "generated.png") -> str:
    return add_binary_to_media_collection(image_data, filename_hint)


def add_audio_to_media_collection(audio_data: bytes, filename_hint: str = "generated.mp3") -> str:
    return add_binary_to_media_collection(audio_data, filename_hint)


def get_field_content(note, field_name: str, default: str = "") -> str:
    """Safely read a note field, returning a default when the field is missing or None."""
    if field_name in note:
        val = note[field_name]
        return val if val is not None else default
    return default


def update_field_content(note, field_name: str, content: str) -> None:
    if field_name not in note:
        raise KeyError(f"Field '{field_name}' not found in note")
    note[field_name] = content
    note.col.update_note(note)


def create_undo_checkpoint(label: str) -> None:
    """Best-effort undo checkpoint for direct note edits."""
    checkpoint = getattr(mw, "checkpoint", None)
    if callable(checkpoint):
        try:
            checkpoint(label)
        except Exception as e:
            print(f"[AINotePro] Failed to create undo checkpoint: {e}")
