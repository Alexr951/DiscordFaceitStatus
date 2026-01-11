"""Configuration management for Faceit Discord Rich Presence."""

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


class Config:
    """Manages application configuration from .env and config.json."""

    DEFAULT_SETTINGS = {
        "poll_interval": 45,  # seconds
        "show_elo": True,
        "show_avg_elo": True,
        "show_kda": True,
        "show_map": True,
        "enabled": True,
    }

    def __init__(self):
        self._load_env()
        self._load_settings()

    def _load_env(self) -> None:
        """Load environment variables from .env file."""
        # Look for .env in project root
        env_path = Path(__file__).parent.parent / ".env"
        load_dotenv(env_path)

        self.faceit_api_key = os.getenv("FACEIT_API_KEY", "")
        self.faceit_nickname = os.getenv("FACEIT_NICKNAME", "")
        self.discord_app_id = os.getenv("DISCORD_APP_ID", "")

    def _load_settings(self) -> None:
        """Load user settings from config.json."""
        self.config_path = Path(__file__).parent.parent / "config.json"

        if self.config_path.exists():
            try:
                with open(self.config_path, "r") as f:
                    self.settings = {**self.DEFAULT_SETTINGS, **json.load(f)}
            except (json.JSONDecodeError, IOError):
                self.settings = self.DEFAULT_SETTINGS.copy()
        else:
            self.settings = self.DEFAULT_SETTINGS.copy()
            self._save_settings()

    def _save_settings(self) -> None:
        """Save current settings to config.json."""
        try:
            with open(self.config_path, "w") as f:
                json.dump(self.settings, f, indent=2)
        except IOError as e:
            print(f"Failed to save settings: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        return self.settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a setting value and save."""
        self.settings[key] = value
        self._save_settings()

    def validate(self) -> tuple[bool, list[str]]:
        """Validate that required configuration is present.

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []

        if not self.faceit_api_key:
            errors.append("FACEIT_API_KEY is not set in .env")
        if not self.faceit_nickname:
            errors.append("FACEIT_NICKNAME is not set in .env")
        if not self.discord_app_id:
            errors.append("DISCORD_APP_ID is not set in .env")

        return len(errors) == 0, errors

    @property
    def poll_interval(self) -> int:
        """Get polling interval in seconds."""
        return self.get("poll_interval", 45)

    @property
    def is_enabled(self) -> bool:
        """Check if rich presence is enabled."""
        return self.get("enabled", True)

    @is_enabled.setter
    def is_enabled(self, value: bool) -> None:
        """Set enabled state."""
        self.set("enabled", value)


# Global config instance
config = Config()
