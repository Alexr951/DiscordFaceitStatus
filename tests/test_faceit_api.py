"""Tests for Faceit API helpers."""

from src.faceit_api import parse_timestamp


def test_parse_timestamp_passes_through_int():
    assert parse_timestamp(1700000000) == 1700000000


def test_parse_timestamp_converts_iso_string():
    assert parse_timestamp("2024-01-01T00:00:00Z") == 1704067200


def test_parse_timestamp_rejects_garbage():
    assert parse_timestamp("nonsense") is None


def test_parse_timestamp_none():
    assert parse_timestamp(None) is None
