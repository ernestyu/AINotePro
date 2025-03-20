# tts_gui.py

from aqt.qt import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QComboBox, QCheckBox, QLineEdit, QSlider,
    QGroupBox, Qt, QSizePolicy, QToolButton, QFontMetrics, QFrame, QProgressDialog, QMessageBox
)
from aqt.utils import showInfo
import os
import json
import random
from aqt import mw
from functools import partial
from .models.edge_tts.tts_handler import get_languages, get_voices, get_language_code, generate_and_play_tts

class TTSTab(QWidget):
    def __init__(self, parent=None, browser=None):
        super().__init__(parent)
        self.browser = browser
        self.setMinimumWidth(900)
        self.setMinimumHeight(550)

        self.current_task = None  # 用于存储 TTS 任务
        self.user_data_dir = os.path.join(os.path.dirname(__file__), "../../user_data/gen_audio/edge_tts")
        os.makedirs(self.user_data_dir, exist_ok=True)  # 确保目录存在

        self.api_key_edit = QLineEdit()

        # 存储 UI 组件
        self.voice_checkboxes = []
        self.voice_combos = []
        self.gender_combos = []
        self.preview_inputs = []
        self.preview_buttons = []
        self.speed_sliders = []
        self.speed_labels = []
        self.volume_sliders = []
        self.volume_labels = []
        self.pitch_sliders = []
        self.pitch_labels = []

        self.password_shown = False
        self.toggle_password_button = QToolButton()
        self.toggle_password_button.setText("🔒")

        if hasattr(QLineEdit, "EchoMode"):
            self._NORMAL_MODE = QLineEdit.EchoMode.Normal
            self._PASSWORD_MODE = QLineEdit.EchoMode.Password
        else:
            self._NORMAL_MODE = QLineEdit.Normal
            self._PASSWORD_MODE = QLineEdit.Password

        self.api_key_edit.setEchoMode(self._PASSWORD_MODE)
        self.toggle_password_button.clicked.connect(self.toggle_password_visibility)

        # 初始化 UI 组件
        self.setup_ui()
        self.get_fields_from_selected_notes()
        self.load_config_list()  # 加载现有配置

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # 标题
        self.title_label = QLabel(
            '<div style="font-size:14px; font-weight:bold; font-style:italic;">'
            'Configure Text-to-Speech (TTS) Settings'
            '</div>'
        )
        fixed_policy = getattr(QSizePolicy, "Fixed", QSizePolicy.Policy.Fixed)
        self.title_label.setSizePolicy(fixed_policy, fixed_policy)

        layout.addWidget(self.title_label)

        # 生成引擎 & 语言选择
        self.generate_label = QLabel("Generate using")
        self.generate_combo = QComboBox()
        self.generate_combo.addItem("Edge-TTS")
        self.generate_combo.currentIndexChanged.connect(self.update_language_list)
        adjust_policy = getattr(QComboBox, "AdjustToContents", QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.generate_combo.setSizeAdjustPolicy(adjust_policy)

        self.language_label = QLabel("Language:")
        self.language_combo = QComboBox()
        self.language_combo.currentIndexChanged.connect(self.update_voice_list)

        # 生成引擎 & 语言选择布局
        generate_layout = QHBoxLayout()
        generate_layout.setContentsMargins(0, 0, 0, 0)
        generate_layout.setSpacing(5)

        generate_layout.addWidget(self.generate_label)
        generate_layout.addWidget(self.generate_combo)
        generate_layout.addWidget(self.language_label)
        generate_layout.addWidget(self.language_combo)

        layout.addLayout(generate_layout)

        # === API Key 行 ===
        api_key_layout = QHBoxLayout()
        self.api_key_label = QLabel("API Key                   ")
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(self._PASSWORD_MODE)  # 默认隐藏密码

        self.toggle_password_button = QToolButton()
        self.toggle_password_button.setText("🔒")
        self.toggle_password_button.clicked.connect(self.toggle_password_visibility)

        api_key_layout.addWidget(self.api_key_label)
        api_key_layout.addWidget(self.api_key_edit)
        api_key_layout.addWidget(self.toggle_password_button)

        layout.addLayout(api_key_layout)

        # 分隔线
        self.separator_line = QFrame()
        self.separator_line.setFrameShape(getattr(QFrame, "Shape", QFrame).HLine)
        self.separator_line.setFrameShadow(getattr(QFrame, "Shadow", QFrame).Sunken)
        layout.addWidget(self.separator_line)

        # 语音设置
        voice_layout = QVBoxLayout()
        for i in range(1, 3 + 1):
            group_box = QGroupBox(f"Voice {i}")
            vbox = QVBoxLayout()

            # 启用复选框 & 语音选择
            voice_hbox = QHBoxLayout()
            checkbox = QCheckBox(f"Enable Voice {i}")
            combo = QComboBox()
            combo.setEnabled(False)
            checkbox.stateChanged.connect(lambda state, idx=i: self.toggle_voice(idx, state))

            preview_input = QLineEdit()
            preview_input.setPlaceholderText("Type a phrase to test...")
            preview_button = QPushButton("Preview")
            preview_button.clicked.connect(partial(self.preview_tts, i))

            voice_hbox.addWidget(checkbox)
            voice_hbox.addWidget(combo)
            voice_hbox.addWidget(preview_input)
            voice_hbox.addWidget(preview_button)
            vbox.addLayout(voice_hbox)

            # 性别 & 速度、音量、音调
            controls_hbox = QHBoxLayout()
            gender_combo = QComboBox()
            gender_combo.addItems(["Female", "Male"])
            gender_combo.currentIndexChanged.connect(lambda _, idx=i: self.update_voice_list(idx))

            # 滑杆
            speed_slider, speed_label = self.create_slider()
            volume_slider, volume_label = self.create_slider()
            pitch_slider, pitch_label = self.create_slider()

            controls_hbox.addWidget(QLabel("Gender:"))
            controls_hbox.addWidget(gender_combo)
            controls_hbox.addWidget(QLabel("Speed:"))
            controls_hbox.addWidget(speed_slider)
            controls_hbox.addWidget(speed_label)
            controls_hbox.addWidget(QLabel("Volume:"))
            controls_hbox.addWidget(volume_slider)
            controls_hbox.addWidget(volume_label)
            controls_hbox.addWidget(QLabel("Pitch:"))
            controls_hbox.addWidget(pitch_slider)
            controls_hbox.addWidget(pitch_label)

            vbox.addLayout(controls_hbox)
            group_box.setLayout(vbox)

            self.voice_checkboxes.append(checkbox)
            self.voice_combos.append(combo)
            self.gender_combos.append(gender_combo)
            self.preview_inputs.append(preview_input)
            self.preview_buttons.append(preview_button)
            self.speed_sliders.append(speed_slider)
            self.speed_labels.append(speed_label)
            self.volume_sliders.append(volume_slider)
            self.volume_labels.append(volume_label)
            self.pitch_sliders.append(pitch_slider)
            self.pitch_labels.append(pitch_label)

            voice_layout.addWidget(group_box)

        layout.addLayout(voice_layout)

        # **Fields and Handling 部分**
        fields_section = QLabel("<b>Fields and Handling</b>")
        layout.addWidget(fields_section)

        fields_layout = QVBoxLayout()

        # Source Field 单独一行
        source_hbox = QHBoxLayout()
        source_hbox.addWidget(QLabel("Source Field:"))
        self.source_combo = QComboBox()
        source_hbox.addWidget(self.source_combo)
        fields_layout.addLayout(source_hbox)

        # Destination Field 单独一行
        destination_hbox = QHBoxLayout()
        destination_hbox.addWidget(QLabel("Destination Field:"))
        self.destination_combo = QComboBox()
        destination_hbox.addWidget(self.destination_combo)
        fields_layout.addLayout(destination_hbox)

        # Save & Load Configuration + 下拉框
        save_load_hbox = QHBoxLayout()
        save_load_hbox.addWidget(QLabel("Save & Load Profile:"))

        # 让 config_combo 自动扩展
        self.config_combo = QComboBox()
        self.config_combo.setEditable(True)  # 允许手动输入名称
        self.config_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)  # 关键
        save_load_hbox.addWidget(self.config_combo)

        # Save 和 Load 按钮
        self.save_button = QPushButton("💾 Save")
        self.load_button = QPushButton("📂 Load")
        self.delete_button = QPushButton("❌ Delete")

        # 固定按钮宽度
        self.save_button.setFixedWidth(100)
        self.load_button.setFixedWidth(100)
        self.delete_button.setFixedWidth(120)

        save_load_hbox.addWidget(self.save_button)
        save_load_hbox.addWidget(self.load_button)
        save_load_hbox.addWidget(self.delete_button)

        fields_layout.addLayout(save_load_hbox)
        layout.addLayout(fields_layout)

        self.setLayout(layout)
        self.update_language_list()

        # 绑定事件
        self.save_button.clicked.connect(self.save_configuration)
        self.load_button.clicked.connect(self.load_configuration)
        self.delete_button.clicked.connect(self.delete_configuration)

    def load_configuration(self):
        """加载已保存的 TTS 配置"""
        config_name = self.config_combo.currentText().strip()
        if not config_name:
            print("No config selected.")
            return

        config_path = os.path.join(self.user_data_dir, "config.json")
        if not os.path.exists(config_path):
            print(f"Configuration file not found: {config_path}")
            return

        with open(config_path, "r", encoding="utf-8") as f:
            all_configs = json.load(f)

        if config_name not in all_configs:
            print(f"Configuration '{config_name}' not found in config.json.")
            return

        config_data = all_configs[config_name]

        # 恢复 UI 设置
        self.generate_combo.setCurrentText(config_data.get("generate_using", "Edge-TTS"))
        self.language_combo.setCurrentText(config_data.get("language", ""))

        voices = config_data.get("voices", [])
        for i, voice_data in enumerate(voices):
            if i < len(self.voice_checkboxes):
                self.voice_checkboxes[i].setChecked(voice_data.get("enabled", False))
                self.voice_combos[i].setCurrentText(voice_data.get("voice", ""))
                self.gender_combos[i].setCurrentText(voice_data.get("gender", ""))
                self.speed_sliders[i].setValue(voice_data.get("speed", 0))
                self.volume_sliders[i].setValue(voice_data.get("volume", 0))
                self.pitch_sliders[i].setValue(voice_data.get("pitch", 0))

        print(f"Configuration '{config_name}' loaded.")

    def load_config_list(self):
        """加载 `config.json` 中的所有配置名称到下拉框"""
        self.config_combo.clear()
        config_path = os.path.join(self.user_data_dir, "config.json")

        if not os.path.exists(config_path):
            return

        with open(config_path, "r", encoding="utf-8") as f:
            all_configs = json.load(f)

        self.config_combo.addItems(all_configs.keys())

    def update_language_list(self):
        """更新语言下拉列表，并按字母顺序排序，同时取消所有勾选的 Voice"""
        selected_tts = self.generate_combo.currentText()
        self.language_combo.blockSignals(True)  # 暂停信号，避免干扰
        self.language_combo.clear()

        if selected_tts == "Edge-TTS":
            language_map = get_languages("Edge-TTS")  # 获取完整语言名称
            sorted_languages = sorted(language_map.items(), key=lambda x: x[1])  # **按完整语言名排序**

            print("Sorted Languages:", sorted_languages)  # **调试信息**

            for lang_code, full_name in sorted_languages:
                self.language_combo.addItem(full_name, lang_code)  # **插入排序后的语言列表**

        self.language_combo.blockSignals(False)  # 恢复信号
        self.language_combo.update()  # **强制 UI 重新渲染**
        if self.language_combo.count() > 0:
            self.language_combo.setCurrentIndex(0)  # **确保 UI 选择第一项**

        # **清空所有 Voice 复选框的选中状态**
        for checkbox in self.voice_checkboxes:
            checkbox.blockSignals(True)  # **暂停信号，防止连锁反应**
            checkbox.setChecked(False)  # **取消勾选**
            checkbox.blockSignals(False)  # **恢复信号**

    from aqt.qt import QMessageBox  # 添加导入

    def save_configuration(self):
        """保存当前的 TTS 配置到 JSON 文件，先弹出确认对话框"""
        config_name = self.config_combo.currentText().strip()
        if not config_name:
            showInfo("请填写配置名称")
            return

        # **弹出确认对话框**
        reply = QMessageBox.question(
            self, "确认保存", f"是否保存当前配置 '{config_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.No:
            return

        config_path = os.path.join(self.user_data_dir, "config.json")

        # 读取现有配置
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                all_configs = json.load(f)
        else:
            all_configs = {}

        # 构建当前配置的字典结构
        current_config = {
            "generate_using": self.generate_combo.currentText(),
            "language": self.language_combo.currentText(),
            "voices": []
        }

        # 遍历所有的 Voice 设置
        for i in range(len(self.voice_checkboxes)):
            current_config["voices"].append({
                "enabled": self.voice_checkboxes[i].isChecked(),
                "voice": self.voice_combos[i].currentText(),
                "gender": self.gender_combos[i].currentText(),
                "speed": self.speed_sliders[i].value(),
                "volume": self.volume_sliders[i].value(),
                "pitch": self.pitch_sliders[i].value()
            })

        # 保存到总配置字典
        all_configs[config_name] = current_config

        # 写入 JSON 文件
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(all_configs, f, indent=4, ensure_ascii=False)

        print(f"Configuration '{config_name}' saved.")
        showInfo(f"配置 '{config_name}' 已保存！")
        self.load_config_list()  # 重新加载配置列表

    def delete_configuration(self):
        """删除当前选中的 TTS 配置，先弹出警告对话框"""
        config_name = self.config_combo.currentText().strip()
        if not config_name:
            showInfo("请选择要删除的配置")
            return

        config_path = os.path.join(self.user_data_dir, "config.json")
        if not os.path.exists(config_path):
            showInfo("配置文件不存在")
            return

        with open(config_path, "r", encoding="utf-8") as f:
            all_configs = json.load(f)

        if config_name not in all_configs:
            showInfo(f"配置 '{config_name}' 不存在")
            return

        # **弹出删除确认对话框**
        reply = QMessageBox.warning(
            self, "警告", f"确定要删除配置 '{config_name}' 吗？\n此操作不可恢复！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.No:
            return

        # 执行删除
        del all_configs[config_name]
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(all_configs, f, indent=4, ensure_ascii=False)

        print(f"Configuration '{config_name}' deleted.")
        showInfo(f"配置 '{config_name}' 已删除")
        self.load_config_list()

    def toggle_voice(self, idx, state):
        """启用或禁用 Voice 下拉框"""
        enabled = state == 2  # 2 = Qt.Checked
        if not (1 <= idx <= len(self.voice_combos)):
            print(f"Invalid toggle_voice index: {idx}")
            return

        print(f"toggle_voice called with idx: {idx}, enabled: {enabled}")
        self.voice_combos[idx - 1].setEnabled(enabled)

        if enabled:
            self.update_voice_list(idx)

    def update_voice_list(self, voice_index):
        """更新 Voice 下拉列表"""
        if not (1 <= voice_index <= len(self.voice_checkboxes)):
            print(f"Invalid voice_index: {voice_index}, skipping update.")
            return  # **防止访问越界**

        print(f"update_voice_list called with voice_index: {voice_index}")

        # 如果 Enable Voice 没有被选中，跳过
        if not self.voice_checkboxes[voice_index - 1].isChecked():
            print(f"Voice {voice_index} not enabled, skipping update.")
            return

        selected_tts = self.generate_combo.currentText()
        selected_lang = self.language_combo.currentText()
        selected_gender = self.gender_combos[voice_index - 1].currentText()

        if not selected_lang or not selected_gender:
            print(f"Missing language or gender, skipping update for voice {voice_index}.")
            return

        lang_code = get_language_code(selected_lang)
        voices = get_voices(selected_tts, lang_code, selected_gender)

        print(f"Available voices for Voice {voice_index}: {voices}")

        self.voice_combos[voice_index - 1].clear()
        self.voice_combos[voice_index - 1].addItems(voices)

    def reset_voice_selection(self):
        """当 `Language` 变更时，重置所有 Voice UI"""
        print("Resetting voice selection...")  # **调试信息**

        for idx in range(len(self.voice_checkboxes)):
            self.voice_checkboxes[idx].blockSignals(True)  # **防止多次触发**
            self.voice_checkboxes[idx].setChecked(False)  # **取消勾选**
            self.voice_checkboxes[idx].blockSignals(False)

            self.voice_combos[idx].clear()  # **清空 Voice 列表**

    def preview_tts(self, idx):
        """ 预览 TTS 语音 """
        if not (1 <= idx <= len(self.preview_inputs)):
            print(f"Invalid preview index: {idx}")
            return

        if not self.voice_checkboxes[idx - 1].isChecked():
            print(f"Voice {idx} is not enabled. Skipping preview.")
            return

        text = self.preview_inputs[idx - 1].text().strip()
        if not text:
            print(f"No text provided for preview at index {idx}.")
            return

        voice = self.voice_combos[idx - 1].currentText()
        speed = self.speed_sliders[idx - 1].value()
        volume = self.volume_sliders[idx - 1].value()
        pitch = self.pitch_sliders[idx - 1].value()

        output_path = os.path.join(os.path.dirname(__file__), f"preview_{idx}.mp3")

        print(f"Generating preview TTS for voice {voice} at index {idx}")

        # ✅ 取消上一个任务（如果有）
        if self.current_task and isinstance(self.current_task, Future) and not self.current_task.done():
            self.current_task.cancel()

        # ✅ 存储新任务
        self.current_task = generate_and_play_tts(text, voice, speed, volume, pitch, output_path, play_audio=True)

    def get_fields_from_selected_notes(self):
        """ 获取当前选中的 Note 字段，并填充 Source 和 Destination 下拉框 """
        if not self.browser:
            print("No browser instance found!")
            return

        selected_notes = self.browser.selectedNotes()  # ✅ 从当前浏览器获取选中的 Notes
        if not selected_notes:
            print("No notes selected.")
            return

        # 获取第一张卡片
        note_id = selected_notes[0]
        note = mw.col.get_note(note_id)  # 获取 Note 对象

        if not note:
            print("No valid note found.")
            return

        # 获取 Note Type 的所有字段
        fields = list(note.keys())

        # 清空下拉框并填充字段
        self.source_combo.clear()
        self.destination_combo.clear()
        self.source_combo.addItems(fields)
        self.destination_combo.addItems(fields)

        print(f"Loaded fields for note type: {note.note_type()['name']}")

    def on_generate_tts(self):
        """ 生成 TTS 语音并写入 Destination Field """
        if not self.browser:
            print("No browser instance found!")
            return

        selected_notes = self.browser.selectedNotes()
        if not selected_notes:
            print("No notes selected for TTS generation.")
            return

        source_field = self.source_combo.currentText()
        destination_field = self.destination_combo.currentText()

        if not source_field or not destination_field:
            print("Source or Destination field not selected.")
            return

        enabled_voices = []
        for i in range(len(self.voice_checkboxes)):
            if self.voice_checkboxes[i].isChecked():
                enabled_voices.append({
                    "voice": self.voice_combos[i].currentText(),
                    "speed": self.speed_sliders[i].value(),
                    "volume": self.volume_sliders[i].value(),
                    "pitch": self.pitch_sliders[i].value()
                })

        if not enabled_voices:
            showInfo("请至少勾选一种声音")
            return

        # ✅ 先创建进度条窗口
        progress = QProgressDialog("正在转换文本为 TTS...", "取消", 0, len(selected_notes), self)

        # ✅ 兼容 PyQt5 和 PyQt6，确保 setWindowModality 不会出错
        try:
            progress.setWindowModality(Qt.WindowModal)
        except AttributeError:
            progress.setWindowModality(Qt.WindowModality.WindowModal)  # PyQt6 兼容模式

        progress.setMinimumDuration(500)  # 进度条显示前的最小等待时间
        progress.show()

        for i, note_id in enumerate(selected_notes):
            if progress.wasCanceled():
                print("TTS 生成被用户取消")
                return  # 退出循环

            note = mw.col.get_note(note_id)
            if not note:
                continue

            text = note[source_field].strip()
            if not text:
                print(f"Skipping note {note_id}, source field is empty.")
                continue

            voice_config = random.choice(enabled_voices)

            voice = voice_config["voice"]
            speed = voice_config["speed"]
            volume = voice_config["volume"]
            pitch = voice_config["pitch"]

            media_dir = mw.col.media.dir()
            audio_filename = f"tts_{note_id}.mp3"
            output_path = os.path.join(media_dir, audio_filename)

            # ✅ 取消上一个任务
            if self.current_task and not self.current_task.done():
                try:
                    self.current_task.cancel()
                except asyncio.CancelledError:
                    print("Previous TTS task was already cancelled.")

            # ✅ 存储新任务
            self.current_task = generate_and_play_tts(text, voice, speed, volume, pitch, output_path, play_audio=False)

            note[destination_field] = f"[sound:{audio_filename}]"
            mw.col.update_note(note)

            print(f"TTS generated for note {note_id}: {audio_filename}")

            # ✅ 更新进度
            progress.setValue(i + 1)

        mw.reset()  # ✅ 刷新 Anki UI

        # ✅ 任务完成后，弹出提示框
        showInfo("所有选中的 Note 已转换完成！")

    def toggle_password_visibility(self):
        """切换 API Key 输入框的可见性"""
        if self.password_shown:
            self.api_key_edit.setEchoMode(self._PASSWORD_MODE)
            self.toggle_password_button.setText("🔒")
        else:
            self.api_key_edit.setEchoMode(self._NORMAL_MODE)
            self.toggle_password_button.setText("👀")

        self.password_shown = not self.password_shown

    def create_slider(self):
        """创建滑块 (Speed, Volume, Pitch)"""
        orientation = getattr(Qt, "Orientation", Qt).Horizontal
        slider = QSlider(orientation)
        slider.setRange(-100, 100)
        slider.setValue(0)
        slider.setSingleStep(1)
        value_label = QLabel("0")
        slider.valueChanged.connect(lambda value: value_label.setText(str(value)))
        return slider, value_label
