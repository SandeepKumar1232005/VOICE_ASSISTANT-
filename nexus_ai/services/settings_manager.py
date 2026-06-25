"""
Nexus AI — Settings Manager

Centralized service for managing user settings, preferences, and configurations.
Handles dynamic updates to the settings.json file.
"""

import os
from typing import Any, Dict, Optional

from nexus_ai.utils.logger import get_logger
from nexus_ai.utils.helpers import load_json_config, save_json_config

logger = get_logger("Settings")


class SettingsManager:
    """
    Settings Manager — Handles global configuration state.
    """

    def __init__(self):
        self._settings_cache = load_json_config("settings.json")
        logger.info("SettingsManager initialized.")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting by key."""
        return self._settings_cache.get(key, default)

    def get_all(self) -> Dict[str, Any]:
        """Get all settings."""
        return self._settings_cache.copy()

    def set(self, key: str, value: Any) -> bool:
        """Update a setting and save to disk."""
        self._settings_cache[key] = value
        
        try:
            save_json_config("settings.json", self._settings_cache)
            logger.info(f"Setting updated: {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to save setting {key}: {e}")
            return False

    def update(self, new_settings: Dict[str, Any]) -> bool:
        """Update multiple settings at once."""
        self._settings_cache.update(new_settings)
        
        try:
            save_json_config("settings.json", self._settings_cache)
            logger.info(f"Updated {len(new_settings)} settings in batch.")
            return True
        except Exception as e:
            logger.error(f"Failed to save batch settings: {e}")
            return False
