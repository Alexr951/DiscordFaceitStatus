"""Discord Rich Presence handler for displaying Faceit match status."""

import logging
import time
from typing import Optional

from pypresence import Presence, DiscordNotFound, PipeClosed

from .faceit_api import MatchInfo, MatchPlayer

logger = logging.getLogger(__name__)


class DiscordRPC:
    """Handles Discord Rich Presence updates."""

    def __init__(self, app_id: str):
        self.app_id = app_id
        self.rpc: Optional[Presence] = None
        self.connected = False
        self._last_update_time = 0
        self._min_update_interval = 15  # Discord rate limit

    def connect(self) -> bool:
        """Connect to Discord RPC.

        Returns:
            True if connected successfully, False otherwise
        """
        try:
            self.rpc = Presence(self.app_id)
            self.rpc.connect()
            self.connected = True
            logger.info("Connected to Discord RPC")
            return True
        except DiscordNotFound:
            logger.warning("Discord not found. Is Discord running?")
            self.connected = False
            return False
        except Exception as e:
            logger.error(f"Failed to connect to Discord: {e}")
            self.connected = False
            return False

    def disconnect(self) -> None:
        """Disconnect from Discord RPC."""
        if self.rpc:
            try:
                self.rpc.close()
            except Exception:
                pass
            self.rpc = None
        self.connected = False
        logger.info("Disconnected from Discord RPC")

    def reconnect(self) -> bool:
        """Attempt to reconnect to Discord.

        Returns:
            True if reconnected successfully
        """
        self.disconnect()
        time.sleep(1)
        return self.connect()

    def clear(self) -> None:
        """Clear the current presence."""
        if not self.connected or not self.rpc:
            return

        try:
            self.rpc.clear()
            logger.debug("Cleared Discord presence")
        except PipeClosed:
            logger.warning("Discord connection lost")
            self.connected = False
        except Exception as e:
            logger.error(f"Failed to clear presence: {e}")

    def update_lobby(
        self,
        match: MatchInfo,
        show_map: bool = True,
        show_avg_elo: bool = True,
    ) -> None:
        """Update presence for pre-match/lobby state.

        Args:
            match: Match information
            show_map: Whether to show map name
            show_avg_elo: Whether to show average ELO
        """
        details = "In Lobby"
        if show_map and match.map_name != "Unknown":
            details = f"In Lobby - {match.map_name}"

        state = "Waiting for match"
        if show_avg_elo and match.avg_elo > 0:
            state = f"Avg ELO: {match.avg_elo}"

        self._update(
            details=details,
            state=state,
            large_image="faceit_logo",
            large_text="Faceit CS2",
            small_image=self._get_map_image(match.map_name),
            small_text=match.map_name,
            buttons=[{"label": "View Match", "url": match.match_url}] if match.match_url else None,
        )

    def update_live(
        self,
        match: MatchInfo,
        player_stats: Optional[MatchPlayer] = None,
        show_map: bool = True,
        show_avg_elo: bool = True,
        show_kda: bool = True,
        show_score: bool = True,
    ) -> None:
        """Update presence for live match state.

        Args:
            match: Match information
            player_stats: Player's current stats
            show_map: Whether to show map name
            show_avg_elo: Whether to show average ELO
            show_kda: Whether to show K/D/A stats
            show_score: Whether to show round score
        """
        # Build details line: "de_mirage | 8 - 5"
        parts = []
        if show_map and match.map_name != "Unknown":
            parts.append(match.map_name)

        # Show score with player's team first
        if show_score:
            if match.player_team == 1:
                score = f"{match.team1_score} - {match.team2_score}"
            else:
                score = f"{match.team2_score} - {match.team1_score}"
            parts.append(score)

        details = " | ".join(parts) if parts else "In Match"

        # Build state line: "K/D/A: 15/8/3 | Avg ELO: 2150"
        state_parts = []

        if show_kda and player_stats:
            kda = f"{player_stats.kills}/{player_stats.deaths}/{player_stats.assists}"
            state_parts.append(f"K/D/A: {kda}")

        if show_avg_elo and match.avg_elo > 0:
            state_parts.append(f"Avg ELO: {match.avg_elo}")

        state = " | ".join(state_parts) if state_parts else "Playing"

        # Calculate elapsed time
        start_time = match.started_at if match.started_at else int(time.time())

        self._update(
            details=details,
            state=state,
            large_image="faceit_logo",
            large_text="Faceit CS2",
            small_image=self._get_map_image(match.map_name),
            small_text=match.map_name,
            start=start_time,
            buttons=[{"label": "View Match", "url": match.match_url}] if match.match_url else None,
        )

    def update_finished(
        self,
        match: MatchInfo,
        elo_change: Optional[int] = None,
        show_elo: bool = True,
        show_score: bool = True,
    ) -> None:
        """Update presence for finished match state.

        Args:
            match: Match information
            elo_change: ELO gained/lost
            show_elo: Whether to show ELO change
            show_score: Whether to show final score
        """
        # Determine win/loss
        if match.player_team == 1:
            won = match.team1_score > match.team2_score
            score = f"{match.team1_score} - {match.team2_score}"
        else:
            won = match.team2_score > match.team1_score
            score = f"{match.team2_score} - {match.team1_score}"

        result = "Victory" if won else "Defeat"
        details = f"Match Finished - {result}"

        # Build state
        state_parts = []
        if show_score:
            state_parts.append(score)
        if show_elo and elo_change is not None:
            sign = "+" if elo_change >= 0 else ""
            state_parts.append(f"ELO: {sign}{elo_change}")

        state = " | ".join(state_parts) if state_parts else "Match Complete"

        self._update(
            details=details,
            state=state,
            large_image="faceit_logo",
            large_text="Faceit CS2",
            small_image=self._get_map_image(match.map_name),
            small_text=match.map_name,
            buttons=[{"label": "View Match", "url": match.match_url}] if match.match_url else None,
        )

    def _update(
        self,
        details: str,
        state: str,
        large_image: str = "faceit_logo",
        large_text: str = "Faceit",
        small_image: Optional[str] = None,
        small_text: Optional[str] = None,
        start: Optional[int] = None,
        buttons: Optional[list[dict]] = None,
    ) -> None:
        """Internal method to update Discord presence.

        Args:
            details: First line of presence
            state: Second line of presence
            large_image: Large image key
            large_text: Tooltip for large image
            small_image: Small image key
            small_text: Tooltip for small image
            start: Start timestamp for elapsed time
            buttons: List of button dicts with "label" and "url"
        """
        if not self.connected or not self.rpc:
            return

        # Rate limit updates
        now = time.time()
        if now - self._last_update_time < self._min_update_interval:
            return

        try:
            kwargs = {
                "details": details[:128],  # Discord limit
                "state": state[:128],
                "large_image": large_image,
                "large_text": large_text[:128],
            }

            if small_image:
                kwargs["small_image"] = small_image
            if small_text:
                kwargs["small_text"] = small_text[:128]
            if start:
                kwargs["start"] = start
            if buttons:
                # Discord allows max 2 buttons
                kwargs["buttons"] = buttons[:2]

            self.rpc.update(**kwargs)
            self._last_update_time = now
            logger.debug(f"Updated presence: {details} | {state}")

        except PipeClosed:
            logger.warning("Discord connection lost")
            self.connected = False
        except Exception as e:
            logger.error(f"Failed to update presence: {e}")

    def _get_map_image(self, map_name: str) -> str:
        """Get the image key for a CS2 map.

        Note: These image keys need to be uploaded to your Discord app.

        Args:
            map_name: Map name (e.g., "de_mirage")

        Returns:
            Image key for Discord
        """
        # Map names to image keys (you'll need to upload these to Discord)
        map_images = {
            "de_mirage": "map_mirage",
            "de_inferno": "map_inferno",
            "de_dust2": "map_dust2",
            "de_nuke": "map_nuke",
            "de_overpass": "map_overpass",
            "de_ancient": "map_ancient",
            "de_anubis": "map_anubis",
            "de_vertigo": "map_vertigo",
        }

        return map_images.get(map_name.lower(), "faceit_logo")
