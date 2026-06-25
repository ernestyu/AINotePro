from __future__ import annotations

import json
import os
import re
from html import unescape
from typing import Any, Dict, Optional
from urllib.parse import unquote, urlparse

from aqt import mw
from aqt.qt import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, QGridLayout, QComboBox, QLineEdit, QToolButton, QObject, pyqtSignal, QThread,
    QPushButton, QFrame, QTextEdit, QSizePolicy, QSlider, Qt, QProgressDialog, QFileDialog, QMessageBox, QCheckBox,
    QIcon, QStyle
)
from aqt.utils import showInfo, showWarning

from ..config.manager import ConfigManager
from ..services.provider_factory import create_provider
from ..core.utils import update_field_content

# Keep a prompt.json for import/export style sharing, but also mirror prompts into
# user_config.json so they survive the normal add-on settings flow.
ADDON_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
USER_DATA_DIR = os.path.join(ADDON_ROOT, "user_data")
PROMPT_DIR = os.path.join(USER_DATA_DIR, "gen_text")
PROMPT_FILE = os.path.join(PROMPT_DIR, "prompt.json")
USER_CONFIG_FILE = os.path.join(USER_DATA_DIR, "user_config.json")
ROOT_CONFIG_FILE = os.path.join(ADDON_ROOT, "config.json")
DEFAULT_PROMPTS = {
    "Default": "Translate the following text to English: {Source Field}",
}


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


def _load_prompts() -> Dict[str, str]:
    prompts: Dict[str, str] = dict(DEFAULT_PROMPTS)

    root_cfg = _read_json_file(ROOT_CONFIG_FILE)
    prompts.update(_extract_prompts(root_cfg))

    user_cfg = _read_json_file(USER_CONFIG_FILE)
    prompts.update(_extract_prompts(user_cfg))

    prompt_file_data = _read_json_file(PROMPT_FILE)
    if prompt_file_data:
        prompts.update({str(k): str(v) for k, v in prompt_file_data.items()})

    return prompts


def _save_prompts(data: Dict[str, str]) -> None:
    data = {str(k): str(v) for k, v in data.items()}
    _write_json_file(PROMPT_FILE, data)

    user_cfg = _read_json_file(USER_CONFIG_FILE)
    text_cfg = user_cfg.setdefault("text", {})
    if not isinstance(text_cfg, dict):
        text_cfg = {}
        user_cfg["text"] = text_cfg
    text_cfg["prompts"] = data
    _write_json_file(USER_CONFIG_FILE, user_cfg)


def _get_last_used_prompt() -> str:
    user_cfg = _read_json_file(USER_CONFIG_FILE)
    text_cfg = user_cfg.get("text", {})
    if isinstance(text_cfg, dict):
        return str(text_cfg.get("last_used_prompt", "Default"))
    return "Default"


def _set_last_used_prompt(name: str) -> None:
    user_cfg = _read_json_file(USER_CONFIG_FILE)
    text_cfg = user_cfg.setdefault("text", {})
    if not isinstance(text_cfg, dict):
        text_cfg = {}
        user_cfg["text"] = text_cfg
    text_cfg["last_used_prompt"] = name
    _write_json_file(USER_CONFIG_FILE, user_cfg)

class GenerationWorker(QObject):
    """
    Runs the generation task in a separate thread to avoid blocking the UI.
    """
    progressUpdated = pyqtSignal(int)
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
            cfg_all = self.params["cfg_all"]
            base_cfg = self.params["base_cfg"]

            concurrency_cfg = cfg_all.get("concurrency", {})
            # The batching logic is removed in favor of a simpler, more robust concurrent model.
            # We will use a thread pool to process items concurrently.
            max_workers = int(concurrency_cfg.get("ollama_workers", 4)) # Re-use ollama_workers for general concurrency
            print(f"[AINotePro] Using concurrent generation with max_workers={max_workers}")

            import concurrent.futures as _fut
            
            # A dictionary to store results as they complete, using nid as key.
            results_map = {}

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
                    results_map[nid] = result
                    
                    # Update note and progress as each task finishes.
                    note = mw.col.get_note(nid)
                    update_field_content(note, dst, result)
                    self.progressUpdated.emit(len(results_map))

            self.finished.emit("Generation complete." if not self._is_cancelled else "Generation cancelled.")

        except Exception as e:
            import traceback
            print("[AINotePro] Unhandled error in worker thread:", traceback.format_exc())
            self.finished.emit(f"An error occurred: {e}")

    def cancel(self):
        self._is_cancelled = True


