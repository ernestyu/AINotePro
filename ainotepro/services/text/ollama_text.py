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
            first_msg = body.get("messages", [{}])[0].get("content", "")
            preview = (first_msg[:200] + "…") if len(first_msg) > 200 else first_msg
            print("[AINotePro] body:", _json.dumps({
                "model": body.get("model"),
                "messages": len(body.get("messages", [])),
                "stream": body.get("stream"),
                "content_preview": preview,
            }, ensure_ascii=False))
        except Exception:
            pass

        timeout = int((config or {}).get("timeout", 300))
        r = requests.post(url, json=body, timeout=timeout)
        r.raise_for_status()
        data = r.json() or {}
        msg = (data.get("message") or {}).get("content", "")
        return _remove_think((msg or "").strip())

    def list_models(self, config: Dict) -> list[str]:
        # Ollama tags endpoint
        url = f"{self._base(config)}/api/tags"
        print(f"[AINotePro] GET {url}")
        try:
            r = requests.get(url, timeout=int((config or {}).get("timeout", 30)))
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

    def generate_batch(self, inputs: list[str], config: Dict) -> list[str]:
        # Ollama does not provide a true multi-input batch endpoint that returns
        # an array mapped to inputs. Perform sequential generation here, but make
        # sure to apply the instruction (Prompt Preview) by replacing {Source Field}
        # for each input. This is now handled by the caller (GenerationWorker)
        # which prepares the final prompt for each item.
        total = len(inputs)
        print(f"[AINotePro][Batch] Ollama: sequential per-item, items={total}")
        results: list[str] = []
        for i, s in enumerate(inputs, 1):
            try:
                # The 's' here is expected to be the fully-formed prompt.
                results.append(self.generate(s, config))
            except Exception as e:
                results.append(f"[Error] {e}")
        return results

    def generate_with_image(self, image_url: str, prompt: str, config: Dict) -> str:
        # Use OpenAI-compatible vision format, as it's more widely supported by models
        # and Ollama's own server. The image_url is already a data URI.
        # The endpoint should be the OpenAI-compatible one.
        base = self._base(config)
        # Some users might have /v1 in their base URL, some might not.
        # Some might use /api. We'll try to be smart.
        if "/api" in base:
            # If they are using the native endpoint, switch to the compatible one for vision
            url = base.replace("/api", "") + "/v1/chat/completions"
        elif not base.endswith("/v1"):
            url = base + "/v1/chat/completions"
        else:
            url = base + "/chat/completions"
            
        body = {
            "model": (config or {}).get("model") or "llava",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url # Pass the full data URI
                            }
                        }
                    ]
                }
            ],
            "stream": False,
            "temperature": (config or {}).get("temperature", 0.7),
        }
        print(f"[AINotePro] POST {url} (vision)")
        try:
            import json as _json
            print("[AINotePro] body:", _json.dumps({"model": body.get("model"), "stream": body.get("stream"), "content_parts": len(body.get("messages", [{}])[0].get("content", []))}, ensure_ascii=False))
        except Exception:
            pass
        
        r = requests.post(url, json=body, timeout=int((config or {}).get("timeout", 300)))
        r.raise_for_status()
        data = r.json() or {}
        return (data.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()


def _remove_think(s: str) -> str:
    import re

    return re.sub(r"<think>.*?</think>", "", s, flags=re.DOTALL).strip()
