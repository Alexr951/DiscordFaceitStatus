"""Tests for Faceit API helpers."""

from src.faceit_api import FaceitAPI, _pick_active_match, parse_timestamp


def test_pick_active_match_prefers_ongoing():
    payload = {
        "READY": [{"id": "m-ready", "game": "cs2"}],
        "ONGOING": [{"id": "m-live", "game": "cs2"}],
    }
    assert _pick_active_match(payload) == "m-live"


def test_pick_active_match_lobby_states():
    payload = {"VOTING": [{"id": "m-vote", "game": "cs2"}]}
    assert _pick_active_match(payload) == "m-vote"


def test_pick_active_match_ignores_other_games():
    payload = {"ONGOING": [{"id": "m-dota", "game": "dota2"}]}
    assert _pick_active_match(payload) is None


def test_pick_active_match_empty():
    assert _pick_active_match({}) is None
    assert _pick_active_match({"ONGOING": []}) is None

SAMPLE_PLAYER = {
    "player_id": "p-123",
    "nickname": "TestNick",
    "avatar": "https://x/avatar.png",
    "country": "cn",
    "games": {
        "cs2": {
            "faceit_elo": 1450,
            "skill_level": 6,
            "game_player_id": "76561198000000002",
            "region": "NA",
        }
    },
}


def test_get_player_by_steam_id_parses_player_and_steam_id():
    api = FaceitAPI("key")
    captured = {}

    def fake_request(endpoint, params=None):
        captured["endpoint"] = endpoint
        captured["params"] = params
        return SAMPLE_PLAYER

    api._request = fake_request
    player = api.get_player_by_steam_id("76561198000000002")
    assert captured["endpoint"] == "/players"
    assert captured["params"] == {
        "game": "cs2",
        "game_player_id": "76561198000000002",
    }
    assert player.nickname == "TestNick"
    assert player.elo == 1450
    assert player.steam_id == "76561198000000002"


def test_get_player_by_nickname_includes_steam_id():
    api = FaceitAPI("key")
    api._request = lambda endpoint, params=None: SAMPLE_PLAYER
    player = api.get_player_by_nickname("TestNick")
    assert player.steam_id == "76561198000000002"
    assert player.region == "NA"
    assert player.country == "cn"


def test_get_region_rank_parses_and_caches():
    api = FaceitAPI("key")
    calls = []

    def fake_request(endpoint, params=None):
        calls.append(endpoint)
        return {"position": 6264, "items": []}

    api._request = fake_request
    assert api.get_region_rank("p-123", "NA") == 6264
    assert api.get_region_rank("p-123", "NA") == 6264  # served from cache
    assert len(calls) == 1
    assert "/rankings/games/cs2/regions/NA/players/p-123" in calls[0]


def test_get_region_rank_handles_missing_region():
    api = FaceitAPI("key")
    assert api.get_region_rank("p-123", "") is None


def test_parse_timestamp_passes_through_int():
    assert parse_timestamp(1700000000) == 1700000000


def test_parse_timestamp_converts_iso_string():
    assert parse_timestamp("2024-01-01T00:00:00Z") == 1704067200


def test_parse_timestamp_rejects_garbage():
    assert parse_timestamp("nonsense") is None


def test_parse_timestamp_none():
    assert parse_timestamp(None) is None
