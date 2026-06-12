"""Tests for command-line argument parsing."""

from src.main import parse_test_arg


def test_no_test_flag():
    assert parse_test_arg(["run.py"]) == (False, "")
    assert parse_test_arg(["run.py", "--debug"]) == (False, "")


def test_test_flag_alone():
    assert parse_test_arg(["run.py", "--test"]) == (True, "")
    assert parse_test_arg(["run.py", "--test", "--debug"]) == (True, "")


def test_test_flag_with_nickname():
    assert parse_test_arg(["run.py", "--test", "s1mple"]) == (True, "s1mple")
