from __future__ import annotations

import json
import requests
from typing import Dict
from ..base import TextProvider, remove_think_tags, clean_html_output


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
        content = (msg or "").strip()
        print(f"[AINotePro] Response content: {(content[:400] + '...') if len(content) > 400 else content}")
        return clean_html_output(remove_think_tags(content))

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

    def generate_with_image(self, image_url: str, prompt: str, config: Dict) -> str:
        base = self._base(config)
        if image_url.startswith("data:image/") and ";base64," in image_url:
            image_b64 = image_url.split(";base64,", 1)[1]
            url = f"{base}/api/chat"
            body = {
                "model": (config or {}).get("model") or "llava",
                "messages": [{"role": "user", "content": prompt, "images": [image_b64]}],
                "stream": False,
                "options": {"temperature": (config or {}).get("temperature", 0.7)},
            }
            print(f"[AINotePro] POST {url} (ollama vision)")
            r = requests.post(url, json=body, timeout=int((config or {}).get("timeout", 300)))
            try:
                r.raise_for_status()
            except Exception:
                error_text = r.text[:1000]
                print(f"[AINotePro] Ollama vision request failed with HTTP {r.status_code}: {error_text}")
                raise RuntimeError(f"HTTP {r.status_code}: {error_text}") from None
            data = r.json() or {}
            content = ((data.get("message") or {}).get("content") or "").strip()
            print(f"[AINotePro] Response content (vision): {(content[:400] + '...') if len(content) > 400 else content}")
            return clean_html_output(remove_think_tags(content))

        if "/api" in base:
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
        try:
            r.raise_for_status()
        except Exception:
            error_text = r.text[:1000]
            print(f"[AINotePro] OpenAI-compatible Ollama vision request failed with HTTP {r.status_code}: {error_text}")
            raise RuntimeError(f"HTTP {r.status_code}: {error_text}") from None
        data = r.json() or {}
        content = (data.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
        print(f"[AINotePro] Response content (vision): {(content[:400] + '...') if len(content) > 400 else content}")
        return clean_html_output(remove_think_tags(content))