class TextTab(QWidget):
    def __init__(self, parent=None, browser=None, note_ids=None):
        super().__init__(parent)
        self.browser = browser
        self.note_ids = list(note_ids or [])
        self.cfg = ConfigManager()
        self.all_prompts: Dict[str, str] = {}
        self._is_updating_prompt_combo = False

        self._build_ui()
        self._load_note_fields()
        self._load_prompt_list()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Title
        title = QLabel('<div style="font-size:14px; font-weight:900;">Insert AI-generated content into the selected note</div>')
        layout.addWidget(title)

        # Generate using
        gen_row = QHBoxLayout()
        gen_row.addWidget(QLabel("<b>Generate using</b>"))
        self.service_combo = QComboBox(); self.service_combo.addItems(["Open AI", "DeepSeek", "Ollama"]) 
        self.service_combo.currentTextChanged.connect(self._populate_provider_cfg)
        gen_row.addWidget(self.service_combo)
        layout.addLayout(gen_row)

        # Use a grid so left edges are aligned and buttons dock to the right
        grid = QGridLayout()
        grid.setColumnStretch(0, 0)  # label column
        grid.setColumnStretch(1, 1)  # main control column expands
        grid.setColumnStretch(2, 0)
        grid.setColumnStretch(3, 0)

        # Base URL
        grid.addWidget(QLabel("<b>Base URL</b>"), 0, 0)
        self.base_url_edit = QLineEdit(); self.base_url_edit.setPlaceholderText("https://api.example.com")
        grid.addWidget(self.base_url_edit, 0, 1, 1, 3)

        # API Key + lock button at far right
        grid.addWidget(QLabel("<b>API Key</b>"), 1, 0)
        self.api_key_edit = QLineEdit()
        try:
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        except Exception:
            self.api_key_edit.setEchoMode(QLineEdit.Password)
        # pack API key field and lock button into an inner row to eliminate the gap
        api_row = QHBoxLayout(); api_row.setContentsMargins(0, 0, 0, 0); api_row.setSpacing(4)
        api_row.addWidget(self.api_key_edit, 1)
        self.toggle_password_button = QToolButton(); self.toggle_password_button.setText("🔒")
        self.toggle_password_button.setFixedWidth(28)
        self.toggle_password_button.clicked.connect(self._toggle_pw)
        api_row.addWidget(self.toggle_password_button, 0)
        api_wrap = QWidget(); api_wrap.setLayout(api_row)
        grid.addWidget(api_wrap, 1, 1, 1, 3)

        # Available Model + right-aligned small buttons
        grid.addWidget(QLabel("<b>Available Model</b>"), 2, 0)
        self.model_combo = QComboBox(); self.model_combo.setEditable(True)
        self.model_combo.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed))
        grid.addWidget(self.model_combo, 2, 1)
        self.refresh_button = QToolButton(); self.refresh_button.setText("Refresh"); self.refresh_button.setFixedWidth(80)
        self.test_button = QToolButton(); self.test_button.setText("Check"); self.test_button.setFixedWidth(80)
        self.refresh_button.clicked.connect(self._refresh_models)
        self.test_button.clicked.connect(self._test_model)
        grid.addWidget(self.refresh_button, 2, 2)
        grid.addWidget(self.test_button, 2, 3)

        # Temperature row: keep label aligned at col 0
        grid.addWidget(QLabel("<b>Temperature</b>"), 3, 0)
        temp_box = QHBoxLayout()
        self.temperature_slider = QSlider(Qt.Orientation.Horizontal); self.temperature_slider.setRange(0, 100); self.temperature_slider.setValue(70)
        self.temperature_value = QLabel("0.70")
        self.temperature_slider.valueChanged.connect(lambda v: self.temperature_value.setText(f"{v/100:.2f}"))
        temp_box.addWidget(self.temperature_slider)
        temp_box.addWidget(self.temperature_value)
        temp_wrap = QWidget(); temp_wrap.setLayout(temp_box)
        grid.addWidget(temp_wrap, 3, 1, 1, 3)

        layout.addLayout(grid)

        # Separator
        sep = QFrame(); sep.setFrameShape(getattr(QFrame, "HLine", QFrame.Shape.HLine)); sep.setFrameShadow(getattr(QFrame, "Sunken", QFrame.Shadow.Sunken))
        layout.addWidget(sep)

        # Prompt preview
        layout.addWidget(QLabel("<b>Prompt Preview</b>"))
        self.prompt_edit = QTextEdit(); self.prompt_edit.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)); 
        self.prompt_edit.setPlaceholderText('Prompt中必须包含“{Source Field}”占位符，以便正确替换和生成内容。')
        layout.addWidget(self.prompt_edit)

        # Prompt list + buttons
        pr_row = QHBoxLayout(); pr_row.addWidget(QLabel("<b>Prompt Name:</b>"))
        self.prompt_list_combo = QComboBox(); self.prompt_list_combo.setEditable(True); pr_row.addWidget(self.prompt_list_combo)
        self.prompt_list_combo.setToolTip("Select an existing prompt or type a new name before saving.")
        pr_row.addWidget(QLabel("<b>Search:</b>"))
        self.prompt_search_edit = QLineEdit(); self.prompt_search_edit.setPlaceholderText("输入关键词过滤...")
        self.prompt_search_edit.textChanged.connect(lambda _text: self._filter_prompts())
        pr_row.addWidget(self.prompt_search_edit)
        layout.addLayout(pr_row)

        # Get standard icons
        style = self.style()
        save_icon = style.standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton)
        load_icon = style.standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton)
        delete_icon = style.standardIcon(QStyle.StandardPixmap.SP_TrashIcon)
        import_icon = style.standardIcon(QStyle.StandardPixmap.SP_ArrowDown)
        export_icon = style.standardIcon(QStyle.StandardPixmap.SP_ArrowUp)
        online_icon = style.standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)

        btn_row = QHBoxLayout()
        self.import_button = QPushButton(" Import"); self.import_button.setIcon(import_icon)
        self.export_button = QPushButton(" Export"); self.export_button.setIcon(export_icon)
        self.online_button = QPushButton(" Online"); self.online_button.setIcon(online_icon)
        self.online_button.setEnabled(False)
        self.online_button.setToolTip("Online shared prompts are not available yet.")
        self.import_button.clicked.connect(self._on_import_prompt)
        self.export_button.clicked.connect(self._on_export_prompt)
        btn_row.addWidget(self.import_button); btn_row.addWidget(self.export_button); btn_row.addWidget(self.online_button)
        btn_row.addStretch(1)
        self.save_button = QPushButton(" Save"); self.save_button.setIcon(save_icon)
        self.save_button.setToolTip("Save the current Prompt Preview under the Prompt Name.")
        self.load_button = QPushButton(" Load"); self.load_button.setIcon(load_icon)
        self.delete_button = QPushButton(" Delete"); self.delete_button.setIcon(delete_icon)
        self.save_button.clicked.connect(self._on_save_prompt); self.load_button.clicked.connect(self._on_load_prompt); self.delete_button.clicked.connect(self._on_delete_prompt)
        self.prompt_list_combo.currentIndexChanged.connect(self._on_prompt_selection_changed)
        btn_row.addWidget(self.save_button); btn_row.addWidget(self.load_button); btn_row.addWidget(self.delete_button)
        layout.addLayout(btn_row)

        # Separator
        sep2 = QFrame(); sep2.setFrameShape(getattr(QFrame, "HLine", QFrame.Shape.HLine)); sep2.setFrameShadow(getattr(QFrame, "Sunken", QFrame.Shadow.Sunken))
        layout.addWidget(sep2)

        # Fields row
        fields_row = QHBoxLayout()
        fields_row.addWidget(QLabel("<b>Source Field:</b>"), 0)
        self.source_field_combo = QComboBox(); fields_row.addWidget(self.source_field_combo, 1)
        self.image_checkbox = QCheckBox("Enable Image Source"); fields_row.addWidget(self.image_checkbox, 0)
        fields_row.addWidget(QLabel("<b>Destination Field:</b>"))
        self.destination_field_combo = QComboBox(); fields_row.addWidget(self.destination_field_combo, 1)
        layout.addLayout(fields_row)

        self.setLayout(layout)
        self._populate_provider_cfg()

    def _toggle_pw(self):
        mode = self.api_key_edit.echoMode()
        try:
            from aqt.qt import QLineEdit as _QLE
            self.api_key_edit.setEchoMode(_QLE.EchoMode.Normal if mode != _QLE.EchoMode.Normal else _QLE.EchoMode.Password)
        except Exception:
            self.api_key_edit.setEchoMode(QLineEdit.Normal if mode != QLineEdit.Normal else QLineEdit.Password)

    def _load_prompt_list(self):
        self.all_prompts = _load_prompts()
        self._filter_prompts(preferred_name=_get_last_used_prompt(), load_selected=True)

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

    def _on_prompt_selection_changed(self, _index: int) -> None:
        if self._is_updating_prompt_combo:
            return
        self._load_prompt_by_name(self.prompt_list_combo.currentText().strip(), show_missing=False)

    def _load_prompt_by_name(self, name: str, show_missing: bool = True) -> bool:
        if not name:
            if show_missing:
                showWarning("Prompt name cannot be empty.")
            return False
        data = _load_prompts()
        if name not in data:
            if show_missing:
                showWarning("Prompt not found.")
            return False
        self.prompt_edit.setPlainText(data[name])
        self.all_prompts = data
        _set_last_used_prompt(name)
        return True

    def _load_note_fields(self):
        try:
            note_ids = self._selected_note_ids()
            if not note_ids:
                return
            n = mw.col.get_note(note_ids[0])
            names = [f["name"] for f in n.note_type()["flds"]]
            self.source_field_combo.clear(); self.destination_field_combo.clear()
            self.source_field_combo.addItems(names); self.destination_field_combo.addItems(names)
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
    def _on_save_prompt(self):
        name = self._prompt_name_text()
        if not name:
            showWarning("Prompt name cannot be empty."); return
        content = self.prompt_edit.toPlainText()
        if not content.strip():
            showWarning("Prompt Preview is empty."); return
        if QMessageBox.question(self, "Confirm Save", "Save this prompt?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.No:
            return
        data = _load_prompts(); data[name] = content; _save_prompts(data)
        self.all_prompts = data
        _set_last_used_prompt(name)
        self._refresh_prompt_combo_after_save(name)
        self.prompt_edit.setPlainText(content)
        showInfo(f"Prompt saved: {name}")

    def _on_load_prompt(self):
        name = self._prompt_name_text()
        self._load_prompt_by_name(name)

    def _on_delete_prompt(self):
        name = self._prompt_name_text()
        if not name:
            showWarning("Prompt name cannot be empty."); return
        if QMessageBox.question(self, "Confirm Delete", "Delete this prompt?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.No:
            return
        data = _load_prompts();
        if name in data:
            del data[name]; _save_prompts(data)
            self.all_prompts = data
            next_name = next(iter(data), "")
            _set_last_used_prompt(next_name)
            self._filter_prompts(preferred_name=next_name, load_selected=bool(next_name))
            if not next_name:
                self.prompt_edit.clear()
            showInfo("Prompt deleted.")

    def _on_import_prompt(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Import Prompts", "", "JSON Files (*.json)")
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                new_prompts = json.load(f)
            if not isinstance(new_prompts, dict):
                showWarning("Invalid prompt file format. Expected a JSON object."); return

            current_prompts = _load_prompts()
            conflicts = [k for k in new_prompts if k in current_prompts]
            if conflicts:
                if QMessageBox.question(self, "Confirm Overwrite", 
                                        f"The following prompts already exist: {', '.join(conflicts)}. Overwrite them?",
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.No:
                    # Don't overwrite, just import non-conflicting ones
                    for k in conflicts:
                        del new_prompts[k]
            
            current_prompts.update(new_prompts)
            _save_prompts(current_prompts)
            self.all_prompts = current_prompts
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
                json.dump({name: content}, f, ensure_ascii=False, indent=2)
            showInfo(f"Prompt '{name}' exported successfully.")
        except Exception as e:
            showWarning(f"Failed to export prompt: {e}")

    # Provider config
    def _service_map(self) -> str:
        svc = self.service_combo.currentText()
        return {"Open AI": "openai", "DeepSeek": "deepseek", "Ollama": "ollama"}.get(svc, "openai")

    def _populate_provider_cfg(self) -> None:
        st = "text"; pv = self._service_map()
        cfg = self.cfg.get_provider_config(st, pv)
        self.base_url_edit.setText(cfg.get("base_url", ""))
        self.api_key_edit.setText(cfg.get("api_key", ""))
        self.model_combo.setEditText(cfg.get("model", ""))
        # Also update temperature slider from config
        temp = cfg.get("temperature", 0.7)
        self.temperature_slider.setValue(int(temp * 100))
        self.temperature_value.setText(f"{temp:.2f}")

    def _refresh_models(self) -> None:
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
            self.cfg.set_provider_config(st, pv, {
                "base_url": base_url,
                "api_key": api_key,
                "model": self.model_combo.currentText().strip(),
                "temperature": self.temperature_slider.value() / 100.0,
            })
        except Exception as e:
            print(f"[AINotePro] Refresh models failed: {e}")
            showWarning(f"Failed to fetch models: {e}")

    def _test_model(self) -> None:
        # simple ping using a tiny prompt
        base_url = self.base_url_edit.text().strip(); api_key = self.api_key_edit.text().strip()
        model = self.model_combo.currentText().strip(); temp = self.temperature_slider.value()/100.0
        st = "text"; pv = self._service_map(); cfg = {"base_url": base_url, "api_key": api_key, "model": model, "temperature": temp}
        print(f"[AINotePro] Check clicked. service={pv}, model={model}, base_url={base_url}, temp={temp}")
        provider = create_provider(st, pv, cfg)
        try:
            content = provider.generate("hello", cfg)
            print("[AINotePro] Check OK. Got response length:", len(content or ""))
            showInfo(f"Test result:\n{content[:200]}")
        except Exception as e:
            print(f"[AINotePro] Check failed: {e}")
            showWarning(f"Test failed: {e}")

    # Public slot called by parent dialog
    def on_generate_text(self) -> None:
        note_ids = self._selected_note_ids()
        if not note_ids:
            showWarning("No notes selected."); return

        base_url = self.base_url_edit.text().strip(); api_key = self.api_key_edit.text().strip()
        model = self.model_combo.currentText().strip(); temp = self.temperature_slider.value()/100.0
        prompt_tpl = self.prompt_edit.toPlainText().strip()
        src = self.source_field_combo.currentText(); dst = self.destination_field_combo.currentText()
        if not prompt_tpl:
            showWarning("Prompt Preview is empty."); return
        if not src or not dst:
            showWarning("Source/Destination field is not set."); return

        st = "text"; pv = self._service_map(); provider = create_provider(st, pv, {})
        # If image-assisted is enabled, fall back to per-note flow for correctness
        if self.image_checkbox and self.image_checkbox.isChecked():
            updated = 0
            failures: list[str] = []
            try:
                mw.progress.start(label="Generating responses...", max=len(note_ids))
            except Exception:
                pass
            for i, nid in enumerate(note_ids):
                note = mw.col.get_note(nid)
                if src not in note: continue
                src_text = (note[src] or "").strip()
                cfg = {"base_url": base_url, "api_key": api_key, "model": model, "temperature": temp}
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
            "cfg_all": self.cfg.get_all(),
            "provider_name": pv,
            "base_cfg": {"base_url": base_url, "api_key": api_key, "model": model, "temperature": temp},
        }
        self.worker = GenerationWorker(params)
        self.worker.moveToThread(self.thread)

        # Connect signals
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.worker.progressUpdated.connect(progress.setValue)
        progress.canceled.connect(self.worker.cancel)

        def on_finish(message):
            progress.setValue(len(items))
            showInfo(message)

        self.worker.finished.connect(on_finish)

        # Start the thread
        self.thread.start()

    # Helpers
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
            return raw_src, None

        if parsed.scheme == "file":
            path = unquote(parsed.path)
        else:
            src = unquote(raw_src.split("?", 1)[0].split("#", 1)[0])
            src = src.lstrip("/")
            path = os.path.join(mw.col.media.dir(), src)

        if not os.path.exists(path):
            return None, f"Image file not found: {raw_src}"

        try:
            with open(path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            
            mime_type, _ = mimetypes.guess_type(path)
            if not mime_type:
                mime_type = "image/png" # Default if type can't be guessed
            
            return f"data:{mime_type};base64,{base64_image}", None
        except Exception as e:
            return None, f"Failed to encode image as Base64: {e}"

    def save_settings(self) -> None:
        """Saves the current UI settings for the selected provider to the config file."""
        st = "text"; pv = self._service_map()
        self.cfg.set_provider_config(st, pv, {
            "base_url": self.base_url_edit.text().strip(),
            "api_key": self.api_key_edit.text().strip(),
            "model": self.model_combo.currentText().strip(),
            "temperature": self.temperature_slider.value() / 100.0,
        })
        print(f"[AINotePro] Saved settings for Text/{pv}")
