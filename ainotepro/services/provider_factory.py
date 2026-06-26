from __future__ import annotations

from typing import Any, Dict


OPENAI_COMPATIBLE_TEXT_PROVIDERS = {
    "openai",
    "deepseek",
    "openrouter",
    "dashscope",
    "moonshot",
    "zhipu",
    "siliconflow",
    "groq",
    "together",
    "perplexity",
    "gemini",
    "lmstudio",
    "localai",
}


def create_provider(service_type: str, provider_name: str, config: Dict[str, Any]):
    service_type = service_type.lower()
    provider_name = provider_name.lower()

    if service_type == "text":
        if provider_name in OPENAI_COMPATIBLE_TEXT_PROVIDERS:
            from .text.openai_text import OpenAITextProvider
            return OpenAITextProvider(provider_name)
        if provider_name == "ollama":
            from .text.ollama_text import OllamaTextProvider
            return OllamaTextProvider()
    elif service_type == "image":
        raise ValueError("Image generation providers are not available in this build")
    elif service_type == "audio":
        if provider_name in ("edge_tts", "edge-tts"):
            from .audio.edge_tts import EdgeTTSProvider
            return EdgeTTSProvider()

    raise ValueError(f"Unknown provider: {service_type}:{provider_name}")
