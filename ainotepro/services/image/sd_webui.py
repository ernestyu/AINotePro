from __future__ import annotations

from typing import Dict

from ..base import ImageProvider


class SDWebUIProvider(ImageProvider):
    def generate(self, prompt: str, config: Dict) -> bytes:
        # Placeholder: integrate with local Automatic1111 if desired.
        # For now, raise to indicate unsupported unless implemented by user.
        raise NotImplementedError("SD WebUI provider is not implemented yet.")

