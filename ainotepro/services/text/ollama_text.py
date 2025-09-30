from __future__ import annotations

import json
import requests
from typing import Dict

from ..base import TextProvider


class OllamaTextProvider(TextProvider):
    def _base(self, config: Dict) -> str:
        return (config or {}).get("base_url", "http://localhost:11434").rstrip("/")

    def generate(self, prompt: str, config: Dict) -> str:
        # Use Ollama's native /api/chat endpoint (non-stream) and parse message.content
        url = f"{self._base(config)}/api/chat"
        body = {
            "model": (config or {}).get("model") or "llama3",
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": (config or {}).get("temperature", 0.7)},
        }
        print(f"[AINotePro] POST {url}")
        try:
            import json as _json
            print("[AINotePro] body:", _json.dumps({"model": body.get("model"), "messages": len(body.get("messages", [])), "stream": body.get("stream")}, ensure_ascii=False))
        except Exception:
            pass

        r = requests.post(url, json=body, timeout=120)
        r.raise_for_status()
        data = r.json() or {}
        msg = (data.get("message") or {}).get("content", "")
        return _remove_think((msg or "").strip())

    def list_models(self, config: Dict) -> list[str]:
        # Ollama tags endpoint
        url = f"{self._base(config)}/api/tags"
        print(f"[AINotePro] GET {url}")
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            data = r.json() or {}
            models = data.get("models", [])
            names = []
            for m in models:
                # Support either 'name' or 'model' key variations
                n = m.get("name") or m.get("model") or ""
                if n:
                    names.append(n)
            names = sorted(set(names))
            return names
        except Exception:
            return []


def _remove_think(s: str) -> str:
    import re

    return re.sub(r"<think>.*?</think>", "", s, flags=re.DOTALL).strip()

