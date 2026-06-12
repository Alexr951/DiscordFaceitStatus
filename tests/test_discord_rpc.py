"""Tests for Discord presence formatting helpers."""

from src.discord_rpc import country_flag, format_elo_at_stake, get_map_image


def test_country_flag_known():
    assert country_flag("cn") == "\U0001f1e8\U0001f1f3"
    assert country_flag("PL") == "\U0001f1f5\U0001f1f1"


def test_country_flag_invalid():
    assert country_flag("") == ""
    assert country_flag("xyz") == ""
    assert country_flag("1a") == ""


def test_map_lookup_known():
    assert get_map_image("de_mirage") == "map_mirage"
    assert get_map_image("Dust II") == "map_dust2"


def test_map_lookup_train():
    assert get_map_image("de_train") == "map_train"
    assert get_map_image("Train") == "map_train"


def test_map_lookup_unknown_falls_back_to_logo():
    assert get_map_image("de_whatever") == "faceit_logo"
    assert get_map_image("") == "faceit_logo"


def test_elo_at_stake_symmetric():
    assert format_elo_at_stake("+25/-25") == "±25"


def test_elo_at_stake_asymmetric():
    assert format_elo_at_stake("+30/-20") == "+30/-20"


def test_elo_at_stake_empty():
    assert format_elo_at_stake("") is None


def test_elo_at_stake_single_value():
    assert format_elo_at_stake("+25") == "+25"
