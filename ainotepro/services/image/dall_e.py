from __future__ import annotations

from typing import Dict
import base64
import requests

from ..base import ImageProvider


class DalleImageProvider(ImageProvider):
    def _headers(self, config: Dict) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        api_key = (config or {}).get("api_key")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def _base(self, config: Dict) -> str:
        base = (config or {}).get("base_url", "").rstrip("/")
        return base + ("" if base.endswith("/v1") else "/v1")

    def generate(self, prompt: str, config: Dict) -> bytes:
        # Use OpenAI images API (base64 output)
        url = f"{self._base(config)}/images/generations"
        body = {"model": (config or {}).get("model", "dall-e-3"), "prompt": prompt, "size": "1024x1024"}
        r = requests.post(url, json=body, headers=self._headers(config), timeout=90)
        r.raise_for_status()
        data = r.json()
        arr = data.get("data") or []
        if not arr:
            raise ValueError("No image data returned")
        b64 = arr[0].get("b64_json")
        if not b64:
            # Some endpoints return URL; fallback to download
            url = arr[0].get("url")
            if not url:
                raise ValueError("No image returned")
            img = requests.get(url, timeout=60)
            img.raise_for_status()
            return img.content
        return base64.b64decode(b64)

