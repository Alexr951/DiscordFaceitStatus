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
            large_image=self._get_map_image(match.map_name),
            large_text=match.map_name if match.map_name != "Unknown" else "Faceit CS2",
            small_image="faceit_logo",
            small_text="Faceit CS2",
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
            large_image=self._get_map_image(match.map_name),
            large_text=match.map_name if match.map_name != "Unknown" else "Faceit CS2",
            small_image="faceit_logo",
            small_text="Faceit CS2",
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
            large_image=self._get_map_image(match.map_name),
            large_text=match.map_name if match.map_name != "Unknown" else "Faceit CS2",
            small_image="faceit_logo",
            small_text="Faceit CS2",
            buttons=[{"label": "View Match", "url": match.match_url}] if match.match_url else None,
        )

    def update_live_simple(
        self,
        map_name: Optional[str] = None,
        score: Optional[str] = None,
        elo_at_stake: Optional[str] = None,
        server: Optional[str] = None,
        queue_name: Optional[str] = None,
        current_elo: Optional[int] = None,
        country_flag: Optional[str] = None,
        region_rank: Optional[int] = None,
        today_elo: Optional[str] = None,
        fpl_status: Optional[str] = None,
        show_elo: bool = True,
        show_score: bool = True,
        show_current_elo: bool = True,
        show_country: bool = True,
        show_region_rank: bool = True,
        show_today_elo: bool = True,
        show_fpl: bool = True,
    ) -> None:
        """Update presence for live match using data from third-party API.

        Args:
            map_name: Map name (e.g., "Dust II")
            score: Score string (e.g., "5:3")
            elo_at_stake: ELO at stake (e.g., "+25/-25")
            server: Server location (e.g., "Chicago")
            queue_name: Queue name (e.g., "North America 5V5 Queue")
            current_elo: Player's current ELO
            country_flag: Country flag emoji
            region_rank: Regional ranking position
            today_elo: Today's ELO change (e.g., "+45" or "-23")
            fpl_status: FPL/FPL-C status text
            show_*: Toggle flags for each statistic
        """
        # Build details line: "Dust II | 5:3" or with ELO "Dust II | 5:3 | ELO: 2,880"
        details_parts = []
        if map_name:
            details_parts.append(map_name)
        if show_score and score:
            details_parts.append(score)
        if show_current_elo and current_elo:
            details_parts.append(f"ELO: {current_elo:,}")
        details = " | ".join(details_parts) if details_parts else "In Match"

        # Build state line: "🇨🇦 Rank #674 | +45 today | Chicago"
        state_parts = []
        if show_country and country_flag:
            if show_region_rank and region_rank:
                state_parts.append(f"{country_flag} Rank #{region_rank}")
            else:
                state_parts.append(country_flag)
        elif show_region_rank and region_rank:
            state_parts.append(f"Rank #{region_rank}")

        if show_today_elo and today_elo:
            state_parts.append(f"{today_elo} today")

        if show_elo and elo_at_stake:
            state_parts.append(f"±{elo_at_stake.replace('+', '').replace('-', '').split('/')[0]}")

        if server:
            state_parts.append(server)

        state = " | ".join(state_parts) if state_parts else "Playing"

        # Build large text with FPL status if applicable
        large_text = map_name or "Faceit CS2"
        if show_fpl and fpl_status and "participate" not in fpl_status.lower():
            large_text = f"{map_name} | {fpl_status}"

        self._update(
            details=details,
            state=state,
            large_image=self._get_map_image(map_name or ""),
            large_text=large_text,
            small_image="faceit_logo",
            small_text=queue_name or "Faceit CS2",
            start=int(time.time()),
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
            map_name: Map name (e.g., "de_mirage" or "Mirage")

        Returns:
            Image key for Discord
        """
        # Map names to image keys (you'll need to upload these to Discord)
        # Supports both official names (de_mirage) and display names (Mirage, Dust II)
        map_images = {
            "de_mirage": "map_mirage",
            "mirage": "map_mirage",
            "de_inferno": "map_inferno",
            "inferno": "map_inferno",
            "de_dust2": "map_dust2",
            "dust2": "map_dust2",
            "dust ii": "map_dust2",
            "de_nuke": "map_nuke",
            "nuke": "map_nuke",
            "de_overpass": "map_overpass",
            "overpass": "map_overpass",
            "de_ancient": "map_ancient",
            "ancient": "map_ancient",
            "de_anubis": "map_anubis",
            "anubis": "map_anubis",
            "de_vertigo": "map_vertigo",
            "vertigo": "map_vertigo",
        }

        return map_images.get(map_name.lower(), "faceit_logo")
