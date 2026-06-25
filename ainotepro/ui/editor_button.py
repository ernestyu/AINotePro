from __future__ import annotations

from typing import List, Optional, Tuple

from aqt.editor import Editor

from ..ainotepro_gui import show_ainotepro_dialog


def _note_id_from_editor(editor: Editor) -> Optional[int]:
    note = getattr(editor, "note", None)
    if note is None:
        return None

    note_id = getattr(note, "id", None)
    if callable(note_id):
        note_id = note_id()
    if note_id:
        return int(note_id)
    return None


def add_ainotepro_button(buttons: List[Tuple[str, str]], editor: Editor) -> List[Tuple[str, str]]:
    def on_click(clicked_editor=None) -> None:
        active_editor = clicked_editor if hasattr(clicked_editor, "note") else editor
        note_id = _note_id_from_editor(active_editor)
        show_ainotepro_dialog(browser=None, note_ids=[note_id] if note_id else None)

    # Keep signature compatible across Anki versions: use positional args only.
    b = editor.addButton(None, "ainotepro", on_click, "AINotePro: Generate AI content")
    return buttons + [b]
