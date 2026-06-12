"""Configuration management for Faceit Discord Rich Presence."""

import json
import logging
import os
import sys
import threading
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

APP_NAME = "FaceitDiscordStatus"

# Embedded credentials: compiled into the executable so players need zero setup.
EMBEDDED_API_KEY = "d059caf3-bf65-44ee-8391-133a1c49f76b"
EMBEDDED_DISCORD_APP_ID = "1459995747989848238"


def get_app_root() -> Path:
    """Directory containing the exe (frozen) or the project root (dev)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent


def get_data_dir() -> Path:
    """Per-user writable data directory (%APPDATA%\\FaceitDiscordStatus)."""
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home()
    return base / APP_NAME


class Config:
    """User settings stored in config.json under the per-user data directory."""

    DEFAULT_SETTINGS = {
        "faceit_nickname": "",
        "poll_interval": 45,  # seconds between checks while not in a match
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

    def __init__(self, data_dir: Optional[Path] = None, legacy_dir: Optional[Path] = None):
        self._lock = threading.RLock()
        self.data_dir = data_dir or get_data_dir()
        self.config_path = self.data_dir / "config.json"
        self.faceit_api_key = EMBEDDED_API_KEY
        self.discord_app_id = EMBEDDED_DISCORD_APP_ID
        self.settings = self.DEFAULT_SETTINGS.copy()
        if not self.config_path.exists():
            self._migrate_legacy(legacy_dir or get_app_root())
        self._load()

    def _migrate_legacy(self, legacy_dir: Path) -> None:
        """One-time import from the pre-2.0 layout (.env + config.json next to the exe)."""
        migrated: dict[str, Any] = {}

        legacy_config = legacy_dir / "config.json"
        if legacy_config.exists():
            try:
                with open(legacy_config, "r", encoding="utf-8") as f:
                    data = json.load(f)
                migrated.update(
                    {k: v for k, v in data.items() if k in self.DEFAULT_SETTINGS}
                )
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Could not migrate legacy config.json: {e}")

        legacy_env = legacy_dir / ".env"
        if legacy_env.exists():
            try:
                for line in legacy_env.read_text(encoding="utf-8").splitlines():
                    if line.startswith("FACEIT_NICKNAME="):
                        nickname = line.split("=", 1)[1].strip()
                        if nickname:
                            migrated["faceit_nickname"] = nickname
            except OSError as e:
                logger.warning(f"Could not migrate legacy .env: {e}")

        if migrated:
            logger.info(f"Migrating legacy settings from {legacy_dir}")
            self.settings.update(migrated)
            self._save_settings()

    def _load(self) -> None:
        if not self.config_path.exists():
            return
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.settings = {**self.DEFAULT_SETTINGS, **json.load(f)}
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to load {self.config_path}: {e} - using defaults")
            self.settings = self.DEFAULT_SETTINGS.copy()

    def _save_settings(self) -> bool:
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            tmp_path = self.config_path.with_suffix(".json.tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2)
            tmp_path.replace(self.config_path)
            return True
        except OSError as e:
            logger.error(f"Failed to save settings: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self.settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self.settings[key] = value
            self._save_settings()

    def update(self, values: dict) -> None:
        """Set several settings with a single save."""
        with self._lock:
            self.settings.update(values)
            self._save_settings()

    @property
    def faceit_nickname(self) -> str:
        return self.get("faceit_nickname", "")

    @faceit_nickname.setter
    def faceit_nickname(self, value: str) -> None:
        self.set("faceit_nickname", value)

    @property
    def poll_interval(self) -> int:
        return self.get("poll_interval", 45)

    @property
    def is_enabled(self) -> bool:
        return self.get("enabled", True)

    @is_enabled.setter
    def is_enabled(self, value: bool) -> None:
        self.set("enabled", value)
