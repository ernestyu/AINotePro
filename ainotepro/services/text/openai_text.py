from __future__ import annotations

import json
import requests
from typing import Dict, List

from ..base import TextProvider


class OpenAITextProvider(TextProvider):
    def __init__(self, name: str = "openai") -> None:
        # name can be 'openai' or 'deepseek' (both OpenAI-compatible)
        self.name = name

    def _headers(self, config: Dict) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        api_key = (config or {}).get("api_key")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def _base(self, config: Dict) -> str:
        base = (config or {}).get("base_url", "").rstrip("/")
        # Ensure we do not double-append /v1 when user provided full path
        return base + ("" if base.endswith("/v1") else "/v1")

    def list_models(self, config: Dict) -> List[str]:
        try:
            url = f"{self._base(config)}/models"
            r = requests.get(url, headers=self._headers(config), timeout=8)
            r.raise_for_status()
            data = r.json()
            models = data.get("data", [])
            names = sorted([m.get("id", "") for m in models if m.get("id")])
            return names
        except Exception:
            return []

    def generate(self, prompt: str, config: Dict) -> str:
        body = {
            "model": (config or {}).get("model") or "gpt-4o-mini",
            "temperature": (config or {}).get("temperature", 0.7),
            "messages": [
                {"role": "user", "content": prompt},
            ],
            "stream": False,
        }

        url = f"{self._base(config)}/chat/completions"
        r = requests.post(url, json=body, headers=self._headers(config), timeout=60)
        r.raise_for_status()
        data = r.json()
        choices = data.get("choices", [])
        if not choices:
            raise ValueError("No choices returned from API")
        return (choices[0]["message"].get("content") or "").strip()

    def generate_with_image(self, image_url: str, prompt: str, config: Dict) -> str:
        body = {
            "model": (config or {}).get("model") or "gpt-4o-mini",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": image_url}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            "stream": False,
        }

        url = f"{self._base(config)}/chat/completions"
        r = requests.post(url, json=body, headers=self._headers(config), timeout=90)
        r.raise_for_status()
        data = r.json()
        choices = data.get("choices", [])
        if not choices:
            raise ValueError("No choices returned from API (vision)")
        return (choices[0]["message"].get("content") or "").strip()

