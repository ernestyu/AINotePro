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

    # Optional: batch generation; default falls back to sequential calls
    def generate_batch(self, inputs: list[str], config: Dict) -> list[str]:
        results: list[str] = []
        for s in inputs:
            try:
                results.append(self.generate(s, config))
            except Exception as e:
                results.append(f"[Error] {e}")
        return results


class ImageProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, config: Dict) -> bytes:
        raise NotImplementedError


class AudioProvider(ABC):
    @abstractmethod
    def generate(self, text: str, config: Dict) -> bytes:
        raise NotImplementedError

