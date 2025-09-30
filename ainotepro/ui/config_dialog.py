from __future__ import annotations

from aqt.qt import QDialog, QVBoxLayout, QLabel, QComboBox, QLineEdit, QHBoxLayout, QPushButton
from aqt.utils import showInfo

from ..config.manager import ConfigManager


class ConfigDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AINotePro Settings")
        self.resize(520, 240)
        self.cfg = ConfigManager()

        lay = QVBoxLayout(self)

        row = QHBoxLayout(); row.addWidget(QLabel("Service:"))
        self.service_combo = QComboBox(); self.service_combo.addItems(["text", "image", "audio"]); row.addWidget(self.service_combo)
        lay.addLayout(row)

        row = QHBoxLayout(); row.addWidget(QLabel("Provider:"))
        self.provider_combo = QComboBox(); lay.addLayout(row); row.addWidget(self.provider_combo)

        row = QHBoxLayout(); row.addWidget(QLabel("Base URL:")); self.base_url = QLineEdit(); row.addWidget(self.base_url); lay.addLayout(row)
        row = QHBoxLayout(); row.addWidget(QLabel("API Key:")); self.api_key = QLineEdit(); row.addWidget(self.api_key); lay.addLayout(row)
        row = QHBoxLayout(); row.addWidget(QLabel("Model:")); self.model = QLineEdit(); row.addWidget(self.model); lay.addLayout(row)

        buttons = QHBoxLayout(); self.save_btn = QPushButton("Save"); self.close_btn = QPushButton("Close"); buttons.addStretch(1); buttons.addWidget(self.save_btn); buttons.addWidget(self.close_btn)
        lay.addLayout(buttons)

        self.service_combo.currentTextChanged.connect(self._on_service_change)
        self.provider_combo.currentTextChanged.connect(self._load)
        self.save_btn.clicked.connect(self._save)
        self.close_btn.clicked.connect(self.accept)

        self._on_service_change(self.service_combo.currentText())

    def _on_service_change(self, st: str) -> None:
        self.provider_combo.clear()
        if st == "text":
            self.provider_combo.addItems(["openai", "deepseek", "ollama"])
        elif st == "image":
            self.provider_combo.addItems(["pollinations", "dalle"])  # sd_webui optional
        else:
            self.provider_combo.addItems(["edge_tts"])  # default audio
        self._load()

    def _load(self) -> None:
        st = self.service_combo.currentText(); pv = self.provider_combo.currentText()
        cfg = self.cfg.get_provider_config(st, pv)
        self.base_url.setText(cfg.get("base_url", ""))
        self.api_key.setText(cfg.get("api_key", ""))
        self.model.setText(cfg.get("model", ""))

    def _save(self) -> None:
        st = self.service_combo.currentText(); pv = self.provider_combo.currentText()
        self.cfg.set_provider_config(st, pv, {
            "base_url": self.base_url.text().strip(),
            "api_key": self.api_key.text().strip(),
            "model": self.model.text().strip(),
        })
        showInfo("Saved.")

