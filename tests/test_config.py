"""Tests for Config storage, defaults, and legacy migration."""

import json

from src.config import Config


def test_defaults_when_no_file(tmp_path):
    cfg = Config(data_dir=tmp_path / "data", legacy_dir=tmp_path / "legacy")
    assert cfg.faceit_nickname == ""
    assert cfg.poll_interval == 45
    assert cfg.is_enabled is True
    assert cfg.get("show_map") is True


def test_set_get_round_trip(tmp_path):
    data_dir = tmp_path / "data"
    cfg = Config(data_dir=data_dir, legacy_dir=tmp_path / "legacy")
    cfg.set("show_map", False)
    cfg.faceit_nickname = "s1mple"

    cfg2 = Config(data_dir=data_dir, legacy_dir=tmp_path / "legacy")
    assert cfg2.get("show_map") is False
    assert cfg2.faceit_nickname == "s1mple"


def test_update_saves_multiple_keys_at_once(tmp_path):
    data_dir = tmp_path / "data"
    cfg = Config(data_dir=data_dir, legacy_dir=tmp_path / "legacy")
    cfg.update({"show_kda": False, "show_score": False})

    cfg2 = Config(data_dir=data_dir, legacy_dir=tmp_path / "legacy")
    assert cfg2.get("show_kda") is False
    assert cfg2.get("show_score") is False


def test_migrates_legacy_env_and_config(tmp_path):
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    (legacy / ".env").write_text(
        "FACEIT_API_KEY=abc\nFACEIT_NICKNAME=OldNick\n", encoding="utf-8"
    )
    (legacy / "config.json").write_text(
        json.dumps({"show_map": False, "unknown_key": 1}), encoding="utf-8"
    )

    cfg = Config(data_dir=tmp_path / "data", legacy_dir=legacy)
    assert cfg.faceit_nickname == "OldNick"
    assert cfg.get("show_map") is False
    assert cfg.get("unknown_key") is None  # unknown keys are not migrated
    assert (tmp_path / "data" / "config.json").exists()  # persisted to new home


def test_corrupt_config_falls_back_to_defaults(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "config.json").write_text("{not json", encoding="utf-8")
    cfg = Config(data_dir=data_dir, legacy_dir=tmp_path / "legacy")
    assert cfg.poll_interval == 45
