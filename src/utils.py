"""Utility functions for Faceit Discord Rich Presence."""

import logging
import sys
from pathlib import Path


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


def setup_logging(debug: bool = False) -> None:
    """Set up logging configuration.

    Args:
        debug: Enable debug logging
    """
    level = logging.DEBUG if debug else logging.INFO

    # Create logs directory (in app root, not bundled location)
    log_dir = get_app_root() / "logs"
    log_dir.mkdir(exist_ok=True)

    # Configure logging
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "faceit_discord.log"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)


def format_elo(elo: int) -> str:
    """Format ELO with thousands separator.

    Args:
        elo: ELO value

    Returns:
        Formatted string (e.g., "2,150")
    """
    return f"{elo:,}"


def format_kda(kills: int, deaths: int, assists: int) -> str:
    """Format K/D/A stats.

    Args:
        kills: Kill count
        deaths: Death count
        assists: Assist count

    Returns:
        Formatted string (e.g., "15/8/3")
    """
    return f"{kills}/{deaths}/{assists}"


def calculate_kd_ratio(kills: int, deaths: int) -> float:
    """Calculate K/D ratio.

    Args:
        kills: Kill count
        deaths: Death count

    Returns:
        K/D ratio (deaths capped at 1 to avoid division by zero)
    """
    return kills / max(deaths, 1)
