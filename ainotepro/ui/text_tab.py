from __future__ import annotations

import json
import os
import re
from html import unescape
from typing import Any, Dict, Optional
import threading
from urllib.parse import unquote, urlparse

from aqt import mw
from aqt.qt import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, QGridLayout, QComboBox, QLineEdit, QToolButton, QObject, pyqtSignal, QThread,
    QPushButton, QFrame, QTextEdit, QSizePolicy, Qt, QProgressDialog, QFileDialog, QMessageBox, QInputDialog, QCheckBox,
    QIcon, QStyle, QEvent
)
from aqt.utils import showInfo, showWarning

from ..config.manager import ConfigManager, CONFIG_FILE, USER_FILES_DIR, migrate_legacy_user_data
from ..services.provider_factory import create_provider
from ..core.utils import create_undo_checkpoint, update_field_content
from ..core.advanced_text import (
    AdvancedRequest, compile_prompt, default_prompt, parse_response,
    preflight_requests, reconcile_field_selection,
)
from ..core.advanced_commit import AdvancedCommitResult, commit_validated_results
from ..core.advanced_ledger import AdvancedBatchLedger

# Keep a prompt.json for import/export style sharing, but also mirror prompts into
# user_config.json so they survive the normal add-on settings flow.
ADDON_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PROMPT_DIR = os.path.join(USER_FILES_DIR, "gen_text")
PROMPT_FILE = os.path.join(PROMPT_DIR, "prompt.json")
USER_CONFIG_FILE = CONFIG_FILE
DEFAULT_PROMPTS = {
    "Default": "Translate the following text to English: {Source Field}",
}
TEXT_PROVIDER_OPTIONS = [
    ("OpenAI", "openai"),
    ("DeepSeek", "deepseek"),
    ("OpenRouter", "openrouter"),
    ("DashScope (Qwen)", "dashscope"),
    ("Moonshot (Kimi)", "moonshot"),
    ("Zhipu GLM", "zhipu"),
    ("SiliconFlow", "siliconflow"),
    ("Groq", "groq"),
    ("Together", "together"),
    ("Perplexity", "perplexity"),
    ("Gemini", "gemini"),
    ("LM Studio", "lmstudio"),
    ("LocalAI", "localai"),
    ("Ollama", "ollama"),
]
TEXT_PROVIDER_LABEL_TO_KEY = dict(TEXT_PROVIDER_OPTIONS)
TEXT_PROVIDER_KEY_TO_LABEL = {key: label for label, key in TEXT_PROVIDER_OPTIONS}
TEXT_PROVIDER_LABEL_ALIASES = {
    "Open AI": "openai",
}


