"""Tests for the Start-with-Windows registry helper (winreg mocked)."""

import sys
from unittest import mock

from src import autostart


def test_not_supported_when_not_frozen():
    # Tests never run frozen, so this must be False in dev mode.
    assert autostart.is_supported() is False


def test_enable_refuses_in_dev_mode():
    assert autostart.enable() is False


def test_is_enabled_checks_registry_value():
    with mock.patch("winreg.OpenKey") as open_key, \
         mock.patch("winreg.QueryValueEx") as query:
        open_key.return_value.__enter__.return_value = "key"
        query.return_value = ('"C:\\app.exe"', 1)
        assert autostart.is_enabled() is True

        query.side_effect = FileNotFoundError
        assert autostart.is_enabled() is False


def test_enable_writes_exe_path_when_frozen():
    with mock.patch.object(sys, "frozen", True, create=True), \
         mock.patch.object(sys, "executable", "C:\\app\\FaceitDiscordStatus.exe"), \
         mock.patch("winreg.OpenKey") as open_key, \
         mock.patch("winreg.SetValueEx") as set_value:
        open_key.return_value.__enter__.return_value = "key"
        assert autostart.enable() is True
        args = set_value.call_args[0]
        assert args[1] == "FaceitDiscordStatus"
        assert args[4] == '"C:\\app\\FaceitDiscordStatus.exe"'
