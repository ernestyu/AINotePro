from __future__ import annotations

from typing import Any, Dict


def create_provider(service_type: str, provider_name: str, config: Dict[str, Any]):
    service_type = service_type.lower()
    provider_name = provider_name.lower()

    if service_type == "text":
        if provider_name in ("openai", "deepseek"):
            from .text.openai_text import OpenAITextProvider
            return OpenAITextProvider(provider_name)
        if provider_name == "ollama":
            from .text.ollama_text import OllamaTextProvider
            return OllamaTextProvider()
    elif service_type == "image":
        if provider_name == "pollinations":
            from .image.pollinations import PollinationsImageProvider
            return PollinationsImageProvider()
        if provider_name == "dalle":
            from .image.dall_e import DalleImageProvider
            return DalleImageProvider()
        if provider_name in ("sd", "sd_webui"):
            from .image.sd_webui import SDWebUIProvider
            return SDWebUIProvider()
    elif service_type == "audio":
        if provider_name in ("edge_tts", "edge-tts"):
            from .audio.edge_tts import EdgeTTSProvider
            return EdgeTTSProvider()

    raise ValueError(f"Unknown provider: {service_type}:{provider_name}")

