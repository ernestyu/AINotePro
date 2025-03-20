# ainotepro_gui.py

from aqt.qt import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget, QWidget,
    QPushButton, QDialogButtonBox, QSpacerItem, QSizePolicy
)
from aqt.utils import openLink
from aqt import mw

# 导入各个子模块
from .gen_text.text_gui import TextTab
from .gen_audio.tts_gui import TTSTab  # 假设 TTS 界面逻辑在 tts_gui.py
from .gen_image.image_gui import ImageTab  # 假设 Images 界面逻辑在 image_gui.py

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

        # 创建多标签页
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # 初始化各个 Tab 界面
        self.tabs = {
            "Text": TextTab(parent=self, browser=browser),
            "TTS": TTSTab(parent=self, browser=browser),
            "Images": ImageTab(parent=self, browser=browser),
        }

        for name, tab in self.tabs.items():
            self.tab_widget.addTab(tab, name)

        # 重新定义底部按钮
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

        main_layout.addWidget(button_box)

        # 底部信息
        bottom_label = QLabel(
            '<p style="font-size:12px;">'
            'Found a bug or have a feature request? '
            '<a href="https://github.com/your-repo/ainotepro/issues">Create an issue on Github</a> '
            '</p>'
        )
        bottom_label.linkActivated.connect(openLink)
        main_layout.addWidget(bottom_label)

    def on_generate(self):
        """根据当前选中的标签页调用不同的生成逻辑"""
        tab_mapping = {
            0: self.tabs["Text"].on_generate_text,  # ✅ 调用实例对象的方法
            1: self.tabs["TTS"].on_generate_tts,  # ✅ 调用实例对象的方法
            2: self.tabs["Images"].on_generate_images,  # ✅ 调用实例对象的方法
        }
        action = tab_mapping.get(self.tab_widget.currentIndex())
        if action:
            action()  # ✅ 正确调用，无需额外的 self 参数

    def on_help(self):
        """打开帮助页面"""
        openLink("https://github.com/your-repo/ainotepro/wiki")

def show_ainotepro_dialog(browser=None):
    """ Shows AINotePro dialog """
    dialog = AiNoteProConfigDialog(parent=None, browser=browser)
    dialog.exec()

