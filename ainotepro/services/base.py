from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict


class TextProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, config: Dict) -> str:
        raise NotImplementedError

    # Optional: used by UI to fetch model list when supported
    def list_models(self, config: Dict) -> list[str]:  # noqa: D401
        """Return available model IDs if supported; otherwise empty list."""
        return []

    # Optional: image-assisted text generation (vision)
    def generate_with_image(self, image_url: str, prompt: str, config: Dict) -> str:
        raise NotImplementedError("Provider does not support vision input")


class ImageProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, config: Dict) -> bytes:
        raise NotImplementedError


class AudioProvider(ABC):
    @abstractmethod
    def generate(self, text: str, config: Dict) -> bytes:
        raise NotImplementedError

