"""Offline coverage for the minimal Text provider endpoint contract."""
from __future__ import annotations

import copy
import ast
import json
import tempfile
import unittest
import sys
import types
from pathlib import Path
from unittest.mock import patch

if "requests" not in sys.modules:
    requests_stub = types.ModuleType("requests")
    requests_stub.post = lambda *_args, **_kwargs: None
    requests_stub.get = lambda *_args, **_kwargs: None
    sys.modules["requests"] = requests_stub

from ainotepro.config import manager
from ainotepro.config.audio_profiles import migrate_audio, validate_audio
from ainotepro.services.text.openai_text import OpenAITextProvider
from ainotepro.provider_presets import PROVIDER_PRESETS


class _Response:
    def __init__(self, data): self.data = data
    def raise_for_status(self): pass
    def json(self): return self.data


class TextProviderMinimalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = (manager.USER_FILES_DIR, manager.LEGACY_USER_DATA_DIR, manager.CONFIG_FILE)
        manager.USER_FILES_DIR = self.tmp.name
        manager.LEGACY_USER_DATA_DIR = str(Path(self.tmp.name) / "no-legacy")
        manager.CONFIG_FILE = str(Path(self.tmp.name) / "user_config.json")

    def tearDown(self):
        manager.USER_FILES_DIR, manager.LEGACY_USER_DATA_DIR, manager.CONFIG_FILE = self.old
        self.tmp.cleanup()

    def test_fresh_config_persists_complete_official_endpoints(self):
        self.assertEqual(len(PROVIDER_PRESETS), 13)
        manager.ConfigManager()
        raw = json.loads(Path(manager.CONFIG_FILE).read_text())
        self.assertEqual(raw["text"]["openai"]["chat_endpoint"],
                         "https://api.openai.com/v1/chat/completions")
        self.assertEqual(raw["text"]["gemini"]["models_endpoint"],
                         "https://generativelanguage.googleapis.com/v1beta/openai/models")
        self.assertIn("anthropic", raw["text"])
        self.assertIn("vllm", raw["text"])

    def test_existing_base_url_keeps_legacy_routes_when_other_values_save(self):
        defaults = manager._get_default_config()
        raw = {"text": {"provider": "deepseek", "deepseek": {
                    "base_url": "https://proxy.example/api", "api_key": "old", "model": "old", "temperature": 0.7}},
               "audio": migrate_audio(defaults["audio"])}
        Path(manager.CONFIG_FILE).write_text(json.dumps(raw), encoding="utf-8")
        cfg = manager.ConfigManager()
        shown = cfg.get_provider_config("text", "deepseek")
        self.assertNotIn("chat_endpoint", shown)
        self.assertNotIn("models_endpoint", shown)
        cfg.set_provider_config("text", "deepseek", {"model": "new", "temperature": 0.2})
        saved = json.loads(Path(manager.CONFIG_FILE).read_text())["text"]["deepseek"]
        self.assertEqual(saved["base_url"], "https://proxy.example/api")
        self.assertNotIn("chat_endpoint", saved)
        self.assertNotIn("models_endpoint", saved)

    def test_custom_providers_are_independent_and_do_not_replace_text_config(self):
        cfg = manager.ConfigManager()
        cfg.save_custom_provider("one", {"name": "Home", "chat_endpoint": "http://a/chat",
                                           "models_endpoint": "", "api_key": "a", "model": "m1", "temperature": 0.1})
        cfg.save_custom_provider("two", {"name": "School", "chat_endpoint": "http://b/chat",
                                           "models_endpoint": "http://b/models", "api_key": "b", "model": "m2", "temperature": 0.2})
        self.assertEqual(cfg.get_provider_config("text", "custom:one")["api_key"], "a")
        self.assertEqual(cfg.get_provider_config("text", "custom:two")["chat_endpoint"], "http://b/chat")
        cfg.delete_custom_provider("one")
        self.assertNotIn("one", cfg.get_custom_providers())
        self.assertIn("two", cfg.get_custom_providers())

    def test_complete_endpoints_are_used_without_path_appending(self):
        provider = OpenAITextProvider("custom:one")
        config = {"chat_endpoint": "https://example.test/my-chat", "models_endpoint": "https://example.test/my-models",
                  "api_key": "secret", "model": "m", "temperature": 0.7, "provider_key": "custom:one"}
        with patch("ainotepro.services.text.openai_text.requests.post", return_value=_Response({"choices": [{"message": {"content": "ok"}}]})) as post:
            self.assertEqual(provider.generate("hello", config), "ok")
            self.assertEqual(post.call_args.args[0], "https://example.test/my-chat")
            self.assertNotIn("reasoning_effort", post.call_args.kwargs["json"])
        with patch("ainotepro.services.text.openai_text.requests.get", return_value=_Response({"data": [{"id": "m"}]})) as get:
            self.assertEqual(provider.list_models(config), ["m"])
            self.assertEqual(get.call_args.args[0], "https://example.test/my-models")

    def test_audio_pitch_is_optional_but_preserved(self):
        audio = migrate_audio(manager._get_default_config()["audio"])
        voice = audio["profiles"]["legacy-edge-default"]["provider_configs"]["edge_tts"]["voices"][0]
        voice["pitch"] = 17
        validate_audio(copy.deepcopy(audio))
        del voice["pitch"]
        validate_audio(audio)

    def test_kokoro_display_rounding_does_not_change_unedited_speed(self):
        source = (Path(__file__).resolve().parents[1] / "ainotepro/ui/tts_tab.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        tab = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "TTSTab")
        capture = next(node for node in tab.body if isinstance(node, ast.FunctionDef) and node.name == "_capture")
        namespace = {}
        module = ast.Module(body=[ast.ClassDef(name="Capture", bases=[], keywords=[], body=[capture], decorator_list=[])], type_ignores=[])
        exec(compile(ast.fix_missing_locations(module), "<capture>", "exec"), namespace)

        class Value:
            def __init__(self, value): self.value_ = value
            def value(self): return self.value_
        class Text:
            def __init__(self, text): self.text_ = text
            def text(self): return self.text_
            def currentText(self): return self.text_
            def currentData(self): return None
            def isChecked(self): return False
            def currentIndex(self): return -1

        class Tab(namespace["Capture"]):
            def __init__(self):
                self._loading = False
                self._draft = {"provider": "kokoro_gradio", "provider_configs": {"kokoro_gradio": {
                    "base_url": "http://127.0.0.1:7860", "voices": [{"enabled": False, "voice": "af_heart",
                    "gender": "Female", "preview_text": "", "accent": "American", "locale": "en-US", "speed": 1.005}]}}}
                self.url_edit = Text("http://127.0.0.1:7860")
                self.voice_blocks = [{"enable": Text(""), "voice": Text(""), "gender": Text("Female"),
                                      "preview": Text(""), "accent": Text("American"), "speed": Value(0),
                                      "speed_dirty": False}]
                self.src_combo = Text(""); self.dst_combo = Text("")

        tab = Tab()
        tab._capture()
        self.assertEqual(tab._draft["provider_configs"]["kokoro_gradio"]["voices"][0]["speed"], 1.005)
        tab.voice_blocks[0]["speed_dirty"] = True
        tab.voice_blocks[0]["speed"].value_ = 1
        tab._capture()
        self.assertEqual(tab._draft["provider_configs"]["kokoro_gradio"]["voices"][0]["speed"], 1.01)


if __name__ == "__main__":
    unittest.main()
