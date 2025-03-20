from aqt.qt import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, Qt, QSlider, QSizePolicy, QFontMetrics, QToolButton
)

class BaseGUI:
    def __init__(self):
        self.base_url_label = QLabel("Base URL")
        self.api_key_label = QLabel("API Key")
        self.model_label = QLabel("Available Model")

        self.base_url_edit = QLineEdit()
        self.api_key_edit = QLineEdit()
        self.model_combo = QComboBox()
        self.model_combo.setEditable(False)

        self.refresh_button = QPushButton("Refresh")
        self.test_button = QPushButton("Check")

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

        self.align_labels()

        orientation = getattr(Qt, "Orientation", Qt).Horizontal
        self.temperature_label = QLabel("Temperature")
        self.temperature_slider = QSlider(orientation)
        self.temperature_slider.setRange(0, 200)
        self.temperature_slider.setValue(70)
        self.temperature_value_label = QLabel("0.70")
        self.temperature_slider.valueChanged.connect(self.update_temperature_display)

        self.base_url_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.api_key_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.model_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def align_labels(self):
        font_metrics = QFontMetrics(self.model_label.font())
        available_model_width = font_metrics.horizontalAdvance(self.model_label.text())

        self.base_url_label.setFixedWidth(available_model_width)
        self.api_key_label.setFixedWidth(available_model_width)

    def setup_api_key(self):
        pass

    def update_temperature_display(self, value):
        self.temperature_value_label.setText(f"{value / 100:.2f}")

    def toggle_password_visibility(self):
        if self.password_shown:
            self.api_key_edit.setEchoMode(self._PASSWORD_MODE)
            self.toggle_password_button.setText("🔒")
        else:
            self.api_key_edit.setEchoMode(self._NORMAL_MODE)
            self.toggle_password_button.setText("👀")

        self.password_shown = not self.password_shown

    def create_layout(self):
        """Create the standard UI layout."""
        layout = QVBoxLayout()

        base_api_layout = QVBoxLayout()

        base_url_layout = QHBoxLayout()
        base_url_layout.addWidget(self.base_url_label)
        base_url_layout.addWidget(self.base_url_edit)
        base_api_layout.addLayout(base_url_layout)

        # Place API Key label, edit, and toggle button on the same row
        api_key_layout = QHBoxLayout()
        api_key_layout.addWidget(self.api_key_label)
        api_key_layout.addWidget(self.api_key_edit)
        api_key_layout.addWidget(self.toggle_password_button)
        base_api_layout.addLayout(api_key_layout)

        layout.addLayout(base_api_layout)

        # 这行很重要！确保 `model_layout` 正确初始化
        model_layout = QHBoxLayout()

        model_layout.addWidget(self.model_label)
        model_layout.addWidget(self.model_combo)
        model_layout.addWidget(self.refresh_button)
        model_layout.addWidget(self.test_button)

        layout.addLayout(model_layout)

        temperature_layout = QHBoxLayout()
        temperature_layout.addWidget(self.temperature_label)
        temperature_layout.addWidget(self.temperature_slider)
        temperature_layout.addWidget(self.temperature_value_label)
        layout.addLayout(temperature_layout)

        return layout

