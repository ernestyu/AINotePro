import os
import json
import urllib.request
import urllib.error
import requests
import re

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

class OllamaGUI(BaseGUI):
    def __init__(self):
        super().__init__()
        cfg = load_config()
        ollama_cfg = cfg.get("Ollama", {})

        self.base_url_edit.setText(ollama_cfg.get("base_url", ""))
        self.api_key_edit.setText(ollama_cfg.get("api_key", ""))

        self.setup_api_key()

        self.refresh_button.clicked.connect(self.refresh_models)
        self.test_button.clicked.connect(self.test_model)

    def setup_api_key(self):
        self.api_key_label.setStyleSheet("color: gray;")
        self.api_key_edit.setEnabled(False)

    def refresh_models(self):
        base_url = self.base_url_edit.text().strip()
        if not base_url:
            showWarning("Base URL is incorrect!")
            return

        url = f"{base_url}/api/tags"
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception:
            showWarning("Base URL is incorrect!")
            return

        models = data.get("models", [])
        if not models:
            showWarning("Base URL is incorrect!")
            return

        self.model_combo.clear()
        for m in models:
            model_name = m.get("model", "")
            if model_name:
                self.model_combo.addItem(model_name)

        cfg = load_config()
        cfg["Ollama"] = {
            "service": "Ollama",
            "base_url": base_url,
            "api_key": ""
        }
        save_config(cfg)

    def test_model(self):
        model_name = self.model_combo.currentText().strip()
        if not model_name:
            showWarning("Please refresh model list.")
            return

        base_url = self.base_url_edit.text().strip()
        temperature = self.temperature_slider.value() / 100.0

        prompt = "hello"
        result = generate_ollama_chat(
            base_url=base_url,
            model_name=model_name,
            temperature=temperature,
            prompt=prompt
        )
        showInfo(f"Test result:\n{result}")

    def create_layout(self):
        layout = super().create_layout()
        return layout

def clean_response(response_text):
    response_text = re.sub(r"<think>.*?</think>", "", response_text, flags=re.DOTALL)
    response_text = response_text.strip()
    return response_text

def generate_ollama_chat(base_url, model_name, temperature, prompt):
    """
    base_url: Ollama 服务地址
    model_name: 模型名称
    temperature: 采样温度
    prompt: 字符串形式的用户提示
    """
    final_url = base_url.rstrip("/") + "/api/chat/completions"
    headers = {"Content-Type": "application/json"}

    # 1. 把单一 prompt 包装成 messages
    messages = [
        {"role": "user", "content": prompt}
    ]

    # 2. 构造符合 Chat Completions 规范的 payload
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
        "chat_template_kwargs": {
            "enable_thinking": False   # 关闭内部推理
        }
    }

    try:
        with requests.post(final_url, json=payload, headers=headers, timeout=60, stream=True) as resp:
            resp.raise_for_status()
            collected = []
            for line in resp.iter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                # Ollama 的 Chat 兼容格式，回答在 choices[0].delta.content
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content", "")
                collected.append(content)

        full = "".join(collected).strip()
        # （可选）如果模型仍偶尔残留 <think> 标签，继续清理
        return clean_response(full)
    except Exception as e:
        return f"[Error] {e}"

