"""Start-with-Windows toggle via the HKCU Run registry key."""

import logging
import sys

logger = logging.getLogger(__name__)

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "FaceitDiscordStatus"


def is_supported() -> bool:
    """Auto-start is only offered for the packaged exe on Windows."""
    return sys.platform == "win32" and bool(getattr(sys, "frozen", False))


def is_enabled() -> bool:
    if sys.platform != "win32":
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.QueryValueEx(key, _VALUE_NAME)
        return True
    except OSError:
        return False


def enable() -> bool:
    if not is_supported():
        return False
    import winreg
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, _VALUE_NAME, 0, winreg.REG_SZ, f'"{sys.executable}"')
        logger.info("Auto-start enabled")
        return True
    except OSError as e:
        logger.error(f"Failed to enable auto-start: {e}")
        return False


def disable() -> bool:
    if sys.platform != "win32":
        return False
    import winreg
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, _VALUE_NAME)
        logger.info("Auto-start disabled")
        return True
    except FileNotFoundError:
        return True
    except OSError as e:
        logger.error(f"Failed to disable auto-start: {e}")
        return False
