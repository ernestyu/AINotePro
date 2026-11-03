"""Small, declarative Text provider defaults used by the existing UI/config path."""
from __future__ import annotations

# A models endpoint is deliberately omitted when the vendor does not document a
# compatible enumeration endpoint.  Users may still enter one themselves.
PROVIDER_PRESETS = {
    "openai": ("OpenAI", "cloud", "https://api.openai.com/v1/chat/completions", "https://api.openai.com/v1/models", "gpt-4o-mini"),
    "anthropic": ("Anthropic (Claude)", "cloud", "https://api.anthropic.com/v1/chat/completions", "", "claude-sonnet-4-5"),
    "deepseek": ("DeepSeek", "cloud", "https://api.deepseek.com/chat/completions", "https://api.deepseek.com/models", "deepseek-chat"),
    "openrouter": ("OpenRouter", "cloud", "https://openrouter.ai/api/v1/chat/completions", "https://openrouter.ai/api/v1/models", "openai/gpt-4o-mini"),
    "dashscope": ("DashScope (Qwen)", "cloud", "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions", "https://dashscope.aliyuncs.com/compatible-mode/v1/models", "qwen-plus"),
    "moonshot": ("Moonshot (Kimi)", "cloud", "https://api.moonshot.cn/v1/chat/completions", "https://api.moonshot.cn/v1/models", "moonshot-v1-8k"),
    "zhipu": ("Zhipu GLM", "cloud", "https://open.bigmodel.cn/api/paas/v4/chat/completions", "", "glm-4-flash"),
    "siliconflow": ("SiliconFlow", "cloud", "https://api.siliconflow.cn/v1/chat/completions", "https://api.siliconflow.cn/v1/models", "Qwen/Qwen2.5-7B-Instruct"),
    "groq": ("Groq", "cloud", "https://api.groq.com/openai/v1/chat/completions", "https://api.groq.com/openai/v1/models", "llama-3.1-8b-instant"),
    "gemini": ("Google Gemini", "cloud", "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", "https://generativelanguage.googleapis.com/v1beta/openai/models", "gemini-2.0-flash"),
    "llama_cpp": ("llama.cpp", "local", "http://127.0.0.1:8080/v1/chat/completions", "http://127.0.0.1:8080/v1/models", ""),
    "vllm": ("vLLM", "local", "http://127.0.0.1:8000/v1/chat/completions", "http://127.0.0.1:8000/v1/models", ""),
    "ollama": ("Ollama", "local", "http://127.0.0.1:11434", "", "llama3"),
}

# Only the established OpenAI-style endpoints and explicitly opted-in local
# servers receive the existing reasoning_effort field.
REASONING_EFFORT_PROVIDERS = {"openai", "gemini", "llama_cpp", "vllm"}


def default_provider_config(key: str):
    label, _group, chat, models, model = PROVIDER_PRESETS[key]
    if key == "ollama":
        return {"base_url": chat, "api_key": "ollama", "model": model, "temperature": 0.7}
    return {"base_url": chat.rsplit("/v1/chat/completions", 1)[0] if "/v1/chat/completions" in chat else chat.rsplit("/chat/completions", 1)[0],
            "chat_endpoint": chat, "models_endpoint": models, "api_key": "", "model": model,
            "temperature": 0.7}
