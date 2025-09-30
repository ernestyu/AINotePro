from __future__ import annotations

import json
import os
import re
from typing import Optional

from aqt import mw
from aqt.qt import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QTextEdit,
    QPushButton,
    QFrame,
    QLineEdit,
    QSlider,
    QSizePolicy,
    Qt,
)
from aqt.utils import showInfo, showWarning

from ..core.manager import AIManager, GenerationRequest
from ..core.async_task import AsyncTask
from ..config.manager import ConfigManager


class MainDialog(QDialog):
    def __init__(self, parent=None, browser=None) -> None:
        super().__init__(parent)
        self.browser = browser
        self.setWindowTitle("AINotePro")
        self.resize(920, 640)

        self.cfg = ConfigManager()
        self.manager = AIManager(self.cfg)

        self._build_ui()
        self._load_initial_state()

    # UI
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Service Type
        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Service Type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["text", "image", "audio"])  # fixed options
        self.type_combo.currentTextChanged.connect(self._on_type_change)
        type_row.addWidget(self.type_combo)
        layout.addLayout(type_row)

        # Provider
        provider_row = QHBoxLayout()
        provider_row.addWidget(QLabel("Provider:"))
        self.provider_combo = QComboBox()
        layout.addLayout(provider_row)
        provider_row.addWidget(self.provider_combo)
        self.provider_combo.currentTextChanged.connect(lambda _: self._populate_provider_cfg())

        # Base URL / API Key / Model for text & image
        self.base_url_edit = QLineEdit(); self.base_url_edit.setPlaceholderText("Base URL (if applicable)")
        self.api_key_edit = QLineEdit(); self.api_key_edit.setPlaceholderText("API Key (if applicable)")
        # password mode if present
        try:
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        except Exception:
            self.api_key_edit.setEchoMode(QLineEdit.Password)
        from aqt.qt import QComboBox as _QComboBox  # alias to avoid shadow
        self.model_combo = _QComboBox(); self.model_combo.setEditable(True)

        row = QHBoxLayout(); row.addWidget(QLabel("Base URL:")); row.addWidget(self.base_url_edit); layout.addLayout(row)
        row = QHBoxLayout(); row.addWidget(QLabel("API Key:")); row.addWidget(self.api_key_edit); layout.addLayout(row)
        row = QHBoxLayout(); row.addWidget(QLabel("Model:")); row.addWidget(self.model_combo); self.model_refresh = QPushButton("Refresh"); row.addWidget(self.model_refresh); layout.addLayout(row)

        # Temperature (text)
        temp_row = QHBoxLayout()
        self.temp_label = QLabel("Temperature: 0.70")
        self.temp_slider = QSlider(Qt.Orientation.Horizontal)
        self.temp_slider.setRange(0, 100)
        self.temp_slider.setValue(70)
        self.temp_slider.valueChanged.connect(lambda v: self.temp_label.setText(f"Temperature: {v/100:.2f}"))
        temp_row.addWidget(self.temp_label)
        temp_row.addWidget(self.temp_slider)
        layout.addLayout(temp_row)

        # Separator
        sep = QFrame(); sep.setFrameShape(getattr(QFrame, "HLine", QFrame.Shape.HLine)); sep.setFrameShadow(getattr(QFrame, "Sunken", QFrame.Shadow.Sunken))
        layout.addWidget(sep)

        # Image-assisted option for text generation
        img_row = QHBoxLayout()
        self.img_assist_label = QLabel("Image-Assisted (from Source <img>):")
        self.img_assist_combo = QComboBox(); self.img_assist_combo.addItems(["off", "on"])  # simple toggle
        img_row.addWidget(self.img_assist_label); img_row.addWidget(self.img_assist_combo); img_row.addStretch(1)
        layout.addLayout(img_row)

        # Prompt
        layout.addWidget(QLabel("Prompt:"))
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding))
        layout.addWidget(self.prompt_edit)

        # Fields
        frow = QHBoxLayout()
        frow.addWidget(QLabel("Source Field:"))
        self.source_combo = QComboBox(); frow.addWidget(self.source_combo)
        frow.addWidget(QLabel("Destination Field:"))
        self.dest_combo = QComboBox(); frow.addWidget(self.dest_combo)
        layout.addLayout(frow)

        # Buttons
        btn_row = QHBoxLayout()
        self.generate_btn = QPushButton("Generate")
        self.close_btn = QPushButton("Close")
        btn_row.addStretch(1)
        btn_row.addWidget(self.generate_btn)
        btn_row.addWidget(self.close_btn)
        layout.addLayout(btn_row)

        self.generate_btn.clicked.connect(self._on_generate)
        self.close_btn.clicked.connect(self.accept)

    def _load_initial_state(self) -> None:
        # load fields from selected note (browser path matches current plugin behavior)
        self._load_note_fields()
        # populate providers according to type
        self._on_type_change(self.type_combo.currentText())
        # load config values
        cfg = self.cfg.get_all()
        tcfg = cfg.get("text", {})
        self.prompt_edit.setPlainText((tcfg.get("prompts", {}) or {}).get(tcfg.get("last_used_prompt", "Default"), ""))

    def _load_note_fields(self) -> None:
        note_fields = []
        try:
            if self.browser:
                sel = self.browser.selectedNotes()
                if sel:
                    n = mw.col.get_note(sel[0])
                    note_fields = [f["name"] for f in n.note_type()["flds"]]
        except Exception:
            pass
        self.source_combo.clear(); self.dest_combo.clear()
        if note_fields:
            self.source_combo.addItems(note_fields)
            self.dest_combo.addItems(note_fields)

    def _on_type_change(self, value: str) -> None:
        self.provider_combo.clear()
        if value == "text":
            self.provider_combo.addItems(["openai", "deepseek", "ollama"])
        elif value == "image":
            self.provider_combo.addItems(["pollinations", "dalle"])  # sd_webui optional
        else:
            self.provider_combo.addItems(["edge_tts"])  # default audio

        # Load saved provider config into UI
        self._populate_provider_cfg()

    def _populate_provider_cfg(self) -> None:
        st = self.type_combo.currentText()
        pv = self.provider_combo.currentText()
        cfg = self.cfg.get_provider_config(st, pv)
        self.base_url_edit.setText(cfg.get("base_url", ""))
        self.api_key_edit.setText(cfg.get("api_key", ""))
        # reset model combo content to current value
        self.model_combo.clear()
        self.model_combo.setEditText(cfg.get("model", ""))
        # fetch model list lazily
        self._refresh_models()

    def _refresh_models(self) -> None:
        try:
            from ..services.provider_factory import create_provider
            st = self.type_combo.currentText(); pv = self.provider_combo.currentText()
            cfg = self.cfg.get_provider_config(st, pv)
            if st != "text":
                return
            provider = create_provider(st, pv, cfg)
            models = []
            try:
                models = provider.list_models(cfg) or []
            except Exception:
                models = []
            if models:
                cur = self.model_combo.currentText()
                self.model_combo.clear()
                self.model_combo.addItems(models)
                if cur:
                    # keep current if present
                    idx = self.model_combo.findText(cur)
                    if idx >= 0:
                        self.model_combo.setCurrentIndex(idx)
                    else:
                        self.model_combo.setEditText(cur)
        except Exception:
            pass

    def _save_provider_cfg(self) -> None:
        st = self.type_combo.currentText()
        pv = self.provider_combo.currentText()
        data = {
            "base_url": self.base_url_edit.text().strip(),
            "api_key": self.api_key_edit.text().strip(),
            "model": self.model_combo.currentText().strip(),
            "temperature": self.temp_slider.value() / 100.0,
        }
        self.cfg.set_provider_config(st, pv, data)

    def _on_generate(self) -> None:
        if not self.browser:
            showWarning("Open the Browser and select notes.")
            return

        note_ids = self.browser.selectedNotes()
        if not note_ids:
            showWarning("No notes selected.")
            return

        # persist provider settings
        self._save_provider_cfg()

        req = GenerationRequest(
            note_ids=note_ids,
            source_field=self.source_combo.currentText(),
            destination_field=self.dest_combo.currentText(),
            service_type=self.type_combo.currentText(),
            provider=self.provider_combo.currentText(),
            prompt=self.prompt_edit.toPlainText().strip(),
            options={},
        )

        def work():
            if req.service_type == "text":
                # optional image-assisted generation using the first note's image src
                if self.img_assist_combo.currentText() == "on":
                    img_url = self._extract_and_upload_image(req.note_ids[0], req.source_field)
                    if img_url:
                        req.options["image_url"] = img_url
                return self.manager.generate_text_for_field(req)
            if req.service_type == "image":
                return self.manager.generate_image_for_field(req)
            if req.service_type == "audio":
                return self.manager.generate_audio_for_field(req)
            raise ValueError("unknown service type")

        task = AsyncTask(target=work)
        task.finished_ok.connect(lambda n: showInfo(f"Done. Updated {n} notes."))
        task.failed.connect(lambda err: showWarning(f"Generation failed: {err}"))
        task.start()

    # Helpers
    def _extract_and_upload_image(self, nid: int, field_name: str) -> Optional[str]:
        try:
            note = mw.col.get_note(nid)
            html = note.get(field_name, "")
            # extract src
            m = re.search(r'<img\s+src=["\']([^"\']+)["\']', html)
            if not m:
                return None
            src = m.group(1)
            media_path = mw.col.media.dir()
            img_path = os.path.join(media_path, src)
            if not os.path.exists(img_path):
                return None
            api_key, upload_url = self._get_img_hosting()
            if not api_key or not upload_url:
                return None
            # reuse existing helper to upload
            from ..gen_text.image_utils import upload_to_img_hosting
            return upload_to_img_hosting(img_path, api_key, upload_url)
        except Exception:
            return None

    def _get_img_hosting(self) -> tuple[Optional[str], Optional[str]]:
        settings_file = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "user_data", "gen_text", "img_hosting.json"
        ))
        if not os.path.exists(settings_file):
            return None, None
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            last_used = data.get("last_used", {})
            platform = last_used.get("service")
            if not platform or platform not in data:
                candidates = [k for k in data.keys() if k != "last_used"]
                platform = candidates[0] if candidates else None
            if not platform:
                return None, None
            cfg = data.get(platform) or {}
            return cfg.get("api_key"), cfg.get("upload_url")
        except Exception:
            return None, None
