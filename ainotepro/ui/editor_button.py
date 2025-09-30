from __future__ import annotations

from typing import Any, List, Tuple

from aqt import mw
from aqt.qt import QIcon, QAction
from aqt.editor import Editor

from .main_dialog import MainDialog


def add_ainotepro_button(buttons: List[Tuple[str, str]], editor: Editor) -> List[Tuple[str, str]]:
    def on_click() -> None:
        dlg = MainDialog(parent=mw, browser=None)
        dlg.exec()

    # Use built-in icons if custom is missing
    label = "AINotePro"
    b = editor.addButton(
        icon=None,
        cmd="ainotepro",
        func=on_click,
        tip="AINotePro: Generate AI content",
        toggle=False,
    )
    return buttons + [b]

