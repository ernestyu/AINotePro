DEFAULTS = {
    "text": {
        "provider": "openai",
        "debug_logging": False,
        "allow_remote_image_urls": False,
        "openai": {
            "base_url": "https://api.openai.com",
            "api_key": "",
            "model": "gpt-4o-mini",
            "temperature": 0.7,
        },
        "deepseek": {
            "base_url": "https://api.deepseek.com",
            "api_key": "",
            "model": "deepseek-chat",
            "temperature": 0.7,
        },
        "ollama": {
            "base_url": "http://localhost:11434",
            "api_key": "ollama",
            "model": "llama3",
            "temperature": 0.7,
        },
        "prompts": {
            "Default": "Translate the following text to English: {Source Field}"
        },
        "last_used_prompt": "Default",
    },
    "audio": {
        "provider": "edge_tts",
        "edge_tts": {
            "voice": "en-US-AriaNeural",
            "speed": 0,
            "volume": 0,
            "pitch": 0,
        },
    },
    "ui": {
        "last_service_tab": "text"
    },
}
