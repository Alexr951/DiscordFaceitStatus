"""Tests for the match-monitor state machine (faked API and Discord RPC)."""

import time

from src.config import Config
from src.faceit_api import LiveMatchInfo, MatchInfo
from src.monitor import GRACE_MISSES, MatchMonitor, parse_duration_to_seconds


def make_live(map_name="Mirage", duration="5:00", score=(1, 0)):
    return LiveMatchInfo(
        is_live=True, map_name=map_name, score_team1=score[0], score_team2=score[1],
        elo_at_stake="+25/-25", server="EU", queue_name="5v5", win_chance=50,
        duration=duration, current_round=2, current_elo=2000, skill_level="10",
        region="EU", country="pl", country_flag="\U0001f1f5\U0001f1f1",
        region_ranking=100, country_ranking=10, ladder_position=0,
        ladder_division="", ladder_points=0, ladder_win_rate=0.0,
        today_elo_change="+25", today_wins=1, today_losses=0, today_matches=1,
        fpl_status="", fplc_status="", trend="W", last_match="",
    )


def make_match(match_id="m1", status="ONGOING"):
    return MatchInfo(
        match_id=match_id, status=status, map_name="de_mirage",
        match_url="https://faceit.com/en/match/m1", team1_score=5, team2_score=3,
        avg_elo=2000, started_at=int(time.time()) - 600, finished_at=None,
        players=[], player_team=1,
    )


class FakeAPI:
    def __init__(self):
        self.live = None
        self.ongoing = None
        self.details = {}

    def get_live_match_info(self, nickname):
        return self.live

    def get_ongoing_match(self, player_id):
        return self.ongoing

    def get_match_details(self, match_id, player_id):
        return self.details[match_id]

    def get_match_stats(self, match_id, player_id):
        return None

    def get_elo_change(self, player_id, match_id):
        return None


class FakeRPC:
    def __init__(self):
        self.connected = True
        self.clear_count = 0
        self.updates = []

    def clear(self):
        self.clear_count += 1

    def connect(self):
        return True

    def disconnect(self):
        pass

    def update_live_simple(self, **kwargs):
        self.updates.append(("live_simple", kwargs))

    def update_lobby(self, match, **kwargs):
        self.updates.append(("lobby", match))

    def update_live(self, match, **kwargs):
        self.updates.append(("live", match))

    def update_finished(self, match, **kwargs):
        self.updates.append(("finished", match))


def make_monitor(tmp_path):
    config = Config(data_dir=tmp_path / "data", legacy_dir=tmp_path / "legacy")
    config.faceit_nickname = "tester"
    api = FakeAPI()
    monitor = MatchMonitor(config, faceit=api)
    monitor.discord = FakeRPC()
    monitor._player_id = "p1"
    monitor._player_nickname = "tester"
    return monitor, api, monitor.discord


def test_parse_duration_mm_ss():
    assert parse_duration_to_seconds("12:34") == 754


def test_parse_duration_h_mm_ss():
    assert parse_duration_to_seconds("1:02:03") == 3723


def test_parse_duration_invalid():
    assert parse_duration_to_seconds("") is None
    assert parse_duration_to_seconds("junk") is None


def test_live_match_sets_start_time_once(tmp_path):
    monitor, api, rpc = make_monitor(tmp_path)
    api.live = make_live(duration="5:00")

    monitor._check_match()
    first_start = monitor._match_start
    assert first_start is not None
    assert abs((int(time.time()) - 300) - first_start) <= 2

    api.live = make_live(duration="6:00")
    monitor._check_match()
    assert monitor._match_start == first_start  # timer must NOT reset

    # the start timestamp is passed through to Discord on every update
    kind, kwargs = rpc.updates[-1]
    assert kind == "live_simple"
    assert kwargs["match_start"] == first_start


def test_grace_period_keeps_presence_through_blips(tmp_path):
    monitor, api, rpc = make_monitor(tmp_path)
    api.live = make_live()
    monitor._check_match()
    assert monitor._in_live_match

    api.live = None  # API blip: no live info, no ongoing match
    for _ in range(GRACE_MISSES - 1):
        monitor._check_match()
    assert rpc.clear_count == 0  # presence survived the blips

    monitor._check_match()  # final miss exceeds the grace period
    assert rpc.clear_count == 1
    assert not monitor._in_live_match


def test_finished_result_shown_then_cleared(tmp_path):
    monitor, api, rpc = make_monitor(tmp_path)
    api.ongoing = "m1"
    api.details["m1"] = make_match("m1", status="ONGOING")
    monitor._check_match()
    assert monitor._current_match_id == "m1"

    # match disappears from ongoing; details now say FINISHED
    api.ongoing = None
    api.details["m1"] = make_match("m1", status="FINISHED")
    for _ in range(GRACE_MISSES):
        monitor._check_match()
    assert ("finished", api.details["m1"]) in rpc.updates
    assert rpc.clear_count == 0  # result lingers instead of clearing

    monitor._finished_shown_at = time.time() - 9999  # linger window elapsed
    monitor._check_match()
    assert rpc.clear_count == 1


def test_match_url_cached_for_tray(tmp_path):
    monitor, api, rpc = make_monitor(tmp_path)
    api.ongoing = "m1"
    api.details["m1"] = make_match("m1")
    monitor._check_match()

    api.details.clear()  # cached URL must not trigger a new API call
    assert monitor.get_current_match_url() == "https://faceit.com/en/match/m1"
