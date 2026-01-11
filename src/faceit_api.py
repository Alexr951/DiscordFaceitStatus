"""Faceit API client for fetching match and player data."""

import logging
import time
from dataclasses import dataclass
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Faceit API base URL
BASE_URL = "https://open.faceit.com/data/v4"

# CS2 game ID on Faceit
CS2_GAME_ID = "cs2"


@dataclass
class PlayerInfo:
    """Player information from Faceit."""

    player_id: str
    nickname: str
    elo: int
    skill_level: int
    avatar_url: str


@dataclass
class MatchPlayer:
    """Player in a match with stats."""

    player_id: str
    nickname: str
    elo: int
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    adr: float = 0.0


@dataclass
class MatchInfo:
    """Match information from Faceit."""

    match_id: str
    status: str  # "READY", "ONGOING", "FINISHED", "CANCELLED"
    map_name: str
    match_url: str
    team1_score: int
    team2_score: int
    avg_elo: int
    started_at: Optional[int]  # Unix timestamp
    finished_at: Optional[int]
    players: list[MatchPlayer]
    player_team: int  # 1 or 2
    elo_change: Optional[int] = None  # ELO gained/lost after match


class FaceitAPIError(Exception):
    """Custom exception for Faceit API errors."""

    pass


class FaceitAPI:
    """Client for interacting with the Faceit Data API."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        })

        # Rate limiting
        self._last_request_time = 0
        self._min_request_interval = 1.0  # seconds between requests

        # Cache
        self._player_cache: dict[str, tuple[PlayerInfo, float]] = {}
        self._cache_ttl = 300  # 5 minutes

    def _rate_limit(self) -> None:
        """Ensure we don't exceed rate limits."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()

    def _request(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """Make a request to the Faceit API.

        Args:
            endpoint: API endpoint (without base URL)
            params: Query parameters

        Returns:
            JSON response as dict

        Raises:
            FaceitAPIError: If request fails
        """
        self._rate_limit()

        url = f"{BASE_URL}{endpoint}"
        try:
            response = self.session.get(url, params=params, timeout=10)

            if response.status_code == 401:
                raise FaceitAPIError("Invalid API key")
            elif response.status_code == 404:
                raise FaceitAPIError("Resource not found")
            elif response.status_code == 429:
                raise FaceitAPIError("Rate limit exceeded")
            elif response.status_code != 200:
                raise FaceitAPIError(f"API error: {response.status_code}")

            return response.json()

        except requests.RequestException as e:
            raise FaceitAPIError(f"Request failed: {e}")

    def get_player_by_nickname(self, nickname: str) -> PlayerInfo:
        """Get player information by nickname.

        Args:
            nickname: Faceit nickname

        Returns:
            PlayerInfo object
        """
        # Check cache first
        cache_key = nickname.lower()
        if cache_key in self._player_cache:
            player, cached_at = self._player_cache[cache_key]
            if time.time() - cached_at < self._cache_ttl:
                return player

        data = self._request("/players", {"nickname": nickname, "game": CS2_GAME_ID})

        # Extract CS2-specific data
        cs2_data = data.get("games", {}).get(CS2_GAME_ID, {})

        player = PlayerInfo(
            player_id=data["player_id"],
            nickname=data["nickname"],
            elo=cs2_data.get("faceit_elo", 0),
            skill_level=cs2_data.get("skill_level", 0),
            avatar_url=data.get("avatar", ""),
        )

        # Cache the result
        self._player_cache[cache_key] = (player, time.time())

        return player

    def get_player_by_id(self, player_id: str) -> PlayerInfo:
        """Get player information by player ID.

        Args:
            player_id: Faceit player ID

        Returns:
            PlayerInfo object
        """
        data = self._request(f"/players/{player_id}")

        cs2_data = data.get("games", {}).get(CS2_GAME_ID, {})

        return PlayerInfo(
            player_id=data["player_id"],
            nickname=data["nickname"],
            elo=cs2_data.get("faceit_elo", 0),
            skill_level=cs2_data.get("skill_level", 0),
            avatar_url=data.get("avatar", ""),
        )

    def get_ongoing_match(self, player_id: str) -> Optional[str]:
        """Check if player is in an ongoing match.

        Args:
            player_id: Faceit player ID

        Returns:
            Match ID if in match, None otherwise
        """
        try:
            data = self._request(f"/players/{player_id}")

            # Check for infractions/bans that might affect status
            if data.get("membership_type") == "free":
                pass  # Normal user

            # The API may include ongoing_match info in some cases
            # Check player's recent matches for ongoing ones
            return self._check_recent_matches_for_ongoing(player_id)

        except FaceitAPIError as e:
            logger.warning(f"Failed to check ongoing match: {e}")
            return None

    def _check_recent_matches_for_ongoing(self, player_id: str) -> Optional[str]:
        """Check recent matches for an ongoing one.

        Args:
            player_id: Faceit player ID

        Returns:
            Match ID if found, None otherwise
        """
        try:
            data = self._request(
                f"/players/{player_id}/history",
                {"game": CS2_GAME_ID, "limit": 5}
            )

            for match in data.get("items", []):
                status = match.get("status", "")
                if status in ("READY", "ONGOING", "VOTING", "CONFIGURING"):
                    return match.get("match_id")

            return None

        except FaceitAPIError:
            return None

    def get_match_details(self, match_id: str, player_id: str) -> MatchInfo:
        """Get detailed match information.

        Args:
            match_id: Faceit match ID
            player_id: Current player's ID (to determine their team)

        Returns:
            MatchInfo object
        """
        data = self._request(f"/matches/{match_id}")

        # Determine map
        voting = data.get("voting", {})
        map_data = voting.get("map", {})
        map_pick = map_data.get("pick", [])
        map_name = map_pick[0] if map_pick else "Unknown"

        # Get teams and find player's team
        teams = data.get("teams", {})
        team1 = teams.get("faction1", {})
        team2 = teams.get("faction2", {})

        team1_roster = team1.get("roster", [])
        team2_roster = team2.get("roster", [])

        # Find which team the player is on
        player_team = 0
        for player in team1_roster:
            if player.get("player_id") == player_id:
                player_team = 1
                break
        for player in team2_roster:
            if player.get("player_id") == player_id:
                player_team = 2
                break

        # Build player list with ELOs
        players = []
        all_elos = []

        for roster, team_num in [(team1_roster, 1), (team2_roster, 2)]:
            for p in roster:
                elo = p.get("elo", 0) or 0
                all_elos.append(elo)
                players.append(MatchPlayer(
                    player_id=p.get("player_id", ""),
                    nickname=p.get("nickname", ""),
                    elo=elo,
                ))

        # Calculate average ELO
        avg_elo = int(sum(all_elos) / len(all_elos)) if all_elos else 0

        # Get scores
        results = data.get("results", {})
        score = results.get("score", {})
        team1_score = int(score.get("faction1", 0) or 0)
        team2_score = int(score.get("faction2", 0) or 0)

        # Get timestamps
        started_at = data.get("started_at")
        finished_at = data.get("finished_at")

        # Convert ISO string to timestamp if needed
        if isinstance(started_at, str):
            try:
                from datetime import datetime
                started_at = int(datetime.fromisoformat(
                    started_at.replace("Z", "+00:00")
                ).timestamp())
            except (ValueError, AttributeError):
                started_at = None

        return MatchInfo(
            match_id=match_id,
            status=data.get("status", "UNKNOWN"),
            map_name=map_name,
            match_url=data.get("faceit_url", "").replace("{lang}", "en"),
            team1_score=team1_score,
            team2_score=team2_score,
            avg_elo=avg_elo,
            started_at=started_at,
            finished_at=finished_at,
            players=players,
            player_team=player_team,
        )

    def get_match_stats(self, match_id: str, player_id: str) -> Optional[MatchPlayer]:
        """Get player's stats from a match.

        Args:
            match_id: Faceit match ID
            player_id: Player's Faceit ID

        Returns:
            MatchPlayer with stats, or None if not available
        """
        try:
            data = self._request(f"/matches/{match_id}/stats")

            for round_data in data.get("rounds", []):
                for team in round_data.get("teams", []):
                    for player in team.get("players", []):
                        if player.get("player_id") == player_id:
                            stats = player.get("player_stats", {})
                            return MatchPlayer(
                                player_id=player_id,
                                nickname=player.get("nickname", ""),
                                elo=0,  # Not in stats endpoint
                                kills=int(stats.get("Kills", 0)),
                                deaths=int(stats.get("Deaths", 0)),
                                assists=int(stats.get("Assists", 0)),
                                adr=float(stats.get("ADR", 0)),
                            )

            return None

        except FaceitAPIError:
            return None

    def get_elo_change(self, player_id: str, match_id: str) -> Optional[int]:
        """Get ELO change from a specific match.

        Args:
            player_id: Player's Faceit ID
            match_id: Match ID to check

        Returns:
            ELO change (positive or negative), or None if not available
        """
        try:
            # Get recent match history
            data = self._request(
                f"/players/{player_id}/history",
                {"game": CS2_GAME_ID, "limit": 10}
            )

            # Find the match and calculate ELO diff
            matches = data.get("items", [])
            for i, match in enumerate(matches):
                if match.get("match_id") == match_id:
                    current_elo = match.get("elo", 0)
                    if i + 1 < len(matches):
                        prev_elo = matches[i + 1].get("elo", 0)
                        return current_elo - prev_elo
                    break

            return None

        except FaceitAPIError:
            return None
