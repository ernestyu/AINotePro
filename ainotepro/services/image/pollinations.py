from __future__ import annotations

import io
import urllib.parse
import random
import time
import requests
from typing import Dict

from ..base import ImageProvider


class PollinationsImageProvider(ImageProvider):
    def generate(self, prompt: str, config: Dict) -> bytes:
        # random small jitter to avoid rate limiting bursts
        time.sleep(random.uniform(0.5, 2.0))

        encoded = urllib.parse.quote(prompt)
        # Use 1024 size by default; the caller may resize after saving
        url = (
            f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&seed=100&model=flux&nologo=true"
        )
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        return r.content

