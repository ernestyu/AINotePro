from __future__ import annotations

import json
import os
from typing import Any, Dict

ADDON_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
USER_DATA_DIR = os.path.join(ADDON_ROOT, "user_data")
CONFIG_FILE = os.path.join(USER_DATA_DIR, "user_config.json")


def _get_default_config() -> Dict[str, Any]:
    """Returns a dictionary with the default configuration."""
    return {
        "text": {
            "provider": "openai",
            "openai": {"base_url": "https://api.openai.com", "api_key": "", "model": "gpt-4o-mini", "temperature": 0.7},
            "deepseek": {"base_url": "https://api.deepseek.com", "api_key": "", "model": "deepseek-chat", "temperature": 0.7},
            "ollama": {"base_url": "http://localhost:11434", "api_key": "ollama", "model": "llama3", "temperature": 0.7},
        },
        "image": {
            "provider": "dalle",
            "dalle": {"base_url": "https://api.openai.com", "api_key": "", "model": "dall-e-3"},
            "sd_webui": {"base_url": "http://127.0.0.1:7860"},
        },
        "audio": {
            "provider": "edge_tts",
            "edge_tts": {"voice": "en-US-AriaNeural", "speed": 0, "volume": 0, "pitch": 0},
        },
        "ui": {
            "last_service_tab": "text",
        },
        "concurrency": {
            "openai_batch_max_size": 20,
            "openai_batch_max_prompt_len": 8000,
            "ollama_workers": 4,
        },
    }

def _deep_merge_dicts(source: Dict, destination: Dict) -> Dict:
    """
    Recursively merges source dict into destination dict.
    If a key exists in both, and both values are dicts, it merges them.
    Otherwise, the value from the destination dict takes precedence.
    """
    for key, value in source.items():
        if isinstance(value, dict) and key in destination and isinstance(destination[key], dict):
            destination[key] = _deep_merge_dicts(value, destination[key])
        elif key not in destination:
            destination[key] = value
    return destination

class ConfigManager:
    def __init__(self):
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Loads config from file, or creates a default one if it doesn't exist."""
        os.makedirs(USER_DATA_DIR, exist_ok=True)
        if not os.path.exists(CONFIG_FILE):
            print(f"[AINotePro] Config file not found. Creating default at {CONFIG_FILE}")
            default_config = _get_default_config()
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(default_config, f, ensure_ascii=False, indent=2)
            return default_config
        
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                user_config = json.load(f)
            # Merge user config into defaults to fill in any missing keys
            default_config = _get_default_config()
            return _deep_merge_dicts(default_config, user_config)
        except (json.JSONDecodeError, IOError) as e:
            print(f"[AINotePro] Error loading config file: {e}. Loading default config.")
            return _get_default_config()


    def get_all(self) -> Dict[str, Any]:
        """Returns the entire configuration dictionary."""
        return self.config

    def get_provider_config(self, service_type: str, provider_name: str) -> Dict[str, Any]:
        """Gets the config for a specific provider (e.g., text.openai)."""
        return self.config.get(service_type, {}).get(provider_name, {})

    def set_provider_config(self, service_type: str, provider_name: str, provider_cfg: Dict[str, Any]):
        """Sets the config for a specific provider and saves it."""
        if service_type not in self.config: self.config[service_type] = {}
        if provider_name not in self.config[service_type]: self.config[service_type][provider_name] = {}
        self.config[service_type][provider_name].update(provider_cfg)
        self._save_config()

    def _save_config(self):
        """Saves the current configuration to the file."""
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)