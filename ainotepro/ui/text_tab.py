from __future__ import annotations

import json
import os
import re
from typing import Dict, Optional

from aqt import mw
from aqt.qt import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, QGridLayout, QComboBox, QLineEdit, QToolButton, QObject, pyqtSignal, QThread,
    QPushButton, QFrame, QTextEdit, QSizePolicy, QSlider, Qt, QProgressDialog,
    QMessageBox, QCheckBox
)
from aqt.utils import showInfo, showWarning

from ..config.manager import ConfigManager
from ..services.provider_factory import create_provider
from ..core.utils import update_field_content

# Note: PROMPT_FILE is separate from user_config.json as prompts can be shared/versioned.
USER_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "user_data", "gen_text")
PROMPT_FILE = os.path.join(USER_DATA_DIR, "prompt.json")


def _load_prompts() -> Dict[str, str]:
    try:
        if os.path.exists(PROMPT_FILE):
            with open(PROMPT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_prompts(data: Dict[str, str]) -> None:
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    with open(PROMPT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

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
            provider_name = self.params.get("provider_name", "openai")

            # Batching is mainly for OpenAI-compatible APIs. Ollama is handled sequentially.
            if provider_name == "ollama":
                USER_MAX_BATCH_SIZE = 1
            else:
                USER_MAX_BATCH_SIZE = int(concurrency_cfg.get("openai_batch_max_size", 20))
            BATCH_MAX_LEN = int(concurrency_cfg.get("openai_batch_max_prompt_len", 4096 * 10))

            print(f"[AINotePro] Concurrency limits: max_batch_size={USER_MAX_BATCH_SIZE}, max_prompt_len={BATCH_MAX_LEN}")

            # Determine effective batch size
            # It considers the prompt template length AND the average input length.
            effective_batch_size = USER_MAX_BATCH_SIZE
            base_prompt_len = len(prompt_tpl)
            if base_prompt_len > 0 and items:
                # Calculate average length of input strings
                avg_input_len = sum(len(t) for _, t in items) / len(items)
                # Estimate per-item cost: prompt template + input text + JSON overhead (quotes, commas, etc.)
                per_item_cost = base_prompt_len + avg_input_len + 10  # Add 10 for JSON chars
                
                if per_item_cost > 0:
                    len_based_batch_size = max(1, int(BATCH_MAX_LEN // per_item_cost))
                else:
                    len_based_batch_size = USER_MAX_BATCH_SIZE

                effective_batch_size = min(USER_MAX_BATCH_SIZE, len_based_batch_size)

            print(f"[AINotePro] Using effective batch size: {effective_batch_size}")

            processed = 0
            while processed < len(items):
                if self._is_cancelled:
                    break

                chunk = items[processed : processed + effective_batch_size]
                inputs = [t for (_, t) in chunk]
                
                outputs = []
                if provider_name == "ollama":
                    # For Ollama, the `generate_batch` method expects a list of fully-formed prompts.
                    # We prepare them here.
                    prompts = [prompt_tpl.replace("{Source Field}", text) for text in inputs]
                    try:
                        # The provider's batch method will handle sequential execution.
                        outputs = provider.generate_batch(prompts, base_cfg)
                    except Exception as e:
                        print(f"[AINotePro][Ollama Batch] provider error: {e}")
                        outputs = [f"[Error] {e}"] * len(inputs)
                else:
                    # OpenAI-compatible providers use batching
                    cfg = {**base_cfg, "instruction": prompt_tpl}
                    try:
                        outputs = provider.generate_batch(inputs, cfg)
                    except Exception as e:
                        print(f"[AINotePro][Batch] provider error: {e}. Falling back to concurrent per-item generation for this chunk.")
                        import concurrent.futures as _fut
                        outputs = [None] * len(inputs)
                        
                        def do_generate(idx, text):
                            prompt = prompt_tpl.replace("{Source Field}", text).replace("{Source}", text)
                            seq_cfg = {k: v for k, v in cfg.items() if k != "instruction"}
                            try:
                                return (idx, provider.generate(prompt, seq_cfg))
                            except Exception as e_inner:
                                return (idx, f"[Error] {e_inner}")

                        with _fut.ThreadPoolExecutor(max_workers=4) as ex:
                            future_to_idx = {ex.submit(do_generate, i, s): i for i, s in enumerate(inputs)}
                            for future in _fut.as_completed(future_to_idx):
                                idx, result = future.result()
                                outputs[idx] = result

                # Align and write back
                for (nid, _src), out in zip(chunk, outputs):
                    if self._is_cancelled:
                        break
                    try:
                        note = mw.col.get_note(nid)
                        update_field_content(note, dst, out)
                    except Exception as e:
                        print(f"[Note {nid}] write failed: {e}")
                    processed += 1
                    self.progressUpdated.emit(processed)

            self.finished.emit("Generation complete.")

        except Exception as e:
            import traceback
            print("[AINotePro] Unhandled error in worker thread:", traceback.format_exc())
            self.finished.emit(f"An error occurred: {e}")

    def cancel(self):
        self._is_cancelled = True


class TextTab(QWidget):
    def __init__(self, parent=None, browser=None):
        super().__init__(parent)
        self.browser = browser
        self.cfg = ConfigManager()
        self.all_prompts: Dict[str, str] = {}

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
        pr_row = QHBoxLayout(); pr_row.addWidget(QLabel("<b>Prompt List:</b>"))
        self.prompt_list_combo = QComboBox(); self.prompt_list_combo.setEditable(True); pr_row.addWidget(self.prompt_list_combo)
        pr_row.addWidget(QLabel("<b>Search:</b>"))
        self.prompt_search_edit = QLineEdit(); self.prompt_search_edit.setPlaceholderText("输入关键词过滤...")
        self.prompt_search_edit.textChanged.connect(self._filter_prompts)
        pr_row.addWidget(self.prompt_search_edit)
        layout.addLayout(pr_row)
        btn_row = QHBoxLayout(); self.save_button = QPushButton("Save Prompt"); self.load_button = QPushButton("Load Prompt"); self.delete_button = QPushButton("Delete Prompt")
        self.save_button.clicked.connect(self._on_save_prompt); self.load_button.clicked.connect(self._on_load_prompt); self.delete_button.clicked.connect(self._on_delete_prompt)
        btn_row.addWidget(self.save_button); btn_row.addWidget(self.load_button); btn_row.addWidget(self.delete_button); layout.addLayout(btn_row)

        # Separator
        sep2 = QFrame(); sep2.setFrameShape(getattr(QFrame, "HLine", QFrame.Shape.HLine)); sep2.setFrameShadow(getattr(QFrame, "Sunken", QFrame.Shadow.Sunken))
        layout.addWidget(sep2)

        # Fields row
        fields_row = QHBoxLayout()
        fields_row.addWidget(QLabel("<b>Source Field:</b>"))
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
        self._filter_prompts()

    def _filter_prompts(self):
        search_text = self.prompt_search_edit.text().lower()
        current_selection = self.prompt_list_combo.currentText()
        self.prompt_list_combo.clear()
        for name, content in self.all_prompts.items():
            if search_text in name.lower() or search_text in content.lower():
                self.prompt_list_combo.addItem(name)
        
        idx = self.prompt_list_combo.findText(current_selection)
        if idx != -1:
            self.prompt_list_combo.setCurrentIndex(idx)
    def _load_note_fields(self):
        try:
            if not self.browser:
                return
            sel = self.browser.selectedNotes()
            if not sel:
                return
            n = mw.col.get_note(sel[0])
            names = [f["name"] for f in n.note_type()["flds"]]
            self.source_field_combo.clear(); self.destination_field_combo.clear()
            self.source_field_combo.addItems(names); self.destination_field_combo.addItems(names)
        except Exception:
            pass

    # Prompt ops
    def _on_save_prompt(self):
        name = self.prompt_list_combo.currentText().strip()
        if not name:
            showWarning("Prompt name cannot be empty."); return
        if QMessageBox.question(self, "Confirm Save", "Save this prompt?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.No:
            return
        data = _load_prompts(); data[name] = self.prompt_edit.toPlainText(); _save_prompts(data)
        self.all_prompts = data
        self._filter_prompts()
        showInfo("Prompt saved.")

    def _on_load_prompt(self):
        name = self.prompt_list_combo.currentText().strip()
        if not name:
            showWarning("Prompt name cannot be empty."); return
        data = _load_prompts();
        if name not in data:
            showWarning("Prompt not found."); return
        self.prompt_edit.setPlainText(data[name])

    def _on_delete_prompt(self):
        name = self.prompt_list_combo.currentText().strip()
        if not name:
            showWarning("Prompt name cannot be empty."); return
        if QMessageBox.question(self, "Confirm Delete", "Delete this prompt?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.No:
            return
        data = _load_prompts();
        if name in data:
            del data[name]; _save_prompts(data)
            self.all_prompts = data
            self._filter_prompts()
            self.prompt_edit.clear(); showInfo("Prompt deleted.")

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
        if not self.browser:
            showWarning("Browser is not ready."); return
        note_ids = self.browser.selectedNotes()
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
        if self.image_checkbox.isChecked():
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
                img_url = self._extract_and_upload_image(src_text)
                if img_url:
                    try:
                        final_prompt = prompt_tpl.replace("{Source Field}", src_text).replace("{Source}", src_text)
                        content = provider.generate_with_image(img_url, final_prompt, cfg)
                    except Exception as e:
                        print(f"[Note {nid}] vision failed: {e}")
                        content = None
                if content:
                    update_field_content(note, dst, content)
                try:
                    mw.progress.update(value=i+1)
                except Exception:
                    pass
            try:
                mw.progress.finish()
            except Exception:
                pass
            showInfo("Generation complete.")
            return

        # Run generation in a background thread with a progress dialog for all providers
        progress = QProgressDialog("Generating content...", "Cancel", 0, len(items), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0) # Show immediately
        progress.setValue(0)

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
    def _extract_and_upload_image(self, html_content: str) -> Optional[str]:
        m = re.search(r'<img\s+src=["\']([^"\']+)["\']', html_content or "")
        if not m:
            return None
        src = m.group(1)
        media_dir = mw.col.media.dir(); path = os.path.join(media_dir, src)
        if not os.path.exists(path):
            return None
        # read hosting config
        api_key, upload_url = self._get_hosting_cfg()
        if not api_key or not upload_url:
            return None
        try:
            return self._upload_to_img_hosting(path, api_key, upload_url)
        except Exception:
            return None

    def _get_hosting_cfg(self) -> tuple[Optional[str], Optional[str]]:
        settings_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "user_data", "gen_text", "img_hosting.json"))
        try:
            if not os.path.exists(settings_file):
                return None, None
            with open(settings_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            last_used = data.get("last_used", {}); svc = last_used.get("service")
            if not svc or svc not in data:
                cand = [k for k in data.keys() if k != "last_used"]
                svc = cand[0] if cand else None
            if not svc:
                return None, None
            cfg = data.get(svc) or {}
            return cfg.get("api_key"), cfg.get("upload_url")
        except Exception:
            return None, None

    def _upload_to_img_hosting(self, image_path: str, api_key: str, upload_url: str) -> Optional[str]:
        import base64, json, requests
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8").replace("\n", "")
        payload = {"key": api_key, "source": b64, "filename": os.path.basename(image_path)}
        r = requests.post(upload_url, headers={"Content-Type": "application/json"}, data=json.dumps(payload), timeout=30)
        if r.status_code != 200:
            return None
        data = r.json()
        if data.get("status") == 200 and data.get("original", {}).get("url"):
            return data["original"]["url"]
        return None
