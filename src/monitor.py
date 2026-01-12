"""Main monitoring loop for Faceit match status."""

import logging
import threading
import time
from typing import Callable, Optional

from .config import Config
from .discord_rpc import DiscordRPC
from .faceit_api import FaceitAPI, FaceitAPIError, MatchInfo, LiveMatchInfo

logger = logging.getLogger(__name__)


class MatchMonitor:
    """Monitors Faceit matches and updates Discord presence."""

    def __init__(self, config: Config):
        self.config = config
        self.faceit = FaceitAPI(config.faceit_api_key)
        self.discord = DiscordRPC(config.discord_app_id)

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._player_id: Optional[str] = None
        self._player_nickname: str = config.faceit_nickname
        self._current_match_id: Optional[str] = None
        self._last_match_status: Optional[str] = None
        self._in_live_match: bool = False

        # Callbacks for UI updates
        self._on_status_change: Optional[Callable[[str], None]] = None
        self._on_error: Optional[Callable[[str], None]] = None

    def set_callbacks(
        self,
        on_status_change: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Set callbacks for status updates.

        Args:
            on_status_change: Called when match status changes
            on_error: Called when an error occurs
        """
        self._on_status_change = on_status_change
        self._on_error = on_error

    def _notify_status(self, status: str) -> None:
        """Notify listeners of status change."""
        if self._on_status_change:
            try:
                self._on_status_change(status)
            except Exception:
                pass

    def _notify_error(self, error: str) -> None:
        """Notify listeners of an error."""
        if self._on_error:
            try:
                self._on_error(error)
            except Exception:
                pass

    def start(self) -> bool:
        """Start the monitoring loop.

        Returns:
            True if started successfully
        """
        if self._running:
            return True

        # Validate config
        is_valid, errors = self.config.validate()
        if not is_valid:
            for error in errors:
                logger.error(error)
                self._notify_error(error)
            return False

        # Get player ID
        try:
            player = self.faceit.get_player_by_nickname(self.config.faceit_nickname)
            self._player_id = player.player_id
            logger.info(f"Found player: {player.nickname} (ELO: {player.elo})")
        except FaceitAPIError as e:
            logger.error(f"Failed to get player info: {e}")
            self._notify_error(f"Failed to get player info: {e}")
            return False

        # Connect to Discord
        if not self.discord.connect():
            self._notify_error("Failed to connect to Discord")
            return False

        # Start monitor thread
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

        self._notify_status("Monitoring started")
        logger.info("Match monitor started")
        return True

    def stop(self) -> None:
        """Stop the monitoring loop."""
        self._running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

        self.discord.clear()
        self.discord.disconnect()

        self._current_match_id = None
        self._last_match_status = None

        self._notify_status("Monitoring stopped")
        logger.info("Match monitor stopped")

    def is_running(self) -> bool:
        """Check if monitor is running."""
        return self._running

    def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        consecutive_errors = 0
        max_errors = 5

        while self._running:
            try:
                if not self.config.is_enabled:
                    self.discord.clear()
                    time.sleep(self.config.poll_interval)
                    continue

                # Check Discord connection
                if not self.discord.connected:
                    logger.info("Attempting to reconnect to Discord...")
                    if not self.discord.reconnect():
                        time.sleep(self.config.poll_interval)
                        continue

                # Check for ongoing match
                self._check_match()

                consecutive_errors = 0

            except FaceitAPIError as e:
                consecutive_errors += 1
                logger.warning(f"Faceit API error: {e}")

                if consecutive_errors >= max_errors:
                    logger.error("Too many consecutive errors, pausing...")
                    self._notify_error(f"API errors: {e}")
                    time.sleep(self.config.poll_interval * 2)
                    consecutive_errors = 0

            except Exception as e:
                consecutive_errors += 1
                logger.exception(f"Unexpected error in monitor loop: {e}")

                if consecutive_errors >= max_errors:
                    self._notify_error(f"Errors: {e}")
                    time.sleep(self.config.poll_interval * 2)
                    consecutive_errors = 0

            # Wait for next poll
            time.sleep(self.config.poll_interval)

    def _check_match(self) -> None:
        """Check for and process current match status."""
        if not self._player_id:
            return

        # First, check for live match using third-party API (more reliable for live detection)
        live_info = self.faceit.get_live_match_info(self._player_nickname)

        if live_info and live_info.is_live:
            # We have a live match from third-party API
            if not self._in_live_match:
                logger.info(f"Live match detected: {live_info.map_name}")
                self._in_live_match = True

            self._update_live_presence(live_info)
            return

        # No live match from third-party API, check official API for other match states
        self._in_live_match = False

        # Look for ongoing match via official API
        match_id = self.faceit.get_ongoing_match(self._player_id)

        if not match_id:
            # No active match
            if self._current_match_id:
                # Match just ended, show final status briefly
                logger.info("Match ended")
                self._notify_status("No active match")

            self._current_match_id = None
            self._last_match_status = None
            self.discord.clear()
            return

        # Get match details
        match = self.faceit.get_match_details(match_id, self._player_id)

        # Track match changes
        if match_id != self._current_match_id:
            logger.info(f"New match detected: {match_id}")
            self._current_match_id = match_id

        if match.status != self._last_match_status:
            logger.info(f"Match status changed: {match.status}")
            self._last_match_status = match.status

        # Update Discord based on match status
        self._update_presence(match)

    def _update_live_presence(self, live_info: LiveMatchInfo) -> None:
        """Update Discord presence for live match from third-party API.

        Args:
            live_info: Live match information
        """
        # Get all display settings
        show_map = self.config.get("show_map", True)
        show_score = self.config.get("show_score", True)
        show_elo = self.config.get("show_elo", True)
        show_current_elo = self.config.get("show_current_elo", True)
        show_country = self.config.get("show_country", True)
        show_region_rank = self.config.get("show_region_rank", True)
        show_today_elo = self.config.get("show_today_elo", True)
        show_fpl = self.config.get("show_fpl", True)

        score = f"{live_info.score_team1}:{live_info.score_team2}"
        self._notify_status(f"Live: {live_info.map_name} ({score})")

        # Determine FPL status to display
        fpl_status = None
        if "participate" not in live_info.fpl_status.lower():
            fpl_status = "FPL"
        elif "participate" not in live_info.fplc_status.lower():
            fpl_status = "FPL-C"

        self.discord.update_live_simple(
            map_name=live_info.map_name if show_map else None,
            score=score if show_score else None,
            elo_at_stake=live_info.elo_at_stake if show_elo else None,
            server=live_info.server,
            queue_name=live_info.queue_name,
            current_elo=live_info.current_elo if show_current_elo else None,
            country_flag=live_info.country_flag if show_country else None,
            region_rank=live_info.region_ranking if show_region_rank else None,
            today_elo=live_info.today_elo_change if show_today_elo else None,
            fpl_status=fpl_status if show_fpl else None,
            show_elo=show_elo,
            show_score=show_score,
            show_current_elo=show_current_elo,
            show_country=show_country,
            show_region_rank=show_region_rank,
            show_today_elo=show_today_elo,
            show_fpl=show_fpl,
        )

    def _update_presence(self, match: MatchInfo) -> None:
        """Update Discord presence based on match state.

        Args:
            match: Current match information
        """
        show_map = self.config.get("show_map", True)
        show_avg_elo = self.config.get("show_avg_elo", True)
        show_kda = self.config.get("show_kda", True)
        show_elo = self.config.get("show_elo", True)
        show_score = self.config.get("show_score", True)

        if match.status in ("READY", "VOTING", "CONFIGURING"):
            # Pre-match lobby
            self._notify_status(f"In lobby: {match.map_name}")
            self.discord.update_lobby(
                match,
                show_map=show_map,
                show_avg_elo=show_avg_elo,
            )

        elif match.status == "ONGOING":
            # Live match
            player_stats = None
            if show_kda and self._player_id:
                player_stats = self.faceit.get_match_stats(
                    match.match_id, self._player_id
                )

            score = f"{match.team1_score}-{match.team2_score}"
            self._notify_status(f"Live: {match.map_name} ({score})")

            self.discord.update_live(
                match,
                player_stats=player_stats,
                show_map=show_map,
                show_avg_elo=show_avg_elo,
                show_kda=show_kda,
                show_score=show_score,
            )

        elif match.status == "FINISHED":
            # Match finished
            elo_change = None
            if show_elo and self._player_id:
                elo_change = self.faceit.get_elo_change(
                    self._player_id, match.match_id
                )

            self._notify_status(f"Finished: {match.map_name}")
            self.discord.update_finished(
                match,
                elo_change=elo_change,
                show_elo=show_elo,
                show_score=show_score,
            )

        elif match.status == "CANCELLED":
            # Match cancelled
            self._notify_status("Match cancelled")
            self.discord.clear()

    def get_current_match_url(self) -> Optional[str]:
        """Get the URL of the current match.

        Returns:
            Match URL or None if no active match
        """
        if not self._current_match_id or not self._player_id:
            return None

        try:
            match = self.faceit.get_match_details(
                self._current_match_id, self._player_id
            )
            return match.match_url
        except FaceitAPIError:
            return None
