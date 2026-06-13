"""Main entry point for Faceit Discord Rich Presence."""

import logging
import signal
import sys
import tempfile
from pathlib import Path

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


def parse_test_arg(argv: list[str]) -> tuple[bool, str]:
    """Parse `--test [nickname]` from the command line.

    Returns (test_mode, nickname). Nickname is "" when --test is given alone
    (runs the first-run wizard against a throwaway profile).
    """
    if "--test" not in argv:
        return False, ""
    i = argv.index("--test")
    if i + 1 < len(argv) and not argv[i + 1].startswith("-"):
        return True, argv[i + 1]
    return True, ""


def main() -> int:
    """Main entry point. Returns the process exit code."""
    test_mode, test_nick = parse_test_arg(sys.argv)
    if getattr(sys, "frozen", False):
        # Test mode bypasses the Steam identity check, so the packaged exe
        # ignores it - otherwise anyone could impersonate a pro player by
        # launching the exe with --test <name>.
        test_mode, test_nick = False, ""
    setup_logging(debug="--debug" in sys.argv or test_mode)
    logger.info("Starting Faceit Discord Rich Presence")

    if _already_running():
        logger.info("Another instance is already running - exiting")
        return 0

    if test_mode:
        # Throwaway profile: the real %APPDATA% config is never read or
        # written, so there is nothing to revert after testing.
        temp_dir = Path(tempfile.mkdtemp(prefix="FaceitDiscordStatus-test-"))
        config = Config(data_dir=temp_dir, legacy_dir=temp_dir)
        config.set("poll_interval", 10)  # fast feedback while testing
        if test_nick:
            config.set("faceit_nickname", test_nick)
        logger.info(
            f"TEST MODE: temp profile at {temp_dir}"
            + (f", tracking '{test_nick}'" if test_nick else ", wizard will run")
        )
    else:
        config = Config()  # loads from %APPDATA%, migrating any legacy .env/config
    api = FaceitAPI(config.faceit_api_key)

    if not config.faceit_nickname:
        logger.info("No nickname configured - showing first-run setup")
        if not run_first_run_wizard(config, api):
            logger.info("Setup cancelled by user")
            return 0

    monitor = MatchMonitor(config, faceit=api)
    if test_mode:
        monitor.disable_ownership_check()  # allow watching any player's match

    def on_toggle(enabled: bool) -> None:
        config.is_enabled = enabled
        tray.update_status(
            "Checking for matches..." if enabled else "Presence disabled"
        )

    tray = SystemTray(
        config=config,
        on_toggle=on_toggle,
        get_match_url=monitor.get_current_match_url,
        open_settings=lambda: open_settings_window(config),
    )

    monitor.set_callbacks(
        on_status_change=tray.update_status,
        on_error=lambda err: tray.update_status(f"Error: {err}"),
        on_notify=tray.notify,
    )

    # SIGTERM (e.g. taskkill): unblock the main thread for clean shutdown.
    # Ctrl+C is handled as KeyboardInterrupt in wait_for_exit() below.
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}")
        tray.stop()

    signal.signal(signal.SIGTERM, signal_handler)

    if not monitor.start():
        logger.error("Failed to start monitor")
        return 1

    logger.info("Running system tray")
    tray.run_detached()
    try:
        tray.wait_for_exit()  # returns when Exit is chosen
    except KeyboardInterrupt:
        logger.info("Interrupted from console")

    tray.stop()
    monitor.stop()  # clears presence, disconnects Discord, joins the thread
    logger.info("Shutdown complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
