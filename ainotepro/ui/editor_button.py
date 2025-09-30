from __future__ import annotations

from typing import List, Tuple

from aqt import mw
from aqt.editor import Editor

# Open the original tabbed dialog to preserve layout
from ..ainotepro_gui import show_ainotepro_dialog


def add_ainotepro_button(buttons: List[Tuple[str, str]], editor: Editor) -> List[Tuple[str, str]]:
    def on_click() -> None:
        show_ainotepro_dialog(browser=None)

    # Keep signature compatible across Anki versions: use positional args only.
    b = editor.addButton(None, "ainotepro", on_click, "AINotePro: Generate AI content")
    return buttons + [b]

