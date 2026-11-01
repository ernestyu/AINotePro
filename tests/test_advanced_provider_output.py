import unittest
from unittest.mock import patch
import sys
import types

# The add-on bundles requests at runtime; the repository's lightweight unit
# environment deliberately does not install it.
if "requests" not in sys.modules:
    requests_stub = types.ModuleType("requests")
    requests_stub.post = lambda *_args, **_kwargs: None
    requests_stub.get = lambda *_args, **_kwargs: None
    sys.modules["requests"] = requests_stub

from ainotepro.services.text.ollama_text import OllamaTextProvider
from ainotepro.services.text.openai_text import OpenAITextProvider


class _Response:
    def raise_for_status(self):
        pass

    def json(self):
        return {"choices": [{"message": {"content": "```json\n{\"A\":\"ok\"}\n```"}}]}


class _OllamaResponse(_Response):
    def json(self):
        return {"message": {"content": "```json\n{\"A\":\"ok\"}\n```"}}


class AdvancedProviderOutputTests(unittest.TestCase):
    @patch("ainotepro.services.text.openai_text.requests.post", return_value=_Response())
    def test_openai_preserves_fence_newlines_only_when_requested(self, _post):
        provider = OpenAITextProvider()
        cfg = {"base_url": "https://example.test", "model": "x"}
        self.assertNotIn("\n", provider.generate("p", cfg))
        self.assertIn("\n", provider.generate("p", {**cfg, "preserve_output": True}))

    @patch("ainotepro.services.text.ollama_text.requests.post", return_value=_OllamaResponse())
    def test_ollama_preserves_fence_newlines_only_when_requested(self, _post):
        provider = OllamaTextProvider()
        cfg = {"base_url": "http://example.test", "model": "x"}
        self.assertNotIn("\n", provider.generate("p", cfg))
        self.assertIn("\n", provider.generate("p", {**cfg, "preserve_output": True}))


if __name__ == "__main__":
    unittest.main()
