from __future__ import annotations

import re
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


def remove_think_tags(s: str) -> str:
    """Removes <think>...</think> blocks from a string."""
    return re.sub(r"<think>.*?</think>", "", s, flags=re.DOTALL).strip()


def clean_html_output(s: str) -> str:
    """
    Cleans the HTML output from the AI.
    - Removes newline characters. Backslashes are preserved for LaTeX.
    """
    if not s:
        return ""

    # 仅移除换行符，保留所有反斜杠以确保 LaTeX 公式和命令的正确性。
    s = s.replace("\n", "")
    return s
