# deepseek.py

import os
import json
import requests
import urllib.request
import urllib.error

from aqt.utils import showWarning, showInfo
from .baseGUI import BaseGUI

CONFIG_FILE = os.path.join(
    os.path.dirname(__file__),  # \AINotePro\ainotepro\gen_text\models
    "..",                       # -> \AINotePro\ainotepro\gen_text
    "..",                       # -> \AINotePro\ainotepro
    "..",                       # -> \AINotePro
    "user_data",
    "gen_text",
    "model_config.json"         # -> \AINotePro\user_data\gen_text\model_config.json
)

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_config(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

class DeepSeekGUI(BaseGUI):
    def __init__(self):
        super().__init__()
        cfg = load_config()
        deepseek_cfg = cfg.get("DeepSeek", {})

        self.base_url_edit.setText(deepseek_cfg.get("base_url", ""))
        self.api_key_edit.setText(deepseek_cfg.get("api_key", ""))

        self.setup_api_key()

        self.refresh_button.clicked.connect(self.refresh_models)
        self.test_button.clicked.connect(self.test_model)

    def setup_api_key(self):
        self.api_key_label.setStyleSheet("")
        self.api_key_edit.setEnabled(True)

    def refresh_models(self):
        base_url = self.base_url_edit.text().strip()
        api_key = self.api_key_edit.text().strip()
        if not base_url:
            showWarning("Base URL is incorrect!")
            return
        if not api_key:
            showWarning("API Key is required!")
            return

        url = f"{base_url.rstrip('/')}/v1/models"
        try:
            req = urllib.request.Request(url)
            req.add_header("Authorization", "Bearer " + api_key)
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception:
            showWarning("Base URL or API Key is incorrect!")
            return

        models = data.get("data", [])
        if not models:
            showWarning("No models found!")
            return

        self.model_combo.clear()
        for m in models:
            model_name = m.get("id", "")
            if model_name:
                self.model_combo.addItem(model_name)

        cfg = load_config()
        cfg["DeepSeek"] = {
            "service": "DeepSeek",
            "base_url": base_url,
            "api_key": api_key
        }
        save_config(cfg)

    def test_model(self):
        model_name = self.model_combo.currentText().strip()
        if not model_name:
            showWarning("Please refresh the model list.")
            return

        base_url = self.base_url_edit.text().strip()
        api_key = self.api_key_edit.text().strip()
        temperature = self.temperature_slider.value() / 100.0

        user_text = "hello"
        system_prompt = ""

        result = generate_deepseek_chat(
            base_url=base_url,
            api_key=api_key,
            model_name=model_name,
            temperature=temperature,
            system_prompt=system_prompt,
            user_text=user_text
        )
        showInfo(f"Test result:\n{result}")

    def create_layout(self):
        layout = super().create_layout()
        return layout

def generate_deepseek_chat(base_url, api_key, model_name, temperature, system_prompt, user_text):
    final_url = base_url.rstrip("/") + "/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key

    payload = {
        "model": model_name,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text}
        ],
        "stream": False
    }
    try:
        resp = requests.post(final_url, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            return "[Error] No content returned."
        content = choices[0]["message"].get("content", "").strip()
        return content
    except Exception as e:
        return f"[Error] {str(e)}"
