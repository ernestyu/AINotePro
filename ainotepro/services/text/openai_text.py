from __future__ import annotations

from typing import Dict, List

import requests

from ...core.endpoint_urls import (
    legacy_chat_endpoint, local_chat_endpoint,
    models_endpoint_from_chat, normalize_local_server_address,
)
from ...provider_presets import NO_MODELS_ENDPOINT_PROVIDERS

from ..base import TextProvider, clean_html_output, remove_think_tags
from ._diagnostics import (request_failed, request_finished, request_http_returned,
                           request_started, safe_failure, safe_url)


class OpenAITextProvider(TextProvider):
    def __init__(self, name: str = "openai") -> None:
        self.name = name

    def _headers(self, config: Dict) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if api_key := (config or {}).get("api_key"):
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    @staticmethod
    def _local_server(config: Dict) -> str:
        """Normalize a local server root, including historical full routes."""
        raw = (config or {}).get("chat_endpoint") or (config or {}).get("base_url") or ""
        return normalize_local_server_address(raw)

    def _chat_endpoint(self, config: Dict) -> str:
        if (config or {}).get("provider_key") in {"llama_cpp", "vllm"}:
            return local_chat_endpoint(self._local_server(config))
        if "chat_endpoint" in (config or {}):
            return (config or {}).get("chat_endpoint", "").strip()
        return legacy_chat_endpoint((config or {}).get("base_url", ""))

    def _models_endpoint(self, config: Dict) -> str:
        provider_key = (config or {}).get("provider_key") or self.name
        if provider_key in NO_MODELS_ENDPOINT_PROVIDERS:
            return ""
        return models_endpoint_from_chat(self._chat_endpoint(config))

    def list_models(self, config: Dict) -> List[str]:
        url = self._models_endpoint(config)
        if not url:
            raise ValueError("Cannot safely derive Models from this Chat Endpoint; enter the model manually.")
        try:
            response = requests.get(url, headers=self._headers(config), timeout=12)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            print(f"[AINotePro] Models refresh failed url={safe_url(url)} error={safe_failure(exc)}")
            raise RuntimeError("Models refresh failed; see terminal diagnostics.") from None
        if not isinstance(data, dict) or not isinstance(data.get("data"), list):
            raise ValueError("Models endpoint returned an incompatible response")
        return sorted(m.get("id", "") for m in data["data"] if isinstance(m, dict) and m.get("id"))

    @staticmethod
    def _apply_reasoning(body: Dict, config: Dict) -> None:
        choices = (config or {}).get("reasoning_by_model") or {}
        mode = choices.get(body.get("model", ""), "default") if isinstance(choices, dict) else "default"
        # OpenAI-compatible endpoints (including a DeepSeek preset pointed at
        # NInfer) receive the user's explicit override. Unsupported servers
        # must report their own request error rather than silently dropping it.
        effort = {"off": "none", "low": "low", "medium": "medium", "high": "high"}.get(mode)
        if effort is not None:
            body["reasoning_effort"] = effort

    def _request(self, body: Dict, config: Dict, *, vision: bool = False) -> str:
        url = self._chat_endpoint(config)
        model = body["model"]
        started, debug = request_started(self.name, model, "POST", url, config, body)
        response = None
        try:
            response = requests.post(url, json=body, headers=self._headers(config), timeout=90 if vision else 60)
            http_elapsed = request_http_returned(started, response, debug)
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices", []) if isinstance(data, dict) else []
            if not choices or not isinstance(choices, list):
                raise ValueError("No choices returned from API")
            content = (choices[0].get("message", {}).get("content") or "").strip()
            request_finished(self.name, model, url, response, started, http_elapsed, content, data, debug)
            cleaned = remove_think_tags(content)
            return cleaned if (config or {}).get("preserve_output") else clean_html_output(cleaned)
        except Exception as exc:
            raise request_failed(self.name, model, url, started, exc, debug, response) from None

    def generate(self, prompt: str, config: Dict) -> str:
        body = {"model": (config or {}).get("model") or "gpt-4o-mini",
                "temperature": (config or {}).get("temperature", 0.7),
                "messages": [{"role": "user", "content": prompt}], "stream": False}
        self._apply_reasoning(body, config)
        return self._request(body, config)

    def generate_with_image(self, image_url: str, prompt: str, config: Dict) -> str:
        body = {"model": (config or {}).get("model") or "gpt-4o-mini",
                "temperature": (config or {}).get("temperature", 0.7),
                "messages": [{"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ]}], "stream": False}
        self._apply_reasoning(body, config)
        return self._request(body, config, vision=True)
