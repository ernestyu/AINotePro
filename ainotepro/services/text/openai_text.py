from __future__ import annotations

import json
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
        return base + ("" if base.endswith("/v1") else "/v1")

    def list_models(self, config: Dict) -> List[str]:
        try:
            url = f"{self._base(config)}/models"
            headers = self._headers(config)
            safe_key = (config or {}).get("api_key")
            if safe_key:
                safe_key = safe_key[:6] + "…" + safe_key[-4:]
            print(f"[AINotePro] GET {url}")
            print(f"[AINotePro] headers: Authorization: Bearer {safe_key or '(none)'}")
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
        safe_key = (config or {}).get("api_key")
        if safe_key:
            safe_key = safe_key[:6] + "…" + safe_key[-4:]
        print(f"[AINotePro] POST {url}")
        print(f"[AINotePro] headers: Authorization: Bearer {safe_key or '(none)'}")
        try:
            import json as _json
            # Log a preview of the message content for better debugging
            content_preview = ""
            if body.get("messages"):
                content_preview = (body["messages"][0].get("content", "") or "")
                content_preview = (content_preview[:200] + "...") if len(content_preview) > 200 else content_preview
            print("[AINotePro] body:", _json.dumps({"model": body.get("model"), "temperature": body.get("temperature"), "stream": body.get("stream"), "content_preview": content_preview}, ensure_ascii=False))
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
        print(f"[AINotePro] Response content: {(content[:400] + '...') if len(content) > 400 else content}")
        return clean_html_output(remove_think_tags(content))

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
        headers = self._headers(config)
        print(f"[AINotePro] POST {url} (vision)")
        try:
            import json as _json
            print("[AINotePro] body:", _json.dumps({"model": body.get("model"), "stream": body.get("stream"), "content_parts": len(body.get("messages", [{}])[0].get("content", []))}, ensure_ascii=False))
        except Exception:
            pass
        r = requests.post(url, json=body, headers=headers, timeout=90)
        r.raise_for_status()
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
        print(f"[AINotePro] Response content (vision): {(content[:400] + '...') if len(content) > 400 else content}")
        return clean_html_output(remove_think_tags(content))
