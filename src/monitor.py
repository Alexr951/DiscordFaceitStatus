"""Main monitoring loop for Faceit match status."""

import logging
import threading
import time
from typing import Callable, Optional

from .config import Config
from .discord_rpc import DiscordRPC
from .faceit_api import FaceitAPI, FaceitAPIError, LiveMatchInfo, MatchInfo

logger = logging.getLogger(__name__)

# Poll faster while a match is live so the score stays fresh.
LIVE_POLL_INTERVAL = 20  # seconds
# Consecutive "no match found" polls before an active presence is cleared.
GRACE_MISSES = 3
# How long the post-match result stays on the presence before clearing.
FINISHED_LINGER = 120  # seconds


def parse_duration_to_seconds(duration: str) -> Optional[int]:
    """Parse a "MM:SS" or "H:MM:SS" duration string into seconds."""
    if not duration:
        return None
    try:
        numbers = [int(p) for p in duration.strip().split(":")]
    except ValueError:
        return None
    if len(numbers) == 2:
        return numbers[0] * 60 + numbers[1]
    if len(numbers) == 3:
        return numbers[0] * 3600 + numbers[1] * 60 + numbers[2]
    return None


class MatchMonitor:
    """Monitors Faceit matches and updates Discord presence."""

    def __init__(self, config: Config, faceit: Optional[FaceitAPI] = None):
        self.config = config
        self.faceit = faceit or FaceitAPI(config.faceit_api_key)
        self.discord = DiscordRPC(config.discord_app_id)

        self._running = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self._player_lock = threading.Lock()
        self._player_id: Optional[str] = None
        self._player_nickname: str = config.faceit_nickname

        # Match state
        self._in_live_match = False
        self._current_match_id: Optional[str] = None
        self._last_match_status: Optional[str] = None
        self._match_start: Optional[int] = None
        self._match_url: Optional[str] = None
        self._miss_count = 0
        self._finished_shown_at: Optional[float] = None

        # One-shot notification flags so toasts are not repeated every poll
        self._notified_discord_down = False
        self._notified_player_error = False
        self._notified_api_outage = False

        # Callbacks for UI updates
        self._on_status_change: Optional[Callable[[str], None]] = None
        self._on_error: Optional[Callable[[str], None]] = None
        self._on_notify: Optional[Callable[[str, str], None]] = None

    def set_callbacks(
        self,
        on_status_change: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_notify: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        """Set callbacks: status line, error line, and (title, message) toasts."""
        self._on_status_change = on_status_change
        self._on_error = on_error
        self._on_notify = on_notify

    def _notify_status(self, status: str) -> None:
        if self._on_status_change:
            try:
                self._on_status_change(status)
            except Exception:
                pass

    def _notify_error(self, error: str) -> None:
        if self._on_error:
            try:
                self._on_error(error)
            except Exception:
                pass

    def _notify_toast(self, title: str, message: str) -> None:
        if self._on_notify:
            try:
                self._on_notify(title, message)
            except Exception:
                pass

    def start(self) -> bool:
        """Start the monitoring loop. Discord/player problems are retried inside
        the loop (with a toast), so this only fails when no nickname is set."""
        if self._running:
            return True
        if not self.config.faceit_nickname:
            self._notify_error("No FACEIT username configured")
            return False

        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._monitor_loop, name="match-monitor", daemon=True
        )
        self._thread.start()
        self._notify_status("Starting...")
        logger.info("Match monitor started")
        return True

    def stop(self) -> None:
        """Stop the loop, then clear and disconnect the presence."""
        if not self._running:
            return
        self._running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)
        self.discord.clear()
        self.discord.disconnect()
        self._reset_match_state()
        self._notify_status("Stopped")
        logger.info("Match monitor stopped")

    def is_running(self) -> bool:
        return self._running

    def update_player(self, nickname: str) -> tuple[bool, Optional[str]]:
        """Switch to tracking a different player. Safe to call while running
        (used by the settings window - no app restart needed)."""
        try:
            player = self.faceit.get_player_by_nickname(nickname)
        except FaceitAPIError as e:
            return False, str(e)
        with self._player_lock:
            self._player_id = player.player_id
            self._player_nickname = player.nickname
        self._reset_match_state()
        self.config.faceit_nickname = player.nickname
        self.discord.clear()
        self._notify_status(f"Tracking {player.nickname}")
        logger.info(f"Now tracking {player.nickname}")
        return True, None

    # --- monitor loop -----------------------------------------------------

    def _monitor_loop(self) -> None:
        consecutive_errors = 0
        max_errors = 5

        while self._running:
            interval = self.config.poll_interval
            try:
                if not self.config.is_enabled:
                    self.discord.clear()
                elif self._ensure_player() and self._ensure_discord():
                    self._check_match()
                    consecutive_errors = 0
                    self._notified_api_outage = False
                    if self._in_live_match:
                        interval = min(interval, LIVE_POLL_INTERVAL)
            except FaceitAPIError as e:
                consecutive_errors += 1
                logger.warning(f"Faceit API error: {e}")
                if consecutive_errors >= max_errors:
                    interval = self.config.poll_interval * 2
                    self._notify_error(f"API errors: {e}")
                    if not self._notified_api_outage:
                        self._notified_api_outage = True
                        self._notify_toast(
                            "Can't reach Faceit",
                            "Connection problems - retrying automatically.",
                        )
            except Exception as e:
                consecutive_errors += 1
                logger.exception(f"Unexpected error in monitor loop: {e}")
                if consecutive_errors >= max_errors:
                    interval = self.config.poll_interval * 2
                    self._notify_error(f"Errors: {e}")

            self._stop_event.wait(interval)

    def _ensure_player(self) -> bool:
        """Resolve the configured nickname to a player ID, retrying each poll."""
        with self._player_lock:
            if self._player_id:
                return True
            nickname = self.config.faceit_nickname
        try:
            player = self.faceit.get_player_by_nickname(nickname)
        except FaceitAPIError as e:
            logger.warning(f"Could not look up player '{nickname}': {e}")
            if not self._notified_player_error:
                self._notified_player_error = True
                self._notify_toast(
                    "Faceit player lookup failed",
                    f"Couldn't look up '{nickname}'. Check the spelling in "
                    "Settings, or your internet connection.",
                )
            self._notify_error(f"Player lookup failed: {e}")
            return False
        with self._player_lock:
            self._player_id = player.player_id
            self._player_nickname = player.nickname
        self._notified_player_error = False
        self._notify_status(f"Tracking {player.nickname}")
        logger.info(f"Found player: {player.nickname} (ELO: {player.elo})")
        return True

    def _ensure_discord(self) -> bool:
        """Connect to Discord if needed, toasting once when it's not running."""
        if self.discord.connected:
            return True
        if self.discord.connect():
            self._notified_discord_down = False
            return True
        if not self._notified_discord_down:
            self._notified_discord_down = True
            self._notify_toast(
                "Discord not found",
                "Start Discord and your match status will connect automatically.",
            )
        self._notify_status("Waiting for Discord...")
        return False

    # --- match state machine ----------------------------------------------

    def _check_match(self) -> None:
        with self._player_lock:
            player_id = self._player_id
            nickname = self._player_nickname
        if not player_id:
            return

        # Primary: third-party live API (rich data, one request)
        live_info = self.faceit.get_live_match_info(nickname)
        if live_info and live_info.is_live:
            self._on_live_match(live_info, player_id)
            return

        # Secondary: official API for lobby/ongoing states (one request)
        match_id = self.faceit.get_ongoing_match(player_id)
        if match_id:
            match = self.faceit.get_match_details(match_id, player_id)
            self._on_official_match(match)
            return

        self._on_no_match(player_id)

    def _on_live_match(self, live_info: LiveMatchInfo, player_id: str) -> None:
        self._miss_count = 0
        self._finished_shown_at = None
        if not self._in_live_match:
            logger.info(f"Live match detected: {live_info.map_name}")
            self._in_live_match = True
            elapsed = parse_duration_to_seconds(live_info.duration)
            self._match_start = int(time.time()) - (elapsed or 0)
            self._resolve_match_url(player_id)
        self._update_live_presence(live_info)

    def _resolve_match_url(self, player_id: str) -> None:
        """Best-effort lookup of the match ID/URL (for the tray's View Match
        and the post-match result). Runs once per match."""
        try:
            match_id = self.faceit.get_ongoing_match(player_id)
            if match_id:
                self._current_match_id = match_id
                match = self.faceit.get_match_details(match_id, player_id)
                self._match_url = match.match_url or None
        except FaceitAPIError as e:
            logger.debug(f"Could not resolve match URL: {e}")

    def _on_official_match(self, match: MatchInfo) -> None:
        self._miss_count = 0
        self._finished_shown_at = None
        if match.match_id != self._current_match_id:
            logger.info(f"New match detected: {match.match_id}")
            self._current_match_id = match.match_id
            self._match_url = match.match_url or None
        if match.status != self._last_match_status:
            logger.info(f"Match status changed: {match.status}")
            self._last_match_status = match.status
        if match.status == "ONGOING":
            if not self._in_live_match:
                self._in_live_match = True
                self._match_start = match.started_at or int(time.time())
        else:
            self._in_live_match = False
        self._update_presence(match)

    def _on_no_match(self, player_id: str) -> None:
        if self._finished_shown_at is not None:
            # Post-match result is showing; clear it once the linger expires.
            if time.time() - self._finished_shown_at >= FINISHED_LINGER:
                self._clear_presence()
                self._notify_status("No active match")
            return

        had_match = self._in_live_match or self._current_match_id is not None
        if not had_match:
            self._clear_presence()
            return

        self._miss_count += 1
        if self._miss_count < GRACE_MISSES:
            logger.debug(
                f"No match found ({self._miss_count}/{GRACE_MISSES}), keeping presence"
            )
            return

        # The match really is over - show the final result before clearing.
        if self._current_match_id and self._show_finished(player_id):
            return
        logger.info("Match ended")
        self._clear_presence()
        self._notify_status("No active match")

    def _show_finished(self, player_id: str) -> bool:
        try:
            match = self.faceit.get_match_details(self._current_match_id, player_id)
        except FaceitAPIError:
            return False
        if match.status != "FINISHED":
            return False
        self._in_live_match = False
        self._finished_shown_at = time.time()
        self._update_presence(match)
        self._notify_status(f"Finished: {match.map_name}")
        return True

    def _reset_match_state(self) -> None:
        self._in_live_match = False
        self._current_match_id = None
        self._last_match_status = None
        self._match_start = None
        self._match_url = None
        self._miss_count = 0
        self._finished_shown_at = None

    def _clear_presence(self) -> None:
        self._reset_match_state()
        self.discord.clear()

    # --- presence formatting ------------------------------------------------

    def _update_live_presence(self, live_info: LiveMatchInfo) -> None:
        """Update Discord presence for a live match (third-party API data)."""
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
            match_start=self._match_start,
            show_elo=show_elo,
            show_score=show_score,
            show_current_elo=show_current_elo,
            show_country=show_country,
            show_region_rank=show_region_rank,
            show_today_elo=show_today_elo,
            show_fpl=show_fpl,
        )

    def _update_presence(self, match: MatchInfo) -> None:
        """Update Discord presence from official-API match state."""
        show_map = self.config.get("show_map", True)
        show_avg_elo = self.config.get("show_avg_elo", True)
        show_kda = self.config.get("show_kda", True)
        show_elo = self.config.get("show_elo", True)
        show_score = self.config.get("show_score", True)

        if match.status in ("READY", "VOTING", "CONFIGURING"):
            self._notify_status(f"In lobby: {match.map_name}")
            self.discord.update_lobby(
                match,
                show_map=show_map,
                show_avg_elo=show_avg_elo,
            )

        elif match.status == "ONGOING":
            player_stats = None
            with self._player_lock:
                player_id = self._player_id
            if show_kda and player_id:
                player_stats = self.faceit.get_match_stats(match.match_id, player_id)

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
            elo_change = None
            with self._player_lock:
                player_id = self._player_id
            if show_elo and player_id:
                elo_change = self.faceit.get_elo_change(player_id, match.match_id)

            self.discord.update_finished(
                match,
                elo_change=elo_change,
                show_elo=show_elo,
                show_score=show_score,
            )

        elif match.status == "CANCELLED":
            self._notify_status("Match cancelled")
            self._clear_presence()

    def get_current_match_url(self) -> Optional[str]:
        """URL for the tray's "View Match" - cached, no API call when known."""
        if self._match_url:
            return self._match_url
        with self._player_lock:
            player_id = self._player_id
        if not self._current_match_id or not player_id:
            return None
        try:
            match = self.faceit.get_match_details(self._current_match_id, player_id)
        except FaceitAPIError:
            return None
        self._match_url = match.match_url or None
        return self._match_url
