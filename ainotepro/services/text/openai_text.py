from __future__ import annotations

import json
import os
import requests
from typing import Dict, List
from ..base import TextProvider, remove_think_tags, clean_html_output


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
        if base.endswith("/v1") or base.endswith("/v1beta/openai"):
            return base
        return base + "/v1"

    def _debug_enabled(self, config: Dict) -> bool:
        return bool((config or {}).get("debug_logging")) or os.environ.get("AINOTEPRO_DEBUG") == "1"

    def list_models(self, config: Dict) -> List[str]:
        try:
            url = f"{self._base(config)}/models"
            headers = self._headers(config)
            print(f"[AINotePro] GET {url}")
            r = requests.get(url, headers=headers, timeout=12)
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
        headers = self._headers(config)
        print(f"[AINotePro] POST {url} model={body.get('model')}")
        try:
            import json as _json
            metadata = {"model": body.get("model"), "temperature": body.get("temperature"), "stream": body.get("stream")}
            if self._debug_enabled(config):
                metadata["prompt_length"] = len(prompt or "")
            print("[AINotePro] body:", _json.dumps(metadata, ensure_ascii=False))
        except Exception:
            pass

        r = requests.post(url, json=body, headers=headers, timeout=60)
        r.raise_for_status()
        data = r.json()
        choices = data.get("choices", [])
        if not choices:
            raise ValueError("No choices returned from API")
        content = (choices[0].get("message", {}).get("content") or "").strip()
        # Safely extract content
        choices = (data or {}).get("choices", [])
        if not choices or not isinstance(choices, list): return ""
        message = choices[0].get("message", {})
        content = (message.get("content", "") or "").strip()
        print(f"[AINotePro] Response received: chars={len(content)}")
        return clean_html_output(remove_think_tags(content))

    def generate_with_image(self, image_url: str, prompt: str, config: Dict) -> str:
        body = {
            "model": (config or {}).get("model") or "gpt-4o-mini",
            "temperature": (config or {}).get("temperature", 0.7),
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ],
            "stream": False,
        }

        url = f"{self._base(config)}/chat/completions"
        headers = self._headers(config)
        print(f"[AINotePro] POST {url} (vision) model={body.get('model')}")
        try:
            import json as _json
            print("[AINotePro] body:", _json.dumps({"model": body.get("model"), "stream": body.get("stream"), "content_parts": len(body.get("messages", [{}])[0].get("content", []))}, ensure_ascii=False))
        except Exception:
            pass
        r = requests.post(url, json=body, headers=headers, timeout=90)
        try:
            r.raise_for_status()
        except Exception:
            print(f"[AINotePro] Vision request failed with HTTP {r.status_code}")
            raise RuntimeError(f"HTTP {r.status_code}") from None
        data = r.json()
        choices = data.get("choices", [])
        if not choices:
            raise ValueError("No choices returned from API (vision)")
        content = (choices[0].get("message", {}).get("content") or "").strip()
        # Safely extract content
        choices = (data or {}).get("choices", [])
        if not choices or not isinstance(choices, list): return ""
        message = choices[0].get("message", {})
        content = (message.get("content", "") or "").strip()
        print(f"[AINotePro] Vision response received: chars={len(content)}")
        return clean_html_output(remove_think_tags(content))
