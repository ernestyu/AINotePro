from aqt.qt import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider, Qt, QProgressDialog, QFileDialog, 
    QComboBox, QCheckBox, QLineEdit, qconnect, QGroupBox, QFrame, QSizePolicy, QFont, QSpacerItem
)
from .tts_handler import get_languages, get_voices, get_language_code, generate_and_play_tts  # 导入 TTS 处理函数
import os 
import json
import random
from aqt import mw
from functools import partial
from aqt.utils import showInfo, showWarning  # 用于弹出提示框

class EchoAIConfigDialog(QDialog):
    def __init__(self, parent=None, browser=None):
        super().__init__(parent)
        self.browser = browser  # 存储浏览器对象
        self.setWindowTitle("EchoAI")
        self.setMinimumWidth(900)
        self.setMinimumHeight(550)

        self.current_task = None  # ✅ 用于存储 TTS 任务

        # **初始化存储列表**
        self.speed_sliders = []
        self.volume_sliders = []
        self.pitch_sliders = []
        self.speed_labels = []
        self.volume_labels = []
        self.pitch_labels = []

        # 设置数据存储路径
        self.user_data_dir = os.path.join(os.path.dirname(__file__), "user_data")
        os.makedirs(self.user_data_dir, exist_ok=True)  # 确保目录存在

        # 初始化 UI 组件
        self.setup_ui()
        self.get_fields_from_selected_notes()  # 只有在 UI 初始化完成后才获取字段

    def setup_ui(self):
        # **添加字体样式**
        self._FONT_TITLE = QFont()
        self._FONT_TITLE.setPointSize(18)  # 调整大标题字体大小
        self._FONT_TITLE.setBold(True)

        self._FONT_HEADER = QFont()
        self._FONT_HEADER.setPointSize(12)
        self._FONT_HEADER.setBold(True)

        self._FONT_LABEL = QFont()
        self._FONT_LABEL.setBold(True)

        self._FONT_INFO = QFont()
        self._FONT_INFO.setItalic(True)

        # **主布局**
        layout = QVBoxLayout()
        layout.addLayout(self._create_title_bar())

        # **配置服务**
        config_section = QLabel("<b>Configure Service</b>")
        config_section.setFont(self._FONT_HEADER)
        layout.addWidget(config_section)

        # **"Generate using" + "Language"**
        gen_layout = QHBoxLayout()
        self.generate_combo = QComboBox()
        self.generate_combo.addItem("Edge-TTS")  # **初始化为 Edge-TTS**
        self.generate_combo.currentIndexChanged.connect(self.update_language_list)  # 绑定选择变更事件
        
        self.language_combo = QComboBox()  # **初始化为空，后续代码填充**
        self.language_combo.currentIndexChanged.connect(self.update_voice_list)  # **语言变更时，更新 Voice**

        gen_layout.addWidget(QLabel("Generate using"))
        gen_layout.addWidget(self.generate_combo)
        gen_layout.addWidget(QLabel("Language:"))
        gen_layout.addWidget(self.language_combo)

        layout.addLayout(gen_layout)

        # **Speed / Volume / Pitch 选项（改为数值）**
        speed_values = [0]
        gender_options = ["Female", "Male"]

        # **声音选项 + 预览**
        self.voice_checkboxes = []  # 存储 Voice 复选框
        self.voice_combos = []  # 存储 Voice 下拉框
        self.gender_combos = []  # 存储 Gender 下拉框
        self.preview_inputs = []  # ⬅️ 确保 preview_input 可以被存储
        self.preview_buttons = []  # ⬅️ 需要添加这个，存储 Preview 按钮
        self.speed_combos = []  # ⬅️ 需要添加这个，存储 Speed 选项
        self.volume_combos = []  # ⬅️ 存储 Volume 选项
        self.pitch_combos = []  # ⬅️ 存储 Pitch 选项

        # 兼容 PyQt5 和 PyQt6
        orientation = getattr(Qt, "Orientation", Qt).Horizontal

        voice_layout = QVBoxLayout()
        for i in range(1, 4):
            group_box = QGroupBox(f"Voice {i}")  # 用 GroupBox 让 UI 更清晰
            vbox = QVBoxLayout()

            # **音色下拉框**
            voice_hbox = QHBoxLayout()
            checkbox = QCheckBox(f"Enable Voice {i}")
            combo = QComboBox()
            combo.setEnabled(False)  # **默认禁用，启用后更新**
            
            checkbox.stateChanged.connect(lambda state, idx=i: self.toggle_voice(idx, state))  # 监听勾选
            
            preview_input = QLineEdit()
            preview_input.setPlaceholderText("Type a phrase to test...")
            preview_button = QPushButton("Preview")

            # **⬇️ 绑定 Preview 按钮**
            preview_button.clicked.connect(partial(self.preview_tts, i))

            # ⬇️ 让 preview_input 被存储，以便 preview_tts() 访问
            # self.preview_inputs.append(preview_input)
            # self.preview_buttons.append(preview_button)  # 添加 Preview 按钮

            voice_hbox.addWidget(checkbox)
            voice_hbox.addWidget(combo)
            voice_hbox.addWidget(preview_input)
            voice_hbox.addWidget(preview_button)
            vbox.addLayout(voice_hbox)

            # **Gender + Speed, Volume, Pitch**
            controls_hbox = QHBoxLayout()

            gender_label = QLabel("Gender:")
            gender_label.setFont(self._FONT_LABEL)
            gender_combo = QComboBox()
            gender_combo.addItems(gender_options)  # **新增 Gender 选项**
            gender_combo.currentIndexChanged.connect(lambda _, idx=i: self.update_voice_list(idx))  # 监听 Gender 变更

            # Speed 组件
            speed_label = QLabel("0")  
            speed_slider = QSlider(orientation.Horizontal)
            speed_slider.setRange(-100, 100)
            speed_slider.setSingleStep(1)
            speed_slider.setValue(0)
            speed_slider.valueChanged.connect(lambda value, lbl=speed_label: lbl.setText(str(value)))

            # Volume 组件
            volume_label = QLabel("0")  
            volume_slider = QSlider(orientation.Horizontal)
            volume_slider.setRange(-100, 100)
            volume_slider.setSingleStep(1)
            volume_slider.setValue(0)
            volume_slider.valueChanged.connect(lambda value, lbl=volume_label: lbl.setText(str(value)))

            # Pitch 组件
            pitch_label = QLabel("0")  
            pitch_slider = QSlider(orientation.Horizontal)
            pitch_slider.setRange(-100, 100)
            pitch_slider.setSingleStep(1)
            pitch_slider.setValue(0)
            pitch_slider.valueChanged.connect(lambda value, lbl=pitch_label: lbl.setText(str(value)))


            controls_hbox.addWidget(gender_label)
            controls_hbox.addWidget(gender_combo)
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

        # **字段选择**
        fields_section = QLabel("<b>Fields and Handling</b>")
        fields_section.setFont(self._FONT_HEADER)
        layout.addWidget(fields_section)

        fields_layout = QVBoxLayout()
        source_hbox = QHBoxLayout()
        source_label = QLabel("Source Field:")
        source_label.setFont(self._FONT_LABEL)
        self.source_combo = QComboBox()
        source_hbox.addWidget(source_label)
        source_hbox.addWidget(self.source_combo)

        destination_hbox = QHBoxLayout()
        destination_label = QLabel("Destination Field:")
        destination_label.setFont(self._FONT_LABEL)
        self.destination_combo = QComboBox()
        destination_hbox.addWidget(destination_label)
        destination_hbox.addWidget(self.destination_combo)

        fields_layout.addLayout(source_hbox)
        fields_layout.addLayout(destination_hbox)
        layout.addLayout(fields_layout)

        # **初始化时填充 Source/Destination 字段**
        self.get_fields_from_selected_notes()  # ✅ 这里调用

        # **兼容 PyQt5 和 PyQt6**
        try:
            expanding_policy = QSizePolicy.Expanding
        except AttributeError:
            expanding_policy = QSizePolicy.Policy.Expanding  # ✅ 兼容 PyQt5

        # **保存 & 加载 配置**
        save_load_layout = QHBoxLayout()

        # **Save & Load Config 标签**
        save_load_label = QLabel("Save & Load Configuration:")
        save_load_label.setFont(self._FONT_LABEL)

        # **创建 Save 和 Load 按钮**
        self.save_button = QPushButton("💾 Save")
        self.load_button = QPushButton("📂 Load")

        # **让 Save 和 Load 按钮填充整个可用空间**
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.load_button)

        # **设置两个按钮等比例扩展**
        button_layout.setStretch(0, 1)  # Save 按钮占 50%
        button_layout.setStretch(1, 1)  # Load 按钮占 50%

        # **让 Save & Load Config 这行对齐 Destination Field**
        save_load_layout.addWidget(save_load_label)
        save_load_layout.addStretch()  # 让按钮靠右对齐
        save_load_layout.addLayout(button_layout)  # 让按钮填充宽度

        layout.addLayout(save_load_layout)

        # **按钮**
        button_layout = QHBoxLayout()
        self.generate_button = QPushButton("Generate")
        self.close_button = QPushButton("Close")
        self.help_button = QPushButton("Help")
        button_layout.addWidget(self.generate_button)
        button_layout.addWidget(self.close_button)
        button_layout.addWidget(self.help_button)
        
        # 初始化弹出窗口
        self.update_language_list()  # **强制初始化 Language 列表**
        layout.addLayout(button_layout)        
        self.setLayout(layout) # **确保窗口正确渲染**

        # **连接按钮点击事件**
        qconnect(self.generate_button.clicked, self.generate_tts)
        qconnect(self.close_button.clicked, self.on_close_clicked)
        qconnect(self.help_button.clicked, self.show_help)
        qconnect(self.save_button.clicked, self.save_configuration_to_file)
        qconnect(self.load_button.clicked, self.load_configuration_from_file)



    def _create_title_bar(self):
        """创建带版本号的标题栏"""
        layout = QHBoxLayout()
        title_label = QLabel("Add TTS Audio to Selected Notes")
        title_label.setFont(self._FONT_TITLE)

        version_label = QLabel("EchoAI v1.0")
        version_label.setFont(self._FONT_INFO)

        layout.addWidget(title_label)
        layout.addStretch()
        layout.addWidget(version_label)
        return layout

    def save_configuration(self):
        """保存当前的 TTS 配置到 JSON 文件"""
        config_name = self.config_combo.currentText().strip()
        if not config_name:
            print("No config name provided.")
            return

        config_path = os.path.join(self.user_data_dir, f"{config_name}.json")
        
        config_data = {
            "generate_using": self.generate_combo.currentText(),
            "language": self.language_combo.currentText()
        }

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4)

        print(f"Configuration saved: {config_path}")
        self.load_config_list()  # 重新加载可选配置文件

    def load_configuration(self):
        """加载已保存的 TTS 配置"""
        config_name = self.config_combo.currentText().strip()
        if not config_name:
            print("No config selected.")
            return

        config_path = os.path.join(self.user_data_dir, f"{config_name}.json")
        if not os.path.exists(config_path):
            print(f"Configuration file not found: {config_path}")
            return

        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)

        # 恢复 UI 设置
        self.generate_combo.setCurrentText(config_data.get("generate_using", "Edge-TTS"))
        self.language_combo.setCurrentText(config_data.get("language", ""))

        print(f"Configuration loaded: {config_name}")

    def load_config_list(self):
        """加载 `user_data` 目录中的所有 JSON 配置文件"""
        self.config_combo.clear()
        if not os.path.exists(self.user_data_dir):
            return

        config_files = [f.replace(".json", "") for f in os.listdir(self.user_data_dir) if f.endswith(".json")]
        self.config_combo.addItems(config_files)

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


    def generate_tts(self):
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


    def closeEvent(self, event):
        """窗口关闭时，确保异步任务被取消"""
        if self.current_task:
            try:
                if not self.current_task.done():
                    self.current_task.cancel()
            except Exception as e:
                print(f"⚠️ Error canceling task: {e}")

        print("✅ EchoAI window closed, pending TTS tasks canceled.")
        event.accept()

    def save_configuration_to_file(self):
        """保存当前的 TTS 配置到 JSON 文件"""
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Configuration", "", "JSON Files (*.json)")

        if not file_path:
            return  # 用户取消保存

        config_data = {
            "generate_using": self.generate_combo.currentText(),
            "language": self.language_combo.currentText(),
            "voices": []
        }

        for i in range(3):  # Voice1 - Voice3
            config_data["voices"].append({
                "enabled": self.voice_checkboxes[i].isChecked(),
                "voice": self.voice_combos[i].currentText(),
                "gender": self.gender_combos[i].currentText(),
                "speed": self.speed_sliders[i].value(),
                "volume": self.volume_sliders[i].value(),
                "pitch": self.pitch_sliders[i].value()
            })

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4)
            print(f"✅ Configuration saved to {file_path}")
        except Exception as e:
            print(f"❌ Error saving configuration: {e}")

    def load_configuration_from_file(self):
        """从 JSON 文件加载 TTS 配置"""
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Configuration", "", "JSON Files (*.json)")

        if not file_path:
            return  # 用户取消选择

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)

            # ✅ 校验 JSON 结构
            if not isinstance(config_data, dict) or "generate_using" not in config_data or "language" not in config_data or "voices" not in config_data:
                raise ValueError("Invalid configuration file format.")

            self.generate_combo.setCurrentText(config_data["generate_using"])
            self.language_combo.setCurrentText(config_data["language"])

            voices = config_data["voices"]
            if len(voices) != 3:
                raise ValueError("Invalid configuration file format.")

            for i in range(3):
                self.voice_checkboxes[i].setChecked(voices[i]["enabled"])
                self.voice_combos[i].setCurrentText(voices[i]["voice"])
                self.gender_combos[i].setCurrentText(voices[i]["gender"])
                self.speed_sliders[i].setValue(voices[i]["speed"])
                self.volume_sliders[i].setValue(voices[i]["volume"])
                self.pitch_sliders[i].setValue(voices[i]["pitch"])

            print(f"✅ Configuration loaded from {file_path}")

        except Exception as e:
            showWarning("Invalid configuration file format.")  # ✅ 提示用户
            print(f"❌ Error loading configuration: {e}")

    def on_close_clicked(self):
        """点击 Close 按钮时触发，确保清理任务"""
        self.close()

    def show_help(self):
        """点击帮助按钮时触发"""
        print("Opening Help...")