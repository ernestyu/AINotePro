"""Small, declarative Text provider defaults used by the existing UI/config path."""
from __future__ import annotations

# Each provider has one Chat Endpoint (or native Ollama server address).
# Models routes are derived from it, never stored as separate addresses.
PROVIDER_PRESETS = {
    "openai": ("OpenAI", "cloud", "https://api.openai.com/v1/chat/completions", "gpt-4o-mini"),
    "anthropic": ("Anthropic (Claude)", "cloud", "https://api.anthropic.com/v1/chat/completions", "claude-sonnet-4-5"),
    "deepseek": ("DeepSeek", "cloud", "https://api.deepseek.com/chat/completions", "deepseek-chat"),
    "openrouter": ("OpenRouter", "cloud", "https://openrouter.ai/api/v1/chat/completions", "openai/gpt-4o-mini"),
    "dashscope": ("DashScope (Qwen)", "cloud", "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions", "qwen-plus"),
    "moonshot": ("Moonshot (Kimi)", "cloud", "https://api.moonshot.cn/v1/chat/completions", "moonshot-v1-8k"),
    "zhipu": ("Zhipu GLM", "cloud", "https://open.bigmodel.cn/api/paas/v4/chat/completions", "glm-4-flash"),
    "siliconflow": ("SiliconFlow", "cloud", "https://api.siliconflow.cn/v1/chat/completions", "Qwen/Qwen2.5-7B-Instruct"),
    "groq": ("Groq", "cloud", "https://api.groq.com/openai/v1/chat/completions", "llama-3.1-8b-instant"),
    "gemini": ("Google Gemini", "cloud", "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", "gemini-2.0-flash"),
    "llama_cpp": ("llama.cpp", "local", "http://127.0.0.1:8080/v1/chat/completions", ""),
    "vllm": ("vLLM", "local", "http://127.0.0.1:8000/v1/chat/completions", ""),
    "ollama": ("Ollama", "local", "http://127.0.0.1:11434", "llama3"),
}

# These presets do not document an OpenAI-compatible /models route.
# Their model IDs remain manually editable.
NO_MODELS_ENDPOINT_PROVIDERS = frozenset({"anthropic", "zhipu"})


def default_provider_config(key: str):
    label, _group, chat, model = PROVIDER_PRESETS[key]
    if key == "ollama":
        return {"base_url": chat, "api_key": "ollama", "model": model, "temperature": 0.7}
    return {"base_url": chat.rsplit("/v1/chat/completions", 1)[0] if "/v1/chat/completions" in chat else chat.rsplit("/chat/completions", 1)[0],
            "chat_endpoint": chat, "api_key": "", "model": model,
            "temperature": 0.7}
