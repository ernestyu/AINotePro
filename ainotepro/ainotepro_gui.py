# ainotepro_gui.py

from aqt.qt import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget,
    QPushButton, QDialogButtonBox
)
from aqt.utils import openLink

from .ui.text_tab import TextTab
from .ui.tts_tab import TTSTab
from .ui.image_tab import ImageTab


class AiNoteProConfigDialog(QDialog):
    def __init__(self, parent=None, browser=None):
        super().__init__(parent)
        self.browser = browser
        self.setWindowTitle("AINotePro")
        self.resize(800, 600)

        main_layout = QVBoxLayout(self)

        # 顶部提示
        top_label = QLabel(
            '<div style="text-align:center; font-size:14px; margin: 10px 0; font-style:italic;">'
            'Enhance your Anki notes with AI-generated text, speech, and images!'
            '</div>'
            '<div style="text-align:right; font-size:11px; margin: 10px 0; font-style:italic;">'
            'AINotePro v1.0    '
            '</div>'
        )
        top_label.linkActivated.connect(openLink)
        main_layout.addWidget(top_label)

        # 多标签页
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # 三个标签页：Text / TTS / Images
        self.tabs = {
            "Text": TextTab(parent=self, browser=browser),
            "TTS": TTSTab(parent=self, browser=browser),
            "Images": ImageTab(parent=self, browser=browser),
        }

        for name, tab in self.tabs.items():
            self.tab_widget.addTab(tab, name)

        # 底部信息 + 按钮
        bottom_layout = QHBoxLayout()

        bottom_label = QLabel(
            '<p style="font-size:12px;">'
            'Found a bug or have a feature request? '
            '<a href="https://github.com/ernestyu/AINotePro/issues">Create an issue on Github</a> '
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
        self.close_button.clicked.connect(self.accept)
        self.help_button.clicked.connect(self.on_help)

        bottom_layout.addStretch()
        bottom_layout.addWidget(button_box)

        main_layout.addLayout(bottom_layout)

    def on_generate(self):
        # 根据当前标签页调用不同逻辑
        mapping = {
            0: self.tabs["Text"].on_generate_text,
            1: self.tabs["TTS"].on_generate_tts,
            2: self.tabs["Images"].on_generate_images,
        }
        fn = mapping.get(self.tab_widget.currentIndex())
        if fn:
            fn()

    def on_help(self):
        openLink("https://github.com/ernestyu/AINotePro/wiki")


def show_ainotepro_dialog(browser=None):
    dlg = AiNoteProConfigDialog(parent=None, browser=browser)
    dlg.exec()
