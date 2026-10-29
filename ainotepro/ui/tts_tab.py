"""Audio V2 UI: existing three-Voice layout with profiles and asynchronous generation.

No Anki collection or Qt widgets are accessed from background workers.
"""
from __future__ import annotations

import copy
import html
import os
import random
import re
import tempfile

from aqt import mw
from aqt.qt import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QComboBox, QCheckBox,
    QLineEdit, QSlider, QGroupBox, QSizePolicy, QFrame, Qt, QProgressDialog,
    QMessageBox, QScrollArea, QInputDialog, QTimer
)
from aqt.utils import showInfo, showWarning

from ..config.manager import ConfigManager
from ..config.audio_profiles import default_profile, new_profile_id, validate_audio
from ..gen_audio.models.edge_tts.tts_handler import get_languages, get_voices
from ..services.provider_factory import create_provider
from ..core.async_task import AsyncTask
from ..core.audio_provenance import owned_tag, record
from ..core.utils import add_audio_to_media_collection, get_field_content

SOUND_RE = re.compile(r"\[sound:[^\]\r\n]+\]")
HTML_RE = re.compile(r"<[^>]*>")
RATINGS = {
    "af_heart":"A", "af_bella":"A-", "af_nicole":"B-", "af_aoede":"C+",
    "af_kore":"C+", "af_sarah":"C+", "af_alloy":"C", "af_nova":"C",
    "af_sky":"C-", "af_jessica":"D", "af_river":"D",
    "am_fenrir":"C+", "am_michael":"C+", "am_puck":"C+", "am_echo":"D",
    "am_eric":"D", "am_liam":"D", "am_onyx":"D", "am_santa":"D-",
    "am_adam":"F+", "bf_emma":"B-", "bf_isabella":"C", "bf_alice":"D",
    "bf_lily":"D", "bm_fable":"C", "bm_george":"C", "bm_lewis":"D+",
    "bm_daniel":"D"
}
# Keep a strong reference until each QThread has actually finished.
_WORKERS = set()


def _task(target, success, failure):
    task = AsyncTask(target=target)
    _WORKERS.add(task)
    task.finished_ok.connect(success)
    task.failed.connect(failure)
    task.finished.connect(lambda t=task: _WORKERS.discard(t))
    task.start()
    return task


def _spoken_text(value):
    value = SOUND_RE.sub(" ", value or "")
    value = re.sub(r"(?i)<(br\s*/?|/p|/div)>", " ", value)
    value = HTML_RE.sub(" ", value)
    return " ".join(html.unescape(value).split())


def _select_voice(voices, chooser=None):
    """Select a complete block, not independently sampled parameters."""
    active = [copy.deepcopy(v) for v in voices if v.get("enabled") and v.get("voice")]
    if not active:
        raise ValueError("Enable at least one valid Voice block")
    return (chooser or random.choice)(active)


