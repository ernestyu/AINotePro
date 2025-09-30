from __future__ import annotations

from typing import Any, Dict, MutableMapping
from aqt import mw
from .defaults import DEFAULTS


class ConfigManager:
    def __init__(self) -> None:
        # Anki uses the addon package name to map config
        self._addon_package = __name__.split('.')[0]

    def get_all(self) -> MutableMapping[str, Any]:
        cfg = mw.addonManager.getConfig(self._addon_package) or {}
        # merge shallowly with DEFAULTS top-level keys
        merged = {**DEFAULTS, **cfg}
        return merged

    def save_all(self, data: Dict[str, Any]) -> None:
        mw.addonManager.writeConfig(self._addon_package, data)

    # Convenience per-service helpers
    def get_provider_config(self, service_type: str, provider: str) -> Dict[str, Any]:
        cfg = self.get_all()
        st = cfg.get(service_type, {})
        return st.get(provider, {})

    def set_provider_config(self, service_type: str, provider: str, data: Dict[str, Any]) -> None:
        cfg = self.get_all()
        st = cfg.setdefault(service_type, {})
        st[provider] = data
        self.save_all(cfg)

