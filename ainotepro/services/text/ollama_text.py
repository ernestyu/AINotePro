from __future__ import annotations

import json
import requests
from typing import Dict

from ..base import TextProvider


class OllamaTextProvider(TextProvider):
    def _base(self, config: Dict) -> str:
        return (config or {}).get("base_url", "http://localhost:11434").rstrip("/")

    def generate(self, prompt: str, config: Dict) -> str:
        # Prefer the chat-compatible streaming endpoint behavior but aggregate content
        url = f"{self._base(config)}/api/chat/completions"
        payload = {
            "model": (config or {}).get("model") or "llama3",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": (config or {}).get("temperature", 0.7),
            "stream": True,
            "chat_template_kwargs": {"enable_thinking": False},
        }

        collected: list[str] = []
        with requests.post(url, json=payload, timeout=120, stream=True) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except Exception:
                    continue
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    collected.append(content)

        text = "".join(collected).strip()
        # Basic cleanup for potential <think> tags
        return _remove_think(text)


def _remove_think(s: str) -> str:
    import re

    return re.sub(r"<think>.*?</think>", "", s, flags=re.DOTALL).strip()

