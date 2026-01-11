"""System tray integration for the application."""

import logging
import threading
import webbrowser
from pathlib import Path
from typing import Callable, Optional

from PIL import Image
import pystray
from pystray import MenuItem, Menu

logger = logging.getLogger(__name__)


class SystemTray:
    """Manages the system tray icon and menu."""

    def __init__(
        self,
        on_toggle: Optional[Callable[[bool], None]] = None,
        on_exit: Optional[Callable[[], None]] = None,
        get_match_url: Optional[Callable[[], Optional[str]]] = None,
    ):
        """Initialize system tray.

        Args:
            on_toggle: Callback when presence is toggled (receives new state)
            on_exit: Callback when exit is clicked
            get_match_url: Callback to get current match URL
        """
        self.on_toggle = on_toggle
        self.on_exit = on_exit
        self.get_match_url = get_match_url

        self._enabled = True
        self._status = "Starting..."
        self._icon: Optional[pystray.Icon] = None
        self._thread: Optional[threading.Thread] = None

    def _create_icon_image(self) -> Image.Image:
        """Create or load the tray icon image.

        Returns:
            PIL Image for the tray icon
        """
        # Try to load custom icon
        icon_path = Path(__file__).parent.parent / "assets" / "icon.ico"

        if icon_path.exists():
            try:
                return Image.open(icon_path)
            except Exception as e:
                logger.warning(f"Failed to load icon: {e}")

        # Create a simple orange square as fallback (Faceit color)
        img = Image.new("RGB", (64, 64), color=(255, 85, 0))
        return img

    def _create_menu(self) -> Menu:
        """Create the tray menu.

        Returns:
            pystray Menu object
        """
        return Menu(
            MenuItem(
                lambda text: f"Status: {self._status}",
                None,
                enabled=False,
            ),
            Menu.SEPARATOR,
            MenuItem(
                lambda text: "Disable Rich Presence" if self._enabled else "Enable Rich Presence",
                self._toggle_presence,
            ),
            MenuItem(
                "View Current Match",
                self._open_match,
                enabled=lambda item: self.get_match_url is not None,
            ),
            Menu.SEPARATOR,
            MenuItem("Exit", self._exit),
        )

    def _toggle_presence(self, icon: pystray.Icon, item: MenuItem) -> None:
        """Toggle rich presence on/off."""
        self._enabled = not self._enabled

        if self.on_toggle:
            self.on_toggle(self._enabled)

        # Update menu
        icon.update_menu()

        logger.info(f"Rich presence {'enabled' if self._enabled else 'disabled'}")

    def _open_match(self, icon: pystray.Icon, item: MenuItem) -> None:
        """Open current match in browser."""
        if self.get_match_url:
            url = self.get_match_url()
            if url:
                webbrowser.open(url)
                logger.info(f"Opened match URL: {url}")
            else:
                logger.info("No active match to view")

    def _exit(self, icon: pystray.Icon, item: MenuItem) -> None:
        """Exit the application."""
        logger.info("Exit requested from tray")

        if self.on_exit:
            self.on_exit()

        icon.stop()

    def update_status(self, status: str) -> None:
        """Update the status shown in the tray menu.

        Args:
            status: New status string
        """
        self._status = status
        if self._icon:
            self._icon.update_menu()

    def set_enabled(self, enabled: bool) -> None:
        """Set the enabled state.

        Args:
            enabled: Whether rich presence is enabled
        """
        self._enabled = enabled
        if self._icon:
            self._icon.update_menu()

    def run(self, blocking: bool = True) -> None:
        """Run the system tray.

        Args:
            blocking: If True, blocks the current thread. If False, runs in background.
        """
        self._icon = pystray.Icon(
            "Faceit Discord Status",
            self._create_icon_image(),
            "Faceit Discord Status",
            self._create_menu(),
        )

        if blocking:
            self._icon.run()
        else:
            self._thread = threading.Thread(target=self._icon.run, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        """Stop the system tray."""
        if self._icon:
            self._icon.stop()
