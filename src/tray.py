"""System tray icon and menu."""

import logging
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Callable, Optional, TYPE_CHECKING

from PIL import Image
import pystray
from pystray import Menu, MenuItem

from . import autostart

if TYPE_CHECKING:
    from .config import Config

logger = logging.getLogger(__name__)


class SystemTray:
    """Manages the system tray icon, menu, and toast notifications."""

    def __init__(
        self,
        config: "Config",
        on_toggle: Optional[Callable[[bool], None]] = None,
        get_match_url: Optional[Callable[[], Optional[str]]] = None,
        open_settings: Optional[Callable[[], None]] = None,
    ):
        self.config = config
        self.on_toggle = on_toggle
        self.get_match_url = get_match_url
        self.open_settings = open_settings

        self._status = "Starting..."
        self._icon: Optional[pystray.Icon] = None
        self._exit_event = threading.Event()

    def _create_icon_image(self) -> Image.Image:
        """Load the tray icon (bundled in _MEIPASS when frozen)."""
        if getattr(sys, "frozen", False):
            base_path = Path(sys._MEIPASS)
        else:
            base_path = Path(__file__).parent.parent

        icon_path = base_path / "assets" / "tray_icon.png"
        if icon_path.exists():
            try:
                img = Image.open(icon_path)
                if img.mode != "RGBA":
                    img = img.convert("RGBA")
                return img.resize((64, 64), Image.Resampling.LANCZOS)
            except Exception as e:
                logger.warning(f"Failed to load icon: {e}")

        # Fallback: plain orange square (Faceit color)
        return Image.new("RGB", (64, 64), color=(255, 85, 0))

    def _create_menu(self) -> Menu:
        items = [
            MenuItem(lambda text: f"Status: {self._status}", None, enabled=False),
            MenuItem(
                lambda text: f"Tracking: {self.config.faceit_nickname or 'not set'}",
                None,
                enabled=False,
            ),
            Menu.SEPARATOR,
            MenuItem(
                "Show match status in Discord",
                self._toggle_presence,
                checked=lambda item: self.config.is_enabled,
            ),
            MenuItem("View Current Match", self._open_match),
            Menu.SEPARATOR,
            MenuItem("Settings...", self._open_settings),
        ]
        if autostart.is_supported():
            items.append(
                MenuItem(
                    "Start with Windows",
                    self._toggle_autostart,
                    checked=lambda item: autostart.is_enabled(),
                )
            )
        items += [Menu.SEPARATOR, MenuItem("Exit", self._exit)]
        return Menu(*items)

    def _toggle_presence(self, icon: pystray.Icon, item: MenuItem) -> None:
        new_state = not self.config.is_enabled
        if self.on_toggle:
            self.on_toggle(new_state)
        icon.update_menu()
        logger.info(f"Rich presence {'enabled' if new_state else 'disabled'}")

    def _toggle_autostart(self, icon: pystray.Icon, item: MenuItem) -> None:
        if autostart.is_enabled():
            autostart.disable()
        else:
            autostart.enable()
        icon.update_menu()

    def _open_settings(self, icon: pystray.Icon, item: MenuItem) -> None:
        if self.open_settings:
            self.open_settings()

    def _open_match(self, icon: pystray.Icon, item: MenuItem) -> None:
        if self.get_match_url:
            url = self.get_match_url()
            if url:
                webbrowser.open(url)
                logger.info(f"Opened match URL: {url}")
            else:
                self.notify("No active match", "You're not in a match right now.")

    def _exit(self, icon: pystray.Icon, item: MenuItem) -> None:
        logger.info("Exit requested from tray")
        icon.stop()
        self._exit_event.set()

    def update_status(self, status: str) -> None:
        """Update the status line shown in the tray menu."""
        self._status = status
        if self._icon:
            self._icon.update_menu()

    def notify(self, title: str, message: str) -> None:
        """Show a Windows toast notification from the tray icon."""
        if self._icon:
            try:
                self._icon.notify(message, title)
            except Exception as e:
                logger.debug(f"Toast notification failed: {e}")

    def run_detached(self) -> None:
        """Run the tray icon on its own thread.

        The main thread must NOT host the Win32 message loop: while blocked
        in it, Ctrl+C handlers only fire when the menu wakes the loop. The
        main thread waits in wait_for_exit() instead, which Ctrl+C can
        interrupt immediately.
        """
        self._icon = pystray.Icon(
            "Faceit Discord Status",
            self._create_icon_image(),
            "Faceit Discord Status",
            self._create_menu(),
        )
        self._icon.run_detached()

    def wait_for_exit(self) -> None:
        """Block the calling thread until Exit is chosen (Ctrl+C friendly)."""
        while not self._exit_event.is_set():
            time.sleep(0.2)

    def stop(self) -> None:
        self._exit_event.set()
        if self._icon:
            self._icon.stop()
