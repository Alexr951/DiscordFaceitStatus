"""Logging setup for Faceit Discord Rich Presence."""

import logging
import sys
from logging.handlers import RotatingFileHandler

from .config import get_data_dir


def setup_logging(debug: bool = False) -> None:
    """Log to %APPDATA%\\FaceitDiscordStatus\\logs with rotation, plus stdout."""
    level = logging.DEBUG if debug else logging.INFO

    log_dir = get_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            RotatingFileHandler(
                log_dir / "faceit_discord.log",
                maxBytes=1_000_000,
                backupCount=2,
                encoding="utf-8",
            ),
            logging.StreamHandler(sys.stdout),
        ],
    )

    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)