class TTSTab(QWidget):
    def __init__(self, parent=None, browser=None, note_ids=None, editor=None):
        super().__init__(parent)
        self.browser, self.editor = browser, editor
        self.note_ids = list(note_ids or [])
        self.cfg = ConfigManager()
        self._audio = self.cfg.get_audio()
        self._revision = self.cfg.audio_revision()
        self._profile_id = self._audio.get("last_profile_id")
        self._draft = (copy.deepcopy(self._audio["profiles"][self._profile_id])
                       if self._profile_id else default_profile("Unsaved Audio settings"))
        self._saved = copy.deepcopy(self._draft)
        self._loading = False
        self._probe_id = 0
        self._draft_revision = 0
        self._probe_state = "unprobed"
        self._available = []
        self._edge_cache = {}
        self._edge_request = 0
        self._running = False
        self._cancelled = False
        self._closing = False
        self._items = []
        self._cursor = 0
        self._results = {}
        self._undo_id = None
        self._build_ui()
        self._load_fields()
        self._load_languages()
        self._refresh_profiles()
        self._apply_draft()

    def _build_ui(self):
        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget(); layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 8, 8, 8); layout.setSpacing(6)
        layout.addWidget(QLabel('<div style="font-size:14px;font-weight:900;">Generate audio from a note field</div>'))
        profile_row = QHBoxLayout()
        profile_row.addWidget(QLabel("Profile:"))
        self.profile_combo = QComboBox(); profile_row.addWidget(self.profile_combo, 1)
        for label, handler in (("Load", self.load_profile), ("Save", self.save_profile),
                               ("Save As", self.save_as_profile), ("Delete", self.delete_profile)):
            button = QPushButton(label); button.clicked.connect(handler); profile_row.addWidget(button)
        layout.addLayout(profile_row)
        h = QHBoxLayout(); h.addWidget(QLabel("Generate using"))
        self.generate_combo = QComboBox()
        self.generate_combo.addItem("Edge-TTS", "edge_tts")
        self.generate_combo.addItem("Kokoro MLX (Local)", "kokoro_gradio")
        h.addWidget(self.generate_combo, 1)
        h.addWidget(QLabel("Language:"))
        self.language_combo = QComboBox(); h.addWidget(self.language_combo, 1)
        layout.addLayout(h)
        state_row = QHBoxLayout()
        self.url_label = QLabel("Local URL:")
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("http://127.0.0.1:7860")
        self.url_edit.setMaximumWidth(190)
        self.url_edit.editingFinished.connect(self._url_changed)
        state_row.addWidget(self.url_label); state_row.addWidget(self.url_edit)
        self.status_label = QLabel(""); state_row.addWidget(self.status_label, 1)
        self.retry_button = QPushButton("Retry"); self.retry_button.clicked.connect(self._probe)
        state_row.addWidget(self.retry_button); layout.addLayout(state_row)
        self.voice_blocks = []
        for index in range(3):
            box = QGroupBox(f"Voice {index+1}")
            vb = QVBoxLayout(box); vb.setContentsMargins(10, 8, 10, 8)
            row = QHBoxLayout()
            enable = QCheckBox(f"Enable Voice {index+1}")
            voice = QComboBox(); voice.setMinimumWidth(150)
            preview = QLineEdit(); preview.setPlaceholderText("Type a phrase to test...")
            button = QPushButton("Preview")
            button.clicked.connect(lambda _, i=index: self._preview(i))
            row.addWidget(enable); row.addWidget(voice); row.addWidget(preview, 1); row.addWidget(button)
            vb.addLayout(row)
            params = QHBoxLayout()
            accent_label = QLabel("Accent:")
            accent = QComboBox(); accent.addItems(["American", "British"])
            params.addWidget(accent_label); params.addWidget(accent)
            params.addWidget(QLabel("Gender:"))
            gender = QComboBox(); gender.addItems(["Female", "Male"]); params.addWidget(gender)
            params.addWidget(QLabel("Speed:"))
            speed = QSlider(Qt.Orientation.Horizontal); params.addWidget(speed, 2)
            speed_label = QLabel(""); params.addWidget(speed_label)
            volume_label = QLabel("Volume:"); params.addWidget(volume_label)
            volume = QSlider(Qt.Orientation.Horizontal); volume.setRange(-50, 50); params.addWidget(volume, 2)
            pitch_label = QLabel("Pitch:"); params.addWidget(pitch_label)
            pitch = QSlider(Qt.Orientation.Horizontal); pitch.setRange(-50, 50); params.addWidget(pitch, 2)
            vb.addLayout(params); layout.addWidget(box)
            block = dict(enable=enable, voice=voice, preview=preview, button=button,
                         accent=accent, accent_label=accent_label, gender=gender,
                         speed=speed, speed_label=speed_label, volume=volume,
                         volume_label=volume_label, pitch=pitch, pitch_label=pitch_label)
            self.voice_blocks.append(block)
            accent.currentIndexChanged.connect(lambda _, b=block: self._voice_filter_changed(b))
            gender.currentIndexChanged.connect(lambda _, b=block: self._voice_filter_changed(b))
            for widget in (enable, voice, preview, speed, volume, pitch):
                if isinstance(widget, QCheckBox):
                    widget.toggled.connect(self._mark_dirty)
                elif isinstance(widget, QLineEdit):
                    widget.textChanged.connect(self._mark_dirty)
                elif isinstance(widget, QSlider):
                    widget.valueChanged.connect(lambda _, b=block: self._slider_changed(b))
                else:
                    widget.currentIndexChanged.connect(self._mark_dirty)
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine); layout.addWidget(sep)
        fields = QHBoxLayout()
        fields.addWidget(QLabel("Source Field:"))
        self.src_combo = QComboBox(); fields.addWidget(self.src_combo, 1)
        fields.addWidget(QLabel("Destination Field:"))
        self.dst_combo = QComboBox(); fields.addWidget(self.dst_combo, 1)
        self.replace_check = QCheckBox("Replace managed audio only")
        fields.addWidget(self.replace_check)
        layout.addLayout(fields)
        scroll.setWidget(content); root.addWidget(scroll)
        self.generate_combo.currentIndexChanged.connect(self._provider_changed)
        self.language_combo.currentIndexChanged.connect(self._language_changed)
        self.src_combo.currentIndexChanged.connect(self._mark_dirty)
        self.dst_combo.currentIndexChanged.connect(self._mark_dirty)

    def _selected_note_ids(self):
        if self.browser:
            try: return list(self.browser.selectedNotes())
            except Exception: return []
        return list(self.note_ids)

    def _load_fields(self):
        try:
            ids = self._selected_note_ids()
            if not ids: return
            note = mw.col.get_note(ids[0])
            fields = [f["name"] for f in note.note_type()["flds"]]
            self.src_combo.addItems(fields); self.dst_combo.addItems(fields)
        except Exception:
            pass

    def _load_languages(self):
        self._languages = get_languages("Edge-TTS")
        self._set_languages("edge_tts")

    def _set_languages(self, provider):
        self.language_combo.blockSignals(True)
        self.language_combo.clear()
        if provider == "kokoro_gradio":
            self.language_combo.addItem("English", "en")
            self.language_combo.setEnabled(False)
        else:
            for code, name in sorted(self._languages.items(), key=lambda x: x[1]):
                self.language_combo.addItem(name, code)
            self.language_combo.setEnabled(True)
        self.language_combo.blockSignals(False)

    def _refresh_profiles(self):
        self.profile_combo.clear()
        for pid, profile in self._audio["profiles"].items():
            self.profile_combo.addItem(profile["name"], pid)
        i = self.profile_combo.findData(self._profile_id)
        if i >= 0: self.profile_combo.setCurrentIndex(i)

    def _is_dirty(self):
        self._capture()
        return self._draft != self._saved

    def _confirm_discard(self):
        if not self._is_dirty(): return True
        choice = QMessageBox.question(self, "Unsaved Audio Profile",
            "Save changes to the current Profile before continuing?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
        if choice == QMessageBox.StandardButton.Cancel: return False
        if choice == QMessageBox.StandardButton.Save: return self.save_profile()
        return True

    def _capture(self):
        if self._loading: return
        provider = self._draft["provider"]
        conf = self._draft["provider_configs"][provider]
        if provider == "kokoro_gradio":
            conf["base_url"] = self.url_edit.text().strip()
        if provider == "edge_tts":
            conf["language_code"] = self.language_combo.currentData() or "en"
        for block, voice in zip(self.voice_blocks, conf["voices"]):
            voice["enabled"] = block["enable"].isChecked()
            voice["voice"] = block["voice"].currentData() or ""
            voice["gender"] = block["gender"].currentText()
            voice["preview_text"] = block["preview"].text()
            if provider == "kokoro_gradio":
                voice["accent"] = block["accent"].currentText()
                voice["locale"] = "en-GB" if voice["accent"] == "British" else "en-US"
                voice["speed"] = round(block["speed"].value() / 100, 2)
            else:
                voice["speed"] = block["speed"].value()
                voice["volume"] = block["volume"].value()
                voice["pitch"] = block["pitch"].value()
        self._draft["source_field"] = self.src_combo.currentText() if self.src_combo.currentIndex() >= 0 else ""
        self._draft["destination_field"] = self.dst_combo.currentText() if self.dst_combo.currentIndex() >= 0 else ""

    def _apply_draft(self):
        self._loading = True
        try:
            provider = self._draft["provider"]
            self.generate_combo.setCurrentIndex(self.generate_combo.findData(provider))
            self._set_languages(provider)
            conf = self._draft["provider_configs"][provider]
            self.url_edit.setText(self._draft["provider_configs"]["kokoro_gradio"]["base_url"])
            self.url_label.setVisible(provider == "kokoro_gradio")
            self.url_edit.setVisible(provider == "kokoro_gradio")
            if provider == "edge_tts":
                i = self.language_combo.findData(conf.get("language_code", "en"))
                if i >= 0: self.language_combo.setCurrentIndex(i)
            for block, voice in zip(self.voice_blocks, conf["voices"]):
                block["enable"].setChecked(voice["enabled"])
                block["gender"].setCurrentText(voice["gender"])
                block["accent"].setCurrentText(voice.get("accent", "American"))
                block["preview"].setText(voice.get("preview_text", ""))
                block["speed"].setRange(70, 130) if provider == "kokoro_gradio" else block["speed"].setRange(-50, 50)
                block["speed"].setValue(round(voice["speed"] * 100) if provider == "kokoro_gradio" else voice["speed"])
                block["volume"].setValue(voice.get("volume", 0))
                block["pitch"].setValue(voice.get("pitch", 0))
                for key in ("volume", "pitch"):
                    block[key].setEnabled(provider == "edge_tts")
                    block[key].setToolTip("" if provider == "edge_tts" else "Not supported by Kokoro")
                for key in ("accent", "accent_label"):
                    block[key].setVisible(provider == "kokoro_gradio")
                self._populate_voice(block, voice.get("voice", ""))
                self._slider_changed(block)
            for combo, field in ((self.src_combo, self._draft["source_field"]),
                                 (self.dst_combo, self._draft["destination_field"])):
                i = combo.findText(field)
                combo.setCurrentIndex(i if i >= 0 else -1)
            self.retry_button.setVisible(provider == "kokoro_gradio")
        finally:
            self._loading = False
        if provider == "kokoro_gradio": self._probe()
        else:
            self._probe_id += 1
            self.status_label.setText("")
            self._request_edge_voices()
        self._refresh_availability()

    def _mark_dirty(self, *_):
        if not self._loading:
            self._capture()
            self._draft_revision += 1

    def _url_changed(self):
        if self._loading or self._draft["provider"] != "kokoro_gradio":
            return
        old = self._draft["provider_configs"]["kokoro_gradio"]["base_url"]
        self._capture()
        if old != self._draft["provider_configs"]["kokoro_gradio"]["base_url"]:
            self._draft_revision += 1
            self._probe()

    def _slider_changed(self, block):
        if not self._loading: self._capture()
        block["speed_label"].setText(
            f'{block["speed"].value()/100:.2f}×' if self._draft["provider"] == "kokoro_gradio" else f'{block["speed"].value():+d}%')

    def _provider_changed(self, *_):
        if self._loading: return
        self._capture()
        self._draft["provider"] = self.generate_combo.currentData()
        self._draft_revision += 1
        self._apply_draft()

    def _language_changed(self, *_):
        if self._loading: return
        self._capture()
        self._draft["provider_configs"]["edge_tts"]["language_code"] = self.language_combo.currentData() or "en"
        self._request_edge_voices()

    def _voice_filter_changed(self, block):
        if self._loading: return
        self._capture()
        self._populate_voice(block, "")
        self._capture()
        self._draft_revision += 1

    def _populate_voice(self, block, wanted):
        provider = self._draft["provider"]
        block["voice"].blockSignals(True)
        block["voice"].clear()
        if provider == "kokoro_gradio":
            prefix = ("b" if block["accent"].currentText() == "British" else "a") + ("f" if block["gender"].currentText() == "Female" else "m") + "_"
            choices = [v for v in self._available if v.startswith(prefix)]
            for v in choices:
                block["voice"].addItem(f'{v[3:].title()} · {block["accent"].currentText()} {block["gender"].currentText()} · {RATINGS.get(v, "Unrated")} ({v})', v)
        else:
            lang = self.language_combo.currentData() or "en"
            choices = self._edge_cache.get((lang, block["gender"].currentText()), [])
            for v in choices: block["voice"].addItem(v.split("-")[-1], v)
        i = block["voice"].findData(wanted)
        if wanted and i < 0:
            block["voice"].addItem(f"Unavailable / saved: {wanted}", wanted)
            i = block["voice"].count() - 1
        block["voice"].setCurrentIndex(i if i >= 0 else -1)
        block["voice"].blockSignals(False)

    def _request_edge_voices(self):
        if self._draft["provider"] != "edge_tts": return
        lang = self.language_combo.currentData() or "en"
        self._edge_request += 1
        request = self._edge_request
        def fetch():
            return {gender: get_voices("Edge-TTS", lang, gender) for gender in ("Female", "Male")}
        def done(values):
            if self._closing or request != self._edge_request or self._draft["provider"] != "edge_tts": return
            for gender, voices in values.items(): self._edge_cache[(lang, gender)] = voices
            self._capture()
            self._loading = True
            for block, voice in zip(self.voice_blocks, self._draft["provider_configs"]["edge_tts"]["voices"]):
                self._populate_voice(block, voice["voice"])
            self._loading = False
        _task(fetch, done, lambda err: None if self._closing else self.status_label.setText(f"Edge voice list: {err[:120]}"))

    def _probe(self, *_):
        if self._draft["provider"] != "kokoro_gradio": return
        self._probe_id += 1
        request = self._probe_id
        revision = self._draft_revision
        url = self._draft["provider_configs"]["kokoro_gradio"]["base_url"]
        self._probe_state = "checking"; self.status_label.setText("Kokoro: Checking...")
        self._refresh_availability()
        def fetch():
            return create_provider("audio", "kokoro_gradio", {}).probe({"base_url": url})
        def done(voices):
            if self._closing or request != self._probe_id or self._draft["provider"] != "kokoro_gradio": return
            if revision != self._draft_revision or url != self._draft["provider_configs"]["kokoro_gradio"]["base_url"]:
                self._probe()
                return
            self._capture()
            self._available = voices; self._probe_state = "ready"
            self.status_label.setText(f"Kokoro: Ready · {len(voices)} English voices")
            self._loading = True
            for block, voice in zip(self.voice_blocks, self._draft["provider_configs"]["kokoro_gradio"]["voices"]):
                self._populate_voice(block, voice["voice"])
            self._loading = False
            self._refresh_availability()
        def failed(err):
            if request != self._probe_id or self._draft["provider"] != "kokoro_gradio": return
            if revision != self._draft_revision:
                self._probe()
                return
            self._available = []; self._probe_state = "unavailable"
            self.status_label.setText(f"Kokoro: Unavailable · {err[:150]}")
            self._refresh_availability()
        _task(fetch, done, failed)

    def _refresh_availability(self):
        ready = self._draft["provider"] == "edge_tts" or self._probe_state == "ready"
        for block in self.voice_blocks: block["button"].setEnabled(ready and not self._running)
        parent = self.parent()
        if parent is not None and hasattr(parent, "generate_button") and getattr(parent, "tab_widget", None) is not None:
            if parent.tab_widget.currentWidget() is self:
                parent.generate_button.setEnabled(not self._running and ready)

    def _save(self, profile_id, profile):
        new_audio = copy.deepcopy(self._audio)
        new_audio["profiles"][profile_id] = copy.deepcopy(profile)
        new_audio["last_profile_id"] = profile_id
        validate_audio(new_audio)
        self._revision = self.cfg.replace_audio(new_audio, expected_revision=self._revision)
        self._audio = new_audio; self._profile_id = profile_id
        self._draft = copy.deepcopy(profile); self._saved = copy.deepcopy(profile)
        self._refresh_profiles()
        return True

    def save_profile(self, *_):
        if not self._profile_id:
            showWarning("No Profile is loaded. Use Load or Save As first.")
            return False
        self._capture()
        try: return self._save(self._profile_id, self._draft)
        except Exception as exc:
            showWarning(f"Could not save Audio Profile: {exc}")
            return False

    def save_as_profile(self, *_):
        self._capture()
        name, ok = QInputDialog.getText(self, "Save Audio Profile As", "Profile name:")
        if not ok: return False
        name = name.strip()
        if not name: return False
        profile = copy.deepcopy(self._draft); profile["name"] = name
        try: return self._save(new_profile_id(), profile)
        except Exception as exc:
            showWarning(f"Could not save Audio Profile: {exc}")
            return False

    def load_profile(self, *_):
        pid = self.profile_combo.currentData()
        if not pid or not self._confirm_discard(): return False
        self._profile_id = pid
        self._draft = copy.deepcopy(self._audio["profiles"][pid])
        self._saved = copy.deepcopy(self._draft)
        self._apply_draft()
        try:
            new_audio = copy.deepcopy(self._audio)
            new_audio["last_profile_id"] = pid
            self._revision = self.cfg.replace_audio(new_audio, expected_revision=self._revision)
            self._audio = new_audio
        except Exception as exc:
            showWarning(f"Profile loaded, but last selection could not be saved: {exc}")
        return True

    def delete_profile(self, *_):
        pid = self.profile_combo.currentData()
        if not pid or len(self._audio["profiles"]) <= 1:
            showWarning("The last Audio Profile cannot be deleted."); return False
        if not self._confirm_discard(): return False
        if QMessageBox.question(self, "Delete Audio Profile", "Delete the selected Profile?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return False
        new_audio = copy.deepcopy(self._audio)
        del new_audio["profiles"][pid]
        if new_audio["last_profile_id"] == pid: new_audio["last_profile_id"] = None
        try:
            self._revision = self.cfg.replace_audio(new_audio, expected_revision=self._revision)
            self._audio = new_audio
            if self._profile_id == pid:
                self._profile_id = None
                self._draft = default_profile("Unsaved Audio settings")
                self._saved = copy.deepcopy(self._draft)
                self._apply_draft()
                self.status_label.setText("Profile deleted. Select another Profile and click Load.")
            self._refresh_profiles()
            return True
        except Exception as exc:
            showWarning(f"Could not delete Profile: {exc}"); return False

    def can_close(self):
        if not self._confirm_discard():
            return False
        self._closing = True
        self.request_cancel()
        return True

    def request_cancel(self):
        self._cancelled = True

    def _preview(self, index):
        self._capture()
        provider = self._draft["provider"]
        if provider == "kokoro_gradio" and self._probe_state != "ready":
            showWarning("Kokoro is unavailable. Retry first."); return
        config = copy.deepcopy(self._draft["provider_configs"][provider]["voices"][index])
        if not config["enabled"] or not config["voice"]:
            showWarning("Enable and configure this Voice first."); return
        if provider == "kokoro_gradio" and config["voice"] not in self._available:
            showWarning("This Kokoro voice is unavailable."); return
        if provider == "kokoro_gradio":
            config["base_url"] = self._draft["provider_configs"][provider]["base_url"]
        text = self.voice_blocks[index]["preview"].text().strip() or "Hello from AINotePro!"
        self.voice_blocks[index]["button"].setEnabled(False)
        def work(): return create_provider("audio", provider, {}).generate(text, config)
        def done(data):
            if self._closing: return
            self.voice_blocks[index]["button"].setEnabled(True)
            try:
                with tempfile.NamedTemporaryFile(prefix="ainotepro-preview-", suffix=".mp3", delete=False) as stream:
                    stream.write(data); path = stream.name
                from aqt.sound import play
                play(path)
                QTimer.singleShot(120000, lambda p=path: os.path.exists(p) and os.unlink(p))
            except Exception as exc:
                showWarning(f"Preview failed: {exc}")
        def failed(err):
            if self._closing: return
            self.voice_blocks[index]["button"].setEnabled(True)
            showWarning(f"Preview failed: {err}")
        _task(work, done, failed)

    def _refresh_editor(self, nid):
        editor = self.editor or getattr(self.browser, "editor", None)
        note = getattr(editor, "note", None) if editor else None
        if note and getattr(note, "id", None) == nid:
            for method in ("loadNoteKeepingFocus", "loadNote"):
                fn = getattr(editor, method, None)
                if callable(fn):
                    try: fn()
                    except Exception: pass
                    break

    def _confirm_write_risk(self, note_ids, src, dst):
        risks = []
        if src == dst: risks.append("Source and destination are the same field.")
        if len(note_ids) > 1: risks.append(f"This will process {len(note_ids)} notes.")
        if not risks: return True
        return QMessageBox.question(self, "Confirm Audio", "\n".join(risks) + "\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes

    def on_generate_tts(self):
        if self._running: return
        if not self._profile_id:
            showWarning("Select an Audio Profile and click Load (or Save As) before generating.")
            return
        self._capture()
        ids = self._selected_note_ids()
        src, dst = self._draft["source_field"], self._draft["destination_field"]
        if not ids or not src or not dst:
            showWarning("Select notes and valid Source/Destination fields."); return
        provider = self._draft["provider"]
        if provider == "kokoro_gradio" and self._probe_state != "ready":
            showWarning("Kokoro is offline; retry before generating."); return
        config = copy.deepcopy(self._draft["provider_configs"][provider])
        voices = config["voices"]
        if provider == "kokoro_gradio":
            voices = [v for v in voices if not v["enabled"] or v["voice"] in self._available]
        try:
            validate_audio({"schema_version":2,"profiles":{"legacy-edge-default":self._draft},
                            "last_profile_id":"legacy-edge-default","migration":{"legacy_edge_v1_done":True}})
            if not any(v["enabled"] and v["voice"] for v in voices):
                raise ValueError("No valid enabled Voice")
        except Exception as exc:
            showWarning(f"Audio settings are invalid: {exc}"); return
        if not self._confirm_write_risk(ids, src, dst): return
        self._snapshot = dict(provider=provider, config=config, voices=copy.deepcopy(voices),
                              source=src, destination=dst, replace=self.replace_check.isChecked())
        self._items = ids; self._cursor = 0; self._results = {}
        self._cancelled = False; self._running = True; self._undo_id = None
        self._progress = QProgressDialog("Generating audio...", "Cancel", 0, len(ids), self)
        self._progress.setWindowTitle("AINotePro Audio")
        self._progress.setMinimumDuration(0)
        self._progress.canceled.connect(self.request_cancel)
        self._progress.show()
        self._refresh_availability()
        self._next()

    def _count(self, category):
        self._results[category] = self._results.get(category, 0) + 1

    def _next(self):
        if self._closing:
            return
        if self._cancelled or self._cursor >= len(self._items):
            self._finish(); return
        nid = self._items[self._cursor]; self._cursor += 1
        spec = self._snapshot
        try:
            note = mw.col.get_note(nid)
            src, dst = spec["source"], spec["destination"]
            if src not in note or dst not in note:
                self._count("skipped_invalid_fields"); self._advance(); return
            raw = get_field_content(note, src, "")
            text = _spoken_text(raw)
            if not text:
                self._count("skipped_empty"); self._advance(); return
            if spec["provider"] == "kokoro_gradio" and len(text) > 6000:
                self._count("failed_validation"); self._advance(); return
            original = get_field_content(note, dst, "")
            old_tag = None
            if SOUND_RE.search(original):
                if not spec["replace"]:
                    self._count("skipped_existing_audio"); self._advance(); return
                old_tag = owned_tag(nid, dst, original, mw.col.media.dir())
                if not old_tag:
                    self._count("skipped_existing_audio"); self._advance(); return
            voice = _select_voice(spec["voices"])
            if spec["provider"] == "kokoro_gradio":
                voice["base_url"] = spec["config"]["base_url"]
            snapshot = (nid, raw, original, old_tag, text, voice)
        except Exception as exc:
            self._count("failed_validation")
            print(f"[AINotePro Audio] snapshot {nid}: {exc}")
            self._advance(); return
        def work():
            return create_provider("audio", spec["provider"], {}).generate(snapshot[4], snapshot[5])
        def done(data):
            if self._cancelled:
                self._count("cancelled")
            else:
                self._commit(snapshot, data)
            self._advance()
        def failed(err):
            self._count("failed_synthesis")
            print(f"[AINotePro Audio] synthesis {nid}: {err}")
            self._advance()
        _task(work, done, failed)

    def _commit(self, snapshot, data):
        if self._closing:
            return
        nid, raw, original, old_tag, _text, voice = snapshot
        spec = self._snapshot
        if self._cancelled:
            self._count("cancelled"); return
        try:
            note = mw.col.get_note(nid)
            src, dst = spec["source"], spec["destination"]
            if src not in note or dst not in note or note[src] != raw or note[dst] != original:
                self._count("conflict_skipped"); return
            if old_tag:
                if owned_tag(nid, dst, original, mw.col.media.dir()) != old_tag:
                    self._count("conflict_skipped"); return
            elif SOUND_RE.search(original):
                self._count("conflict_skipped"); return
            # Final cancel gate. Once media is written, finish this note's commit.
            if self._cancelled:
                self._count("cancelled"); return
            if self._undo_id is None:
                add = getattr(mw.col, "add_custom_undo_entry", None)
                merge = getattr(mw.col, "merge_undo_entries", None)
                if not callable(add) or not callable(merge):
                    raise RuntimeError("Anki collection undo grouping API unavailable")
                self._undo_id = add("AINotePro audio generation")
            filename = add_audio_to_media_collection(data, f"ainotepro-{nid}.mp3")
            tag = f"[sound:{filename}]"
            content = original.replace(old_tag, tag, 1) if old_tag else (original + " " + tag).strip()
            note[dst] = content
            try:
                mw.col.update_note(note)
                mw.col.merge_undo_entries(self._undo_id)
            except Exception:
                self._count("failed_commit")
                return
            self._refresh_editor(nid)
            try:
                record(nid, dst, filename, data, spec["provider"])
                self._count("success")
            except Exception as exc:
                self._count("generated_unmanaged")
                print(f"[AINotePro Audio] provenance {nid}: {exc}")
        except Exception as exc:
            self._count("failed_commit")
            print(f"[AINotePro Audio] commit {nid}: {exc}")

    def _advance(self):
        if not self._running or self._closing: return
        self._progress.setValue(self._cursor)
        QTimer.singleShot(0, self._next)

    def _finish(self):
        if not self._running or self._closing: return
        if self._cancelled:
            self._results["cancelled"] = self._results.get("cancelled", 0) + len(self._items) - self._cursor
        self._running = False
        self._progress.close()
        self._refresh_availability()
        try: mw.reset()
        except Exception: pass
        summary = ", ".join(f"{k}: {v}" for k, v in sorted(self._results.items()))
        showInfo("Audio batch complete. " + (summary or "No notes changed."))

    def closeEvent(self, event):
        if not self.can_close():
            event.ignore(); return
        super().closeEvent(event)
