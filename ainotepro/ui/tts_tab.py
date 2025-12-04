from __future__ import annotations

import os
from typing import List

from aqt import mw
from aqt.qt import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QComboBox, QCheckBox,
    QLineEdit, QSlider, QGroupBox, QSizePolicy, QToolButton, QFrame, Qt, QProgressDialog
)
from aqt.utils import showInfo, showWarning
from ..config.manager import ConfigManager
from ..gen_audio.models.edge_tts.tts_handler import get_languages, get_voices

from ..services.provider_factory import create_provider
from ..core.utils import add_audio_to_media_collection, get_field_content, update_field_content


class TTSTab(QWidget):
    def __init__(self, parent=None, browser=None):
        super().__init__(parent)
        self.browser = browser
        self.cfg = ConfigManager()
        self._build_ui()
        self._load_fields()
        self._load_languages()
        self._load_settings()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel('<div style="font-size:14px; font-weight:900;">Configure Text-to-Speech (TTS) Settings</div>')
        fixed_policy = getattr(QSizePolicy, "Fixed", QSizePolicy.Policy.Fixed)
        title.setSizePolicy(fixed_policy, fixed_policy)
        layout.addWidget(title)

        # header
        h = QHBoxLayout(); h.addWidget(QLabel("Generate using"))
        self.generate_combo = QComboBox(); self.generate_combo.addItem("Edge-TTS")
        h.addWidget(self.generate_combo)
        h.addWidget(QLabel("Language:"))
        self.language_combo = QComboBox(); self.language_combo.addItem("English")
        h.addWidget(self.language_combo)
        layout.addLayout(h)

        # API Key
        ak = QHBoxLayout(); ak.addWidget(QLabel("API Key                   "))
        self.api_key_edit = QLineEdit(); self.toggle_password_button = QToolButton(); self.toggle_password_button.setText("🔒")
        try:
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        except Exception:
            self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.toggle_password_button.clicked.connect(self._toggle_pw)
        ak.addWidget(self.api_key_edit); ak.addWidget(self.toggle_password_button); layout.addLayout(ak)

        # separator
        sep = QFrame(); sep.setFrameShape(getattr(QFrame, "HLine", QFrame.Shape.HLine)); sep.setFrameShadow(getattr(QFrame, "Sunken", QFrame.Shadow.Sunken))
        layout.addWidget(sep)

        # Three voice blocks (Enable, voice, preview, sliders)
        self.voice_blocks: List[dict] = []
        for idx in range(1, 4):
            box = QGroupBox(f"Voice {idx}")
            vb = QVBoxLayout()

            row1 = QHBoxLayout(); cb = QCheckBox(f"Enable Voice {idx}")
            voice_combo = QComboBox(); voice_combo.setEditable(True); voice_combo.addItem("en-US-AriaNeural")
            preview_text = QLineEdit(); preview_text.setPlaceholderText("Type a phrase to test...")
            preview_btn = QPushButton("Preview")
            preview_btn.clicked.connect(lambda _, c=cb, v=voice_combo, t=preview_text: self._preview_voice(c, v, t))
            row1.addWidget(cb); row1.addWidget(voice_combo); row1.addWidget(preview_text); row1.addWidget(preview_btn)

            row2 = QHBoxLayout()
            row2.addWidget(QLabel("Gender:")); gender_combo = QComboBox(); gender_combo.addItems(["Female", "Male"]) ; row2.addWidget(gender_combo)
            row2.addWidget(QLabel("Speed:")); sp = QSlider(Qt.Orientation.Horizontal); sp.setRange(-50, 50); sp.setValue(0); row2.addWidget(sp)
            row2.addWidget(QLabel("Volume:")); vol = QSlider(Qt.Orientation.Horizontal); vol.setRange(-50, 50); vol.setValue(0); row2.addWidget(vol)
            row2.addWidget(QLabel("Pitch:")); pit = QSlider(Qt.Orientation.Horizontal); pit.setRange(-50, 50); pit.setValue(0); row2.addWidget(pit)

            vb.addLayout(row1); vb.addLayout(row2); box.setLayout(vb); layout.addWidget(box)
            self.voice_blocks.append({"enable": cb, "voice": voice_combo, "preview": preview_text, "speed": sp, "volume": vol, "pitch": pit, "gender": gender_combo})

        # Fields and handling
        field_sep = QFrame(); field_sep.setFrameShape(getattr(QFrame, "HLine", QFrame.Shape.HLine)); field_sep.setFrameShadow(getattr(QFrame, "Sunken", QFrame.Shadow.Sunken))
        layout.addWidget(field_sep)
        fr = QHBoxLayout(); fr.addWidget(QLabel("Source Field:")); self.src_combo = QComboBox(); fr.addWidget(self.src_combo)
        fr.addWidget(QLabel("Destination Field:")); self.dst_combo = QComboBox(); fr.addWidget(self.dst_combo); layout.addLayout(fr)

        self.setLayout(layout)
        # react to language/gender changes
        self.language_combo.currentIndexChanged.connect(self._update_all_voices)
        for blk in self.voice_blocks:
            blk["gender"].currentIndexChanged.connect(lambda _=None, b=blk: self._update_block_voices(b))

    def _toggle_pw(self):
        mode = self.api_key_edit.echoMode()
        try:
            from aqt.qt import QLineEdit as _QLE
            self.api_key_edit.setEchoMode(_QLE.EchoMode.Normal if mode != _QLE.EchoMode.Normal else _QLE.EchoMode.Password)
        except Exception:
            self.api_key_edit.setEchoMode(QLineEdit.Normal if mode != QLineEdit.Normal else QLineEdit.Password)

    def _load_fields(self) -> None:
        try:
            if not self.browser:
                return
            sel = self.browser.selectedNotes();
            if not sel:
                return
            n = mw.col.get_note(sel[0])
            names = [f["name"] for f in n.note_type()["flds"]]
            self.src_combo.clear(); self.dst_combo.clear(); self.src_combo.addItems(names); self.dst_combo.addItems(names)
        except Exception:
            pass

    def _load_languages(self) -> None:
        try:
            langs = get_languages("Edge-TTS")  # returns {code: full_name}
            items = sorted(langs.items(), key=lambda x: x[1])
            self.language_combo.clear()
            for code, full in items:
                self.language_combo.addItem(full, code)
            # seed voices for initial language
            self._update_all_voices()
        except Exception as e:
            print(f"[AINotePro] load languages failed: {e}")

    def _current_lang_code(self) -> str:
        idx = self.language_combo.currentIndex()
        if idx < 0:
            return "en"
        data = self.language_combo.itemData(idx)
        return data or "en"

    def _update_all_voices(self) -> None:
        for blk in self.voice_blocks:
            self._update_block_voices(blk)

    def _update_block_voices(self, blk: dict) -> None:
        try:
            code = self._current_lang_code()
            gender = blk["gender"].currentText()
            short_names = get_voices("Edge-TTS", code, gender) or []  # e.g., en-US-AriaNeural
            cur_data = blk["voice"].currentData()
            blk["voice"].clear()
            for sn in short_names:
                display = sn.split("-")[-1] if "-" in sn else sn
                blk["voice"].addItem(display, sn)
            if cur_data:
                i = blk["voice"].findData(cur_data)
                if i >= 0:
                    blk["voice"].setCurrentIndex(i)
        except Exception as e:
            print(f"[AINotePro] update voices failed: {e}")

    # Settings persistence
    def _load_settings(self) -> None:
        cfg = self.cfg.get_all().get("audio", {}).get("edge_tts", {})
        # language
        lang_code = cfg.get("language_code")
        if lang_code:
            for i in range(self.language_combo.count()):
                if self.language_combo.itemData(i) == lang_code:
                    self.language_combo.setCurrentIndex(i)
                    break
        # voices (list of up to 3)
        voices = cfg.get("voices") or []
        for idx, blk in enumerate(self.voice_blocks):
            if idx >= len(voices):
                break
            vcfg = voices[idx]
            blk["enable"].setChecked(bool(vcfg.get("enabled", False)))
            # gender first (so voices query matches)
            g = vcfg.get("gender") or "Female"
            gi = blk["gender"].findText(g)
            if gi >= 0:
                blk["gender"].setCurrentIndex(gi)
            # refresh voices for current gender/lang, then set voice by data
            self._update_block_voices(blk)
            short_name = vcfg.get("voice")
            if short_name:
                vi = blk["voice"].findData(short_name)
                if vi >= 0:
                    blk["voice"].setCurrentIndex(vi)
            blk["speed"].setValue(int(vcfg.get("speed", 0)))
            blk["volume"].setValue(int(vcfg.get("volume", 0)))
            blk["pitch"].setValue(int(vcfg.get("pitch", 0)))
            if vcfg.get("preview_text"):
                blk["preview"].setText(vcfg.get("preview_text"))

    def save_settings(self) -> None:
        voices_cfg = []
        for blk in self.voice_blocks:
            voices_cfg.append({
                "enabled": blk["enable"].isChecked(),
                "voice": blk["voice"].currentData() or blk["voice"].currentText(),
                "gender": blk["gender"].currentText(),
                "speed": blk["speed"].value(),
                "volume": blk["volume"].value(),
                "pitch": blk["pitch"].value(),
                "preview_text": blk["preview"].text().strip(),
            })
        data = self.cfg.get_all()
        audio = data.setdefault("audio", {})
        et = audio.setdefault("edge_tts", {})
        et["language_code"] = self._current_lang_code()
        et["voices"] = voices_cfg
        self.cfg.save_all(data)

    def _preview_voice(self, enable_cb: QCheckBox, voice_combo: QComboBox, text_edit: QLineEdit):
        if not enable_cb.isChecked():
            showWarning("Enable this voice first."); return
        text = text_edit.text().strip() or "Hello from AINotePro!"
        voice = voice_combo.currentData() or voice_combo.currentText().strip() or "en-US-AriaNeural"
        provider = create_provider("audio", "edge_tts", {})
        try:
            preview_snippet = (text[:60] + "…") if len(text) > 60 else text
            print(f"[AINotePro][TTS Preview] voice={voice}, text_len={len(text)}, text=\"{preview_snippet}\"")
            data = provider.generate(text, {"voice": voice, "speed": 0, "volume": 0, "pitch": 0})
            # play via Anki after writing to temp media
            fname = add_audio_to_media_collection(data, "preview.mp3")
            from aqt.sound import play
            play(mw.col.media.dir() + os.sep + fname)
        except Exception as e:
            showWarning(f"Preview failed: {e}")

    # Called by parent dialog
    def on_generate_tts(self) -> None:
        if not self.browser:
            showWarning("Browser is not ready."); return
        note_ids = self.browser.selectedNotes()
        if not note_ids:
            showWarning("No notes selected."); return
        src = self.src_combo.currentText(); dst = self.dst_combo.currentText()
        provider = create_provider("audio", "edge_tts", {})
        progress = QProgressDialog("Generating TTS...", "Cancel", 0, len(note_ids), self); progress.setWindowTitle("TTS"); progress.show()
        for i, nid in enumerate(note_ids):
            if progress.wasCanceled(): break
            note = mw.col.get_note(nid)
            text = (get_field_content(note, src, "") or "").strip()
            if not text: continue
            # pick first enabled voice
            voice = "en-US-AriaNeural"; speed = volume = pitch = 0
            for block in self.voice_blocks:
                if block["enable"].isChecked():
                    # Prefer the stored short name in item data; fall back to the visible text or default
                    voice = block["voice"].currentData() or block["voice"].currentText().strip() or voice
                    speed = block["speed"].value(); volume = block["volume"].value(); pitch = block["pitch"].value();
                    break
            try:
                data = provider.generate(text, {"voice": voice, "speed": speed, "volume": volume, "pitch": pitch})
                fname = add_audio_to_media_collection(data, f"ainotepro-{nid}.mp3")
                new_val = f"{get_field_content(note, dst, '')} [sound:{fname}]".strip()
                update_field_content(note, dst, new_val)
            except Exception as e:
                print(f"[Note {nid}] TTS failed: {e}")
            progress.setValue(i+1)
        progress.close(); showInfo("TTS complete.")
