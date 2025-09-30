from __future__ import annotations

import json
import os
import re
from typing import Dict, Optional

from aqt import mw
from aqt.qt import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, QGridLayout, QComboBox, QLineEdit, QToolButton,
    QPushButton, QFrame, QTextEdit, QSizePolicy, QSlider, Qt, QProgressDialog,
    QMessageBox, QCheckBox
)
from aqt.utils import showInfo, showWarning

from ..config.manager import ConfigManager
from ..services.provider_factory import create_provider
from ..core.utils import update_field_content


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


class TextTab(QWidget):
    def __init__(self, parent=None, browser=None):
        super().__init__(parent)
        self.browser = browser
        self.cfg = ConfigManager()

        self._build_ui()
        self._load_note_fields()
        self._load_prompt_list()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Title
        title = QLabel('<div style="font-size:14px; font-weight:bold; font-style:italic;">Insert AI-generated content into the selected note</div>')
        layout.addWidget(title)

        # Generate using
        gen_row = QHBoxLayout()
        gen_row.addWidget(QLabel("Generate using"))
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
        grid.addWidget(QLabel("Base URL"), 0, 0)
        self.base_url_edit = QLineEdit(); self.base_url_edit.setPlaceholderText("https://api.example.com")
        grid.addWidget(self.base_url_edit, 0, 1, 1, 3)

        # API Key + lock button at far right
        grid.addWidget(QLabel("API Key"), 1, 0)
        self.api_key_edit = QLineEdit()
        try:
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        except Exception:
            self.api_key_edit.setEchoMode(QLineEdit.Password)
        # pack API key field and lock button into an inner row to eliminate the gap
        api_row = QHBoxLayout(); api_row.setContentsMargins(0, 0, 0, 0); api_row.setSpacing(4)
        api_row.addWidget(self.api_key_edit, 1)
        self.toggle_password_button = QToolButton(); self.toggle_password_button.setText("馃敀")
        self.toggle_password_button.setFixedWidth(28)
        self.toggle_password_button.clicked.connect(self._toggle_pw)
        api_row.addWidget(self.toggle_password_button, 0)
        api_wrap = QWidget(); api_wrap.setLayout(api_row)
        grid.addWidget(api_wrap, 1, 1, 1, 3)

        # Available Model + right-aligned small buttons
        grid.addWidget(QLabel("Available Model"), 2, 0)
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
        grid.addWidget(QLabel("Temperature"), 3, 0)
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
        layout.addWidget(QLabel("Prompt Preview"))
        self.prompt_edit = QTextEdit(); self.prompt_edit.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding))
        layout.addWidget(self.prompt_edit)

        # Prompt list + buttons
        pr_row = QHBoxLayout(); pr_row.addWidget(QLabel("Prompt List:"))
        self.prompt_list_combo = QComboBox(); self.prompt_list_combo.setEditable(True)
        pr_row.addWidget(self.prompt_list_combo); layout.addLayout(pr_row)
        btn_row = QHBoxLayout(); self.save_button = QPushButton("Save Prompt"); self.load_button = QPushButton("Load Prompt"); self.delete_button = QPushButton("Delete Prompt")
        self.save_button.clicked.connect(self._on_save_prompt); self.load_button.clicked.connect(self._on_load_prompt); self.delete_button.clicked.connect(self._on_delete_prompt)
        btn_row.addWidget(self.save_button); btn_row.addWidget(self.load_button); btn_row.addWidget(self.delete_button); layout.addLayout(btn_row)

        # Source Field
        srow = QHBoxLayout(); srow.addWidget(QLabel("Source Field:"))
        self.source_field_combo = QComboBox(); srow.addWidget(self.source_field_combo); layout.addLayout(srow)

        # Image input toggle + button
        img_row = QHBoxLayout(); self.image_checkbox = QCheckBox("Enable Image Source"); self.image_checkbox.stateChanged.connect(self._on_img_toggle)
        self.image_input_button = QPushButton("Image Hosting Platform"); self.image_input_button.setEnabled(False)
        img_row.addWidget(self.image_checkbox); img_row.addWidget(self.image_input_button); layout.addLayout(img_row)

        # Destination Field
        drow = QHBoxLayout(); drow.addWidget(QLabel("Destination Field:"))
        self.destination_field_combo = QComboBox(); drow.addWidget(self.destination_field_combo); layout.addLayout(drow)

        self.setLayout(layout)
        self._populate_provider_cfg()

    # UI helpers
    def _toggle_pw(self):
        mode = self.api_key_edit.echoMode()
        try:
            from aqt.qt import QLineEdit as _QLE
            self.api_key_edit.setEchoMode(_QLE.EchoMode.Normal if mode != _QLE.EchoMode.Normal else _QLE.EchoMode.Password)
        except Exception:
            self.api_key_edit.setEchoMode(QLineEdit.Normal if mode != QLineEdit.Normal else QLineEdit.Password)

    def _on_img_toggle(self):
        self.image_input_button.setEnabled(bool(self.image_checkbox.isChecked()))

    # Data loaders
    def _load_prompt_list(self):
        prompts = _load_prompts()
        self.prompt_list_combo.clear()
        for k in prompts.keys():
            self.prompt_list_combo.addItem(k)

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
        if self.prompt_list_combo.findText(name) < 0:
            self.prompt_list_combo.addItem(name)
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
            idx = self.prompt_list_combo.findText(name); 
            if idx >= 0: self.prompt_list_combo.removeItem(idx)
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
                cfg = {"base_url": base_url, "api_key": api_key, "model": model, "temperature": temp}
                content: Optional[str] = None
                img_url = self._extract_and_upload_image(note[src])
                if img_url:
                    try:
                        content = provider.generate_with_image(img_url, prompt_tpl, cfg)
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

        # Read concurrency config
        try:
            cfg_all = self.cfg.get_all()
            BATCH_SIZE = int((cfg_all.get("concurrency", {}) or {}).get("openai_batch_size", 20))
            OLLAMA_WORKERS = int((cfg_all.get("concurrency", {}) or {}).get("ollama_workers", 4))
        except Exception:
            BATCH_SIZE = 20
            OLLAMA_WORKERS = 4
        total = len(items)
        try:
            mw.progress.start(label=f"Generating {total} items...", max=total)
        except Exception:
            pass

        processed = 0
        # Ollama: run concurrent per-item requests for performance
        if self.service_combo.currentText() == "Ollama":
            import concurrent.futures as _fut
            cfg = {"base_url": base_url, "api_key": api_key, "model": model, "temperature": temp}
            with _fut.ThreadPoolExecutor(max_workers=OLLAMA_WORKERS) as ex:
                futures = []
                for nid, text in items:
                    prompt = prompt_tpl.replace("{Source Field}", text)
                    prev = (prompt[:200] + "...") if len(prompt) > 200 else prompt
                    print("[AINotePro][Ollama Seq] prompt:", prev)
                    futures.append(ex.submit(lambda n,s: (n, provider.generate(s, cfg)), nid, prompt))
                for fut in _fut.as_completed(futures):
                    nid, out = fut.result()
                    try:
                        note = mw.col.get_note(nid)
                        update_field_content(note, dst, out)
                    except Exception as e:
                        print(f"[Note {nid}] write failed: {e}")
                    processed += 1
                    try:
                        mw.progress.update(value=processed)
                    except Exception:
                        pass
            try:
                mw.progress.finish()
            except Exception:
                pass
            showInfo("Batch generation complete.")
            return

        while processed < total:
            chunk = items[processed: processed + BATCH_SIZE]
            inputs = [t for (_, t) in chunk]
            cfg = {
                "base_url": base_url,
                "api_key": api_key,
                "model": model,
                "temperature": temp,
                "instruction": prompt_tpl,
            }
            try:
                outputs = provider.generate_batch(inputs, cfg)
            except Exception as e:
                print("[AINotePro][Batch] provider error:", e)
                # fallback sequential with detailed logging
                outputs = []
                for s in inputs:
                    prompt = prompt_tpl.replace("{Source Field}", s)
                    print("[AINotePro][Seq Fallback] prompt:", (prompt[:200] + "...") if len(prompt) > 200 else prompt)
                    outputs.append(provider.generate(prompt, cfg))

            # Align and write back
            if len(outputs) != len(chunk):
                print("[AINotePro][Batch] size mismatch, falling back per-item.")
                outputs = []
                for s in inputs:
                    prompt = prompt_tpl.replace("{Source Field}", s)
                    print("[AINotePro][Seq Fallback] prompt:", (prompt[:200] + "...") if len(prompt) > 200 else prompt)
                    outputs.append(provider.generate(prompt, cfg))

            for (nid, _src), out in zip(chunk, outputs):
                try:
                    note = mw.col.get_note(nid)
                    update_field_content(note, dst, out)
                except Exception as e:
                    print(f"[Note {nid}] write failed: {e}")
                processed += 1
                try:
                    mw.progress.update(value=processed)
                except Exception:
                    pass

        try:
            mw.progress.finish()
        except Exception:
            pass
        showInfo("Batch generation complete.")

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

