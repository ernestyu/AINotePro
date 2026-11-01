"""Main tabbed dialog (Text / Audio)."""

from aqt.qt import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget,
    QPushButton, QDialogButtonBox
)
from aqt.utils import openLink

from .ui.text_tab import TextTab
from .ui.tts_tab import TTSTab


class AiNoteProConfigDialog(QDialog):
    def __init__(self, parent=None, browser=None, note_ids=None, editor=None):
        super().__init__(parent)
        self.browser = browser
        self.note_ids = list(note_ids or [])
        self.editor = editor
        self.setWindowTitle("AINotePro — v1.0.0")
        # Audio V2 has three voice blocks and an inline Profile editor.
        # Give them one full page without introducing an Audio scroll area.
        self.resize(1000, 700)
        self.setMinimumSize(870, 610)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 6, 10, 6)
        main_layout.setSpacing(5)

        # Tabs
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        self.tabs = {
            "Text": TextTab(parent=self, browser=browser, note_ids=self.note_ids, editor=editor),
            "Audio": TTSTab(parent=self, browser=browser, note_ids=self.note_ids, editor=editor),
        }
        for name, tab in self.tabs.items():
            self.tab_widget.addTab(tab, name)

        # Bottom info + buttons
        bottom_layout = QHBoxLayout()
        bottom_label = QLabel(
            '<p style="font-size:12px; margin:0;">'
            'Enjoying AINotePro? '
            '<a href="https://github.com/ernestyu/AINotePro">Star it on GitHub</a> '
            '</p>'
        )
        bottom_label.linkActivated.connect(openLink)
        bottom_layout.addWidget(bottom_label)

        button_box = QDialogButtonBox()
        self.generate_button = QPushButton("Generate")
        self.close_button = QPushButton("Close")
        self.help_button = QPushButton("Help")
        button_box.addButton(self.generate_button, QDialogButtonBox.ButtonRole.AcceptRole)
        button_box.addButton(self.close_button, QDialogButtonBox.ButtonRole.RejectRole)
        button_box.addButton(self.help_button, QDialogButtonBox.ButtonRole.HelpRole)

        self.generate_button.clicked.connect(self.on_generate)
        self.close_button.clicked.connect(self._on_close)
        self.help_button.clicked.connect(self.on_help)

        bottom_layout.addStretch()
        bottom_layout.addWidget(button_box)
        main_layout.addLayout(bottom_layout)
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

    def _on_tab_changed(self, *_):
        if self.tab_widget.currentWidget() is self.tabs["Audio"]:
            self.tabs["Audio"]._refresh_availability()
        else:
            self.generate_button.setEnabled(True)

    def on_generate(self):
        current_tab = self.tab_widget.currentWidget()
        fn = None
        for handler_name in ("on_generate_text", "on_generate_tts"):
            candidate = getattr(current_tab, handler_name, None)
            if callable(candidate):
                fn = candidate
                break
        if fn:
            fn()

    def _on_close(self):
        if self._prepare_dialog_close():
            self.accept()

    def reject(self):
        if self._prepare_dialog_close():
            super().reject()

    def closeEvent(self, event):
        # macOS title-bar close must persist the same Text settings as Close/Esc.
        if self._prepare_dialog_close():
            event.accept()
        else:
            event.ignore()

    def _prepare_dialog_close(self):
        """Use one close gate for Close, Esc and title-bar destruction.

        Prompt confirmation and Audio's own draft guard happen before a Text
        task is marked closing. Settings are saved synchronously next; only
        after all three checks pass do we cancel callbacks and allow Qt to
        destroy the tab.
        """
        text = self.tabs["Text"]
        if not text.can_close():
            return False
        if not self.tabs["Audio"].can_close():
            return False
        if not text.save_settings():
            return False
        return text.prepare_close(confirmed=True)

    def on_help(self):
        openLink("https://github.com/ernestyu/AINotePro/wiki")


def show_ainotepro_dialog(browser=None, note_ids=None, editor=None):
    dlg = AiNoteProConfigDialog(parent=None, browser=browser, note_ids=note_ids, editor=editor)
    dlg.exec()
