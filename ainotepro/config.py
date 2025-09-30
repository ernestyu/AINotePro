# c:/Users/ernest/AppData/Roaming/Anki2/addons21/AINotePro/ainotepro/config.py

from aqt import mw
from typing import Any, Dict, MutableMapping

# __name__ will be 'ainotepro.config', so we get the parent package name
ADDON_PACKAGE_NAME = __name__.split('.')[0]

DEFAULTS = {
    "models": {
        "Open AI": {
            "base_url": "https://api.openai.com/v1",
            "api_key": ""
        },
        "DeepSeek": {
            "base_url": "https://api.deepseek.com",
            "api_key": ""
        },
        "Ollama": {
            "base_url": "http://localhost:11434",
            "api_key": ""
        }
    },
    "prompts": {
        "Default": "Translate the following text to English: {Source Field}"
    },
    "last_used_service": "Open AI",
    "last_used_prompt": "Default"
}

def load_config() -> MutableMapping[str, Any]:
    """Loads the add-on's configuration, providing defaults if keys are missing."""
    config = mw.addonManager.getConfig(ADDON_PACKAGE_NAME)
    if config is None:
        return DEFAULTS.copy()
    # In case new keys are added to DEFAULTS in an update
    return {**DEFAULTS, **config}

def save_config(config: Dict[str, Any]) -> None:
    """Saves the configuration."""
    mw.addonManager.writeConfig(ADDON_PACKAGE_NAME, config)