class CheckableFieldCombo(QComboBox):
    """Compact multi-select combo suitable for the Text tab's field row."""
    selectionChanged = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        self.setMaxVisibleItems(12)
        self._keep_popup_open = False
        self.view().pressed.connect(self._toggle_index)
        self.view().installEventFilter(self)

    def set_fields(self, names: list[str], selected: Optional[list[str]] = None,
                   disabled: Optional[set[str]] = None) -> None:
        selected_set = set(selected or [])
        disabled = disabled or set()
        self.clear()
        for name in names:
            self.addItem(name)
            item = self.model().item(self.count() - 1)
            item.setData(Qt.CheckState.Checked if name in selected_set else Qt.CheckState.Unchecked,
                         Qt.ItemDataRole.CheckStateRole)
            item.setToolTip(name)
            if name in disabled:
                item.setEnabled(False)
                item.setToolTip(f"{name} (selected in the other field set)")
        self._update_label()

    def set_disabled_fields(self, disabled: set[str]) -> None:
        """Refresh conflict availability without recreating the open popup."""
        for index in range(self.count()):
            item = self.model().item(index)
            name = self.itemText(index)
            is_disabled = name in disabled and name not in self.selected_fields()
            item.setEnabled(not is_disabled)
            item.setToolTip(f"{name} (selected in the other field set)" if is_disabled else name)

    def eventFilter(self, watched, event):
        if watched is self.view() and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key.Key_Space, Qt.Key.Key_Select):
                index = self.view().currentIndex()
                if index.isValid():
                    self._toggle_index(index)
                return True
        return super().eventFilter(watched, event)

    def selected_fields(self) -> list[str]:
        result = []
        for index in range(self.count()):
            item = self.model().item(index)
            if item.data(Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked:
                result.append(self.itemText(index))
        return result

    def _toggle_index(self, index) -> None:
        item = self.model().item(index.row())
        if not item or not item.isEnabled():
            return
        state = item.data(Qt.ItemDataRole.CheckStateRole)
        item.setData(Qt.CheckState.Unchecked if state == Qt.CheckState.Checked else Qt.CheckState.Checked,
                     Qt.ItemDataRole.CheckStateRole)
        self._keep_popup_open = True
        self._update_label()
        self.selectionChanged.emit()

    def hidePopup(self) -> None:
        # A check action should permit consecutive mouse/keyboard selections;
        # clicking elsewhere or Escape uses the normal QComboBox close path.
        if self._keep_popup_open:
            self._keep_popup_open = False
            return
        super().hidePopup()

    def _update_label(self) -> None:
        values = self.selected_fields()
        summary = ', '.join(values)
        self.lineEdit().setText(summary or 'Select fields…')
        self.setToolTip(summary or 'Select one or more fields')


class AdvancedGenerationWorker(QObject):
    """Provider-only worker. It does not hold or access Anki notes or Qt widgets."""
    progressUpdated = pyqtSignal(object)
    resultReady = pyqtSignal(object)
    finished = pyqtSignal(object)

    def __init__(self, run_id: int, requests: list[AdvancedRequest], parsed, provider, config, cancel_event):
        super().__init__()
        self.run_id = run_id
        self.requests = requests
        self.parsed = parsed
        self.provider = provider
        self.config = config
        self.cancel_event = cancel_event

    def run(self):
        completed = 0
        try:
            for request in self.requests:
                if self.cancel_event.is_set():
                    break
                try:
                    response = self.provider.generate(
                        compile_prompt(self.parsed, request.snapshot.input_values), self.config)
                except Exception as exc:
                    self.resultReady.emit((self.run_id, request.snapshot, None, str(exc), "provider-failed"))
                else:
                    try:
                        values = parse_response(response, [name for name, _ in self.parsed[1]])
                        self.resultReady.emit((self.run_id, request.snapshot, values, None, None))
                    except Exception as exc:
                        self.resultReady.emit((self.run_id, request.snapshot, None, str(exc), "json-failed"))
                completed += 1
                self.progressUpdated.emit((self.run_id, completed))
            self.finished.emit((self.run_id,
                                'Generation cancelled.' if self.cancel_event.is_set() else 'Generation complete.',
                                None))
        except Exception as exc:
            self.finished.emit((self.run_id, f'Advanced generation failed: {exc}', 'worker-failed'))


def _read_json_file(path: str) -> Dict[str, Any]:
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception as e:
        print(f"[AINotePro] Failed to read JSON from {path}: {e}")
    return {}


def _write_json_file(path: str, data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _extract_prompts(data: Dict[str, Any]) -> Dict[str, str]:
    text_cfg = data.get("text", {})
    prompts = text_cfg.get("prompts", {}) if isinstance(text_cfg, dict) else {}
    if not isinstance(prompts, dict):
        return {}
    return {str(k): str(v) for k, v in prompts.items()}


def _load_prompts(mode: str = "easy") -> Dict[str, str]:
    """Load the authoritative per-mode prompt mapping.

    ``prompt.json`` is intentionally not read here: ConfigManager performs its
    single migration before this function sees a snapshot, so deleted prompts
    cannot be resurrected by a stale compatibility mirror.
    """
    prompts, _digest = ConfigManager().prompt_snapshot(mode)
    if mode == "easy":
        prompts.setdefault("Default", DEFAULT_PROMPTS["Default"])
    return prompts


def _save_prompts(data: Dict[str, str], mode: str = "easy", expected_digest: Optional[str] = None) -> str:
    data = {str(k): str(v) for k, v in data.items()}
    current, current_digest = ConfigManager().prompt_snapshot(mode)
    if mode == "easy" and data.get("Default") != current.get("Default", DEFAULT_PROMPTS["Default"]):
        raise ValueError("Default prompt is protected. Use Save As to make a copy.")
    digest = ConfigManager().replace_prompts(mode, data, expected_digest or current_digest)
    if mode == "easy":
        try:
            _write_json_file(PROMPT_FILE, data)
        except OSError as exc:
            print(f"[AINotePro] Prompt saved in config; prompt.json mirror failed: {exc}")
    return digest


def _get_last_used_prompt(mode: str = "easy") -> str:
    user_cfg = _read_json_file(USER_CONFIG_FILE)
    text_cfg = user_cfg.get("text", {})
    if isinstance(text_cfg, dict):
        return str(text_cfg.get("advanced_last_used_prompt" if mode == "advanced" else "last_used_prompt", "Default"))
    return "Default"


def _set_last_used_prompt(name: str, mode: str = "easy") -> None:
    ConfigManager().update_text_fields({"advanced_last_used_prompt" if mode == "advanced" else "last_used_prompt": name})

class GenerationWorker(QObject):
    """
    Runs the generation task in a separate thread to avoid blocking the UI.
    """
    progressUpdated = pyqtSignal(int)
    resultReady = pyqtSignal(object)
    finished = pyqtSignal(str)

    def __init__(self, params: Dict):
        super().__init__()
        self.params = params
        self._is_cancelled = False

    def run(self):
        """The main workhorse method that runs in the background."""
        try:
            # Unpack parameters
            items = self.params["items"]
            provider = self.params["provider"]
            prompt_tpl = self.params["prompt_tpl"]
            dst = self.params["dst"]
            base_cfg = self.params["base_cfg"]

            max_workers = 1
            print(f"[AINotePro] Using text generation workers={max_workers}")

            import concurrent.futures as _fut
            
            completed = 0

            def do_generate(nid, text):
                """Generates content for a single item."""
                if self._is_cancelled:
                    return (nid, "[Cancelled]")
                
                # Prepare the prompt for this specific item.
                prompt = prompt_tpl.replace("{Source Field}", text).replace("{Source}", text)
                
                # For OpenAI-compatible providers, the 'instruction' key is not used in single generation.
                # For Ollama, base_cfg is used directly.
                # This creates a clean config for the `generate` call.
                seq_cfg = {k: v for k, v in base_cfg.items() if k != "instruction"}
                
                try:
                    # The provider's `generate` method handles the API call for a single item.
                    return (nid, provider.generate(prompt, seq_cfg))
                except Exception as e_inner:
                    return (nid, f"[Error] {e_inner}")

            with _fut.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Map future to nid to process results correctly.
                future_to_nid = {executor.submit(do_generate, nid, text): nid for nid, text in items}

                for future in _fut.as_completed(future_to_nid):
                    if self._is_cancelled:
                        # Cancel remaining futures
                        for f in future_to_nid:
                            f.cancel()
                        break
                    
                    nid, result = future.result()
                    completed += 1
                    self.resultReady.emit((nid, dst, result))
                    self.progressUpdated.emit(completed)

            self.finished.emit("Generation complete." if not self._is_cancelled else "Generation cancelled.")

        except Exception as e:
            import traceback
            print("[AINotePro] Unhandled error in worker thread:", traceback.format_exc())
            self.finished.emit(f"An error occurred: {e}")

    def cancel(self):
        self._is_cancelled = True


class TextTab(QWidget):
    def __init__(self, parent=None, browser=None, note_ids=None, editor=None):
        super().__init__(parent)
        self.browser = browser
        self.note_ids = list(note_ids or [])
        self.editor = editor
        self.cfg = ConfigManager()
        self._active_provider: Optional[str] = None
        self._active_model = ""
        self._reasoning_by_model: Dict[str, str] = {}
        self._loading_provider = False
        self.all_prompts: Dict[str, str] = {}
        self._active_prompt_name: Optional[str] = None
        self._new_prompt_name: Optional[str] = None
        self._saved_prompt_text = ""
        self._prompt_digest = ""
        self._is_updating_prompt_combo = False
        self._generation_update_count = 0
        self._generation_success_count = 0
        self._generation_failure_count = 0
        self._generation_failures: list[str] = []
        self._field_mode = str(self.cfg.get_all().get("text", {}).get("field_mode", "easy"))
        if self._field_mode not in ("easy", "advanced"):
            self._field_mode = "easy"
        self._easy_field_selection: tuple[str, str] = ("", "")
        self._advanced_field_selection: tuple[list[str], list[str]] = ([], [])
        self._last_advanced_fields: tuple[list[str], list[str]] = ([], [])
        self._advanced_note_type_id: Optional[int] = None
        # These are unresolved semantic selections, not merely fields absent
        # from the currently rendered combo.  A user action on one visible
        # field must never clear a different invalid selection.
        self._advanced_invalid_source_fields: set[str] = set()
        self._advanced_invalid_destination_fields: set[str] = set()
        self._advanced_results: list[tuple[Any, Optional[dict[str, str]], Optional[str], Optional[str]]] = []
        self._advanced_cancel = threading.Event()
        self._advanced_active = False
        self._advanced_closing = False
        self._advanced_run_id = 0
        self._advanced_ui_finished = False
        self._advanced_ledger = AdvancedBatchLedger.for_notes([])
        self._discarded_dynamic_default = False
        self.destroyed.connect(self._abandon_advanced_task)
        if parent is not None:
            parent.destroyed.connect(self._abandon_advanced_task)

        self._build_ui()
        self._load_note_fields()
        self._load_prompt_list()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(5)

        # Title
        title = QLabel('<div style="font-size:14px; font-weight:900;">Insert AI-generated content into the selected note</div>')
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(4)
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 0)
        grid.setColumnStretch(2, 0)
        grid.setColumnStretch(3, 1)
        grid.setColumnStretch(4, 0)
        grid.setColumnStretch(5, 0)

        # Row 0: Provider + Base URL
        grid.addWidget(QLabel("<b>Provider:</b>"), 0, 0)
        self.service_combo = QComboBox(); self.service_combo.addItems([label for label, _key in TEXT_PROVIDER_OPTIONS])
        saved_provider = self.cfg.get_all().get("text", {}).get("provider", "openai")
        saved_label = TEXT_PROVIDER_KEY_TO_LABEL.get(str(saved_provider).lower(), "OpenAI")
        saved_idx = self.service_combo.findText(saved_label)
        if saved_idx >= 0:
            self.service_combo.setCurrentIndex(saved_idx)
        self.service_combo.currentTextChanged.connect(self._populate_provider_cfg)
        grid.addWidget(self.service_combo, 0, 1)
        grid.addWidget(QLabel("<b>Base URL:</b>"), 0, 2)
        self.base_url_edit = QLineEdit(); self.base_url_edit.setPlaceholderText("https://api.example.com")
        grid.addWidget(self.base_url_edit, 0, 3, 1, 3)

        # Row 1: API Key + Temp
        grid.addWidget(QLabel("<b>API Key:</b>"), 1, 0)
        self.api_key_edit = QLineEdit()
        try:
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        except Exception:
            self.api_key_edit.setEchoMode(QLineEdit.Password)
        api_row = QHBoxLayout(); api_row.setContentsMargins(0, 0, 0, 0); api_row.setSpacing(2)
        api_row.addWidget(self.api_key_edit, 1)
        self.toggle_password_button = QToolButton(); self.toggle_password_button.setText("🔒")
        self.toggle_password_button.setFixedWidth(24)
        self.toggle_password_button.clicked.connect(self._toggle_pw)
        api_row.addWidget(self.toggle_password_button, 0)
        api_wrap = QWidget(); api_wrap.setLayout(api_row)
        grid.addWidget(api_wrap, 1, 1, 1, 3)
        grid.addWidget(QLabel("<b>Temp:</b>"), 1, 4)
        self.temperature_edit = QLineEdit()
        self.temperature_edit.setText("0.70")
        self.temperature_edit.setFixedWidth(48)
        self.temperature_edit.setToolTip("Sampling temperature. Default: 0.70")
        grid.addWidget(self.temperature_edit, 1, 5)

        # Row 2: Model + actions
        grid.addWidget(QLabel("<b>Model:</b>"), 2, 0)
        self.model_combo = QComboBox(); self.model_combo.setEditable(True)
        self.model_combo.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed))
        model_row = QHBoxLayout()
        model_row.setContentsMargins(0, 0, 0, 0)
        model_row.setSpacing(6)
        model_row.addWidget(self.model_combo, 1)
        model_row.addWidget(QLabel("<b>Reasoning:</b>"))
        self.reasoning_combo = QComboBox()
        for label, mode in (
            ("Off", "off"), ("Low", "low"), ("Medium", "medium"),
            ("High", "high"), ("Model Default", "default")
        ):
            self.reasoning_combo.addItem(label, mode)
        self.reasoning_combo.setToolTip(
            "Per-model reasoning preference. For llama.cpp: Off=none, "
            "Low=low, Medium=medium, High=xhigh; Model Default sends no override. "
            "Other servers may not support these parameters."
        )
        self.reasoning_combo.setCurrentIndex(self.reasoning_combo.findData("default"))
        model_row.addWidget(self.reasoning_combo)
        grid.addLayout(model_row, 2, 1, 1, 3)
        # User selection and completed manual entry both persist the chosen model.
        # Avoid currentTextChanged: it fires on every typed character and during Refresh.
        self.model_combo.activated.connect(self._model_selection_changed)
        self.model_combo.lineEdit().editingFinished.connect(self._model_selection_changed)
        self.reasoning_combo.currentIndexChanged.connect(self._reasoning_selection_changed)
        self.refresh_button = QPushButton("Refresh"); self.refresh_button.setFixedWidth(70)
        self.test_button = QPushButton("Check"); self.test_button.setFixedWidth(60)
        self.refresh_button.clicked.connect(self._refresh_models)
        self.test_button.clicked.connect(self._test_model)
        grid.addWidget(self.refresh_button, 2, 4)
        grid.addWidget(self.test_button, 2, 5)

        layout.addLayout(grid)

        # Separator
        sep = QFrame(); sep.setFrameShape(getattr(QFrame, "HLine", QFrame.Shape.HLine)); sep.setFrameShadow(getattr(QFrame, "Sunken", QFrame.Shadow.Sunken))
        layout.addWidget(sep)

        # Prompt preview
        layout.addWidget(QLabel("<b>Prompt Preview</b>"))
        self.prompt_edit = QTextEdit()
        # Let Prompt Preview consume the height freed by removing the
        # decorative header; keep the other controls at their natural size.
        self.prompt_edit.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding))
        self.prompt_edit.setMinimumHeight(120)
        self.prompt_edit.setPlaceholderText('Prompt must contain "{Source Field}" so the selected source field can be inserted.')
        layout.addWidget(self.prompt_edit, 1)

        # Prompt list + buttons
        # Split the entire row equally (including labels), rather than
        # allowing Search to squeeze the editable Prompt Name selector.
        pr_row = QHBoxLayout()
        pr_row.setContentsMargins(0, 0, 0, 0)
        pr_row.setSpacing(10)
        name_row = QHBoxLayout()
        name_row.setContentsMargins(0, 0, 0, 0)
        name_row.setSpacing(6)
        name_row.addWidget(QLabel("<b>Prompt Name:</b>"))
        self.prompt_list_combo = QComboBox()
        self.prompt_list_combo.setEditable(True)
        # Names are selected here, but created only by New / Save As. Keep
        # editable mode for showing an unsaved new name or filtered selection.
        self.prompt_list_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.prompt_list_combo.setCompleter(None)
        self.prompt_list_combo.lineEdit().setReadOnly(True)
        self.prompt_list_combo.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed))
        self.prompt_list_combo.setToolTip("Select a saved prompt. Use New or Save As to create a new one.")
        name_row.addWidget(self.prompt_list_combo, 1)
        search_row = QHBoxLayout()
        search_row.setContentsMargins(0, 0, 0, 0)
        search_row.setSpacing(6)
        search_row.addWidget(QLabel("<b>Search:</b>"))
        self.prompt_search_edit = QLineEdit()
        self.prompt_search_edit.setPlaceholderText("输入关键词过滤...")
        self.prompt_search_edit.textChanged.connect(lambda _text: self._filter_prompts())
        search_row.addWidget(self.prompt_search_edit, 1)
        pr_row.addLayout(name_row, 1)
        pr_row.addLayout(search_row, 1)
        layout.addLayout(pr_row)

        # Get standard icons
        style = self.style()
        save_icon = style.standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton)
        delete_icon = style.standardIcon(QStyle.StandardPixmap.SP_TrashIcon)
        import_icon = style.standardIcon(QStyle.StandardPixmap.SP_ArrowDown)
        export_icon = style.standardIcon(QStyle.StandardPixmap.SP_ArrowUp)
        btn_row = QHBoxLayout()
        self.import_button = QPushButton(" Import"); self.import_button.setIcon(import_icon)
        self.export_button = QPushButton(" Export"); self.export_button.setIcon(export_icon)
        self.import_button.clicked.connect(self._on_import_prompt)
        self.export_button.clicked.connect(self._on_export_prompt)
        btn_row.addWidget(self.import_button); btn_row.addWidget(self.export_button)
        btn_row.addStretch(1)
        self.new_button = QPushButton("New")
        self.save_button = QPushButton(" Save"); self.save_button.setIcon(save_icon)
        self.save_as_button = QPushButton("Save As")
        self.delete_button = QPushButton(" Delete"); self.delete_button.setIcon(delete_icon)
        self.new_button.setToolTip("Start a blank, unsaved prompt with a new name.")
        self.save_button.setToolTip("Save the selected prompt. Default is read-only.")
        self.save_as_button.setToolTip("Save the current text under a new name.")
        self.new_button.clicked.connect(self._on_new_prompt)
        self.save_button.clicked.connect(self._on_save_prompt)
        self.save_as_button.clicked.connect(self._on_save_as_prompt)
        self.delete_button.clicked.connect(self._on_delete_prompt)
        self.prompt_list_combo.currentIndexChanged.connect(self._on_prompt_selection_changed)
        for button in (self.new_button, self.save_button, self.save_as_button, self.delete_button):
            btn_row.addWidget(button)
        layout.addLayout(btn_row)

        # Separator
        sep2 = QFrame(); sep2.setFrameShape(getattr(QFrame, "HLine", QFrame.Shape.HLine)); sep2.setFrameShadow(getattr(QFrame, "Sunken", QFrame.Shadow.Sunken))
        layout.addWidget(sep2)

        # Fields row
        fields_row = QHBoxLayout()
        fields_row.setContentsMargins(0, 0, 0, 0)
        fields_row.setSpacing(6)
        fields_row.addWidget(QLabel("<b>Mode:</b>"))
        self.field_mode_combo = QComboBox()
        self.field_mode_combo.addItem("Easy", "easy")
        self.field_mode_combo.addItem("Advanced", "advanced")
        self.field_mode_combo.setCurrentIndex(self.field_mode_combo.findData(self._field_mode))
        self.field_mode_combo.currentIndexChanged.connect(self._on_field_mode_changed)
        fields_row.addWidget(self.field_mode_combo, 0)
        self.easy_source_label = QLabel("<b>Source Field:</b>")
        fields_row.addWidget(self.easy_source_label)
        self.source_field_combo = QComboBox(); fields_row.addWidget(self.source_field_combo, 1)
        self.easy_destination_label = QLabel("<b>Destination Field:</b>")
        fields_row.addWidget(self.easy_destination_label)
        self.destination_field_combo = QComboBox(); fields_row.addWidget(self.destination_field_combo, 1)
        self.advanced_source_label = QLabel("<b>Source Fields:</b>")
        self.advanced_source_fields = CheckableFieldCombo()
        self.advanced_destination_label = QLabel("<b>Destination Fields:</b>")
        self.advanced_destination_fields = CheckableFieldCombo()
        self.advanced_source_fields.selectionChanged.connect(self._on_advanced_field_selection_changed)
        self.advanced_destination_fields.selectionChanged.connect(self._on_advanced_field_selection_changed)
        fields_row.addWidget(self.advanced_source_label)
        fields_row.addWidget(self.advanced_source_fields, 1)
        fields_row.addWidget(self.advanced_destination_label)
        fields_row.addWidget(self.advanced_destination_fields, 1)
        self.image_checkbox = QCheckBox("Image Recognition")
        self.image_checkbox.setToolTip(
            "Read images from the source field and send them to a vision-capable model. "
            "Remote image URLs are not supported."
        )
        fields_row.addWidget(self.image_checkbox, 0)
        layout.addLayout(fields_row)

        self.setLayout(layout)
        self._update_field_mode_widgets()
        self._populate_provider_cfg()

    def _toggle_pw(self):
        mode = self.api_key_edit.echoMode()
        try:
            from aqt.qt import QLineEdit as _QLE
            self.api_key_edit.setEchoMode(_QLE.EchoMode.Normal if mode != _QLE.EchoMode.Normal else _QLE.EchoMode.Password)
        except Exception:
            self.api_key_edit.setEchoMode(QLineEdit.Normal if mode != QLineEdit.Normal else QLineEdit.Password)

    def _load_prompt_list(self):
        mode = self._field_mode
        prompts, self._prompt_digest = self.cfg.prompt_snapshot(mode)
        self.all_prompts = dict(prompts)
        if mode == "easy":
            self.all_prompts.setdefault("Default", DEFAULT_PROMPTS["Default"])
        else:
            self.all_prompts["Default"] = default_prompt(
                self.advanced_source_fields.selected_fields(),
                self.advanced_destination_fields.selected_fields(),
            )
        name = _get_last_used_prompt(mode)
        self._filter_prompts(preferred_name=name if name in self.all_prompts else "Default",
                             load_selected=True)

    def _on_field_mode_changed(self, _index: int) -> None:
        requested = self.field_mode_combo.currentData() or "easy"
        if requested == self._field_mode:
            return
        if not self._confirm_leave_prompt():
            self.field_mode_combo.blockSignals(True)
            self.field_mode_combo.setCurrentIndex(self.field_mode_combo.findData(self._field_mode))
            self.field_mode_combo.blockSignals(False)
            return
        self._easy_field_selection = (self.source_field_combo.currentText(),
                                      self.destination_field_combo.currentText())
        self._advanced_field_selection = (self.advanced_source_fields.selected_fields(),
                                          self.advanced_destination_fields.selected_fields())
        self._field_mode = requested
        self._update_field_mode_widgets()
        try:
            self.cfg.update_text_fields({"field_mode": requested})
        except Exception as exc:
            showWarning(f"Could not save Text mode: {exc}")
        self._load_prompt_list()

    def _update_field_mode_widgets(self) -> None:
        advanced = self._field_mode == "advanced"
        for widget in (self.easy_source_label, self.source_field_combo,
                       self.easy_destination_label, self.destination_field_combo):
            widget.setVisible(not advanced)
        for widget in (self.advanced_source_label, self.advanced_source_fields,
                       self.advanced_destination_label, self.advanced_destination_fields):
            widget.setVisible(advanced)
        self.image_checkbox.setVisible(not advanced)
        self.image_checkbox.setEnabled(not advanced)
        if advanced:
            self.prompt_edit.setPlaceholderText(
                'Use {Field} for inputs and {OUT:Field} for output declarations. '
                'Escape literal braces as {{ and }}.')
        else:
            self.prompt_edit.setPlaceholderText(
                'Prompt must contain "{Source Field}" so the selected source field can be inserted.')

    def _on_advanced_field_selection_changed(self) -> None:
        if self._field_mode != "advanced":
            return
        source = self.advanced_source_fields.selected_fields()
        destination = self.advanced_destination_fields.selected_fields()
        discarded = False
        if self._active_prompt_name == "Default" and self._prompt_is_dirty():
            if not self._confirm_dynamic_default_regeneration():
                old_source, old_destination = self._last_advanced_fields
                names = [self.advanced_source_fields.itemText(i)
                         for i in range(self.advanced_source_fields.count())]
                self.advanced_source_fields.set_fields(names, old_source, set(old_destination))
                self.advanced_destination_fields.set_fields(names, old_destination, set(old_source))
                return
            discarded = self._discarded_dynamic_default
        # An item that is selected on the other side is disabled before it can
        # be selected. Existing selections are never silently removed.
        # Do not recreate either model here: doing so closes the popup after
        # every click and makes continuous selection and keyboard use brittle.
        self.advanced_source_fields.set_disabled_fields(set(destination))
        self.advanced_destination_fields.set_disabled_fields(set(source))
        old_source, old_destination = self._last_advanced_fields
        names = [self.advanced_source_fields.itemText(i)
                 for i in range(self.advanced_source_fields.count())]
        source_changed = set(source).symmetric_difference(old_source)
        destination_changed = set(destination).symmetric_difference(old_destination)
        saved_source, saved_destination = self._advanced_field_selection
        # Keep selections absent from this Note Type in the semantic state.
        # The only way to resolve a previously-invalid field that is visible
        # again is to explicitly toggle that field; changing another visible
        # field must leave its invalid status intact.
        merged_source = ([name for name in names if name in source] +
                         [name for name in saved_source if name not in names])
        merged_destination = ([name for name in names if name in destination] +
                              [name for name in saved_destination if name not in names])
        self._advanced_invalid_source_fields.intersection_update(merged_source)
        self._advanced_invalid_destination_fields.intersection_update(merged_destination)
        self._advanced_invalid_source_fields.difference_update(source_changed)
        self._advanced_invalid_destination_fields.difference_update(destination_changed)
        self._last_advanced_fields = (list(source), list(destination))
        self._advanced_field_selection = (merged_source, merged_destination)
        if self._active_prompt_name == "Default" and (discarded or not self._prompt_is_dirty()):
            self._discarded_dynamic_default = False
            self._load_prompt_list()

    def _confirm_dynamic_default_regeneration(self) -> bool:
        """Offer Save As before a dynamic Default is regenerated."""
        box = QMessageBox(self)
        box.setWindowTitle("Unsaved Advanced Default")
        box.setText("Field changes will regenerate Advanced Default. Keep this draft?")
        save_as = box.addButton("Save As", QMessageBox.ButtonRole.ActionRole)
        discard = box.addButton(QMessageBox.StandardButton.Discard)
        cancel = box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        clicked = box.clickedButton()
        if clicked == save_as:
            self._discarded_dynamic_default = False
            self._on_save_as_prompt()
            return self._active_prompt_name != "Default" and not self._prompt_is_dirty()
        if clicked == discard:
            self._discarded_dynamic_default = True
            return True
        return False

    def _filter_prompts(self, preferred_name: Optional[str] = None, load_selected: bool = False):
        search_text = self.prompt_search_edit.text().lower()
        keywords = [k for k in search_text.split() if k]
        current_selection = preferred_name or self.prompt_list_combo.currentText()
        self._is_updating_prompt_combo = True
        self.prompt_list_combo.clear()

        for name, content in self.all_prompts.items():
            # If no keywords, show all prompts
            if not keywords:
                self.prompt_list_combo.addItem(name)
                continue
            # All keywords must be present in either name or content
            full_text_to_search = (name.lower() + " " + content.lower())
            if all(keyword in full_text_to_search for keyword in keywords):
                self.prompt_list_combo.addItem(name)
        
        idx = self.prompt_list_combo.findText(current_selection)
        if idx != -1:
            self.prompt_list_combo.setCurrentIndex(idx)
        elif current_selection:
            # An editable combo can display text while retaining an old index.
            # Reset it so choosing the first visible row still emits a change.
            self.prompt_list_combo.setCurrentIndex(-1)
            self.prompt_list_combo.setEditText(current_selection)
        self._is_updating_prompt_combo = False
        if load_selected:
            self._load_prompt_by_name(self.prompt_list_combo.currentText().strip(), show_missing=False)

    def _refresh_prompt_combo_after_save(self, name: str) -> None:
        self._is_updating_prompt_combo = True
        try:
            if self.prompt_search_edit.text():
                self.prompt_search_edit.blockSignals(True)
                self.prompt_search_edit.clear()
                self.prompt_search_edit.blockSignals(False)
            self.prompt_list_combo.clear()
            for prompt_name in self.all_prompts:
                self.prompt_list_combo.addItem(prompt_name)
            idx = self.prompt_list_combo.findText(name)
            if idx < 0:
                self.prompt_list_combo.addItem(name)
                idx = self.prompt_list_combo.findText(name)
            if idx >= 0:
                self.prompt_list_combo.setCurrentIndex(idx)
            else:
                self.prompt_list_combo.setEditText(name)
        finally:
            try:
                self.prompt_search_edit.blockSignals(False)
            except Exception:
                pass
            self._is_updating_prompt_combo = False

    def _prompt_name_text(self) -> str:
        try:
            editor = self.prompt_list_combo.lineEdit()
            if editor:
                return editor.text().strip()
        except Exception:
            pass
        return self.prompt_list_combo.currentText().strip()

    def _restore_prompt_selector(self) -> None:
        # A rejected switch must restore the name that owns the editor text.
        name = self._new_prompt_name or self._active_prompt_name or ""
        self._is_updating_prompt_combo = True
        try:
            index = self.prompt_list_combo.findText(name)
            if index >= 0:
                self.prompt_list_combo.setCurrentIndex(index)
            else:
                self.prompt_list_combo.setCurrentIndex(-1)
                self.prompt_list_combo.setEditText(name)
        finally:
            self._is_updating_prompt_combo = False

    def _update_prompt_actions(self) -> None:
        editable = self._active_prompt_name not in (None, "Default")
        self.save_button.setEnabled(editable or self._new_prompt_name is not None)
        self.delete_button.setEnabled(editable)

    def _prompt_is_dirty(self) -> bool:
        return (self._new_prompt_name is not None or
                (self._active_prompt_name is not None and
                 self.prompt_edit.toPlainText() != self._saved_prompt_text))

    def _confirm_leave_prompt(self) -> bool:
        if not self._prompt_is_dirty():
            return True
        if self._active_prompt_name == "Default":
            if self._field_mode == "advanced":
                return self._confirm_dynamic_default_regeneration()
            message = ("Default is protected. Use Save As to keep your changes. "
                       "Discard the edits and switch?")
            buttons = (QMessageBox.StandardButton.Discard |
                       QMessageBox.StandardButton.Cancel)
        else:
            message = "Save changes to the current prompt before switching?"
            buttons = (QMessageBox.StandardButton.Save |
                       QMessageBox.StandardButton.Discard |
                       QMessageBox.StandardButton.Cancel)
        choice = QMessageBox.question(self, "Unsaved Prompt", message, buttons,
                                      QMessageBox.StandardButton.Cancel)
        if choice == QMessageBox.StandardButton.Discard:
            return True
        if choice == QMessageBox.StandardButton.Save and self._active_prompt_name != "Default":
            name = self._new_prompt_name or self._active_prompt_name
            return self._save_prompt_to_name(name, overwrite=self._new_prompt_name is None)
        return False

    def _on_prompt_selection_changed(self, index: int) -> None:
        if self._is_updating_prompt_combo or index < 0:
            return
        target = self.prompt_list_combo.itemText(index).strip()
        if not target or target == self._active_prompt_name:
            return
        if not self._confirm_leave_prompt():
            self._restore_prompt_selector()
            return
        if not self._load_prompt_by_name(target, show_missing=False):
            self._restore_prompt_selector()

    def _load_prompt_by_name(self, name: str, show_missing: bool = True) -> bool:
        if not name:
            if show_missing:
                showWarning("Prompt name cannot be empty.")
            return False
        data = self.all_prompts
        if name not in data:
            if show_missing:
                showWarning("Prompt not found.")
            return False
        self.prompt_edit.setPlainText(data[name])
        self.all_prompts = data
        self._active_prompt_name = name
        self._new_prompt_name = None
        self._saved_prompt_text = data[name]
        self._restore_prompt_selector()
        self._update_prompt_actions()
        _set_last_used_prompt(name, self._field_mode)
        return True

    def _valid_new_prompt_name(self, name: str) -> bool:
        if not name or len(name) > 100:
            showWarning("Prompt name must contain 1 to 100 characters.")
            return False
        if any(existing.casefold() == name.casefold() for existing in self.all_prompts):
            showWarning("A prompt with this name already exists. Choose another name.")
            return False
        return True

    def _set_new_prompt_draft(self, name: str) -> None:
        self._active_prompt_name = None
        self._new_prompt_name = name
        self._saved_prompt_text = ""
        self.prompt_edit.clear()
        self._restore_prompt_selector()
        self._update_prompt_actions()
        self.prompt_edit.setFocus()

    def _on_new_prompt(self) -> None:
        name, ok = QInputDialog.getText(self, "New Prompt", "Name for the new prompt:")
        if not ok:
            return
        name = name.strip()
        if not self._valid_new_prompt_name(name):
            return
        if not self._confirm_leave_prompt():
            self._restore_prompt_selector()
            return
        self._set_new_prompt_draft(name)

    def _load_note_fields(self):
        try:
            note_ids = self._selected_note_ids()
            if not note_ids:
                return
            n = mw.col.get_note(note_ids[0])
            note_type = n.note_type()
            note_type_id = int(note_type["id"])
            names = [f["name"] for f in note_type["flds"]]
            old_source = self.advanced_source_fields.selected_fields()
            old_destination = self.advanced_destination_fields.selected_fields()
            saved_source, saved_destination = self._advanced_field_selection
            new_source, new_destination, _invalid_fields = reconcile_field_selection(
                saved_source, saved_destination, names,
            )
            if (self._field_mode == "advanced" and self._active_prompt_name == "Default"
                    and self._prompt_is_dirty()
                    and (self._advanced_note_type_id is not None
                         and (self._advanced_note_type_id != note_type_id
                              or old_source != new_source or old_destination != new_destination))):
                # A Note Type refresh can invalidate selections just as a click
                # can; never replace an edited dynamic Default without consent.
                if not self._confirm_dynamic_default_regeneration():
                    return
            discarded = self._discarded_dynamic_default
            self.source_field_combo.clear(); self.destination_field_combo.clear()
            self.source_field_combo.addItems(names); self.destination_field_combo.addItems(names)
            source, destination = self._easy_field_selection
            if source in names:
                self.source_field_combo.setCurrentIndex(self.source_field_combo.findText(source))
            if destination in names:
                self.destination_field_combo.setCurrentIndex(self.destination_field_combo.findText(destination))
            source, destination = new_source, new_destination
            self.advanced_source_fields.set_fields(names, source, set(destination))
            self.advanced_destination_fields.set_fields(names, destination, set(source))
            self._last_advanced_fields = (list(source), list(destination))
            # Keep the old semantic selection as-is: invalid names must block
            # Generate instead of becoming an unannounced smaller request.
            # Previously unresolved fields stay unresolved even when a later
            # Note Type makes them visible, until the user toggles that field.
            self._advanced_invalid_source_fields.update(
                name for name in saved_source if name not in names)
            self._advanced_invalid_destination_fields.update(
                name for name in saved_destination if name not in names)
            self._advanced_invalid_source_fields.intersection_update(saved_source)
            self._advanced_invalid_destination_fields.intersection_update(saved_destination)
            self._advanced_note_type_id = note_type_id
            if (self._field_mode == "advanced" and self._active_prompt_name == "Default"
                    and (discarded or not self._prompt_is_dirty())):
                self._discarded_dynamic_default = False
                self._load_prompt_list()
        except Exception:
            pass

    def _selected_note_ids(self) -> list[int]:
        if self.browser:
            try:
                return list(self.browser.selectedNotes())
            except Exception:
                return []
        return list(self.note_ids)

    # Prompt ops
    def _save_prompt_to_name(self, name: Optional[str], *, overwrite: bool) -> bool:
        name = (name or "").strip()
        if not name or len(name) > 100:
            showWarning("Prompt name must contain 1 to 100 characters.")
            return False
        if name.casefold() == "default":
            showWarning("Default is protected. Use Save As to create a new prompt.")
            return False
        content = self.prompt_edit.toPlainText()
        if not content.strip():
            showWarning("Prompt Preview is empty.")
            return False
        try:
            data = dict(self.all_prompts)
            if self._field_mode == "advanced":
                data.pop("Default", None)
            if overwrite and name not in data:
                showWarning("The selected prompt no longer exists. Use Save As.")
                return False
            if not overwrite and any(key.casefold() == name.casefold() for key in data):
                showWarning("That prompt name already exists. Choose a different name.")
                return False
            data[name] = content
            self._prompt_digest = _save_prompts(data, self._field_mode, self._prompt_digest)
            saved = dict(data)
            if self._field_mode == "advanced":
                saved["Default"] = default_prompt(
                    self.advanced_source_fields.selected_fields(),
                    self.advanced_destination_fields.selected_fields(),
                )
            if saved.get(name) != content:
                raise RuntimeError("Saved prompt could not be verified on disk")
        except Exception as exc:
            print(f"[AINotePro] Prompt save failed name={name!r}: {exc}")
            showWarning(f"Could not save prompt '{name}': {exc}")
            return False
        self.all_prompts = saved
        self._active_prompt_name = name
        self._new_prompt_name = None
        self._saved_prompt_text = content
        self._refresh_prompt_combo_after_save(name)
        self._update_prompt_actions()
        try:
            _set_last_used_prompt(name, self._field_mode)
            # Preserve existing behavior: Prompt Save also saves model settings.
            self._save_current_provider_config()
        except Exception as exc:
            showWarning(f"Prompt saved, but settings could not be updated: {exc}")
        showInfo(f"Prompt saved: {name}")
        return True

    def _on_save_prompt(self) -> None:
        if self._new_prompt_name is not None:
            self._save_prompt_to_name(self._new_prompt_name, overwrite=False)
            return
        name = self._active_prompt_name
        if not name:
            showWarning("Use New to create a prompt or select a saved prompt.")
            return
        if name == "Default":
            showWarning("Default is protected. Use Save As to keep your changes.")
            return
        if QMessageBox.question(
                self, "Confirm Save", f'Update saved prompt "{name}"?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        self._save_prompt_to_name(name, overwrite=True)

    def _on_save_as_prompt(self) -> None:
        if not self.prompt_edit.toPlainText().strip():
            showWarning("Prompt Preview is empty.")
            return
        source = self._new_prompt_name or self._active_prompt_name or "New Prompt"
        name, ok = QInputDialog.getText(
            self, "Save Prompt As", "New prompt name:", text=f"{source} Copy")
        if not ok:
            return
        self._save_prompt_to_name(name, overwrite=False)

    def _on_delete_prompt(self) -> None:
        name = self._active_prompt_name
        if not name:
            showWarning("Select a saved prompt to delete.")
            return
        if name == "Default":
            showWarning("Default is protected and cannot be deleted.")
            return
        if QMessageBox.question(
                self, "Confirm Delete",
                f'Delete saved prompt "{name}"? Unsaved edits will be lost.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        try:
            data = dict(self.all_prompts)
            if self._field_mode == "advanced":
                data.pop("Default", None)
            if name not in data:
                showWarning("The selected prompt no longer exists.")
                return
            del data[name]
            self._prompt_digest = _save_prompts(data, self._field_mode, self._prompt_digest)
            self.all_prompts = dict(data)
            if self._field_mode == "advanced":
                self.all_prompts["Default"] = default_prompt(
                    self.advanced_source_fields.selected_fields(),
                    self.advanced_destination_fields.selected_fields(),
                )
            self._active_prompt_name = None
            self._new_prompt_name = None
            self._saved_prompt_text = ""
            self._refresh_prompt_combo_after_save("Default")
            self._load_prompt_by_name("Default")
            showInfo(f"Prompt deleted: {name}")
        except Exception as exc:
            showWarning(f"Could not delete prompt '{name}': {exc}")

    def _on_import_prompt(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Import Prompts", "", "JSON Files (*.json)")
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                imported = json.load(f)
            if not isinstance(imported, dict):
                showWarning("Invalid prompt file format. Expected a JSON object."); return
            if "mode" in imported or "prompts" in imported:
                imported_mode = imported.get("mode")
                new_prompts = imported.get("prompts")
                if imported_mode != self._field_mode:
                    showWarning(f"This is a {imported_mode!r} Prompt export; switch modes before importing it.")
                    return
            else:
                if self._field_mode != "easy":
                    showWarning("Legacy prompt files can only be imported in Easy mode.")
                    return
                new_prompts = imported
            if not isinstance(new_prompts, dict) or any(not isinstance(key, str) or not isinstance(value, str)
                                                        for key, value in new_prompts.items()):
                showWarning("Invalid prompt names or contents."); return
            if "Default" in new_prompts:
                del new_prompts["Default"]
                showWarning("Default is protected and was skipped during import.")
            if not new_prompts:
                return

            current_prompts = dict(self.all_prompts)
            if self._field_mode == "advanced":
                current_prompts.pop("Default", None)
            conflicts = [k for k in new_prompts if k in current_prompts]
            if conflicts:
                if QMessageBox.question(self, "Confirm Overwrite", 
                                        f"The following prompts already exist: {', '.join(conflicts)}. Overwrite them?",
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.No:
                    # Don't overwrite, just import non-conflicting ones
                    for k in conflicts:
                        del new_prompts[k]
            
            current_prompts.update(new_prompts)
            self._prompt_digest = _save_prompts(current_prompts, self._field_mode, self._prompt_digest)
            self.all_prompts = current_prompts
            if self._field_mode == "advanced":
                self.all_prompts["Default"] = default_prompt(
                    self.advanced_source_fields.selected_fields(),
                    self.advanced_destination_fields.selected_fields(),
                )
            self._filter_prompts()
            showInfo(f"Successfully imported {len(new_prompts)} prompts.")

        except Exception as e:
            showWarning(f"Failed to import prompts: {e}")

    def _on_export_prompt(self):
        name = self._prompt_name_text()
        if not name:
            showWarning("Please select a prompt to export."); return
        
        content = self.prompt_edit.toPlainText()
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Prompt", f"{name}.json", "JSON Files (*.json)")
        if not file_path:
            return
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump({"version": 1, "mode": self._field_mode,
                           "prompts": {name: content}}, f, ensure_ascii=False, indent=2)
            showInfo(f"Prompt '{name}' exported successfully.")
        except Exception as e:
            showWarning(f"Failed to export prompt: {e}")

    # Provider config
    def _service_map(self) -> str:
        svc = self.service_combo.currentText()
        return TEXT_PROVIDER_LABEL_TO_KEY.get(svc, TEXT_PROVIDER_LABEL_ALIASES.get(svc, "openai"))

    def _current_provider_config(self) -> Dict[str, Any]:
        model = self.model_combo.currentText().strip()
        if model:
            self._reasoning_by_model[model] = self.reasoning_combo.currentData() or "default"
        return {
            "base_url": self.base_url_edit.text().strip(),
            "api_key": self.api_key_edit.text().strip(),
            "model": model,
            "temperature": self._temperature_value(),
            "reasoning_by_model": dict(self._reasoning_by_model),
        }

    def _temperature_value(self) -> float:
        try:
            value = float(self.temperature_edit.text().strip())
        except Exception:
            value = 0.7
        return max(0.0, min(value, 2.0))

    def _save_current_provider_config(self, provider_key: Optional[str] = None) -> None:
        pv = provider_key or self._active_provider or self._service_map()
        self.cfg.set_provider_config("text", pv, self._current_provider_config())
        print(f"[AINotePro] Saved settings for Text/{pv}")

    def _model_selection_changed(self, *_):
        if self._loading_provider:
            return
        new_model = self.model_combo.currentText().strip()
        if self._active_model and self._active_model != new_model:
            self._reasoning_by_model[self._active_model] = self.reasoning_combo.currentData() or "default"
        self._active_model = new_model
        self._loading_provider = True
        try:
            mode = self._reasoning_by_model.get(new_model, "default")
            index = self.reasoning_combo.findData(mode)
            self.reasoning_combo.setCurrentIndex(index if index >= 0 else self.reasoning_combo.findData("default"))
        finally:
            self._loading_provider = False
        self._save_current_provider_config()

    def _reasoning_selection_changed(self, *_):
        if not self._loading_provider:
            self._save_current_provider_config()

    def _populate_provider_cfg(self, *_):
        pv = self._service_map()
        previous = self._active_provider
        if previous is not None and previous != pv:
            self._save_current_provider_config(provider_key=previous)
        self._loading_provider = True
        try:
            cfg = self.cfg.get_provider_config("text", pv)
            self.base_url_edit.setText(cfg.get("base_url", ""))
            self.api_key_edit.setText(cfg.get("api_key", ""))
            self.model_combo.setEditText(cfg.get("model", ""))
            temp = cfg.get("temperature", 0.7)
            try:
                temp = float(temp)
            except Exception:
                temp = 0.7
            self.temperature_edit.setText(f"{temp:.2f}")
            stored = cfg.get("reasoning_by_model", {})
            self._reasoning_by_model = dict(stored) if isinstance(stored, dict) else {}
            self._active_model = self.model_combo.currentText().strip()
            mode = self._reasoning_by_model.get(self._active_model, "default")
            index = self.reasoning_combo.findData(mode)
            self.reasoning_combo.setCurrentIndex(index if index >= 0 else self.reasoning_combo.findData("default"))
            # Native Ollama reasoning parameters are a separate protocol.
            self.reasoning_combo.setEnabled(pv != "ollama")
            self._active_provider = pv
        finally:
            self._loading_provider = False
        if previous is not None and previous != pv:
            self._save_current_provider_config()

    def _refresh_models(self) -> None:
        # Commit a manually entered model before replacing the combo's items.
        self._model_selection_changed()
        st = "text"; pv = self._service_map()
        # Use current UI values rather than stored config
        base_url = self.base_url_edit.text().strip(); api_key = self.api_key_edit.text().strip()
        cfg = {"base_url": base_url, "api_key": api_key}
        print(f"[AINotePro] Refresh models clicked. service={pv}, base_url={base_url}")
        provider = create_provider(st, pv, cfg)
        try:
            models = provider.list_models(cfg) or []
            print(f"[AINotePro] Refresh fetched {len(models)} models.")
            if models:
                cur = self.model_combo.currentText()
                self.model_combo.clear(); self.model_combo.addItems(models)
                if cur:
                    i = self.model_combo.findText(cur)
                    if i >= 0: self.model_combo.setCurrentIndex(i)
                    else: self.model_combo.setEditText(cur)
            # persist current provider config
            self._save_current_provider_config()
        except Exception as e:
            print(f"[AINotePro] Refresh models failed: {e}")
            showWarning(f"Failed to fetch models: {e}")

    def _test_model(self) -> None:
        # Test the exact request settings, including the reasoning override.
        self._model_selection_changed()
        cfg = self._current_provider_config()
        base_url, model, temp = cfg["base_url"], cfg["model"], cfg["temperature"]
        st = "text"; pv = self._service_map()
        print(f"[AINotePro] Check clicked. service={pv}, model={model}, base_url={base_url}, temp={temp}")
        provider = create_provider(st, pv, cfg)
        try:
            content = provider.generate("hello", cfg)
            print("[AINotePro] Check OK. Got response length:", len(content or ""))
            self._save_current_provider_config()
            showInfo(f"Test result:\n{content[:200]}")
        except Exception as e:
            print(f"[AINotePro] Check failed: {e}")
            showWarning(f"Test failed: {e}")

    # Public slot called by parent dialog
    def on_generate_text(self) -> None:
        if self._advanced_active:
            showWarning("Advanced generation is already running.")
            return
        if self._field_mode == "advanced":
            self._start_advanced_generation()
            return
        note_ids = self._selected_note_ids()
        if not note_ids:
            showWarning("No notes selected."); return

        base_url = self.base_url_edit.text().strip(); api_key = self.api_key_edit.text().strip()
        model = self.model_combo.currentText().strip(); temp = self._temperature_value()
        prompt_tpl = self.prompt_edit.toPlainText().strip()
        src = self.source_field_combo.currentText(); dst = self.destination_field_combo.currentText()
        if not prompt_tpl:
            showWarning("Prompt Preview is empty."); return
        if not src or not dst:
            showWarning("Source/Destination field is not set."); return
        if not self._confirm_write_risk(note_ids, src, dst):
            return

        # Save the chosen model even if Generate is the first action after selection.
        self._model_selection_changed()
        request_cfg = self._current_provider_config()
        st = "text"; pv = self._service_map(); provider = create_provider(st, pv, {})
        # If image-assisted is enabled, fall back to per-note flow for correctness
        if self.image_checkbox and self.image_checkbox.isChecked():
            updated = 0
            failures: list[str] = []
            try:
                mw.progress.start(label="Generating responses...", max=len(note_ids))
            except Exception:
                pass
            create_undo_checkpoint("AINotePro text generation")
            for i, nid in enumerate(note_ids):
                note = mw.col.get_note(nid)
                if src not in note: continue
                src_text = (note[src] or "").strip()
                cfg = dict(request_cfg)
                content: Optional[str] = None
                image_ref, image_error = self._extract_image_reference(src_text)
                if image_ref:
                    print(f"[AINotePro] Image reference prepared successfully. Length: {len(image_ref)}")
                    try:
                        image_prompt_text = self._html_to_prompt_text(src_text)
                        final_prompt = prompt_tpl.replace("{Source Field}", image_prompt_text).replace("{Source}", image_prompt_text)
                        content = provider.generate_with_image(image_ref, final_prompt, cfg)
                    except Exception as e:
                        msg = f"Note {nid}: vision request failed: {e}"
                        failures.append(msg)
                        print(f"[AINotePro] {msg}")
                        content = None
                else:
                    msg = f"Note {nid}: {image_error or 'No image found in source field'}"
                    failures.append(msg)
                    print(f"[AINotePro] {msg}")

                if content and content.strip():
                    update_field_content(note, dst, content)
                    updated += 1
                elif image_ref:
                    failures.append(f"Note {nid}: model returned empty content")
                try:
                    mw.progress.update(value=i+1)
                except Exception:
                    pass
            try:
                mw.progress.finish()
            except Exception:
                pass
            if updated:
                self._save_current_provider_config()
                summary = f"Generation complete. Updated {updated} notes."
                if failures:
                    summary += f"\n\nSkipped/failed: {len(failures)}\n" + "\n".join(failures[:5])
                showInfo(summary)
            else:
                detail = "\n".join(failures[:8]) if failures else "No image source was found."
                showWarning(f"Image OCR generation produced no content.\n\n{detail}")
            return

        # Batch mode for plain text generation: collect inputs
        items: list[tuple[int, str]] = []
        for nid in note_ids:
            note = mw.col.get_note(nid)
            if src not in note:
                continue
            user_text = (note[src] or "").strip()
            if not user_text:
                continue
            items.append((nid, user_text))

        if not items:
            showWarning("No valid source text to process.")
            return

        # Run generation in a background thread with a progress dialog for all providers
        progress = QProgressDialog("Generating content...", "Cancel", 0, len(items), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0) # Show immediately
        progress.setValue(0)

        # Setup worker and thread for all providers
        self.thread = QThread()
        params = {
            "items": items,
            "provider": provider,
            "prompt_tpl": prompt_tpl,
            "dst": dst,
            "provider_name": pv,
            "base_cfg": dict(request_cfg),
        }
        self.worker = GenerationWorker(params)
        self.worker.moveToThread(self.thread)

        # Connect signals
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.worker.progressUpdated.connect(progress.setValue)
        self.worker.resultReady.connect(self._apply_generated_text_result)
        progress.canceled.connect(self.worker.cancel)
        create_undo_checkpoint("AINotePro text generation")

        def on_finish(message):
            progress.setValue(len(items))
            try:
                mw.reset()
            except Exception:
                pass
            if self._generation_success_count:
                self._save_current_provider_config()
            summary = f"{message} Updated {self._generation_update_count} notes."
            if self._generation_failure_count:
                summary += f"\n\nSkipped/failed: {self._generation_failure_count}"
                if self._generation_failures:
                    summary += "\n" + "\n".join(self._generation_failures[:5])
            showInfo(summary)

        self.worker.finished.connect(on_finish)
        self.thread.finished.connect(lambda: setattr(self, "_generation_update_count", 0))

        # Start the thread
        self._generation_update_count = 0
        self._generation_success_count = 0
        self._generation_failure_count = 0
        self._generation_failures = []
        self.thread.start()

    def _start_advanced_generation(self) -> None:
        """Complete all local checks before constructing a provider request."""
        if self._advanced_active:
            showWarning("Advanced generation is already running.")
            return
        note_ids = self._selected_note_ids()
        sources = self.advanced_source_fields.selected_fields()
        destinations = self.advanced_destination_fields.selected_fields()
        prompt = self.prompt_edit.toPlainText()
        invalid_fields = (
            [f"Source: {name}" for name in sorted(self._advanced_invalid_source_fields)] +
            [f"Destination: {name}" for name in sorted(self._advanced_invalid_destination_fields)]
        )
        if invalid_fields:
            showWarning("Selected Advanced fields remain unresolved: "
                        + ", ".join(invalid_fields)
                        + ". Re-select or deselect each listed field before generating.")
            return
        if not note_ids:
            showWarning("No notes selected.")
            return
        if not prompt.strip():
            showWarning("Prompt Preview is empty.")
            return
        records = []
        try:
            for note_id in note_ids:
                note = mw.col.get_note(note_id)
                note_type = note.note_type()
                field_names = [field["name"] for field in note_type["flds"]]
                records.append({
                    "note_id": int(note_id),
                    "note_type_id": int(note_type["id"]),
                    "field_names": field_names,
                    "raw_values": {name: note[name] for name in field_names if name in note},
                })
            parsed, snapshots = preflight_requests(records, sources, destinations, prompt,
                                                   records[0]["field_names"])
        except Exception as exc:
            # Zero provider calls, writes, undo checkpoints, and config saves.
            showWarning(str(exc))
            return
        overwrites = [f"Note {snapshot.note_id}: {name}" for snapshot in snapshots
                      for name in destinations if snapshot.raw_values[name].strip()]
        if overwrites:
            preview = "\n".join(overwrites[:12])
            if len(overwrites) > 12:
                preview += f"\n…and {len(overwrites) - 12} more"
            answer = QMessageBox.question(
                self, "Confirm Advanced overwrite",
                "The following target fields contain existing content and will be replaced:\n\n"
                + preview + "\n\nContinue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        request_cfg = self._current_provider_config()
        if not request_cfg["base_url"] or not request_cfg["model"]:
            showWarning("Provider Base URL and Model are required.")
            return
        request_cfg["preserve_output"] = True
        self._advanced_cancel = threading.Event()
        self._advanced_run_id += 1
        run_id = self._advanced_run_id
        self._advanced_active = True
        self._advanced_ui_finished = False
        self._advanced_sources = tuple(sources)
        self._advanced_destinations = tuple(destinations)
        self._advanced_results = []
        self._advanced_ledger = AdvancedBatchLedger.for_notes(snapshot.note_id for snapshot in snapshots)
        self._set_advanced_ui_busy(True)
        self._advanced_progress = QProgressDialog("Generating structured responses…", "Cancel", 0,
                                                  len(snapshots), self)
        self._advanced_progress.setWindowModality(Qt.WindowModality.WindowModal)
        self._advanced_progress.setMinimumDuration(0)
        self._advanced_progress.canceled.connect(self._cancel_advanced)
        self._advanced_thread = QThread()
        self._advanced_worker = AdvancedGenerationWorker(
            run_id, [AdvancedRequest(snapshot, prompt) for snapshot in snapshots], parsed,
            create_provider("text", self._service_map(), {}), dict(request_cfg), self._advanced_cancel)
        self._advanced_worker.moveToThread(self._advanced_thread)
        self._advanced_thread.started.connect(self._advanced_worker.run)
        self._advanced_worker.resultReady.connect(self._collect_advanced_result)
        self._advanced_worker.progressUpdated.connect(self._update_advanced_progress)
        thread = self._advanced_thread
        self._advanced_worker.finished.connect(lambda _payload, worker_thread=thread: worker_thread.quit())
        self._advanced_worker.finished.connect(self._advanced_worker.deleteLater)
        self._advanced_thread.finished.connect(self._advanced_thread.deleteLater)
        self._advanced_worker.finished.connect(self._finish_advanced_requests)
        self._advanced_thread.start()

    def _cancel_advanced(self) -> None:
        self._advanced_cancel.set()

    def _abandon_advanced_task(self, *_args) -> None:
        """Detach callbacks before Qt can destroy this tab or its parent."""
        self._advanced_closing = True
        self._advanced_cancel.set()

    def _update_advanced_progress(self, payload) -> None:
        run_id, value = payload
        if (run_id != self._advanced_run_id or self._advanced_closing
                or self._advanced_cancel.is_set()):
            return
        progress = getattr(self, "_advanced_progress", None)
        if progress is not None:
            progress.setValue(value)

    def _collect_advanced_result(self, payload) -> None:
        run_id, snapshot, values, error, category = payload
        if (run_id == self._advanced_run_id and not self._advanced_closing
                and not self._advanced_cancel.is_set()):
            self._advanced_results.append((snapshot, values, error, category))
            self._advanced_ledger.record_worker(snapshot.note_id, category, error)

    def _finish_advanced_requests(self, payload) -> None:
        run_id, message, terminal_category = payload
        if run_id != self._advanced_run_id:
            return
        if self._advanced_cancel.is_set() or self._advanced_closing or not self.isVisible():
            self._advanced_ledger.cancel_pending()
            self._finish_advanced_ui(self._advanced_ledger.summary("Generation cancelled."))
            return
        if terminal_category:
            self._advanced_ledger.mark_pending("not-run", message)
            self._advanced_ledger.add_issue(terminal_category, message)
            self._finish_advanced_ui(self._advanced_ledger.summary(message))
            return
        valid = [(snapshot, values, error) for snapshot, values, error, _category
                 in self._advanced_results if values is not None]
        if not valid:
            self._advanced_ledger.mark_pending("not-run")
            self._finish_advanced_ui(self._advanced_ledger.summary(message + " No valid responses were returned."))
            return
        self._advanced_progress.setLabelText("Committing validated results…")
        self._commit_advanced_results(valid)

    def _commit_advanced_results(self, valid_results) -> None:
        """Final re-read through CollectionOp; the inner unit never yields."""
        sources = self._advanced_sources
        destinations = self._advanced_destinations
        cancel_event = self._advanced_cancel
        run_id = self._advanced_run_id

        def operation(col):
            from anki.collection import OpChanges
            # CollectionOp serializes collection access. The helper performs
            # final read/compare/cancel/assignment/update with no await, event
            # loop, UI call or task dispatch between validation and submission.
            return commit_validated_results(
                col, valid_results, sources, destinations, cancel_event, OpChanges,
            )

        def committed(result: AdvancedCommitResult):
            if run_id == self._advanced_run_id:
                self._handle_advanced_commit_result(result)

        def failed(exc: Exception):
            if run_id == self._advanced_run_id and not self._advanced_closing:
                self._advanced_ledger.mark_pending("commit-task-failed", str(exc))
                self._finish_advanced_ui(self._advanced_ledger.summary("Advanced commit task failed."))

        try:
            from aqt.operations import CollectionOp
            CollectionOp(parent=self, op=operation).success(committed).failure(failed).run_in_background(
                initiator=self)
        except Exception as exc:
            failed(exc)

    def _handle_advanced_commit_result(self, result: AdvancedCommitResult) -> None:
        """Render a terminal commit result without changing its data outcome."""
        if self._advanced_closing:
            return
        self._advanced_ledger.apply_commit_result(result)
        updated = self._advanced_ledger.count("updated")
        if updated:
            try:
                self._save_current_provider_config()
            except Exception as exc:
                # The database outcome is already known. Saving current UI
                # settings is separate and must not poison completion.
                self._advanced_ledger.add_issue("settings-save-failed", str(exc))
            try:
                mw.reset()
            except Exception:
                self._advanced_ledger.add_issue("ui-refresh-failed", "reopen the note to verify")
        self._finish_advanced_ui(self._advanced_ledger.summary("Advanced generation complete."))

    def _finish_advanced_ui(self, message: str) -> None:
        if self._advanced_ui_finished:
            return
        self._advanced_ui_finished = True
        self._advanced_active = False
        if self._advanced_closing:
            return
        try:
            if getattr(self, "_advanced_progress", None) is not None:
                self._advanced_progress.close()
            self._set_advanced_ui_busy(False)
        except RuntimeError:
            # Qt may delete children during a close event; no late callback is
            # allowed to revive or access them.
            return
        if not self._advanced_closing and self.isVisible():
            showInfo(message)

    def _set_advanced_ui_busy(self, busy: bool) -> None:
        self.field_mode_combo.setEnabled(not busy)
        self.advanced_source_fields.setEnabled(not busy)
        self.advanced_destination_fields.setEnabled(not busy)
        generate = getattr(self.window(), "generate_button", None)
        if generate is not None:
            generate.setEnabled(not busy)

    def closeEvent(self, event) -> None:
        if not self._advanced_closing and not self.prepare_close():
            event.ignore()
            return
        super().closeEvent(event)

    def can_close(self) -> bool:
        """Ask about an unsaved prompt without changing task state."""
        return self._confirm_leave_prompt()

    def prepare_close(self, *, confirmed: bool = False) -> bool:
        """Cancel Advanced callbacks immediately before this tab is destroyed."""
        if not confirmed and not self.can_close():
            return False
        self._advanced_closing = True
        self._advanced_cancel.set()
        return True

    # Helpers
    def _confirm_write_risk(self, note_ids: list[int], src: str, dst: str) -> bool:
        risky = []
        if src == dst:
            risky.append("The source and destination fields are the same.")
        if len(note_ids) > 1:
            risky.append(f"This will update {len(note_ids)} selected notes.")
        if not risky:
            return True
        message = "\n".join(risky) + "\n\nContinue?"
        return QMessageBox.question(
            self,
            "Confirm AINotePro generation",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes

    def _is_generation_failure(self, result: Any) -> bool:
        result_text = str(result or "").strip()
        return not result_text or result_text.startswith("[Error]") or result_text == "[Cancelled]"

    def _apply_generated_text_result(self, payload) -> None:
        nid, dst, result = payload
        try:
            if self._is_generation_failure(result):
                self._generation_failure_count += 1
                result_text = str(result or "").strip() or "empty response"
                self._generation_failures.append(f"Note {nid}: {result_text}")
                print(f"[AINotePro] Skipped note {nid}; generation returned no usable content.")
                return
            editor_note = self._editor_note_for_id(nid)
            note = editor_note or mw.col.get_note(nid)
            update_field_content(note, dst, result)
            self._generation_update_count += 1
            self._generation_success_count += 1
            print(f"[AINotePro] Updated note {nid} field '{dst}' on main thread.")
            self._refresh_editor_note(nid)
        except Exception as e:
            print(f"[AINotePro] Failed to update note {nid} field '{dst}': {e}")

    def _editor_note_for_id(self, nid: int):
        editor = self.editor
        if editor is None and self.browser is not None:
            editor = getattr(self.browser, "editor", None)
        note = getattr(editor, "note", None) if editor is not None else None
        if note is None:
            return None
        note_id = getattr(note, "id", None)
        if callable(note_id):
            note_id = note_id()
        return note if int(note_id or 0) == int(nid) else None

    def _refresh_editor_note(self, nid: int) -> None:
        editor = self.editor
        if editor is None and self.browser is not None:
            editor = getattr(self.browser, "editor", None)
        if editor is None or self._editor_note_for_id(nid) is None:
            return
        for method_name in ("loadNoteKeepingFocus", "loadNote"):
            method = getattr(editor, method_name, None)
            if callable(method):
                try:
                    method()
                except TypeError:
                    try:
                        method(focusTo=None)
                    except Exception:
                        pass
                except Exception:
                    pass
                return

    def _html_to_prompt_text(self, html_content: str) -> str:
        text = re.sub(r"<img\b[^>]*>", "", html_content or "", flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _extract_image_reference(self, html_content: str) -> tuple[Optional[str], Optional[str]]:
        """Return a URL/data URI suitable for a vision model, or an error message."""
        import base64
        import mimetypes

        m = re.search(r"<img\b[^>]*\bsrc\s*=\s*(?:\"([^\"]+)\"|'([^']+)'|([^\\s>]+))", html_content or "", re.IGNORECASE)
        if not m:
            return None, "No <img src=...> tag found in source field"

        raw_src = unescape((m.group(1) or m.group(2) or m.group(3) or "").strip())
        if not raw_src:
            return None, "Image tag has an empty src attribute"

        if raw_src.startswith("data:image/"):
            return raw_src, None

        parsed = urlparse(raw_src)
        if parsed.scheme in ("http", "https"):
            return None, (
                "Remote image URLs are not supported for privacy and security. "
                "Please download the image and add it to Anki media first."
            )

        if parsed.scheme == "file":
            path = unquote(parsed.path)
        else:
            src = unquote(raw_src.split("?", 1)[0].split("#", 1)[0])
            src = src.lstrip("/")
            path = os.path.join(mw.col.media.dir(), src)

        media_dir = os.path.realpath(mw.col.media.dir())
        real_path = os.path.realpath(path)
        try:
            is_media_file = os.path.commonpath([media_dir, real_path]) == media_dir
        except ValueError:
            is_media_file = False
        if not is_media_file:
            return None, "Refusing to read an image outside the Anki media folder"

        if not os.path.exists(real_path):
            return None, f"Image file not found: {raw_src}"

        try:
            with open(real_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            
            mime_type, _ = mimetypes.guess_type(real_path)
            if not mime_type:
                mime_type = "image/png" # Default if type can't be guessed
            
            return f"data:{mime_type};base64,{base64_image}", None
        except Exception as e:
            return None, f"Failed to encode image as Base64: {e}"

    def save_settings(self) -> bool:
        """Persist Text settings on dialog close, including model and reasoning."""
        try:
            self._model_selection_changed()
            self._save_current_provider_config()
            return True
        except Exception as exc:
            showWarning(f"Could not save Text provider settings: {exc}")
            return False
