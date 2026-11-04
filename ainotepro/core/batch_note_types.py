"""Read-only Note Type preflight for simple Text and Audio generation.

Only call this on Anki's collection/UI thread, before requests or writes.
Card templates are intentionally not compared: they share their Note Type's
field definition.
"""
from __future__ import annotations


def validate_batch_note_types(note_ids, get_note, required_fields=()):
    """Reject a mixed Note Type selection before any work can be committed.

    `get_note` is supplied by the caller (normally mw.col.get_note). Do not
    access Anki's collection from generation worker threads.
    """
    if not note_ids:
        raise ValueError("No notes selected.")
    expected_id = None
    expected_name = ""
    expected_fields = ()
    first_note_id = None
    for note_id in note_ids:
        try:
            note_type = get_note(note_id).note_type()
            type_id = int(note_type["id"])
            type_name = str(note_type.get("name") or type_id)
            fields = tuple(field["name"] for field in note_type["flds"])
        except Exception as exc:
            raise ValueError(
                f"Could not inspect selected note {note_id}: {exc}. "
                "No generation started."
            ) from exc
        if expected_id is None:
            expected_id, expected_name = type_id, type_name
            expected_fields, first_note_id = fields, note_id
        elif type_id != expected_id:
            raise ValueError(
                f"Selected notes use different Note Types: "
                f"'{expected_name}' (note {first_note_id}) and "
                f"'{type_name}' (note {note_id}). "
                "No generation started. Select only one Note Type and retry."
            )
        elif fields != expected_fields:
            raise ValueError(
                f"Selected notes have inconsistent field definitions "
                f"(note {note_id}). No generation started."
            )
    missing = [field for field in dict.fromkeys(required_fields)
               if field not in expected_fields]
    if missing:
        raise ValueError(
            f"Selected Note Type '{expected_name}' is missing field(s): "
            + ", ".join(repr(field) for field in missing)
            + ". No generation started. Review Source/Destination fields."
        )
    return expected_id
