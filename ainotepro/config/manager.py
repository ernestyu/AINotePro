from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import hashlib
import copy

from .audio_profiles import migrate_audio, validate_audio

_CONFIG_LOCK = threading.RLock()
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
    """Single writer for settings; Audio profiles are always replaced, never deep-merged."""

    def __init__(self):
        self.config = self._load_config()

    @staticmethod
    def _atomic_write(data):
        os.makedirs(USER_FILES_DIR, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".ainotepro-", suffix=".json", dir=USER_FILES_DIR)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(data, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp, CONFIG_FILE)
            try:
                dfd = os.open(USER_FILES_DIR, os.O_RDONLY)
                try:
                    os.fsync(dfd)
                finally:
                    os.close(dfd)
            except OSError:
                pass
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    @staticmethod
    def _revision():
        if not os.path.exists(CONFIG_FILE):
            return None
        with open(CONFIG_FILE, "rb") as stream:
            return hashlib.sha256(stream.read()).hexdigest()

    @staticmethod
    def _read_raw():
        if not os.path.exists(CONFIG_FILE):
            return None
        with open(CONFIG_FILE, "r", encoding="utf-8") as stream:
            raw = json.load(stream)
        if not isinstance(raw, dict):
            raise ValueError("AINotePro config root must be a JSON object")
        return raw

    def _load_config(self):
        with _CONFIG_LOCK:
            migrate_legacy_user_data()
            os.makedirs(USER_FILES_DIR, exist_ok=True)
            raw = self._read_raw()
            if raw is None:
                raw = _get_default_config()
                raw["audio"] = migrate_audio(raw["audio"])
                self._atomic_write(raw)
            else:
                _prune_removed_config_keys(raw)
                audio = raw.get("audio", {})
                if not isinstance(audio, dict):
                    raise ValueError("Invalid Audio configuration; original file retained")
                if "profiles" not in audio and not audio.get("migration", {}).get("legacy_edge_v1_done"):
                    backup = CONFIG_FILE + ".pre-audio-v2.bak"
                    if not os.path.exists(backup):
                        shutil.copy2(CONFIG_FILE, backup)
                    raw["audio"] = migrate_audio(audio)
                    self._atomic_write(raw)
                else:
                    validate_audio(audio)
            merged = _deep_merge_dicts(_get_default_config(), copy.deepcopy(raw))
            merged["audio"] = copy.deepcopy(raw["audio"])
            return merged

    def get_all(self):
        return copy.deepcopy(self.config)

    def get_provider_config(self, service_type, provider_name):
        return copy.deepcopy(self.config.get(service_type, {}).get(provider_name, {}))

    def _replace_raw(self, mutator, expected_revision=None):
        with _CONFIG_LOCK:
            current = self._read_raw()
            if current is None:
                raise ValueError("Configuration file disappeared")
            if expected_revision is not None and self._revision() != expected_revision:
                raise RuntimeError("Configuration changed in another window; reload before saving")
            updated = copy.deepcopy(current)
            mutator(updated)
            if "audio" in updated and "profiles" in updated["audio"]:
                validate_audio(updated["audio"])
            self._atomic_write(updated)
            self.config = _deep_merge_dicts(_get_default_config(), copy.deepcopy(updated))
            self.config["audio"] = copy.deepcopy(updated["audio"])
            return self._revision()

    def audio_revision(self):
        return self._revision()

    def get_audio(self):
        return copy.deepcopy(self.config["audio"])

    def replace_audio(self, audio, expected_revision=None):
        validate_audio(audio)
        return self._replace_raw(
            lambda raw: raw.__setitem__("audio", copy.deepcopy(audio)),
            expected_revision=expected_revision,
        )

    def set_provider_config(self, service_type, provider_name, provider_cfg):
        def update(raw):
            service = raw.setdefault(service_type, {})
            service.setdefault(provider_name, {}).update(copy.deepcopy(provider_cfg))
            service["provider"] = provider_name
        self._replace_raw(update)

    def save_all(self, data):
        """Compatibility API: preserve unknown keys and replace Audio profiles as one unit."""
        _prune_removed_config_keys(data)
        def update(raw):
            for key, value in data.items():
                if key == "audio":
                    validate_audio(value)
                    raw[key] = copy.deepcopy(value)
                elif isinstance(value, dict) and isinstance(raw.get(key), dict):
                    raw[key].update(copy.deepcopy(value))
                else:
                    raw[key] = copy.deepcopy(value)
        self._replace_raw(update)

    def _save_config(self):
        self.save_all(self.config)
