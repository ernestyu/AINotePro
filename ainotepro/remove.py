from aqt.qt import (
    QDialog, QVBoxLayout, QLabel, QComboBox, QPushButton, QHBoxLayout, QMessageBox, Qt
)
from aqt import mw
from aqt.utils import showWarning, showInfo


class RemoveDialog(QDialog):
    """窗口：选择要清除的字段"""

    def __init__(self, parent=None, browser=None):
        super().__init__(parent)
        self.browser = browser
        self.setWindowTitle("Remove Field Content")
        self.resize(400, 150)

        layout = QVBoxLayout(self)

        # **标题（加大字体、加粗、居中）**
        self.title_label = QLabel("<div style='font-size:18px; font-weight:bold; text-align:center;'>"
                                  "Remove field's content from selected Notes.</div>")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # ✅ 居中对齐
        layout.addWidget(self.title_label)

        # **Destination Field 选择**
        field_layout = QHBoxLayout()
        self.field_label = QLabel("Destination Field:")
        self.field_combo = QComboBox()
        field_layout.addWidget(self.field_label)
        field_layout.addWidget(self.field_combo)
        layout.addLayout(field_layout)

        # **按钮行**
        button_layout = QHBoxLayout()
        self.remove_button = QPushButton("Remove")
        self.cancel_button = QPushButton("Quit")

        button_layout.addWidget(self.remove_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

        # **加载当前选中 Notes 的字段**
        self.load_fields_from_selected_note()

        # **绑定事件**
        self.remove_button.clicked.connect(self.confirm_and_remove)
        self.cancel_button.clicked.connect(self.reject)

    def load_fields_from_selected_note(self):
        """
        读取当前选中的 Note 的字段名，并填充 Destination Field 下拉框。
        """
        if not self.browser:
            showWarning("Browser instance not found.")
            return

        selected_notes = self.browser.selectedNotes()
        if not selected_notes:
            showWarning("No notes selected.")
            return

        first_note_id = selected_notes[0]
        note = mw.col.get_note(first_note_id)

        if not note:
            showWarning(f"Failed to retrieve Note ID {first_note_id}.")
            return

        field_names = list(note.keys())

        # 清空并填充下拉框
        self.field_combo.clear()
        self.field_combo.addItems(field_names)

    def confirm_and_remove(self):
        """
        弹出确认窗口，并在用户确认后清除选定字段内容。
        """
        destination_field = self.field_combo.currentText()

        if not destination_field:
            showWarning("Please select a Destination Field.")
            return

        # ✅ **修正 PyQt6 兼容性**
        confirm = QMessageBox.question(
            self,
            "Confirm Removal",
            f"Are you sure you want to remove content from '{destination_field}' in selected notes?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if confirm == QMessageBox.StandardButton.No:
            return

        self.remove_field_content(destination_field)

    def remove_field_content(self, field_name):
        """
        清除选定的字段内容。
        """
        selected_notes = self.browser.selectedNotes()
        if not selected_notes:
            showWarning("No notes selected.")
            return

        count = 0
        for note_id in selected_notes:
            note = mw.col.get_note(note_id)
            if field_name in note:
                note[field_name] = ""  # ✅ 清空字段内容
                note.flush()
                count += 1

        mw.reset()
        showInfo(f"Removed content from '{field_name}' in {count} notes.")

        # ✅ **不关闭窗口，而是刷新 UI，用户可以继续删除其他字段**
        self.load_fields_from_selected_note()
