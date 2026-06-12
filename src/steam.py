"""Detect the locally logged-in Steam account (Windows).

Faceit accounts are hard-linked to a Steam ID, so the Steam account that is
logged in on this PC identifies the player's real Faceit account. Steam exposes
the active login in the registry; when Steam isn't running we fall back to the
most recent login recorded in loginusers.vdf.
"""

import logging
import re
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# SteamID64 = this base + the 32-bit account ID
STEAM64_BASE = 76561197960265728


def parse_loginusers(text: str) -> Optional[str]:
    """Return the Steam64 ID marked "MostRecent" in a loginusers.vdf body."""
    for match in re.finditer(r'"(7656\d{13})"\s*\{(.*?)\}', text, re.DOTALL):
        steam64, body = match.groups()
        if re.search(r'"MostRecent"\s*"1"', body):
            return steam64
    return None


def get_logged_in_steam64() -> Optional[str]:
    """Steam64 ID of the currently (or most recently) logged-in Steam user."""
    if sys.platform != "win32":
        return None
    account_id = _active_user_from_registry()
    if account_id:
        return str(STEAM64_BASE + account_id)
    return _most_recent_login()


def _active_user_from_registry() -> Optional[int]:
    """Account ID of the user logged into the running Steam client (0 = none)."""
    import winreg
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam\ActiveProcess"
        ) as key:
            value, _ = winreg.QueryValueEx(key, "ActiveUser")
        return int(value) or None
    except OSError:
        return None


def _steam_path() -> Optional[Path]:
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            value, _ = winreg.QueryValueEx(key, "SteamPath")
        return Path(value)
    except OSError:
        return None


def _most_recent_login() -> Optional[str]:
    path = _steam_path()
    if not path:
        return None
    vdf = path / "config" / "loginusers.vdf"
    try:
        return parse_loginusers(vdf.read_text(encoding="utf-8", errors="replace"))
    except OSError as e:
        logger.debug(f"Could not read loginusers.vdf: {e}")
        return None
