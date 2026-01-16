"""Main entry point for Faceit Discord Rich Presence."""

import logging
import signal
import sys

from .config import Config
from .monitor import MatchMonitor
from .tray import SystemTray, _windows_input_box, _windows_message_box
from .utils import setup_logging

logger = logging.getLogger(__name__)


def prompt_for_username(config: Config) -> bool:
    """Prompt user to enter their FACEIT username.

    Returns:
        True if username was set, False if cancelled
    """
    username = _windows_input_box(
        "FACEIT Username Required",
        "Enter your FACEIT username (case-sensitive):",
        ""
    )

    if username is None or not username.strip():
        return False

    username = username.strip()
    success, error = config.update_env_value("FACEIT_NICKNAME", username)

    if success:
        config.faceit_nickname = username
        logger.info(f"Username set to: {username}")
        return True
    else:
        _windows_message_box("Error", f"Failed to save username: {error}", 0)
        return False


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Set up logging
    setup_logging(debug="--debug" in sys.argv)

    logger.info("Starting Faceit Discord Rich Presence")

    # Load configuration
    config = Config()

    # If nickname is missing, prompt for it
    if not config.faceit_nickname:
        logger.info("No FACEIT nickname configured, prompting user...")
        if not prompt_for_username(config):
            _windows_message_box(
                "Setup Cancelled",
                "FACEIT username is required to run this application.\n\nExiting.",
                0
            )
            return 1

    # Validate configuration
    is_valid, errors = config.validate()
    if not is_valid:
        for error in errors:
            logger.error(error)
        _windows_message_box("Configuration Error", "\n".join(errors), 0)
        return 1

    # Create monitor
    monitor = MatchMonitor(config)

    # Create system tray
    def on_toggle(enabled: bool) -> None:
        """Handle toggle from tray menu."""
        config.is_enabled = enabled
        if enabled:
            tray.update_status("Enabled - checking for matches...")
        else:
            tray.update_status("Disabled")

    def on_exit() -> None:
        """Handle exit from tray menu."""
        logger.info("Shutting down...")
        monitor.stop()

    def on_status_change(status: str) -> None:
        """Handle status change from monitor."""
        tray.update_status(status)

    def on_error(error: str) -> None:
        """Handle error from monitor."""
        tray.update_status(f"Error: {error}")

    def on_setting_change(key: str, value: bool) -> None:
        """Handle display setting change from tray menu."""
        logger.info(f"Display setting changed: {key} = {value}")

    tray = SystemTray(
        config=config,
        on_toggle=on_toggle,
        on_exit=on_exit,
        get_match_url=monitor.get_current_match_url,
        on_setting_change=on_setting_change,
    )

    # Set up monitor callbacks
    monitor.set_callbacks(
        on_status_change=on_status_change,
        on_error=on_error,
    )

    # Handle SIGINT/SIGTERM
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}")
        monitor.stop()
        tray.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start monitor
    if not monitor.start():
        logger.error("Failed to start monitor")
        return 1

    # Run tray (blocks until exit)
    logger.info("Running system tray")
    tray.run(blocking=True)

    # Clean up
    monitor.stop()
    logger.info("Shutdown complete")

    return 0


if __name__ == "__main__":
    sys.exit(main())
