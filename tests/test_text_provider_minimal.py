"""Offline coverage for the minimal Text provider endpoint contract."""
from __future__ import annotations

import copy
import ast
import json
import tempfile
import unittest
import sys
import types
from typing import Any, Dict, Optional
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

    def test_legacy_models_refresh_uses_base_url_without_persisting_endpoint(self):
        defaults = manager._get_default_config()
        raw = {"text": {"provider": "deepseek", "deepseek": {
                    "base_url": "https://proxy.example/api", "api_key": "old", "model": "old", "temperature": 0.7}},
               "audio": migrate_audio(defaults["audio"])}
        Path(manager.CONFIG_FILE).write_text(json.dumps(raw), encoding="utf-8")
        config = manager.ConfigManager().get_provider_config("text", "deepseek")
        with patch("ainotepro.services.text.openai_text.requests.get", return_value=_Response({"data": []})) as get:
            self.assertEqual(OpenAITextProvider("deepseek").list_models(config), [])
        self.assertEqual(get.call_args.args[0], "https://proxy.example/api/v1/models")
        saved = json.loads(Path(manager.CONFIG_FILE).read_text())["text"]["deepseek"]
        self.assertNotIn("models_endpoint", saved)

    def test_explicit_blank_models_endpoint_does_not_fall_back_to_legacy_path(self):
        config = manager.ConfigManager().get_provider_config("text", "anthropic")
        self.assertIn("models_endpoint", config)
        self.assertEqual(config["models_endpoint"], "")
        with self.assertRaisesRegex(ValueError, "no Models Endpoint"):
            OpenAITextProvider("anthropic").list_models(config)

    def test_previous_provider_identity_controls_switch_save_shape(self):
        source = (Path(__file__).resolve().parents[1] / "ainotepro/ui/text_tab.py").read_text(encoding="utf-8-sig")
        tree = ast.parse(source)
        tab = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "TextTab")
        current = next(node for node in tab.body if isinstance(node, ast.FunctionDef) and node.name == "_current_provider_config")
        namespace = {"Optional": Optional, "Dict": Dict, "Any": Any}
        module = ast.Module(body=[ast.ClassDef(name="Current", bases=[], keywords=[], body=[current], decorator_list=[])], type_ignores=[])
        exec(compile(ast.fix_missing_locations(module), "<current provider config>", "exec"), namespace)

        class Text:
            def __init__(self, value): self.value = value
            def text(self): return self.value
            def currentText(self): return self.value
            def currentData(self): return "default"

        class Tab(namespace["Current"]):
            def _service_map(self): return "ollama"  # combo has already changed
            def _temperature_value(self): return 0.7

        tab = Tab()
        tab.model_combo = Text("old-model")
        tab.reasoning_combo = Text("default")
        tab.api_key_edit = Text("old-key")
        tab.base_url_edit = Text("https://proxy.example/api/v1/chat/completions")
        tab.models_endpoint_edit = Text("https://proxy.example/api/v1/models")
        tab._reasoning_by_model = {}
        tab._legacy_base_url = "https://proxy.example/api"
        tab._stored_chat_endpoint = tab._stored_models_endpoint = ""
        tab._shown_chat_endpoint = "https://proxy.example/api/v1/chat/completions"
        tab._shown_models_endpoint = "https://proxy.example/api/v1/models"
        tab._has_explicit_models_endpoint = False
        saved = tab._current_provider_config("deepseek")
        self.assertEqual(saved["provider_key"], "deepseek")
        self.assertEqual(saved["base_url"], "https://proxy.example/api")
        self.assertNotIn("chat_endpoint", saved)
        self.assertNotIn("models_endpoint", saved)

    def test_custom_dirty_comparison_uses_previous_custom_identity(self):
        source = (Path(__file__).resolve().parents[1] / "ainotepro/ui/text_tab.py").read_text(encoding="utf-8-sig")
        tree = ast.parse(source)
        tab_node = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "TextTab")
        methods = [next(node for node in tab_node.body if isinstance(node, ast.FunctionDef) and node.name == name)
                   for name in ("_current_provider_config", "_custom_unsaved")]
        namespace = {"Optional": Optional, "Dict": Dict, "Any": Any}
        module = ast.Module(body=[ast.ClassDef(name="CustomState", bases=[], keywords=[], body=methods, decorator_list=[])], type_ignores=[])
        exec(compile(ast.fix_missing_locations(module), "<custom state>", "exec"), namespace)

        class Text:
            def __init__(self, value): self.value = value
            def text(self): return self.value
            def currentText(self): return self.value
            def currentData(self): return "default"
        class Config:
            def get_provider_config(self, _service, key):
                self.last_key = key
                return {"chat_endpoint": "http://custom.test/chat", "models_endpoint": "",
                        "api_key": "k", "model": "m", "temperature": 0.7,
                        "reasoning_by_model": {"m": "default"}}
        class Tab(namespace["CustomState"]):
            def _service_map(self): return "openai"  # combo now points at the new provider
            def _temperature_value(self): return 0.7

        tab = Tab()
        tab.model_combo = Text("m"); tab.reasoning_combo = Text("default"); tab.api_key_edit = Text("k")
        tab.base_url_edit = Text("http://custom.test/chat"); tab.models_endpoint_edit = Text("")
        tab._reasoning_by_model = {}; tab._legacy_base_url = ""; tab._stored_chat_endpoint = "http://custom.test/chat"
        tab._shown_chat_endpoint = "http://custom.test/chat"; tab._shown_models_endpoint = ""
        tab._has_explicit_models_endpoint = True; tab._custom_is_new = False
        tab.cfg = Config()
        self.assertFalse(tab._custom_unsaved("custom:one"))
        self.assertEqual(tab.cfg.last_key, "custom:one")

    def test_switch_save_does_not_rebuild_combo_back_to_old_custom(self):
        source = (Path(__file__).resolve().parents[1] / "ainotepro/ui/text_tab.py").read_text(encoding="utf-8-sig")
        tree = ast.parse(source)
        tab_node = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "TextTab")
        method = next(node for node in tab_node.body if isinstance(node, ast.FunctionDef) and node.name == "_save_custom_provider")
        namespace = {"Optional": Optional}
        module = ast.Module(body=[ast.ClassDef(name="CustomSave", bases=[], keywords=[], body=[method], decorator_list=[])], type_ignores=[])
        exec(compile(ast.fix_missing_locations(module), "<custom save>", "exec"), namespace)

        class Config:
            def get_custom_providers(self): return {"one": {"name": "Home"}}
            def save_custom_provider(self, custom_id, config): self.saved = (custom_id, config)
        class Tab(namespace["CustomSave"]):
            def _current_provider_config(self, _key):
                return {"chat_endpoint": "http://custom.test/chat", "models_endpoint": "", "api_key": "k",
                        "model": "m", "temperature": 0.7, "reasoning_by_model": {}, "provider_key": _key}
            def _valid_endpoint(self, *_args, **_kwargs): return True
            def _rebuild_provider_combo(self, _selected): self.rebuilds += 1

        tab = Tab()
        tab.cfg = Config(); tab._custom_is_new = False; tab._custom_draft_name = ""
        tab._stored_chat_endpoint = tab._stored_models_endpoint = ""; tab._shown_chat_endpoint = tab._shown_models_endpoint = ""
        tab.rebuilds = 0
        self.assertTrue(tab._save_custom_provider("custom:one", rebuild_combo=False))
        self.assertEqual(tab.rebuilds, 0)
        self.assertEqual(tab.cfg.saved[0], "one")

    def test_custom_close_save_discard_cancel_have_explicit_results(self):
        source = (Path(__file__).resolve().parents[1] / "ainotepro/ui/text_tab.py").read_text(encoding="utf-8-sig")
        tree = ast.parse(source)
        tab_node = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "TextTab")
        method = next(node for node in tab_node.body if isinstance(node, ast.FunctionDef) and node.name == "_confirm_leave_custom")

        class Buttons:
            Save, Discard, Cancel = 1, 2, 4
        class Box:
            StandardButton = Buttons
            answer = Buttons.Cancel
            @classmethod
            def question(cls, *_args, **_kwargs): return cls.answer
        namespace = {"QMessageBox": Box}
        module = ast.Module(body=[ast.ClassDef(name="Close", bases=[], keywords=[], body=[method], decorator_list=[])], type_ignores=[])
        exec(compile(ast.fix_missing_locations(module), "<custom close>", "exec"), namespace)

        class Tab(namespace["Close"]):
            def __init__(self, save=True):
                self._active_provider = "custom:one"; self._custom_is_new = False; self.save = save; self.reloads = 0
            def _custom_unsaved(self, _provider): return True
            def _save_custom_provider(self, _provider): return self.save
            def _populate_provider_cfg(self): self.reloads += 1

        Box.answer = Buttons.Save
        self.assertFalse(Tab(save=False)._confirm_leave_custom())
        self.assertTrue(Tab(save=True)._confirm_leave_custom())
        Box.answer = Buttons.Discard
        tab = Tab(); self.assertTrue(tab._confirm_leave_custom()); self.assertEqual(tab.reloads, 1)
        Box.answer = Buttons.Cancel
        self.assertFalse(Tab()._confirm_leave_custom())

    def test_provider_controls_reapply_capabilities_after_busy_finishes(self):
        source = (Path(__file__).resolve().parents[1] / "ainotepro/ui/text_tab.py").read_text(encoding="utf-8-sig")
        tree = ast.parse(source)
        tab_node = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "TextTab")
        method = next(node for node in tab_node.body if isinstance(node, ast.FunctionDef) and node.name == "_set_provider_controls_busy")
        namespace = {}
        module = ast.Module(body=[ast.ClassDef(name="Busy", bases=[], keywords=[], body=[method], decorator_list=[])], type_ignores=[])
        exec(compile(ast.fix_missing_locations(module), "<busy>", "exec"), namespace)

        class Widget:
            def __init__(self): self.enabled = None
            def setEnabled(self, value): self.enabled = value
            def isEnabled(self): return bool(self.enabled)
            def text(self): return ""
        class Tab(namespace["Busy"]):
            def __init__(self):
                for name in ("service_combo", "base_url_edit", "models_endpoint_edit", "api_key_edit", "model_combo",
                             "temperature_edit", "reasoning_combo", "refresh_button", "test_button", "custom_new_button",
                             "custom_save_button", "custom_rename_button", "custom_delete_button", "custom_cancel_button",
                             "restore_endpoints_button"):
                    setattr(self, name, Widget())
                self.capability_calls = 0
            def window(self): return object()
            def _apply_provider_capabilities(self): self.capability_calls += 1

        tab = Tab()
        tab._set_provider_controls_busy(True)
        self.assertEqual(tab.capability_calls, 0)
        tab._set_provider_controls_busy(False)
        self.assertEqual(tab.capability_calls, 1)

    def test_new_custom_cancel_restores_the_provider_that_started_the_draft(self):
        source = (Path(__file__).resolve().parents[1] / "ainotepro/ui/text_tab.py").read_text(encoding="utf-8-sig")
        tree = ast.parse(source)
        tab_node = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "TextTab")
        method = next(node for node in tab_node.body if isinstance(node, ast.FunctionDef) and node.name == "_cancel_custom_provider")
        namespace = {}
        module = ast.Module(body=[ast.ClassDef(name="Cancel", bases=[], keywords=[], body=[method], decorator_list=[])], type_ignores=[])
        exec(compile(ast.fix_missing_locations(module), "<cancel custom>", "exec"), namespace)

        class Config:
            def get_all(self): return {"text": {"provider": "openai"}}
        class Tab(namespace["Cancel"]):
            def __init__(self, previous):
                self._custom_is_new = True; self._custom_draft_id = "draft"; self._custom_draft_name = "Draft"
                self._custom_draft_previous_provider = previous; self._active_provider = "custom:draft"; self.cfg = Config()
                self.rebuilt = []; self.loads = 0
            def _rebuild_provider_combo(self, selected): self.rebuilt.append(selected)
            def _populate_provider_cfg(self): self.loads += 1

        for previous in ("deepseek", "together", "custom:two"):
            tab = Tab(previous)
            tab._cancel_custom_provider()
            self.assertEqual(tab.rebuilt, [previous])
            self.assertEqual(tab.loads, 1)
            self.assertIsNone(tab._active_provider)

    def test_models_endpoint_edit_immediately_controls_refresh(self):
        source = (Path(__file__).resolve().parents[1] / "ainotepro/ui/text_tab.py").read_text(encoding="utf-8-sig")
        tree = ast.parse(source)
        tab_node = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "TextTab")
        method = next(node for node in tab_node.body if isinstance(node, ast.FunctionDef) and node.name == "_apply_provider_capabilities")

        class Field:
            def __init__(self, text=""):
                self.value = text; self.enabled = None; self.visible = None
            def text(self): return self.value
            def setEnabled(self, value): self.enabled = value
            def isEnabled(self): return bool(self.enabled)
            def setPlaceholderText(self, _value): pass
            def setToolTip(self, _value): pass
            def setVisible(self, value): self.visible = value
            def setChecked(self, _value): pass
        namespace = {"Optional": Optional, "PROVIDER_PRESETS": {"anthropic": (), "ollama": ()}}
        module = ast.Module(body=[ast.ClassDef(name="Capabilities", bases=[], keywords=[], body=[method], decorator_list=[])], type_ignores=[])
        exec(compile(ast.fix_missing_locations(module), "<provider capabilities>", "exec"), namespace)

        class Tab(namespace["Capabilities"]):
            def __init__(self, models_url):
                self.models_endpoint_edit = Field(models_url); self.reasoning_combo = Field(); self.refresh_button = Field()
                self.restore_endpoints_button = Field(); self.image_checkbox = Field()
            def _service_map(self): return "anthropic"
            def _valid_endpoint(self, value, *, required): return bool(value) and value.startswith("https://")

        tab = Tab("")
        tab._apply_provider_capabilities("anthropic")
        self.assertFalse(tab.refresh_button.enabled)
        tab.models_endpoint_edit.value = "https://models.example.test/v1/models"
        tab._apply_provider_capabilities("anthropic")
        self.assertTrue(tab.refresh_button.enabled)
        tab.models_endpoint_edit.value = ""
        tab._apply_provider_capabilities("anthropic")
        self.assertFalse(tab.refresh_button.enabled)
        tab._apply_provider_capabilities("ollama")
        self.assertTrue(tab.refresh_button.enabled)

    def test_custom_providers_are_independent_and_do_not_replace_text_config(self):
        cfg = manager.ConfigManager()
        cfg.save_custom_provider("one", {"name": "Home", "chat_endpoint": "http://a/chat",
                                           "models_endpoint": "", "api_key": "a", "model": "m1", "temperature": 0.1})
        cfg.save_custom_provider("two", {"name": "School", "chat_endpoint": "http://b/chat",
                                           "models_endpoint": "http://b/models", "api_key": "b", "model": "m2", "temperature": 0.2})
        self.assertEqual(cfg.get_provider_config("text", "custom:one")["api_key"], "a")
        self.assertEqual(cfg.get_provider_config("text", "custom:two")["chat_endpoint"], "http://b/chat")
        cfg.set_active_provider("text", "custom:two")
        self.assertEqual(json.loads(Path(manager.CONFIG_FILE).read_text())["text"]["provider"], "custom:two")
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
