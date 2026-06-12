"""Tests for local Steam account detection."""

from unittest import mock

from src import steam


SAMPLE_VDF = '''
"users"
{
\t"76561198000000001"
\t{
\t\t"AccountName"\t\t"olduser"
\t\t"PersonaName"\t\t"Old User"
\t\t"MostRecent"\t\t"0"
\t\t"Timestamp"\t\t"1700000000"
\t}
\t"76561198000000002"
\t{
\t\t"AccountName"\t\t"currentuser"
\t\t"PersonaName"\t\t"Current User"
\t\t"RememberPassword"\t\t"1"
\t\t"MostRecent"\t\t"1"
\t\t"Timestamp"\t\t"1710000000"
\t}
}
'''


def test_parse_loginusers_picks_most_recent():
    assert steam.parse_loginusers(SAMPLE_VDF) == "76561198000000002"


def test_parse_loginusers_none_marked():
    text = SAMPLE_VDF.replace('"MostRecent"\t\t"1"', '"MostRecent"\t\t"0"')
    assert steam.parse_loginusers(text) is None


def test_parse_loginusers_empty():
    assert steam.parse_loginusers("") is None


def test_active_user_registry_converts_to_steam64():
    with mock.patch("winreg.OpenKey") as open_key, \
         mock.patch("winreg.QueryValueEx") as query:
        open_key.return_value.__enter__.return_value = "key"
        query.return_value = (12345, 4)  # account id DWORD
        assert steam.get_logged_in_steam64() == str(76561197960265728 + 12345)


def test_steam_not_running_falls_back_to_loginusers(tmp_path):
    steam_dir = tmp_path / "Steam"
    (steam_dir / "config").mkdir(parents=True)
    (steam_dir / "config" / "loginusers.vdf").write_text(SAMPLE_VDF, encoding="utf-8")

    def fake_query(key, name):
        if name == "ActiveUser":
            return (0, 4)  # Steam installed but nobody logged in right now
        if name == "SteamPath":
            return (str(steam_dir), 1)
        raise FileNotFoundError

    with mock.patch("winreg.OpenKey") as open_key, \
         mock.patch("winreg.QueryValueEx", side_effect=fake_query):
        open_key.return_value.__enter__.return_value = "key"
        assert steam.get_logged_in_steam64() == "76561198000000002"


def test_no_steam_at_all():
    with mock.patch("winreg.OpenKey", side_effect=FileNotFoundError):
        assert steam.get_logged_in_steam64() is None
