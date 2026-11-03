"""Offline contract tests for the simplified built-in Text providers."""
from __future__ import annotations

import copy
import ast
import io
import json
import tempfile
import unittest
import sys
import types
from contextlib import redirect_stdout
from pathlib import Path
from typing import Optional
from unittest.mock import patch

# The add-on bundles requests at runtime; isolated unit tests do not install it.
if "requests" not in sys.modules:
    requests_stub = types.ModuleType("requests")
    requests_stub.get = lambda *_args, **_kwargs: None
    requests_stub.post = lambda *_args, **_kwargs: None
    sys.modules["requests"] = requests_stub

from ainotepro.config import manager
from ainotepro.config.audio_profiles import migrate_audio
from ainotepro.provider_presets import PROVIDER_PRESETS
from ainotepro.services.provider_factory import OPENAI_COMPATIBLE_TEXT_PROVIDERS, create_provider
from ainotepro.services.text.ollama_text import OllamaTextProvider
from ainotepro.services.text.openai_text import OpenAITextProvider


class Response:
    status_code = 200

    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


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

    def raw(self):
        return json.loads(Path(manager.CONFIG_FILE).read_text(encoding="utf-8"))

    def test_fresh_config_has_only_13_builtin_providers(self):
        manager.ConfigManager()
        raw = self.raw()
        self.assertEqual(len(PROVIDER_PRESETS), 13)
        self.assertEqual(set(PROVIDER_PRESETS), set(raw["text"]).intersection(PROVIDER_PRESETS))
        for removed in ("together", "perplexity", "lmstudio", "localai", "custom_providers"):
            self.assertNotIn(removed, raw["text"])

    def test_cleanup_persists_once_and_keeps_other_values(self):
        defaults = manager._get_default_config()
        raw = {"text": {"provider": "custom:old", "together": {"api_key": "x"},
                        "perplexity": {}, "lmstudio": {}, "localai": {},
                        "custom_providers": {"old": {}}, "prompts": {"Keep": "unchanged"},
                        "deepseek": {"api_key": "keep", "model": "m"}},
               "audio": migrate_audio(defaults["audio"]), "ui": {"keep": True}}
        Path(manager.CONFIG_FILE).write_text(json.dumps(raw), encoding="utf-8")
        cfg = manager.ConfigManager()
        disk = self.raw()
        self.assertEqual(disk["text"]["provider"], "openai")
        self.assertEqual(cfg.get_all()["text"]["provider"], "openai")
        self.assertEqual(disk["text"]["deepseek"]["api_key"], "keep")
        self.assertEqual(disk["text"]["prompts"], {"Keep": "unchanged"})
        self.assertEqual(disk["ui"], {"keep": True})
        self.assertEqual(manager.ConfigManager()._raw_config, disk)
        for removed in ("together", "perplexity", "lmstudio", "localai", "custom_providers"):
            self.assertNotIn(removed, disk["text"])

    def test_cloud_refresh_keeps_independent_explicit_models_url(self):
        config = {"provider_key": "deepseek", "base_url": "https://chat.example",
                  "chat_endpoint": "https://chat.example/custom", "models_endpoint": "https://models.example/list"}
        with patch("ainotepro.services.text.openai_text.requests.get", return_value=Response({"data": []})) as get:
            self.assertEqual(OpenAITextProvider("deepseek").list_models(config), [])
        self.assertEqual(get.call_args.args[0], "https://models.example/list")

    def test_old_cloud_base_url_keeps_refresh_enabled_and_uses_legacy_models_route(self):
        source = (Path(__file__).resolve().parents[1] / "ainotepro/ui/text_tab.py").read_text(encoding="utf-8-sig")
        tree = ast.parse(source)
        tab = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "TextTab")
        methods = [next(node for node in tab.body if isinstance(node, ast.FunctionDef) and node.name == name)
                   for name in ("_apply_provider_capabilities", "_refresh_models")]
        warnings = []
        namespace = {"Optional": Optional, "REASONING_EFFORT_PROVIDERS": {"openai"},
                     "create_provider": create_provider, "showWarning": lambda message: warnings.append(message)}
        module = ast.Module(body=[ast.ClassDef(name="Tab", bases=[], keywords=[], body=methods,
                                                decorator_list=[])], type_ignores=[])
        exec(compile(ast.fix_missing_locations(module), "<text tab>", "exec"), namespace)

        class Field:
            def __init__(self): self.enabled = None
            def setEnabled(self, value): self.enabled = value
            def isEnabled(self): return bool(self.enabled)
            def setToolTip(self, _value): pass
            def setChecked(self, _value): pass
        class Model:
            def currentText(self): return "old"
            def clear(self): pass
            def addItems(self, _items): pass
            def findText(self, _text): return -1
            def setCurrentIndex(self, _index): pass
            def setEditText(self, _text): pass
        class Config:
            def get_provider_config(self, *_args): return {"base_url": "https://proxy.example/api"}
        class Tab(namespace["Tab"]):
            def __init__(self):
                self.cfg = Config(); self.reasoning_combo = Field(); self.refresh_button = Field(); self.image_checkbox = Field()
                self.model_combo = Model(); self.saved = 0
            def _service_map(self): return "deepseek"
            def _model_selection_changed(self): return True
            def _current_provider_config(self): return {"provider_key": "deepseek", "base_url": "https://proxy.example/api"}
            def _save_current_provider_config(self): self.saved += 1; return True

        instance = Tab()
        instance._apply_provider_capabilities("deepseek")
        self.assertTrue(instance.refresh_button.enabled)
        with patch("ainotepro.services.text.openai_text.requests.get", return_value=Response({"data": []})) as get:
            instance._refresh_models()
        self.assertEqual(get.call_args.args[0], "https://proxy.example/api/v1/models")
        self.assertNotIn("This provider has no Models Endpoint", warnings)

    def test_old_cloud_base_url_refresh_does_not_write_endpoint_fields(self):
        defaults = manager._get_default_config()
        raw = {"text": {"provider": "deepseek", "deepseek": {
                    "base_url": "https://proxy.example/api", "api_key": "keep", "model": "old", "temperature": 0.7}},
               "audio": migrate_audio(defaults["audio"])}
        Path(manager.CONFIG_FILE).write_text(json.dumps(raw), encoding="utf-8")
        config = manager.ConfigManager().get_provider_config("text", "deepseek")
        self.assertNotIn("models_endpoint", config)
        with patch("ainotepro.services.text.openai_text.requests.get", return_value=Response({"data": []})) as get:
            self.assertEqual(OpenAITextProvider("deepseek").list_models(config), [])
        self.assertEqual(get.call_args.args[0], "https://proxy.example/api/v1/models")
        saved = self.raw()["text"]["deepseek"]
        self.assertNotIn("chat_endpoint", saved)
        self.assertNotIn("models_endpoint", saved)

    def test_provider_busy_state_also_controls_main_restore_button(self):
        source = (Path(__file__).resolve().parents[1] / "ainotepro/ui/text_tab.py").read_text(encoding="utf-8-sig")
        tree = ast.parse(source)
        tab = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "TextTab")
        method = next(node for node in tab.body if isinstance(node, ast.FunctionDef)
                      and node.name == "_set_provider_controls_busy")
        module = ast.Module(body=[ast.ClassDef(name="Tab", bases=[], keywords=[], body=[method], decorator_list=[])],
                                type_ignores=[])
        namespace = {}
        exec(compile(ast.fix_missing_locations(module), "<busy controls>", "exec"), namespace)

        class Widget:
            def __init__(self): self.enabled = None
            def setEnabled(self, value): self.enabled = value
        class Window:
            def __init__(self): self.generate_button = Widget(); self.restore_llm_button = Widget()
        class Tab(namespace["Tab"]):
            def __init__(self):
                for name in ("service_combo", "base_url_edit", "api_key_edit", "model_combo", "temperature_edit",
                             "reasoning_combo", "refresh_button", "test_button"):
                    setattr(self, name, Widget())
                self.parent = Window(); self.capabilities = 0
            def window(self): return self.parent
            def _apply_provider_capabilities(self): self.capabilities += 1

        instance = Tab()
        instance._set_provider_controls_busy(True)
        self.assertFalse(instance.parent.restore_llm_button.enabled)
        instance._set_provider_controls_busy(False)
        self.assertTrue(instance.parent.restore_llm_button.enabled)
        self.assertEqual(instance.capabilities, 1)

    def test_local_llama_and_vllm_use_same_server_for_chat_and_refresh(self):
        for key in ("llama_cpp", "vllm"):
            config = {"provider_key": key, "chat_endpoint": "http://server-b:9000/v1/chat/completions",
                      "models_endpoint": "http://server-a:8000/v1/models", "model": "m"}
            provider = OpenAITextProvider(key)
            with patch("ainotepro.services.text.openai_text.requests.get", return_value=Response({"data": []})) as get:
                provider.list_models(config)
            with patch("ainotepro.services.text.openai_text.requests.post", return_value=Response({"choices": [{"message": {"content": "ok"}}]})) as post:
                provider.generate("p", config)
            self.assertEqual(get.call_args.args[0], "http://server-b:9000/v1/models")
            self.assertEqual(post.call_args.args[0], "http://server-b:9000/v1/chat/completions")

    def test_ollama_uses_native_routes_from_current_server(self):
        provider = OllamaTextProvider()
        config = {"base_url": "http://remote-ollama:11434", "model": "m"}
        with patch("ainotepro.services.text.ollama_text.requests.get", return_value=Response({"models": []})) as get:
            provider.list_models(config)
        with patch("ainotepro.services.text.ollama_text.requests.post", return_value=Response({"message": {"content": "ok"}})) as post:
            provider.generate("p", config)
        self.assertEqual(get.call_args.args[0], "http://remote-ollama:11434/api/tags")
        self.assertEqual(post.call_args.args[0], "http://remote-ollama:11434/api/chat")

    def test_restore_cloud_and_local_scope(self):
        cfg = manager.ConfigManager()
        cfg.set_provider_config("text", "deepseek", {"api_key": "keep", "chat_endpoint": "https://private/chat",
                                                        "models_endpoint": "https://private/models", "model": "old",
                                                        "temperature": 0.1, "reasoning_by_model": {"old": "high"}})
        cfg.set_provider_config("text", "openai", {"model": "untouched"})
        cfg.restore_provider_defaults("deepseek")
        raw = self.raw()["text"]
        self.assertEqual(raw["deepseek"]["api_key"], "keep")
        self.assertEqual(raw["deepseek"]["chat_endpoint"], PROVIDER_PRESETS["deepseek"][2])
        self.assertEqual(raw["deepseek"]["models_endpoint"], PROVIDER_PRESETS["deepseek"][3])
        self.assertEqual(raw["deepseek"]["temperature"], 0.7)
        self.assertNotIn("reasoning_by_model", raw["deepseek"])
        self.assertEqual(raw["openai"]["model"], "untouched")
        cfg.set_provider_config("text", "anthropic", {"models_endpoint": "https://private/models"})
        cfg.restore_provider_defaults("anthropic")
        self.assertEqual(self.raw()["text"]["anthropic"]["models_endpoint"], "")
        cfg.set_provider_config("text", "vllm", {"base_url": "http://server-b:9000", "api_key": "local-key",
                                                    "model": "old", "temperature": 0.1, "reasoning_by_model": {"old": "high"}})
        cfg.restore_provider_defaults("vllm")
        vllm = self.raw()["text"]["vllm"]
        self.assertEqual(vllm["base_url"], "http://server-b:9000")
        self.assertEqual(vllm["api_key"], "local-key")
        self.assertEqual(vllm["temperature"], 0.7)
        self.assertNotIn("reasoning_by_model", vllm)

    def test_factory_has_no_removed_or_custom_routes(self):
        self.assertFalse({"together", "perplexity", "lmstudio", "localai"} & OPENAI_COMPATIBLE_TEXT_PROVIDERS)
        for name in ("together", "perplexity", "lmstudio", "localai", "custom:one"):
            with self.assertRaises(ValueError):
                create_provider("text", name, {})

    def test_success_logs_redact_query_but_request_keeps_it(self):
        url = "https://api.example/v1/chat/completions?api_key=SECRET&x=1"
        config = {"provider_key": "openai", "chat_endpoint": url, "model": "m", "debug_logging": True}
        out = io.StringIO()
        with redirect_stdout(out), patch("ainotepro.services.text.openai_text.requests.post",
                                         return_value=Response({"choices": [{"message": {"content": "ok"}}],
                                                                "usage": {"prompt_tokens": 2, "completion_tokens": 3}})) as post:
            self.assertEqual(OpenAITextProvider().generate("prompt", config), "ok")
        self.assertEqual(post.call_args.args[0], url)
        self.assertNotIn("SECRET", out.getvalue())
        self.assertIn("input_tokens=2", out.getvalue())
        self.assertIn("response-processed", out.getvalue())

    def test_failure_logs_redact_query_for_openai_and_ollama(self):
        secret_url = "https://api.example/chat?token=SECRET"
        out = io.StringIO()
        with redirect_stdout(out), patch("ainotepro.services.text.openai_text.requests.post",
                                         side_effect=RuntimeError(secret_url)) as post:
            with self.assertRaisesRegex(RuntimeError, "LLM request failed"):
                OpenAITextProvider().generate("p", {"provider_key": "openai", "chat_endpoint": secret_url, "model": "m"})
        self.assertEqual(post.call_args.args[0], secret_url)
        self.assertNotIn("SECRET", out.getvalue())
        out = io.StringIO()
        with redirect_stdout(out), patch("ainotepro.services.text.ollama_text.requests.post",
                                         side_effect=RuntimeError("http://host/api/chat?key=SECRET")):
            with self.assertRaisesRegex(RuntimeError, "LLM request failed"):
                OllamaTextProvider().generate("p", {"base_url": "http://host?key=SECRET", "model": "m"})
        self.assertNotIn("SECRET", out.getvalue())


if __name__ == "__main__":
    unittest.main()
