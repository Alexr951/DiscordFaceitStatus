"""Main entry point for Faceit Discord Rich Presence."""

import logging
import signal
import sys

from .config import Config
from .faceit_api import FaceitAPI
from .gui import open_settings_window, run_first_run_wizard
from .monitor import MatchMonitor
from .tray import SystemTray
from .utils import setup_logging

logger = logging.getLogger(__name__)

# Keep the mutex handle alive for the lifetime of the process.
_instance_mutex = None


def _already_running() -> bool:
    """Windows named-mutex guard so a second launch exits instead of
    creating a duplicate tray icon (e.g. auto-start + manual start)."""
    if sys.platform != "win32":
        return False
    global _instance_mutex
    import ctypes
    _instance_mutex = ctypes.windll.kernel32.CreateMutexW(
        None, False, "FaceitDiscordStatus_SingleInstance"
    )
    return ctypes.windll.kernel32.GetLastError() == 183  # ERROR_ALREADY_EXISTS


def main() -> int:
    """Main entry point. Returns the process exit code."""
    setup_logging(debug="--debug" in sys.argv)
    logger.info("Starting Faceit Discord Rich Presence")

    if _already_running():
        logger.info("Another instance is already running - exiting")
        return 0

    config = Config()  # loads from %APPDATA%, migrating any legacy .env/config
    api = FaceitAPI(config.faceit_api_key)

    if not config.faceit_nickname:
        logger.info("No nickname configured - showing first-run setup")
        if not run_first_run_wizard(config, api):
            logger.info("Setup cancelled by user")
            return 0

    monitor = MatchMonitor(config, faceit=api)

    def on_toggle(enabled: bool) -> None:
        config.is_enabled = enabled
        tray.update_status(
            "Checking for matches..." if enabled else "Presence disabled"
        )

    tray = SystemTray(
        config=config,
        on_toggle=on_toggle,
        get_match_url=monitor.get_current_match_url,
        open_settings=lambda: open_settings_window(
            config, api, monitor.update_player
        ),
    )

    monitor.set_callbacks(
        on_status_change=tray.update_status,
        on_error=lambda err: tray.update_status(f"Error: {err}"),
        on_notify=tray.notify,
    )

    # Ctrl+C / termination: stop the tray loop; cleanup runs after run() returns.
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}")
        tray.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if not monitor.start():
        logger.error("Failed to start monitor")
        return 1

    logger.info("Running system tray")
    tray.run()  # blocks until Exit is chosen

    monitor.stop()  # clears presence, disconnects Discord, joins the thread
    logger.info("Shutdown complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
