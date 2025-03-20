# text_gui.py

import os
import json
from aqt.qt import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QTextEdit,
    QPushButton, QFrame, Qt, QFont, QSizePolicy, QProgressDialog, QProgressBar,
    QCoreApplication, QCheckBox, QMessageBox, QWidget
)
from aqt.utils import showInfo, showWarning
from aqt import mw
import re
from .models.openai import OpenAIGUI, generate_openai_chat
from .models.ollama import OllamaGUI, generate_ollama_chat
from .models.deepseek import DeepSeekGUI, generate_deepseek_chat
from .img_hosting import ImageHostingDialog
from .image_utils import upload_to_img_hosting, generate_with_img

USER_DATA_DIR = os.path.join(
    os.path.dirname(__file__),       # \AINotePro\ainotepro\gen_text
    "..",                            # -> \AINotePro\ainotepro
    "..",                            # -> \AINotePro
    "user_data",                     # -> \AINotePro\user_data
    "gen_text"                       # -> \AINotePro\user_data\gen_text
)
PROMPT_FILE = os.path.join(USER_DATA_DIR, "prompt.json")

def load_prompts():
    """加载 prompt.json"""
    if not os.path.exists(PROMPT_FILE):
        return {}
    try:
        with open(PROMPT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_prompts(data):
    """保存 prompt.json"""
    with open(PROMPT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

class TextTab(QWidget):
    def __init__(self, parent=None, browser=None):
        super().__init__(parent)
        self.parent = parent
        self.browser = browser

        layout = QVBoxLayout(self)

        # 标题
        self.title_label = QLabel(
            '<div style="font-size:14px; font-weight:bold; font-style:italic;">'
            'Insert AI-generated content into the selected note'
            '</div>'
        )
        layout.addWidget(self.title_label)

        # 选择服务
        self.generate_label = QLabel("Generate using")
        self.service_combo = QComboBox()
        self.service_combo.addItems(["Open AI", "DeepSeek", "Ollama"])
        self.service_combo.currentIndexChanged.connect(self.switch_service_ui)
        #layout.addWidget(self.service_combo)

        # Generate using 选择
        generate_layout = QHBoxLayout()
        generate_layout.addWidget(self.generate_label)
        generate_layout.addWidget(self.service_combo)
        layout.addLayout(generate_layout)

        # AI 模型的动态 UI 容器
        self.dynamic_ui_container = QVBoxLayout()
        layout.addLayout(self.dynamic_ui_container)

        # 载入默认 UI（OpenAI）
        self.current_service_ui = OpenAIGUI()
        self.dynamic_ui_container.addLayout(self.current_service_ui.create_layout())

        # 分隔线
        self.separator_line = QFrame()
        self.separator_line.setFrameShape(getattr(QFrame, "Shape", QFrame).HLine)
        self.separator_line.setFrameShadow(getattr(QFrame, "Shadow", QFrame).Sunken)
        layout.addWidget(self.separator_line)

        # Prompt 预览
        self.prompt_label = QLabel("Prompt Preview")
        layout.addWidget(self.prompt_label)

        self.prompt_text_edit = QTextEdit()
        self.prompt_text_edit.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding))
        layout.addWidget(self.prompt_text_edit)

        # Prompt List & 按钮
        prompt_list_layout = QHBoxLayout()
        self.prompt_list_label = QLabel("Prompt List:")
        self.prompt_list_combo = QComboBox()
        self.prompt_list_combo.setEditable(True)
        prompt_list_layout.addWidget(self.prompt_list_label)
        prompt_list_layout.addWidget(self.prompt_list_combo)
        layout.addLayout(prompt_list_layout)

        prompt_buttons_layout = QHBoxLayout()
        self.save_button = QPushButton("💾 Save Prompt")
        self.load_button = QPushButton("📂 Load Prompt")
        self.delete_button = QPushButton("❌ Delete Prompt")
        prompt_buttons_layout.addWidget(self.save_button)
        prompt_buttons_layout.addWidget(self.load_button)
        prompt_buttons_layout.addWidget(self.delete_button)
        layout.addLayout(prompt_buttons_layout)

        # Source Field
        source_field_layout = QHBoxLayout()
        self.source_field_label = self._create_bold_label("Source Field: ")
        self.source_field_combo = QComboBox()
        source_field_layout.addWidget(self.source_field_label)
        source_field_layout.addWidget(self.source_field_combo)
        layout.addLayout(source_field_layout)

        # “Image Input”复选框和按钮
        image_layout = QHBoxLayout()
        self.image_checkbox = QCheckBox("Enable Image Source")
        self.image_checkbox.setChecked(False)

        self.image_input_button = QPushButton("🖼️ Image Hosting Platform")
        self.image_input_button.setEnabled(False)  # 默认不可点击

        # 将这两个控件放入一个布局中
        image_layout.addWidget(self.image_checkbox)
        image_layout.addWidget(self.image_input_button)
        layout.addLayout(image_layout)

        # 连接信号槽
        self.image_checkbox.stateChanged.connect(self.on_image_checkbox_toggled)
        self.image_input_button.clicked.connect(self.on_image_input_button_clicked)

        # Destination Field
        destination_field_layout = QHBoxLayout()
        self.destination_field_label = self._create_bold_label("Destination Field: ")
        self.destination_field_combo = QComboBox()
        destination_field_layout.addWidget(self.destination_field_label)
        destination_field_layout.addWidget(self.destination_field_combo)
        layout.addLayout(destination_field_layout)

        self.setLayout(layout)

        # 加载 prompt 列表
        self.load_prompt_list()

        # 绑定按钮事件
        self.save_button.clicked.connect(self.on_save_prompt)
        self.load_button.clicked.connect(self.on_load_prompt)
        self.delete_button.clicked.connect(self.on_delete_prompt)

        # 加载当前选中的牌组字段
        self.load_current_note_fields()

    def _get_anki_media_path(self, image_filename):
        """类内方法：获取 Anki collection.media 目录下的文件路径"""
        media_dir = mw.col.media.dir()  # ✅ 使用 Anki API 获取路径
        return os.path.join(media_dir, image_filename)

    def _extract_image_filename(self, html_content):
        """从 Anki 字段 HTML 提取图片文件名"""
        match = re.search(r'<img\s+src=["\'](.*?)["\']', html_content)
        return match.group(1) if match else None

    def _create_bold_label(self, text, font_size=10):
        """创建加粗 & 指定字号的 QLabel（私有方法）"""
        label = QLabel(text)
        font = label.font()
        font.setBold(True)
        font.setPointSize(font_size)
        label.setFont(font)
        return label

    def _get_hosting_api_key(self):
        """从 img_hosting.json 读取上次使用的 API Key 和 Upload URL"""
        settings_file = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "..", "user_data", "gen_text", "img_hosting.json"
        ))

        if not os.path.exists(settings_file):
            showWarning("Image hosting configuration not found!")
            return None, None

        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # **优先使用 "last_used" 里的服务**
            last_used = data.get("last_used", {})
            platform_name = last_used.get("service")

            if not platform_name or platform_name not in data:
                # **如果 "last_used" 不存在或无效，使用第一个可用的 Hosting**
                available_platforms = [k for k in data.keys() if k != "last_used"]
                platform_name = available_platforms[0] if available_platforms else None

            if not platform_name:
                showWarning("No valid hosting platform found.")
                return None, None

            print(f"📌 Using platform: {platform_name}")

            return data[platform_name].get("api_key", None), data[platform_name].get("upload_url", None)

        except Exception as e:
            print(f"⚠️ 读取 img_hosting.json 失败: {e}")
            showWarning("Failed to read image hosting configuration.")
            return None, None

    def on_image_checkbox_toggled(self):
        """根据勾选状态启用/禁用 Image Input 按钮"""
        # 暂停按钮自己的信号，避免某些环境下产生的连锁反应
        self.image_input_button.blockSignals(True)

        # 如果勾选了，按钮启用且显示为黑色；否则禁用并显示为灰色
        if self.image_checkbox.isChecked():
            self.image_input_button.setEnabled(True)
            self.image_input_button.setStyleSheet("color: black;")
        else:
            self.image_input_button.setEnabled(False)
            self.image_input_button.setStyleSheet("color: gray;")

        # 恢复按钮的信号
        self.image_input_button.blockSignals(False)
        # 强制按钮 UI 刷新
        self.image_input_button.update()

    def on_image_input_button_clicked(self):
        dialog = ImageHostingDialog(self)
        dialog.exec()

    def _clear_layout(self, layout):
        """递归清理布局中的子控件与子布局"""
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            else:
                sub_layout = item.layout()
                if sub_layout is not None:
                    self._clear_layout(sub_layout)

    def switch_service_ui(self):
        """切换不同的服务 UI"""
        selected_service = self.service_combo.currentText()

        # 解绑旧的温度滑块信号
        if hasattr(self.current_service_ui, "temperature_slider") and self.current_service_ui.temperature_slider:
            try:
                self.current_service_ui.temperature_slider.valueChanged.disconnect()
            except (AttributeError, TypeError, RuntimeError):
                pass

        # 彻底清理旧的 UI 布局和控件
        self._clear_layout(self.dynamic_ui_container)
        self.repaint()

        # 根据选择加载新的 UI
        if selected_service == "Open AI":
            self.current_service_ui = OpenAIGUI()
        elif selected_service == "Ollama":
            self.current_service_ui = OllamaGUI()
        elif selected_service == "DeepSeek":
            self.current_service_ui = DeepSeekGUI()
        else:
            # 其他选项可以自行扩展
            self.current_service_ui = OpenAIGUI()

        # 调用 setup_api_key()
        self.current_service_ui.setup_api_key()

        # 温度滑块重置
        self.current_service_ui.temperature_slider.setValue(70)

        # 重新绑定滑块信号
        self.current_service_ui.temperature_slider.valueChanged.connect(
            self.current_service_ui.update_temperature_display
        )

        # 添加新布局
        self.dynamic_ui_container.addLayout(self.current_service_ui.create_layout())

        self.repaint()

    def load_prompt_list(self):
        prompts_data = load_prompts()
        self.prompt_list_combo.clear()
        for key in prompts_data.keys():
            self.prompt_list_combo.addItem(key)

    def on_save_prompt(self):
        """保存 Prompt"""
        prompt_name = self.prompt_list_combo.currentText().strip()
        if not prompt_name:
            showWarning("Prompt name cannot be empty.")
            return

        reply = QMessageBox.question(
            self, "Confirm Save", "Are you sure you want to save this prompt?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.No:
            return

        prompt_value = self.prompt_text_edit.toPlainText()
        prompts_data = load_prompts()
        prompts_data[prompt_name] = prompt_value
        save_prompts(prompts_data)

        if self.prompt_list_combo.findText(prompt_name) < 0:
            self.prompt_list_combo.addItem(prompt_name)
        showInfo("Prompt saved successfully.")

    def on_load_prompt(self):
        """加载 Prompt"""
        prompt_name = self.prompt_list_combo.currentText().strip()
        if not prompt_name:
            showWarning("Prompt name cannot be empty.")
            return

        prompts_data = load_prompts()
        if prompt_name not in prompts_data:
            showWarning("Prompt not found in prompt.json.")
            return

        self.prompt_text_edit.setPlainText(prompts_data[prompt_name])

    def on_delete_prompt(self):
        """删除 Prompt"""
        prompt_name = self.prompt_list_combo.currentText().strip()
        if not prompt_name:
            showWarning("Prompt name cannot be empty.")
            return

        reply = QMessageBox.question(
            self, "Confirm Delete", "Are you sure you want to delete this prompt?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.No:
            return

        prompts_data = load_prompts()
        if prompt_name in prompts_data:
            del prompts_data[prompt_name]
            save_prompts(prompts_data)
            showInfo("Prompt deleted.")
        else:
            showWarning("Prompt not found in prompt.json.")

        index = self.prompt_list_combo.findText(prompt_name)
        if index >= 0:
            self.prompt_list_combo.removeItem(index)
        self.prompt_text_edit.clear()

    def load_current_note_fields(self):
        """读当前浏览器选中笔记的字段名，填入 Source/Destination"""
        if not self.browser:
            return
        note_ids = self.browser.selectedNotes()
        if not note_ids:
            return

        first_note_id = note_ids[0]
        note_obj = self.browser.mw.col.get_note(first_note_id)
        model = note_obj.note_type()
        field_names = [fld["name"] for fld in model["flds"]]

        self.source_field_combo.clear()
        self.destination_field_combo.clear()
        self.source_field_combo.addItems(field_names)
        self.destination_field_combo.addItems(field_names)

    def on_generate_text(self):
        if not self.browser:
            showWarning("Browser is not ready.")
            return

        note_ids = self.browser.selectedNotes()
        if not note_ids:
            showWarning("No notes selected.")
            return

        base_url = self.current_service_ui.base_url_edit.text().strip()
        api_key = self.current_service_ui.api_key_edit.text().strip()
        model_name = self.current_service_ui.model_combo.currentText().strip()
        temperature = self.current_service_ui.temperature_slider.value() / 100.0
        system_prompt = self.prompt_text_edit.toPlainText().strip()

        if not system_prompt:
            showWarning("Prompt Preview is empty.")
            return

        source_field = self.source_field_combo.currentText()
        destination_field = self.destination_field_combo.currentText()
        if not source_field or not destination_field:
            showWarning("Source/Destination field is not set.")
            return

        # 进度对话框示例，可选
        progress = QProgressDialog("Generating responses...", "Cancel", 0, len(note_ids), self)
        progress.setWindowTitle("Generating")
        progress.show()

        # 在终端打印出生成前的一些关键信息
        print("=== Begin generating AI content ===")
        print(f"Base URL: {base_url}")
        print(f"API Key: {api_key if api_key else '(empty)'}")
        print(f"Model: {model_name}")
        print(f"Temperature: {temperature:.2f}")
        print(f"Notes to process: {len(note_ids)}")

        # **修正：从 self.image_checkbox 获取状态**
        is_image_input_enabled = self.image_checkbox.isChecked()
        print(f"Image Input Enabled: {is_image_input_enabled}")

        for i, nid in enumerate(note_ids):
            if progress.wasCanceled():
                showInfo("Operation canceled.")
                print("=== User canceled operation ===")
                break

            note = self.browser.mw.col.get_note(nid)
            if source_field not in note:
                print(f"[Note {nid}] Source field '{source_field}' not found, skipping.")
                continue

            if is_image_input_enabled:
                # **从 HTML 提取 <img src="...">**
                html_content = note[source_field].strip()
                image_filename = self._extract_image_filename(html_content)

                # **用 Anki API 获取 collection.media 目录**
                image_path = self._get_anki_media_path(image_filename)

                # **检查文件是否存在**
                if not os.path.exists(image_path):
                    print(f"[Note {nid}] Image file not found: {image_path}, skipping.")
                    continue

                # 获取当前选中的 Hosting 平台的 API Key 和 Upload URL
                img_hosting_api_key, upload_url = self._get_hosting_api_key()

                if not img_hosting_api_key or not upload_url:
                    print(f"[Note {nid}] No valid image hosting API key found, skipping.")
                    continue

                # **上传图片到图床**
                try:
                    image_url = upload_to_img_hosting(image_path, img_hosting_api_key, upload_url)
                    print(f"[Note {nid}] Uploaded Image URL: {image_url}")
                except Exception as e:
                    print(f"[Note {nid}] Image upload failed: {str(e)}")
                    continue

                # **用 Claude 生成描述**
                final_url = base_url.rstrip("/") + "/v1/chat/completions"
                cleaned_content = generate_with_img(image_url, api_key, final_url, system_prompt)
            else:
                user_text = note[source_field].strip()
                if not user_text:
                    print(f"[Note {nid}] Source field is empty, skipping.")
                    continue

                modified_prompt = system_prompt.replace("{Source Field}", user_text)
                print(f"[Note {nid}] Sending text: {user_text[:50]}...")

                if "ollama" in model_name.lower():
                    cleaned_content = generate_ollama_chat(base_url, model_name, temperature, modified_prompt)
                elif "openai" in model_name.lower():
                    cleaned_content = generate_openai_chat(base_url, api_key, model_name, temperature, system_prompt,
                                                           user_text)
                elif "deepseek" in model_name.lower():
                    cleaned_content = generate_deepseek_chat(base_url, api_key, model_name, temperature, system_prompt,
                                                             user_text)
                else:
                    cleaned_content = generate_deepseek_chat(base_url, api_key, model_name, temperature, system_prompt,
                                                             user_text)

            note[destination_field] = cleaned_content
            note.col.update_note(note)

            # 在终端打印出返回的结果（只显示前50字符）
            print(f"[Note {nid}] Received content: {cleaned_content[:50]}...")
            print(f"[Note {nid}] Updated '{destination_field}' field successfully.")

            progress.setValue(i + 1)
            QCoreApplication.processEvents()

        progress.close()
        print("=== Generation complete ===")
        showInfo("Generation complete.")