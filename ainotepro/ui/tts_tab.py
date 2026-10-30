"""Audio V2 UI: existing three-Voice layout with profiles and asynchronous generation.

No Anki collection or Qt widgets are accessed from background workers.
"""
from __future__ import annotations

import copy
import html
import os
import random
import re
from ..core.audio_preview import play_preview, stop_previews

from aqt import mw
from aqt.qt import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QComboBox, QCheckBox,
    QLineEdit, QSlider, QGroupBox, QSizePolicy, QFrame, Qt, QProgressDialog,
    QMessageBox, QTimer
)
from aqt.utils import showInfo, showWarning

from ..config.manager import ConfigManager
from ..config.audio_profiles import new_profile_id, validate_audio
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
        self._audio, self._revision = self.cfg.get_audio_snapshot()
        self._profile_id = self._audio.get("last_profile_id")
        if self._profile_id is None:
            # A deleted/cleared selection must not silently open an unrelated
            # unsaved default when saved Profiles still exist.
            self._profile_id = next(iter(sorted(
                self._audio["profiles"],
                key=lambda pid: (self._audio["profiles"][pid]["name"].casefold(), pid)
            )))
        self._draft = copy.deepcopy(self._audio["profiles"][self._profile_id])
        self._saved = copy.deepcopy(self._draft)
        # _load_fields() emits currentIndexChanged while adding the first field.
        # Keep all initialization signals from capturing blank/uninitialized
        # voice combos, URL and speed sliders into the saved Profile draft.
        self._loading = True
        self._probe_id = 0
        self._draft_revision = 0
        self._probe_state = "unprobed"
        self._available = []
        self._edge_cache = {}
        self._edge_request = 0
        self._running = False
        self._cancelled = False
        self._closing = False
        self._close_pending = False
        self._close_ready = False
        self._halt_reason = None
        self._committing = False
        self._edge_state = "unprobed"
        self._items = []
        self._cursor = 0
        self._results = {}
        self._undo_id = None
        self._build_ui()
        self._load_fields()
        self._load_languages()
        self._refresh_profiles(self._draft["name"] if self._profile_id else "")
        self._apply_draft()

    def _build_ui(self):
        # Audio fits on one page: no nested scroll area. Profile actions belong
        # below the voice/field controls, immediately above the dialog footer.
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 4, 8, 2)
        root.setSpacing(4)
        title = QLabel('<b>Generate audio from a note field</b>')
        root.addWidget(title)

        h = QHBoxLayout()
        h.setSpacing(6)
        h.addWidget(QLabel("Generate using"))
        self.generate_combo = QComboBox()
        self.generate_combo.addItem("Edge-TTS", "edge_tts")
        self.generate_combo.addItem("Kokoro MLX (Local)", "kokoro_gradio")
        h.addWidget(self.generate_combo, 1)
        h.addWidget(QLabel("Language:"))
        self.language_combo = QComboBox()
        h.addWidget(self.language_combo, 1)
        root.addLayout(h)

        state_row = QHBoxLayout()
        state_row.setSpacing(6)
        self.url_label = QLabel("Local URL:")
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("http://127.0.0.1:7860")
        self.url_edit.setMaximumWidth(190)
        self.url_edit.editingFinished.connect(self._url_changed)
        state_row.addWidget(self.url_label)
        state_row.addWidget(self.url_edit)
        self.status_label = QLabel("")
        state_row.addWidget(self.status_label, 1)
        self.retry_button = QPushButton("Retry")
        self.retry_button.clicked.connect(self._probe)
        state_row.addWidget(self.retry_button)
        root.addLayout(state_row)

        self.voice_blocks = []
        for index in range(3):
            box = QGroupBox(f"Voice {index + 1}")
            vb = QVBoxLayout(box)
            vb.setContentsMargins(7, 5, 7, 5)
            vb.setSpacing(3)
            row = QHBoxLayout()
            row.setSpacing(6)
            enable = QCheckBox(f"Enable Voice {index + 1}")
            voice = QComboBox()
            voice.setMinimumWidth(165)
            preview = QLineEdit()
            preview.setPlaceholderText("Type a phrase to test...")
            button = QPushButton("Preview")
            button.clicked.connect(lambda _, i=index: self._preview(i))
            row.addWidget(enable)
            row.addWidget(voice, 2)
            row.addWidget(preview, 3)
            row.addWidget(button)
            vb.addLayout(row)

            params = QHBoxLayout()
            params.setSpacing(5)
            accent_label = QLabel("Accent:")
            accent = QComboBox()
            accent.addItems(["American", "British"])
            params.addWidget(accent_label)
            params.addWidget(accent)
            params.addWidget(QLabel("Gender:"))
            gender = QComboBox()
            gender.addItems(["Female", "Male"])
            params.addWidget(gender)
            params.addWidget(QLabel("Speed:"))
            speed = QSlider(Qt.Orientation.Horizontal)
            params.addWidget(speed, 2)
            speed_label = QLabel("")
            params.addWidget(speed_label)
            volume_label = QLabel("Volume:")
            params.addWidget(volume_label)
            volume = QSlider(Qt.Orientation.Horizontal)
            volume.setRange(-50, 50)
            params.addWidget(volume, 2)
            pitch_label = QLabel("Pitch:")
            params.addWidget(pitch_label)
            pitch = QSlider(Qt.Orientation.Horizontal)
            pitch.setRange(-50, 50)
            params.addWidget(pitch, 2)
            vb.addLayout(params)
            root.addWidget(box)

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

        fields = QHBoxLayout()
        fields.setSpacing(6)
        fields.addWidget(QLabel("Source Field:"))
        self.src_combo = QComboBox()
        fields.addWidget(self.src_combo, 1)
        fields.addWidget(QLabel("Destination Field:"))
        self.dst_combo = QComboBox()
        fields.addWidget(self.dst_combo, 1)
        self.replace_check = QCheckBox("Replace managed audio only")
        fields.addWidget(self.replace_check)
        root.addLayout(fields)
        root.addStretch(1)

        # Selecting an existing Profile loads it immediately. Typing a new name
        # only changes the proposed Save target; it never loads another Profile.
        profile_row = QHBoxLayout()
        profile_row.setSpacing(6)
        profile_row.addWidget(QLabel("Profile:"))
        self.profile_combo = QComboBox()
        self.profile_combo.setEditable(True)
        self.profile_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.profile_combo.setMaxVisibleItems(12)
        self.profile_combo.lineEdit().setPlaceholderText("Enter a name or select a saved Profile")
        profile_row.addWidget(self.profile_combo, 1)
        for label, handler in (("Save", self.save_profile),
                               ("Delete", self.delete_profile)):
            button = QPushButton(label)
            button.clicked.connect(handler)
            profile_row.addWidget(button)
        self.profile_combo.currentIndexChanged.connect(self._on_profile_selection_changed)
        root.addLayout(profile_row)

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

    def _refresh_profiles(self, display_name=None):
        # Preserve a typed, not-yet-saved name when refreshing the list.
        name = (self.profile_combo.currentText() if display_name is None
                else display_name)
        self.profile_combo.blockSignals(True)
        try:
            self.profile_combo.clear()
            self.profile_combo.addItem("", None)
            for pid, profile in sorted(self._audio["profiles"].items(),
                                       key=lambda item: item[1]["name"].casefold()):
                self.profile_combo.addItem(profile["name"], pid)
            self.profile_combo.setCurrentIndex(0)
            self.profile_combo.setEditText(name)
        finally:
            self.profile_combo.blockSignals(False)

    def _profile_for_name(self, name):
        for pid, profile in self._audio["profiles"].items():
            if profile["name"].casefold() == name.casefold():
                return pid
        return None

    def _selected_profile_id(self):
        # QComboBox.currentData() can still point to an old selection after
        # typing; resolve by the actual visible text instead.
        name = self.profile_combo.currentText().strip()
        return self._profile_for_name(name) if name else None

    def _is_dirty(self):
        self._capture()
        return self._draft != self._saved

    def _confirm_discard(self):
        if not self._is_dirty():
            return True
        # Close/Delete still offer Discard/Cancel. Saving through an editable
        # combo at this point could target a newly typed name instead.
        return QMessageBox.question(
            self, "Unsaved Audio Settings",
            "The current Audio settings have unsaved changes. Discard them?\n"
            "Click Cancel to return and use Save first.",
            QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel
        ) == QMessageBox.StandardButton.Discard

    def _restore_profile_selection(self):
        # The combo may already show the target of a cancelled switch. Always
        # restore the Profile that actually owns the visible editor draft.
        name = (self._audio["profiles"][self._profile_id]["name"]
                if self._profile_id in self._audio["profiles"] else "")
        self._refresh_profiles(name)

    def _confirm_profile_switch(self):
        if not self._is_dirty():
            return True
        choice = QMessageBox.question(
            self, "Unsaved Audio Settings",
            "Save changes to the current Audio Profile before switching?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard |
            QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel
        )
        if choice == QMessageBox.StandardButton.Discard:
            return True
        if choice != QMessageBox.StandardButton.Save:
            return False
        # Never use the combo's *new* selection as the Save target: its text
        # already belongs to the Profile the user is trying to switch to.
        if self._profile_id not in self._audio["profiles"]:
            showWarning("The current draft is not a saved Profile. Cancel the "
                        "switch and save it under a new name first.")
            return False
        original = copy.deepcopy(self._draft)
        original["name"] = self._audio["profiles"][self._profile_id]["name"]
        try:
            self._save(self._profile_id, original)
            return True
        except Exception as exc:
            showWarning(f"Could not save current Audio Profile: {exc}")
            return False

    def _on_profile_selection_changed(self, index):
        # Typing in the editable combo must not switch Profiles. Only selecting
        # an actual saved row does so, and _refresh_profiles blocks its signals.
        if self._loading or index < 0:
            return
        pid = self.profile_combo.itemData(index)
        if pid is None or pid == self._profile_id:
            return
        if not self._confirm_profile_switch():
            self._restore_profile_selection()
            return
        if not self._activate_profile(pid):
            self._restore_profile_selection()

    def _capture(self):
        if self._loading: return
        provider = self._draft["provider"]
        conf = self._draft["provider_configs"][provider]
        if provider == "kokoro_gradio":
            # Preserve the saved URL verbatim except for surrounding whitespace.
            # Both a bare origin and a trailing root slash are valid endpoints.
            conf["base_url"] = self.url_edit.text().strip()
        if provider == "edge_tts":
            conf["language_code"] = self.language_combo.currentData() or "en"
        for block, voice in zip(self.voice_blocks, conf["voices"]):
            voice["enabled"] = block["enable"].isChecked()
            selected_voice = block["voice"].currentData()
            # Provider discovery is asynchronous. An empty/unpopulated combo
            # must not erase a saved Voice while Kokoro or Edge is offline.
            if isinstance(selected_voice, str):
                voice["voice"] = selected_voice
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
        # No selected note, or a different note type, may leave field combos
        # empty. That is not a request to erase saved Profile field names.
        if self.src_combo.currentIndex() >= 0:
            self._draft["source_field"] = self.src_combo.currentText()
        if self.dst_combo.currentIndex() >= 0:
            self._draft["destination_field"] = self.dst_combo.currentText()

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
        self._edge_state = "checking"
        self.status_label.setText("Edge: Loading voices...")
        self._refresh_availability()
        def fetch():
            return {gender: get_voices("Edge-TTS", lang, gender) for gender in ("Female", "Male")}
        def done(values):
            if self._closing or request != self._edge_request or self._draft["provider"] != "edge_tts": return
            for gender, voices in values.items(): self._edge_cache[(lang, gender)] = voices
            self._edge_state = "ready" if any(values.values()) else "unavailable"
            self.status_label.setText("Edge: Ready" if self._edge_state == "ready" else "Edge: No voices returned")
            self._capture()
            self._loading = True
            for block, voice in zip(self.voice_blocks, self._draft["provider_configs"]["edge_tts"]["voices"]):
                self._populate_voice(block, voice["voice"])
            self._loading = False
            self._refresh_availability()
        def failed(err):
            if self._closing or request != self._edge_request or self._draft["provider"] != "edge_tts":
                return
            self._edge_state = "unavailable"
            self.status_label.setText(f"Edge: Voice list unavailable · {err[:120]}")
            self._refresh_availability()
        _task(fetch, done, failed)

    def _probe(self, *_):
        if self._draft["provider"] != "kokoro_gradio": return
        # Retry must use the URL currently visible in the editor, even when
        # QLineEdit.editingFinished has not fired yet.
        self._capture()
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
            if self._closing or request != self._probe_id or self._draft["provider"] != "kokoro_gradio": return
            if revision != self._draft_revision:
                self._probe()
                return
            self._available = []; self._probe_state = "unavailable"
            self.status_label.setText(f"Kokoro: Unavailable · {err[:150]}")
            self._refresh_availability()
        _task(fetch, done, failed)

    def _refresh_availability(self):
        ready = (self._edge_state == "ready" if self._draft["provider"] == "edge_tts"
                 else self._probe_state == "ready")
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
        self._audio = new_audio
        self._profile_id = profile_id
        self._draft = copy.deepcopy(profile)
        self._saved = copy.deepcopy(profile)
        self._refresh_profiles(profile["name"])
        return True

    def save_profile(self, *_):
        # Save is both Create and Update; Save As / New are unnecessary.
        name = self.profile_combo.currentText().strip()
        if not name:
            showWarning("Enter a Profile name before saving.")
            return False
        if len(name) > 100:
            showWarning("Profile name must be 100 characters or fewer.")
            return False
        self._capture()
        existing_id = self._profile_for_name(name)
        if existing_id and existing_id != self._profile_id:
            answer = QMessageBox.question(
                self, "Overwrite Audio Profile",
                f'Profile "{name}" already exists. Replace its saved settings?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return False
        pid = existing_id or new_profile_id()
        profile = copy.deepcopy(self._draft)
        profile["name"] = name
        try:
            return self._save(pid, profile)
        except Exception as exc:
            showWarning(f"Could not save Audio Profile: {exc}")
            return False

    def _activate_profile(self, pid):
        profile = copy.deepcopy(self._audio["profiles"][pid])
        # Commit selection before changing the editor; on a CAS failure leave
        # the previous Profile and its draft intact.
        try:
            new_audio = copy.deepcopy(self._audio)
            new_audio["last_profile_id"] = pid
            self._revision = self.cfg.replace_audio(new_audio, expected_revision=self._revision)
            self._audio = new_audio
        except Exception as exc:
            showWarning(f"Could not select Audio Profile: {exc}")
            return False
        self._profile_id = pid
        self._draft = profile
        self._saved = copy.deepcopy(profile)
        self._refresh_profiles(profile["name"])
        self._apply_draft()
        return True

    def delete_profile(self, *_):
        pid = self._selected_profile_id()
        if not pid:
            showWarning("Choose a saved Profile from the list before deleting.")
            return False
        if len(self._audio["profiles"]) <= 1:
            showWarning("The last Audio Profile cannot be deleted.")
            return False
        if pid == self._profile_id and not self._confirm_discard():
            return False
        name = self._audio["profiles"][pid]["name"]
        if QMessageBox.question(
                self, "Delete Audio Profile",
                f'Delete saved Profile "{name}"? This does not delete Anki audio.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return False
        new_audio = copy.deepcopy(self._audio)
        del new_audio["profiles"][pid]
        if new_audio["last_profile_id"] == pid:
            new_audio["last_profile_id"] = None
        try:
            self._revision = self.cfg.replace_audio(new_audio, expected_revision=self._revision)
            self._audio = new_audio
            if self._profile_id == pid:
                # Keep the current controls available for unsaved Generate/Save.
                # Deleting a Profile must never delete generated Anki media.
                self._profile_id = None
                self._saved = copy.deepcopy(self._draft)
            self._refresh_profiles("")
            return True
        except Exception as exc:
            showWarning(f"Could not delete Profile: {exc}")
            return False

    def can_close(self):
        if self._close_ready:
            self._closing = True
            stop_previews()
            return True
        if not self._confirm_discard():
            return False
        if self._running:
            # Do not destroy the dialog or progress widget while the worker still
            # owns a callback. Cancellation prevents a later commit; the dialog
            # closes asynchronously after the in-flight worker returns.
            self._close_pending = True
            self.request_cancel()
            self.status_label.setText("Cancelling current audio; closing when the worker returns...")
            return False
        self._closing = True
        stop_previews()
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
                play_preview(data)
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
        try:
            validate_audio({"schema_version":2,"profiles":{"legacy-edge-default":self._draft},
                            "last_profile_id":"legacy-edge-default","migration":{"legacy_edge_v1_done":True}})
            active = [(i + 1, v) for i, v in enumerate(voices) if v["enabled"]]
            if not active:
                raise ValueError("No enabled Voice")
            if provider == "kokoro_gradio":
                unavailable = [i for i, v in active if v["voice"] not in self._available]
            else:
                if self._edge_state != "ready":
                    raise ValueError("Edge voice list is not ready")
                lang = config["language_code"]
                unavailable = [i for i, v in active
                               if v["voice"] not in self._edge_cache.get((lang, v["gender"]), [])]
            if unavailable:
                raise ValueError("Enabled Voice block(s) unavailable: " +
                                 ", ".join(map(str, unavailable)) +
                                 ". Disable or reconfigure them; random weights were not changed.")
        except Exception as exc:
            showWarning(f"Audio settings are invalid: {exc}"); return
        if not self._confirm_write_risk(ids, src, dst): return
        self._snapshot = dict(provider=provider, config=config, voices=copy.deepcopy(voices),
                              source=src, destination=dst, replace=self.replace_check.isChecked())
        self._items = ids; self._cursor = 0; self._results = {}
        self._cancelled = False; self._running = True; self._undo_id = None
        self._halt_reason = None
        self._close_pending = False
        self._close_ready = False
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
            if self._closing:
                return
            category = str(err).split(":", 1)[0]
            if category not in ("failed_download", "failed_validation", "failed_probe", "failed_synthesis"):
                category = "failed_synthesis"
            self._count(category)
            print(f"[AINotePro Audio] {category} note={nid}: {err}")
            self._advance()
        _task(work, done, failed)

    def _stop_batch(self, reason):
        """Stop dispatch without altering the already committed notes."""
        self._halt_reason = reason
        self._cancelled = True
        print(f"[AINotePro Audio] BATCH STOPPED: {reason}")

    def _commit(self, snapshot, data):
        if self._closing:
            return
        nid, raw, original, old_tag, _text, voice = snapshot
        spec = self._snapshot
        if self._cancelled:
            self._count("cancelled")
            return
        try:
            note = mw.col.get_note(nid)
            src, dst = spec["source"], spec["destination"]
            if src not in note or dst not in note or note[src] != raw or note[dst] != original:
                self._count("conflict_skipped")
                return
            if old_tag:
                if owned_tag(nid, dst, original, mw.col.media.dir()) != old_tag:
                    self._count("conflict_skipped")
                    return
            elif SOUND_RE.search(original):
                self._count("conflict_skipped")
                return

            add = getattr(mw.col, "add_custom_undo_entry", None)
            merge = getattr(mw.col, "merge_undo_entries", None)
            if not callable(add) or not callable(merge):
                self._count("failed_commit")
                self._stop_batch("Anki single-step undo API unavailable; no media was written")
                return

            # Final cancellation gate: all following media/note/provenance operations
            # are a single non-interruptible main-thread commit for this note.
            if self._cancelled:
                self._count("cancelled")
                return
            self._committing = True
            try:
                if self._undo_id is None:
                    try:
                        self._undo_id = add("AINotePro audio generation")
                    except Exception as exc:
                        self._count("failed_commit")
                        self._stop_batch(f"Cannot create Anki undo group: {exc}")
                        return
                try:
                    filename = add_audio_to_media_collection(data, f"ainotepro-{nid}.mp3")
                except Exception as exc:
                    self._count("failed_commit")
                    print(f"[AINotePro Audio] media write failed note={nid}: {exc}")
                    return

                tag = f"[sound:{filename}]"
                content = (original.replace(old_tag, tag, 1)
                           if old_tag else (original + " " + tag).strip())
                note[dst] = content
                update_error = None
                try:
                    mw.col.update_note(note)
                except Exception as exc:
                    update_error = exc

                # Re-read even when update_note raised: an exception can happen
                # after the collection has persisted the field change.
                try:
                    persisted = mw.col.get_note(nid)[dst] == content
                except Exception as exc:
                    # This is an indeterminate commit, NOT a confirmed failed write.
                    # Never retry automatically: the new sound tag may be present.
                    self._count("commit_unverified")
                    self._stop_batch(
                        f"Cannot determine whether note {nid} was committed: {exc}; "
                        "inspect the note and its media before retrying")
                    return
                if not persisted:
                    self._count("failed_commit")
                    if update_error:
                        print(f"[AINotePro Audio] note update failed note={nid}: {update_error}")
                    # Even a confirmed non-persisted note can leave a changed undo
                    # state or an unreferenced media file. Never continue the batch.
                    self._stop_batch(
                        f"Note {nid} did not retain its audio reference; "
                        "inspect collection and unreferenced media before retrying")
                    return

                # The note IS committed. An undo merge failure must never turn it
                # into failed_commit or prevent provenance from being recorded.
                undo_error = None
                try:
                    merge(self._undo_id)
                except Exception as exc:
                    undo_error = exc
                    self._stop_batch(
                        f"Undo grouping failed after note {nid} was written: {exc}; "
                        "no further notes will be submitted")
                try:
                    record(nid, dst, filename, data, spec["provider"])
                except Exception as exc:
                    self._count("generated_unmanaged")
                    print(f"[AINotePro Audio] provenance unavailable note={nid}: {exc}")
                else:
                    self._count("success")
                if update_error:
                    print(f"[AINotePro Audio] note={nid} persisted despite update exception: {update_error}")
                if undo_error:
                    print(f"[AINotePro Audio] note={nid} persisted; undo grouping requires manual review")
                self._refresh_editor(nid)
            finally:
                self._committing = False
        except Exception as exc:
            self._count("failed_commit")
            self._stop_batch(f"Unexpected commit error for note {nid}: {exc}")

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
        message = "Audio batch complete. " + (summary or "No notes changed.")
        if self._halt_reason:
            message += "\nSTOPPED: " + self._halt_reason
        print("[AINotePro Audio] " + message)
        showInfo(message)
        if self._close_pending:
            self._close_ready = True
            QTimer.singleShot(0, lambda: self.window().reject())

    def closeEvent(self, event):
        if not self.can_close():
            event.ignore(); return
        super().closeEvent(event)
