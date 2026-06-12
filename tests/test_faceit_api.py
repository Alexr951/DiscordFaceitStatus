"""Tests for Faceit API helpers."""

from src.faceit_api import FaceitAPI, parse_timestamp

SAMPLE_PLAYER = {
    "player_id": "p-123",
    "nickname": "TestNick",
    "avatar": "https://x/avatar.png",
    "games": {
        "cs2": {
            "faceit_elo": 1450,
            "skill_level": 6,
            "game_player_id": "76561198000000002",
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


def test_parse_timestamp_passes_through_int():
    assert parse_timestamp(1700000000) == 1700000000


def test_parse_timestamp_converts_iso_string():
    assert parse_timestamp("2024-01-01T00:00:00Z") == 1704067200


def test_parse_timestamp_rejects_garbage():
    assert parse_timestamp("nonsense") is None


def test_parse_timestamp_none():
    assert parse_timestamp(None) is None
