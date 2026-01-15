"""Configuration management for Faceit Discord Rich Presence."""

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def get_app_root() -> Path:
    """Get the application root directory.

    Works both in development and when packaged with PyInstaller.
    """
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return Path(sys.executable).parent
    else:
        # Running as script
        return Path(__file__).parent.parent


class Config:
    """Manages application configuration from .env and config.json."""

    DEFAULT_SETTINGS = {
        "poll_interval": 45,  # seconds
        "enabled": True,

        # Match display settings
        "show_map": True,
        "show_score": True,
        "show_elo": True,  # ELO at stake per match
        "show_avg_elo": True,
        "show_kda": True,

        # Player statistics settings
        "show_current_elo": True,
        "show_country": True,
        "show_region_rank": True,
        "show_today_elo": True,
        "show_fpl": True,
    }

    def __init__(self):
        self._load_env()
        self._load_settings()

    def _load_env(self) -> None:
        """Load environment variables from .env file."""
        # Look for .env in app root (works for both dev and packaged)
        env_path = get_app_root() / ".env"
        load_dotenv(env_path)

        self.faceit_api_key = os.getenv("FACEIT_API_KEY", "")
        self.faceit_nickname = os.getenv("FACEIT_NICKNAME", "")
        self.discord_app_id = os.getenv("DISCORD_APP_ID", "")

    def _load_settings(self) -> None:
        """Load user settings from config.json."""
        self.config_path = get_app_root() / "config.json"

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

    def _get_env_path(self) -> Path:
        """Get the path to the .env file."""
        return get_app_root() / ".env"

    def update_env_value(self, key: str, value: str) -> tuple[bool, Optional[str]]:
        """Update a value in the .env file.

        Args:
            key: The environment variable key to update
            value: The new value to set

        Returns:
            Tuple of (success, error_message)
        """
        env_path = self._get_env_path()

        try:
            # Read existing content
            if env_path.exists():
                with open(env_path, "r", encoding="utf-8") as f:
                    content = f.read()
            else:
                content = ""

            # Check if key exists and update it
            pattern = rf'^{re.escape(key)}=.*$'
            if re.search(pattern, content, re.MULTILINE):
                # Update existing key
                content = re.sub(pattern, f'{key}={value}', content, flags=re.MULTILINE)
            else:
                # Add new key
                if content and not content.endswith('\n'):
                    content += '\n'
                content += f'{key}={value}\n'

            # Write back to file
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(content)

            # Update in-memory value
            if key == "FACEIT_NICKNAME":
                self.faceit_nickname = value
            elif key == "FACEIT_API_KEY":
                self.faceit_api_key = value
            elif key == "DISCORD_APP_ID":
                self.discord_app_id = value

            logger.info(f"Updated {key} in .env file")
            return True, None

        except IOError as e:
            error_msg = f"Failed to update .env file: {e}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Unexpected error updating .env: {e}"
            logger.error(error_msg)
            return False, error_msg

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
