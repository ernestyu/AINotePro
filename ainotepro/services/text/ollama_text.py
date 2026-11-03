from __future__ import annotations

from typing import Dict

import requests

from ..base import TextProvider, clean_html_output, remove_think_tags
from ._diagnostics import (request_failed, request_finished, request_http_returned,
                           request_started, safe_failure, safe_url)


class OllamaTextProvider(TextProvider):
    def _base(self, config: Dict) -> str:
        raw = (config or {}).get("base_url", "http://localhost:11434").rstrip("/")
        for suffix in ("/api/chat", "/api/tags"):
            if raw.endswith(suffix):
                return raw[:-len(suffix)].rstrip("/")
        return raw

    def _request(self, url: str, body: Dict, config: Dict) -> str:
        model = body["model"]
        started, debug = request_started("ollama", model, "POST", url, config)
        response = None
        try:
            response = requests.post(url, json=body, timeout=int((config or {}).get("timeout", 300)))
            http_elapsed = request_http_returned(started, response, debug)
            response.raise_for_status()
            data = response.json() or {}
            content = ((data.get("message") or {}).get("content") or "").strip()
            request_finished("ollama", model, url, response, started, http_elapsed, content, data, debug)
            cleaned = remove_think_tags(content)
            return cleaned if (config or {}).get("preserve_output") else clean_html_output(cleaned)
        except Exception as exc:
            raise request_failed("ollama", model, url, started, exc, debug, response) from None

    def generate(self, prompt: str, config: Dict) -> str:
        body = {"model": (config or {}).get("model") or "llama3",
                "messages": [{"role": "user", "content": prompt}], "stream": False,
                "options": {"temperature": (config or {}).get("temperature", 0.7)}}
        return self._request(f"{self._base(config)}/api/chat", body, config)

    def list_models(self, config: Dict) -> list[str]:
        url = f"{self._base(config)}/api/tags"
        try:
            response = requests.get(url, timeout=int((config or {}).get("timeout", 30)))
            response.raise_for_status()
            data = response.json() or {}
        except Exception as exc:
            print(f"[AINotePro] Models refresh failed url={safe_url(url)} error={safe_failure(exc)}")
            raise RuntimeError("Models refresh failed; see terminal diagnostics.") from None
        models = data.get("models") if isinstance(data, dict) else None
        if not isinstance(models, list):
            raise ValueError("Ollama models endpoint returned an incompatible response")
        return sorted({m.get("name") or m.get("model") for m in models
                       if isinstance(m, dict) and (m.get("name") or m.get("model"))})

    def generate_with_image(self, image_url: str, prompt: str, config: Dict) -> str:
        base = self._base(config)
        if image_url.startswith("data:image/") and ";base64," in image_url:
            body = {"model": (config or {}).get("model") or "llava",
                    "messages": [{"role": "user", "content": prompt,
                                  "images": [image_url.split(";base64,", 1)[1]]}],
                    "stream": False, "options": {"temperature": (config or {}).get("temperature", 0.7)}}
            return self._request(f"{base}/api/chat", body, config)

        # Keep the historical OpenAI-compatible vision fallback for servers
        # that advertise Ollama but only accept that payload format.
        url = base + "/v1/chat/completions"
        body = {"model": (config or {}).get("model") or "llava",
                "messages": [{"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ]}], "stream": False, "temperature": (config or {}).get("temperature", 0.7)}
        model = body["model"]
        started, debug = request_started("ollama", model, "POST", url, config)
        response = None
        try:
            response = requests.post(url, json=body, timeout=int((config or {}).get("timeout", 300)))
            http_elapsed = request_http_returned(started, response, debug)
            response.raise_for_status()
            data = response.json() or {}
            content = (data.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
            request_finished("ollama", model, url, response, started, http_elapsed, content, data, debug)
            return clean_html_output(remove_think_tags(content))
        except Exception as exc:
            raise request_failed("ollama", model, url, started, exc, debug, response) from None
