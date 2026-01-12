"""Faceit API client for fetching match and player data."""

import logging
import time
from dataclasses import dataclass
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Faceit API base URLs
BASE_URL = "https://open.faceit.com/data/v4"
MATCH_HISTORY_URL = "https://api.faceit.com/match-history/v5"
THIRD_PARTY_API_URL = "https://faceit.lcrypt.eu"

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


@dataclass
class LiveMatchInfo:
    """Live match information from third-party API."""

    # Match state
    is_live: bool
    map_name: str
    score_team1: int
    score_team2: int
    elo_at_stake: str  # e.g., "+25/-25"
    server: str
    queue_name: str
    win_chance: int
    duration: str
    current_round: int

    # Player statistics
    current_elo: int
    skill_level: str
    region: str
    country: str
    country_flag: str
    region_ranking: int
    country_ranking: int

    # Ladder info
    ladder_position: int
    ladder_division: str
    ladder_points: int
    ladder_win_rate: float

    # Today's stats
    today_elo_change: str  # e.g., "-56" or "+45"
    today_wins: int
    today_losses: int
    today_matches: int

    # FPL status
    fpl_status: str
    fplc_status: str

    # Recent performance
    trend: str  # e.g., "WWLLL"
    last_match: str


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

    def get_live_match_info(self, nickname: str) -> Optional[LiveMatchInfo]:
        """Get live match info from third-party API.

        Args:
            nickname: Faceit nickname

        Returns:
            LiveMatchInfo if in live match, None otherwise
        """
        try:
            self._rate_limit()
            url = f"{THIRD_PARTY_API_URL}/?n={nickname}"
            response = requests.get(url, timeout=10)

            if response.status_code != 200:
                logger.debug(f"[third-party] API returned status {response.status_code}")
                return None

            data = response.json()

            if data.get("error"):
                logger.debug(f"[third-party] API returned error")
                return None

            current = data.get("current", {})
            if not current.get("present") or current.get("status") != "LIVE":
                logger.debug(f"[third-party] Player not in live match")
                return None

            # Parse score (format: "2:5")
            score_str = current.get("score", "0:0")
            try:
                score_parts = score_str.split(":")
                score_team1 = int(score_parts[0])
                score_team2 = int(score_parts[1])
            except (ValueError, IndexError):
                score_team1, score_team2 = 0, 0

            # Parse ladder info
            ladder = data.get("detail", {}).get("ladder", {})
            today = data.get("today", {})

            live_info = LiveMatchInfo(
                # Match state
                is_live=True,
                map_name=current.get("map", "Unknown"),
                score_team1=score_team1,
                score_team2=score_team2,
                elo_at_stake=current.get("elo", ""),
                server=current.get("server", ""),
                queue_name=current.get("what", ""),
                win_chance=current.get("chance", 50),
                duration=current.get("duration", ""),
                current_round=current.get("round", 0),

                # Player statistics
                current_elo=data.get("elo", 0),
                skill_level=str(data.get("level", "")),
                region=data.get("region", ""),
                country=data.get("country", ""),
                country_flag=data.get("country_flag", ""),
                region_ranking=data.get("region_ranking", 0),
                country_ranking=data.get("country_ranking", 0),

                # Ladder info
                ladder_position=ladder.get("position", 0),
                ladder_division=ladder.get("division", ""),
                ladder_points=ladder.get("points", 0),
                ladder_win_rate=ladder.get("win_rate", 0.0),

                # Today's stats
                today_elo_change=today.get("elo", "0") if today.get("present") else "0",
                today_wins=today.get("win", 0) if today.get("present") else 0,
                today_losses=today.get("lose", 0) if today.get("present") else 0,
                today_matches=today.get("count", 0) if today.get("present") else 0,

                # FPL status
                fpl_status=data.get("fpl", ""),
                fplc_status=data.get("fplc", ""),

                # Recent performance
                trend=data.get("trend", ""),
                last_match=data.get("last_match", ""),
            )

            logger.debug(f"[third-party] Found live match: {live_info.map_name} ({score_team1}:{score_team2})")
            return live_info

        except Exception as e:
            logger.debug(f"[third-party] Error: {e}")
            return None

    def get_ongoing_match(self, player_id: str) -> Optional[str]:
        """Check if player is in an ongoing match.

        Args:
            player_id: Faceit player ID

        Returns:
            Match ID if in match, None otherwise
        """
        try:
            # First, check if player endpoint has active_match info
            data = self._request(f"/players/{player_id}")

            # Log all top-level keys to see what's available
            logger.debug(f"Player endpoint keys: {list(data.keys())}")

            # Check for various possible ongoing match fields
            if "active_match_id" in data:
                logger.debug(f"Found active_match_id: {data['active_match_id']}")
                return data["active_match_id"]

            if "ongoing_match" in data:
                logger.debug(f"Found ongoing_match: {data['ongoing_match']}")
                return data["ongoing_match"].get("match_id") if isinstance(data["ongoing_match"], dict) else data["ongoing_match"]

            if "current_match" in data:
                logger.debug(f"Found current_match: {data['current_match']}")
                return data["current_match"]

            # Fallback: Check player's recent matches for ongoing ones
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
        # Try v5 match history API first (may include ongoing matches)
        match_id = self._check_v5_match_history(player_id)
        if match_id:
            return match_id

        # Fallback to v4 API
        try:
            data = self._request(
                f"/players/{player_id}/history",
                {"game": CS2_GAME_ID, "limit": 5}
            )

            items = data.get("items", [])
            logger.debug(f"[v4] Found {len(items)} recent matches")

            for match in items:
                status = match.get("status", "")
                match_id = match.get("match_id", "")
                logger.debug(f"[v4] Match {match_id}: status={status}")
                if status.upper() in ("READY", "ONGOING", "VOTING", "CONFIGURING"):
                    logger.debug(f"[v4] Found active match: {match_id}")
                    return match_id

            logger.debug("[v4] No active match found in recent history")
            return None

        except FaceitAPIError as e:
            logger.debug(f"[v4] Error checking recent matches: {e}")
            return None

    def _check_v5_match_history(self, player_id: str) -> Optional[str]:
        """Check v5 match history API for ongoing matches.

        Args:
            player_id: Faceit player ID

        Returns:
            Match ID if found, None otherwise
        """
        try:
            self._rate_limit()
            url = f"{MATCH_HISTORY_URL}/players/{player_id}/history"
            response = self.session.get(
                url,
                params={"page": 0, "size": 10},
                timeout=10
            )

            if response.status_code != 200:
                logger.debug(f"[v5] API returned status {response.status_code}")
                return None

            data = response.json()
            matches = data.get("payload", [])
            logger.debug(f"[v5] Found {len(matches)} recent matches")

            for match in matches:
                status = match.get("status", "")
                match_id = match.get("matchId", "") or match.get("match_id", "")
                logger.debug(f"[v5] Match {match_id}: status={status}")
                if status.upper() in ("READY", "ONGOING", "VOTING", "CONFIGURING", "LIVE"):
                    logger.debug(f"[v5] Found active match: {match_id}")
                    return match_id

            logger.debug("[v5] No active match found")
            return None

        except Exception as e:
            logger.debug(f"[v5] Error: {e}")
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
