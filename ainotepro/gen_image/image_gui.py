# image_gui.py

from aqt.qt import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QComboBox,
    QLineEdit, QToolButton, QFrame, Qt, QImage, QProgressDialog
)

from aqt.utils import showInfo
from aqt import mw
import importlib.util
import os
import time
import random

class ImageTab(QWidget):
    def __init__(self, parent=None, browser=None):
        super().__init__(parent)
        self.browser = browser
        self.setMinimumWidth(900)
        self.setMinimumHeight(550)

        self.password_shown = False  # 追踪密码显示状态
        self.supports_customization = {"base_url": False, "api_key": False, "model": False}  # 默认禁用

        if hasattr(QLineEdit, "EchoMode"):  # PyQt6 及以上
            self._NORMAL_MODE = QLineEdit.EchoMode.Normal
            self._PASSWORD_MODE = QLineEdit.EchoMode.Password
        else:  # PyQt5
            self._NORMAL_MODE = QLineEdit.Normal
            self._PASSWORD_MODE = QLineEdit.Password

        # 初始化 UI
        self.setup_ui()

        # **初始化默认模型 Pollinations**
        self.set_default_model()

        # **加载当前选中的 Note 的字段**
        self.load_fields_from_selected_note()

    def setup_ui(self):
        """设置 UI 布局"""
        layout = QVBoxLayout(self)

        # **标题**
        self.title_label = QLabel(
            '<div style="font-size:14px; font-weight:bold; font-style:italic;">'
            'Insert AI-generated images into the selected note'
            '</div>'
        )
        layout.addWidget(self.title_label)

        # 分隔线
        self.separator_line = QFrame()
        self.separator_line.setFrameShape(getattr(QFrame, "Shape", QFrame).HLine)
        self.separator_line.setFrameShadow(getattr(QFrame, "Shadow", QFrame).Sunken)
        layout.addWidget(self.separator_line)

        # **生成方式 (Generate using)**
        generate_layout = QHBoxLayout()
        self.generate_label = QLabel("Generate using")  # ✅ 修正：确保该变量被定义
        generate_layout.addWidget(self.generate_label)

        self.generate_combo = QComboBox()
        self.generate_combo.addItems(["Pollinations", "Open AI", "Stable Diffusion"])
        self.generate_combo.currentIndexChanged.connect(self.on_model_change)
        generate_layout.addWidget(self.generate_combo)
        layout.addLayout(generate_layout)

        # **Base URL**
        base_url_layout = QHBoxLayout()
        self.base_url_label = QLabel("Base URL")
        base_url_layout.addWidget(self.base_url_label)

        self.base_url_edit = QLineEdit()
        self.base_url_edit.setPlaceholderText("Enter API base URL...")
        base_url_layout.addWidget(self.base_url_edit)
        layout.addLayout(base_url_layout)

        # **API Key + 显示/隐藏按钮**
        api_key_layout = QHBoxLayout()
        self.api_key_label = QLabel("API Key")
        api_key_layout.addWidget(self.api_key_label)

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(self._PASSWORD_MODE)

        self.toggle_password_button = QToolButton()
        self.toggle_password_button.setText("🔒")
        self.toggle_password_button.clicked.connect(self.toggle_password_visibility)

        api_key_layout.addWidget(self.api_key_edit)
        api_key_layout.addWidget(self.toggle_password_button)
        layout.addLayout(api_key_layout)

        # **Available Model**
        model_layout = QHBoxLayout()
        self.model_label = QLabel("Available Model")
        model_layout.addWidget(self.model_label)

        self.model_combo = QComboBox()
        self.model_combo.setEditable(False)

        self.refresh_button = QPushButton("Refresh")
        self.test_button = QPushButton("Check")

        model_layout.addWidget(self.model_combo)
        model_layout.addWidget(self.refresh_button)
        model_layout.addWidget(self.test_button)
        layout.addLayout(model_layout)

        # **Image Resolution**
        resolution_layout = QHBoxLayout()
        self.resolution_label = QLabel("Image Resolution")
        resolution_layout.addWidget(self.resolution_label)

        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(["384x384", "512x512"])
        resolution_layout.addWidget(self.resolution_combo)
        layout.addLayout(resolution_layout)

        # **Source Field**
        source_hbox = QHBoxLayout()
        source_hbox.addWidget(QLabel("Source Field:"))
        self.source_combo = QComboBox()
        source_hbox.addWidget(self.source_combo)
        layout.addLayout(source_hbox)

        # **Destination Field**
        destination_hbox = QHBoxLayout()
        destination_hbox.addWidget(QLabel("Destination Field:"))
        self.destination_combo = QComboBox()
        destination_hbox.addWidget(self.destination_combo)
        layout.addLayout(destination_hbox)

        self.setLayout(layout)

    def toggle_password_visibility(self):
        """切换 API Key 的可见性"""
        if self.password_shown:
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_password_button.setText("🔒")
        else:
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_password_button.setText("👀")

        self.password_shown = not self.password_shown

    def set_default_model(self):
        """设置默认模型 Pollinations，并检查支持状态"""
        self.generate_combo.setCurrentText("Pollinations")
        self.on_model_change()

    def on_model_change(self):
        """当用户选择的模型改变时，检查哪些组件可用"""
        selected_model = self.generate_combo.currentText()
        self.supports_customization = self.load_model_support(selected_model)
        self.toggle_input_fields()  # ✅ 修正，不传递 `dict`

    def load_model_support(self, model_name):
        """加载模型文件并返回具体支持的配置"""
        model_file = f"{model_name.lower().replace(' ', '')}.py"
        model_folder = model_name.lower().replace(' ', '')
        module_path = os.path.join(os.path.dirname(__file__), "models", model_folder, model_file)

        if not os.path.exists(module_path):
            print(f"Model file {model_name} not found: {module_path}")
            return {"base_url": False, "api_key": False, "model": False}

        spec = importlib.util.spec_from_file_location(model_name, module_path)
        model_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(model_module)

        if hasattr(model_module, "supports_customization"):
            return model_module.supports_customization()

        return {"base_url": False, "api_key": False, "model": False}

    def toggle_input_fields(self):
        """启用/禁用各个 UI 组件"""
        # **Base URL**
        self.base_url_edit.setEnabled(self.supports_customization["base_url"])
        self.base_url_label.setStyleSheet("color: black" if self.supports_customization["base_url"] else "color: gray")

        # **API Key**
        self.api_key_edit.setEnabled(self.supports_customization["api_key"])
        self.api_key_label.setStyleSheet("color: black" if self.supports_customization["api_key"] else "color: gray")

        # **Model**
        self.model_combo.setEnabled(self.supports_customization["model"])
        self.model_label.setStyleSheet("color: black" if self.supports_customization["model"] else "color: gray")

    def load_fields_from_selected_note(self):
        """
        读取当前选中的 Note 的字段名，填充 Source Field 和 Destination Field 下拉框。
        """
        if not self.browser:
            print("[ImageTab] Browser instance not available.")
            return

        selected_notes = self.browser.selectedNotes()
        if not selected_notes:
            print("[ImageTab] No notes selected.")
            return

        first_note_id = selected_notes[0]  # 只取第一个 Note
        note = mw.col.get_note(first_note_id)

        if not note:
            print(f"[ImageTab] No valid note found for ID {first_note_id}")
            return

        # 读取字段列表
        field_names = list(note.keys())

        # 清空并填充下拉框
        self.source_combo.clear()
        self.destination_combo.clear()
        self.source_combo.addItems(field_names)
        self.destination_combo.addItems(field_names)

        print(f"[ImageTab] Loaded fields: {field_names}")

    def resize_image(self, image_filename, resolution):
        """
        使用 Qt 的 QImage 进行图片缩放（不依赖绝对路径）
        :param image_filename: 图片的相对路径（存储在 Anki 媒体文件夹）
        :param resolution: 目标分辨率，例如 '384x384'
        :return: 处理后的图片文件名（存入 Anki 媒体库）
        """
        media_dir = mw.col.media.dir()  # Anki 媒体文件夹
        full_path = os.path.join(media_dir, image_filename)  # 计算完整路径

        if not os.path.exists(full_path):
            print(f"[ImageTab] Error: Image not found - {image_filename}")
            return None

        try:
            width, height = map(int, resolution.split('x'))  # 解析分辨率字符串
            img = QImage(full_path)  # ✅ 从 Anki 媒体文件夹加载图片

            if img.isNull():
                print(f"[ImageTab] Error: Failed to load image - {image_filename}")
                return None

            # ✅ 直接在 **内存中** 调整大小
            img_resized = img.scaled(width, height, Qt.AspectRatioMode.IgnoreAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation)

            # ✅ 重新保存 **覆盖原文件**
            img_resized.save(full_path)
            print(f"[ImageTab] Resized image to {resolution} - {full_path}")

            return image_filename  # 仅返回相对路径
        except Exception as e:
            print(f"[ImageTab] Error resizing image: {e}")
            return None

    def on_generate_images(self):
        """
        由 `Generate` 按钮触发，执行批量图片生成，并将结果插入到 Destination Field。
        """
        if not self.browser:
            showWarning("Browser instance not found.")
            return

        note_ids = self.browser.selectedNotes()
        if not note_ids:
            showWarning("No notes selected.")
            return

        source_field = self.source_combo.currentText()
        destination_field = self.destination_combo.currentText()

        if not source_field or not destination_field:
            showWarning("Please select Source / Destination Field.")
            return

        selected_model = self.generate_combo.currentText()
        resolution = self.resolution_combo.currentText()  # ✅ 获取用户选择的分辨率

        # ✅ **创建进度条**
        progress = QProgressDialog("Generating images...", "Cancel", 0, len(note_ids), self)
        progress.setWindowTitle("Image Generation")
        progress.setMinimumDuration(500)  # 进度条至少显示0.5秒
        # ✅ **兼容 PyQt5 和 PyQt6**
        try:
            progress.setWindowModality(Qt.WindowModal)
        except AttributeError:
            progress.setWindowModality(Qt.WindowModality.WindowModal)  # **PyQt6 兼容写法**

        progress.show()

        for i, nid in enumerate(note_ids):
            if progress.wasCanceled():
                showInfo("Operation canceled.")
                return

            note = mw.col.get_note(nid)
            if source_field not in note:
                print(f"[Note {nid}] Source field '{source_field}' not found, skip.")
                continue

            prompt_text = note[source_field].strip()
            if not prompt_text:
                print(f"[Note {nid}] Source field is empty, skip.")
                continue

            # 调用模型生成图片
            image_filename = self.call_generate_image(selected_model, prompt_text, nid)
            if not image_filename:
                print(f"[Note {nid}] Failed to generate image.")
                continue

            # ✅ **调整图片大小**
            resized_image = self.resize_image(image_filename, resolution)
            if not resized_image:
                print(f"[Note {nid}] Failed to resize image, using original.")
                resized_image = image_filename  # 失败时，使用原始图片

            # ✅ **覆盖 `Destination Field`，而不是追加**
            note[destination_field] = f'<div><img src="{resized_image}"></div>'

            # ✅ 立即保存修改
            mw.col.update_note(note)

            # ✅ **更新进度**
            progress.setValue(i + 1)

        # ✅ **关闭进度条**
        progress.close()

        # ✅ 刷新 Anki UI
        mw.reset()
        showInfo("Image generation complete.")

    def call_generate_image(self, model_name, prompt, note_id):
        """
        调用对应模型的 `generate_image()` 方法，带 **重试机制**。
        """
        model_file = f"{model_name.lower().replace(' ', '')}.py"
        model_folder = model_name.lower().replace(' ', '')
        module_path = os.path.join(os.path.dirname(__file__), "models", model_folder, model_file)

        if not os.path.exists(module_path):
            print(f"[ImageTab] Model file {model_name} not found: {module_path}")
            return None

        spec = importlib.util.spec_from_file_location(model_name, module_path)
        model_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(model_module)

        media_dir = mw.col.media.dir()
        output_filename = f"pollinations_{note_id}.jpg"
        output_path = os.path.join(media_dir, output_filename)

        # ✅ **重试机制**
        retry_count = 3  # **最多尝试 3 次**
        for attempt in range(1, retry_count + 1):
            print(f"[Pollinations] Attempt {attempt}: Generating image for Note {note_id}")

            if hasattr(model_module, "generate_image"):
                result = model_module.generate_image(prompt, output_path, width=1024, height=1024, seed=100,
                                                     model="flux",
                                                     nologo=True)

                if result:  # **成功返回图片**
                    print(f"[Pollinations] Image successfully generated on attempt {attempt}")
                    return result

            # **请求失败**
            print(f"[Pollinations] Error: Request failed (attempt {attempt}/{retry_count}). Retrying...")
            if attempt < retry_count:
                wait_time = random.uniform(1, 5)  # **随机等待 1~5 秒**
                print(f"[Pollinations] Waiting {wait_time:.2f} seconds before retrying...")
                time.sleep(wait_time)

        # **三次尝试都失败**
        print(f"[Pollinations] Failed to generate image after {retry_count} attempts. Skipping...")
        return None

