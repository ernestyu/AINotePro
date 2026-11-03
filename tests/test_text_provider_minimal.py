"""Offline contract tests for the simplified built-in Text providers."""
from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
import sys
import types
from contextlib import redirect_stdout
from pathlib import Path
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
