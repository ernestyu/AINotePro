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

    def _chat_endpoint(self, config: Dict) -> str:
        """Use an explicit complete endpoint when the user selected one.

        Falling back to _base is intentional: it is the historical route for
        provider objects that only contain base_url.
        """
        if "chat_endpoint" in (config or {}):
            return (config or {}).get("chat_endpoint", "").strip()
        return f"{self._base(config)}/chat/completions"

    def _models_endpoint(self, config: Dict) -> str:
        if "models_endpoint" in (config or {}):
            return (config or {}).get("models_endpoint", "").strip()
        return f"{self._base(config)}/models"

    def _debug_enabled(self, config: Dict) -> bool:
        return bool((config or {}).get("debug_logging")) or os.environ.get("AINOTEPRO_DEBUG") == "1"

    def list_models(self, config: Dict) -> List[str]:
        url = self._models_endpoint(config)
        if not url:
            raise ValueError("This provider has no Models Endpoint; enter the model manually.")
        headers = self._headers(config)
        print(f"[AINotePro] GET {url}")
        r = requests.get(url, headers=headers, timeout=12)
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, dict) or not isinstance(data.get("data"), list):
            raise ValueError("Models endpoint returned an incompatible response")
        return sorted([m.get("id", "") for m in data["data"] if isinstance(m, dict) and m.get("id")])

    @staticmethod
    def _apply_reasoning(body: Dict, config: Dict) -> None:
        """Map a user's per-model preference to llama.cpp/OpenAI-compatible effort.

        Unsupported endpoints may reject an explicit effort; never silently
        remove the field or claim the backend applied it.
        """
        model = body.get("model", "")
        choices = (config or {}).get("reasoning_by_model") or {}
        mode = choices.get(model, "default") if isinstance(choices, dict) else "default"
        from ...provider_presets import REASONING_EFFORT_PROVIDERS
        effort = {"off": "none", "low": "low", "medium": "medium", "high": "xhigh"}.get(mode)
        if effort is not None and (config or {}).get("provider_key", "") in REASONING_EFFORT_PROVIDERS:
            body["reasoning_effort"] = effort

    def generate(self, prompt: str, config: Dict) -> str:
        body = {
            "model": (config or {}).get("model") or "gpt-4o-mini",
            "temperature": (config or {}).get("temperature", 0.7),
            "messages": [
                {"role": "user", "content": prompt},
            ],
            "stream": False,
        }

        self._apply_reasoning(body, config)
        url = self._chat_endpoint(config)
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
        cleaned = remove_think_tags(content)
        # Advanced uses a strict JSON protocol where line breaks are meaningful
        # for the only accepted fenced-response form.
        return cleaned if (config or {}).get("preserve_output") else clean_html_output(cleaned)

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

        self._apply_reasoning(body, config)
        url = self._chat_endpoint(config)
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
