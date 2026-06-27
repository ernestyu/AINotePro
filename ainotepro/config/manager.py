from __future__ import annotations

import json
import os
import shutil
from typing import Any, Dict

ADDON_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
USER_FILES_DIR = os.path.join(ADDON_ROOT, "user_files")
LEGACY_USER_DATA_DIR = os.path.join(ADDON_ROOT, "user_data")
CONFIG_FILE = os.path.join(USER_FILES_DIR, "user_config.json")


def _copy_missing_tree(src: str, dst: str) -> None:
    for root, dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        target_root = dst if rel == "." else os.path.join(dst, rel)
        os.makedirs(target_root, exist_ok=True)
        for dirname in dirs:
            os.makedirs(os.path.join(target_root, dirname), exist_ok=True)
        for filename in files:
            src_file = os.path.join(root, filename)
            dst_file = os.path.join(target_root, filename)
            if not os.path.exists(dst_file):
                shutil.copy2(src_file, dst_file)


def migrate_legacy_user_data() -> None:
    """Move pre-release user_data files into Anki's upgrade-safe user_files."""
    os.makedirs(USER_FILES_DIR, exist_ok=True)
    if not os.path.isdir(LEGACY_USER_DATA_DIR):
        return
    try:
        _copy_missing_tree(LEGACY_USER_DATA_DIR, USER_FILES_DIR)
    except Exception as e:
        print(f"[AINotePro] Failed to migrate user_data to user_files: {e}")


def _prune_removed_config_keys(data: Dict[str, Any]) -> Dict[str, Any]:
    """Remove pre-1.0 config keys that are no longer public or supported."""
    if not isinstance(data, dict):
        return data
    data.pop("concurrency", None)
    data.pop("image", None)
    text_cfg = data.get("text")
    if isinstance(text_cfg, dict):
        text_cfg.pop("allow_remote_image_urls", None)
    return data


def _get_default_config() -> Dict[str, Any]:
    """Returns a dictionary with the default configuration."""
    return {
        "text": {
            "provider": "openai",
            "debug_logging": False,
            "openai": {"base_url": "https://api.openai.com", "api_key": "", "model": "gpt-4o-mini", "temperature": 0.7},
            "deepseek": {"base_url": "https://api.deepseek.com", "api_key": "", "model": "deepseek-chat", "temperature": 0.7},
            "openrouter": {"base_url": "https://openrouter.ai/api", "api_key": "", "model": "openai/gpt-4o-mini", "temperature": 0.7},
            "dashscope": {"base_url": "https://dashscope.aliyuncs.com/compatible-mode", "api_key": "", "model": "qwen-plus", "temperature": 0.7},
            "moonshot": {"base_url": "https://api.moonshot.cn", "api_key": "", "model": "moonshot-v1-8k", "temperature": 0.7},
            "zhipu": {"base_url": "https://open.bigmodel.cn/api/paas", "api_key": "", "model": "glm-4-flash", "temperature": 0.7},
            "siliconflow": {"base_url": "https://api.siliconflow.cn", "api_key": "", "model": "Qwen/Qwen2.5-7B-Instruct", "temperature": 0.7},
            "groq": {"base_url": "https://api.groq.com/openai", "api_key": "", "model": "llama-3.1-8b-instant", "temperature": 0.7},
            "together": {"base_url": "https://api.together.xyz", "api_key": "", "model": "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo", "temperature": 0.7},
            "perplexity": {"base_url": "https://api.perplexity.ai", "api_key": "", "model": "sonar", "temperature": 0.7},
            "gemini": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "api_key": "", "model": "gemini-1.5-flash", "temperature": 0.7},
            "lmstudio": {"base_url": "http://localhost:1234", "api_key": "lm-studio", "model": "", "temperature": 0.7},
            "localai": {"base_url": "http://localhost:8080", "api_key": "", "model": "", "temperature": 0.7},
            "ollama": {"base_url": "http://localhost:11434", "api_key": "ollama", "model": "llama3", "temperature": 0.7},
            "prompts": {
                "Default": "Translate the following text to English: {Source Field}",
            },
            "last_used_prompt": "Default",
        },
        "audio": {
            "provider": "edge_tts",
            "edge_tts": {"voice": "en-US-AriaNeural", "speed": 0, "volume": 0, "pitch": 0},
        },
        "ui": {
            "last_service_tab": "text",
        },
    }

def _deep_merge_dicts(source: Dict, destination: Dict) -> Dict:
    """
    Recursively merges source dict into destination dict.
    - If a key exists in both and both values are dicts, it merges them recursively.
    - If a key exists in source but not in destination, it's added to destination.
    - If a key exists in both but values are not both dicts, destination's value is kept.
    """
    for key, value in source.items():
        if isinstance(value, dict) and key in destination and isinstance(destination[key], dict):
            _deep_merge_dicts(value, destination.setdefault(key, {}))
        elif key not in destination:
            destination[key] = value
    return destination

class ConfigManager:
    def __init__(self):
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Loads config from file, or creates a default one if it doesn't exist."""
        migrate_legacy_user_data()
        os.makedirs(USER_FILES_DIR, exist_ok=True)
        if not os.path.exists(CONFIG_FILE):
            print(f"[AINotePro] Config file not found. Creating default at {CONFIG_FILE}")
            default_config = _get_default_config()
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(default_config, f, ensure_ascii=False, indent=2)
            return default_config
        
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                user_config = json.load(f)
            user_config = _prune_removed_config_keys(user_config)
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
        self.config = _prune_removed_config_keys(self._load_config())
        if service_type not in self.config: self.config[service_type] = {}
        if provider_name not in self.config[service_type]: self.config[service_type][provider_name] = {}
        self.config[service_type][provider_name].update(provider_cfg)
        self.config[service_type]["provider"] = provider_name
        self._save_config()

    def save_all(self, data: Dict[str, Any]):
        """Replaces the full config and saves it."""
        data = _prune_removed_config_keys(data)
        self.config = _deep_merge_dicts(_get_default_config(), data)
        self._save_config()

    def _save_config(self):
        """Saves the current configuration to the file."""
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)
