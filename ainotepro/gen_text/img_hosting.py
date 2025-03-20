import os
import json
from aqt.qt import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QLineEdit, QPushButton, QMessageBox
)


class ImageHostingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image Hosting")
        self.resize(500, 150)

        main_layout = QVBoxLayout(self)

        # Hosting Platform 选择
        platform_layout = QHBoxLayout()
        platform_label = QLabel("Hosting Platform:")
        self.platform_combo = QComboBox()
        self.platform_combo.addItem("PStorage")  # 默认选项
        platform_layout.addWidget(platform_label)
        platform_layout.addWidget(self.platform_combo)
        main_layout.addLayout(platform_layout)

        # Hosting Upload URL
        upload_layout = QHBoxLayout()
        upload_label = QLabel("Hosting Upload URL:")
        self.upload_url_edit = QLineEdit()
        upload_layout.addWidget(upload_label)
        upload_layout.addWidget(self.upload_url_edit)
        main_layout.addLayout(upload_layout)

        # API Key
        api_layout = QHBoxLayout()
        api_label = QLabel("Hosting API Key:")
        self.api_key_edit = QLineEdit()
        api_layout.addWidget(api_label)
        api_layout.addWidget(self.api_key_edit)
        main_layout.addLayout(api_layout)

        # 按钮布局
        button_layout = QHBoxLayout()
        self.add_button = QPushButton("Add")  # 替换 Confirm 按钮
        self.delete_button = QPushButton("Delete")  # 新增删除按钮
        self.quit_button = QPushButton("Quit")

        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addWidget(self.quit_button)
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

        # 绑定事件
        self.add_button.clicked.connect(self.on_add)
        self.delete_button.clicked.connect(self.on_delete)
        self.quit_button.clicked.connect(self.reject)

        # **加载历史配置**
        self.load_settings()

    def get_settings_file_path(self, return_dir=False):
        """获取 img_hosting.json 存储路径
        - `return_dir=False` 时，只返回 `settings_file`
        - `return_dir=True` 时，返回 `(settings_dir, settings_file)`
        """
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        settings_dir = os.path.join(base_dir, "user_data", "gen_text")
        settings_file = os.path.join(settings_dir, "img_hosting.json")

        if return_dir:
            return settings_dir, settings_file
        return settings_file

    def load_settings(self):
        """加载已保存的 Hosting 配置"""
        settings_file = self.get_settings_file_path()

        if os.path.exists(settings_file):
            try:
                with open(settings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # 先清空下拉框，确保不会重复添加
                    self.platform_combo.clear()
                    for platform in data.keys():
                        self.platform_combo.addItem(platform)

                    # 选中第一个，并填充对应数据
                    if self.platform_combo.count() > 0:
                        self.platform_combo.setCurrentIndex(0)
                        self.update_fields()
            except Exception as e:
                print(f"⚠️ 读取 img_hosting.json 失败: {e}")

        # 监听下拉框变化，自动填充对应数据
        self.platform_combo.currentIndexChanged.connect(self.update_fields)

    def update_fields(self):
        """当用户切换 Hosting Platform 时，更新 URL 和 API Key"""
        settings_file = self.get_settings_file_path()

        if os.path.exists(settings_file):
            try:
                with open(settings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                    platform = self.platform_combo.currentText()
                    if platform in data:
                        self.upload_url_edit.setText(data[platform].get("upload_url", ""))
                        self.api_key_edit.setText(data[platform].get("api_key", ""))
            except Exception as e:
                print(f"⚠️ 更新 UI 失败: {e}")

    def on_add(self):
        """添加 / 更新 Hosting 配置"""
        settings_dir, settings_file = self.get_settings_file_path(return_dir=True)

        # 确保目录存在
        os.makedirs(settings_dir, exist_ok=True)

        # 获取当前输入的数据
        platform_name = self.platform_combo.currentText().strip()
        upload_url = self.upload_url_edit.text().strip()
        api_key = self.api_key_edit.text().strip()

        if not platform_name or not upload_url or not api_key:
            QMessageBox.warning(self, "Warning", "Platform, Upload URL, and API Key cannot be empty.")
            return

        # 读取已有数据
        data = {}
        if os.path.exists(settings_file):
            try:
                with open(settings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                print(f"⚠️ 读取 JSON 失败: {e}")

        # 更新数据
        data[platform_name] = {
            "upload_url": upload_url,
            "api_key": api_key
        }

        # 保存到 JSON 文件
        try:
            with open(settings_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"✅ 配置已保存到 {settings_file}")
            QMessageBox.information(self, "Success", f"Configuration for {platform_name} has been saved.")

            # 确保平台已在下拉列表中
            if self.platform_combo.findText(platform_name) == -1:
                self.platform_combo.addItem(platform_name)
        except Exception as e:
            print(f"❌ 保存失败: {e}")

    def on_delete(self):
        """删除当前选中的 Hosting 配置"""
        settings_dir, settings_file = self.get_settings_file_path(return_dir=True)
        platform_name = self.platform_combo.currentText().strip()

        if not platform_name:
            QMessageBox.warning(self, "Warning", "No platform selected.")
            return

        # 读取已有数据
        data = {}
        if os.path.exists(settings_file):
            try:
                with open(settings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                print(f"⚠️ 读取 JSON 失败: {e}")

        if platform_name in data:
            reply = QMessageBox.question(
                self, "Confirm Delete", f"Are you sure you want to delete {platform_name}?",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.No:
                return

            # 删除该平台配置
            del data[platform_name]

            # 保存更新后的数据
            try:
                with open(settings_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print(f"✅ {platform_name} 配置已删除")
                QMessageBox.information(self, "Success", f"{platform_name} has been deleted.")

                # 从下拉框移除
                self.platform_combo.removeItem(self.platform_combo.currentIndex())

                # 清空输入框
                self.upload_url_edit.clear()
                self.api_key_edit.clear()
            except Exception as e:
                print(f"❌ 删除失败: {e}")
