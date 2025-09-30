from __future__ import annotations

import os
from typing import Optional

from aqt import mw
from aqt.qt import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QComboBox,
    QLineEdit, QToolButton, QFrame, Qt, QImage, QProgressDialog
)
from aqt.utils import showInfo, showWarning

from ..services.provider_factory import create_provider
from ..core.utils import add_image_to_media_collection, update_field_content


class ImageTab(QWidget):
    def __init__(self, parent=None, browser=None):
        super().__init__(parent)
        self.browser = browser
        self._build_ui()
        self._load_fields()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel('<div style="font-size:14px; font-weight:bold; font-style:italic;">Insert AI-generated images into the selected note</div>')
        layout.addWidget(title)

        sep = QFrame(); sep.setFrameShape(getattr(QFrame, "HLine", QFrame.Shape.HLine)); sep.setFrameShadow(getattr(QFrame, "Sunken", QFrame.Shadow.Sunken))
        layout.addWidget(sep)

        # Generate using
        gen_row = QHBoxLayout(); gen_row.addWidget(QLabel("Generate using"))
        self.generate_combo = QComboBox(); self.generate_combo.addItems(["Pollinations", "DALL-E"]) ; gen_row.addWidget(self.generate_combo)
        layout.addLayout(gen_row)

        # Base URL
        row = QHBoxLayout(); row.addWidget(QLabel("Base URL"))
        self.base_url_edit = QLineEdit(); self.base_url_edit.setPlaceholderText("Enter API base URL...")
        row.addWidget(self.base_url_edit); layout.addLayout(row)

        # API Key + toggle
        row = QHBoxLayout(); row.addWidget(QLabel("API Key"))
        self.api_key_edit = QLineEdit(); self.toggle_password_button = QToolButton(); self.toggle_password_button.setText("🔒")
        try:
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        except Exception:
            self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.toggle_password_button.clicked.connect(self._toggle_pw)
        row.addWidget(self.api_key_edit); row.addWidget(self.toggle_password_button); layout.addLayout(row)

        # Available Model
        row = QHBoxLayout(); row.addWidget(QLabel("Available Model"))
        self.model_combo = QComboBox(); self.model_combo.setEditable(True)
        self.refresh_button = QPushButton("Refresh"); self.test_button = QPushButton("Check")
        row.addWidget(self.model_combo); row.addWidget(self.refresh_button); row.addWidget(self.test_button)
        layout.addLayout(row)

        # Image Resolution
        row = QHBoxLayout(); row.addWidget(QLabel("Image Resolution"))
        self.resolution_combo = QComboBox(); self.resolution_combo.addItems(["384x384", "512x512", "1024x1024"]) ; row.addWidget(self.resolution_combo)
        layout.addLayout(row)

        # Fields
        srow = QHBoxLayout(); srow.addWidget(QLabel("Source Field:")); self.source_combo = QComboBox(); srow.addWidget(self.source_combo); layout.addLayout(srow)
        drow = QHBoxLayout(); drow.addWidget(QLabel("Destination Field:")); self.destination_combo = QComboBox(); drow.addWidget(self.destination_combo); layout.addLayout(drow)

        self.setLayout(layout)

    def _toggle_pw(self):
        mode = self.api_key_edit.echoMode()
        try:
            from aqt.qt import QLineEdit as _QLE
            self.api_key_edit.setEchoMode(_QLE.EchoMode.Normal if mode != _QLE.EchoMode.Normal else _QLE.EchoMode.Password)
        except Exception:
            self.api_key_edit.setEchoMode(QLineEdit.Normal if mode != QLineEdit.Normal else QLineEdit.Password)

    def _load_fields(self) -> None:
        try:
            if not self.browser: return
            sel = self.browser.selectedNotes();
            if not sel: return
            n = mw.col.get_note(sel[0]); names = [f["name"] for f in n.note_type()["flds"]]
            self.source_combo.clear(); self.destination_combo.clear(); self.source_combo.addItems(names); self.destination_combo.addItems(names)
        except Exception:
            pass

    # Called by parent dialog
    def on_generate_images(self) -> None:
        if not self.browser:
            showWarning("Browser is not ready."); return
        note_ids = self.browser.selectedNotes()
        if not note_ids:
            showWarning("No notes selected."); return

        prompt_field = self.source_combo.currentText(); dest_field = self.destination_combo.currentText()
        model = self.model_combo.currentText().strip()
        base_url = self.base_url_edit.text().strip(); api_key = self.api_key_edit.text().strip()
        resolution = self.resolution_combo.currentText()
        provider_name = "pollinations" if self.generate_combo.currentText() == "Pollinations" else "dalle"
        provider = create_provider("image", provider_name, {})

        progress = QProgressDialog("Generating images...", "Cancel", 0, len(note_ids), self); progress.setWindowTitle("Image Generation"); progress.show()
        for i, nid in enumerate(note_ids):
            if progress.wasCanceled(): break
            note = mw.col.get_note(nid)
            prompt = (note.get(prompt_field, "") or "").strip()
            if not prompt:
                continue
            cfg = {"base_url": base_url, "api_key": api_key, "model": model}
            try:
                data = provider.generate(prompt, cfg)
                fname = add_image_to_media_collection(data, f"pollinations_{nid}.jpg")
                fname = self._resize_media_image(fname, resolution)
                html = f'<div><img src="{fname}"></div>'
                update_field_content(note, dest_field, html)
            except Exception as e:
                print(f"[Note {nid}] image failed: {e}")
            progress.setValue(i+1)
        progress.close(); showInfo("Image generation complete.")

    def _resize_media_image(self, filename: str, resolution: str) -> str:
        try:
            w, h = [int(x) for x in resolution.split("x", 1)]
            path = os.path.join(mw.col.media.dir(), filename)
            img = QImage(path)
            if img.isNull():
                return filename
            resized = img.scaled(w, h, getattr(Qt, "KeepAspectRatio", Qt.AspectRatioMode.KeepAspectRatio), getattr(Qt, "SmoothTransformation", Qt.TransformationMode.SmoothTransformation))
            # overwrite to a new file
            out_name = f"resized_{filename}"
            out_path = os.path.join(mw.col.media.dir(), out_name)
            resized.save(out_path)
            return out_name
        except Exception:
            return filename
