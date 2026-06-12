# DiscordFaceitStatus v2.0 "Easy Mode" Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the Faceit→Discord presence tray app into a zero-friction tool for non-technical players: download one exe, type a nickname into a friendly window, done — with auto-start, toast error feedback, fewer API calls, and the live-timer/grace-period bugs fixed.

**Architecture:** Same module layout (config / faceit_api / monitor / discord_rpc / tray) plus two new stdlib-only modules: `gui.py` (tkinter first-run wizard + settings window) and `autostart.py` (HKCU Run registry key). Config and logs move to `%APPDATA%\FaceitDiscordStatus\` with one-time migration from the old `.env`/local `config.json`. `python-dotenv` is removed. Spec: `docs/superpowers/specs/2026-06-12-easy-mode-overhaul-design.md`.

**Tech Stack:** Python 3.13, requests, pypresence, pystray, Pillow, tkinter (stdlib), winreg (stdlib), pytest for tests, PyInstaller one-file build.

**Verification command for every task:** `python -m pytest tests/ -v` from the repo root (`D:\GitHub\DiscordFaceitStatus`).

---

### Task 1: Test infrastructure

**Files:**
- Create: `requirements-dev.txt`
- Create: `tests/` (directory, no `__init__.py` needed)

- [ ] **Step 1: Create dev requirements**

`requirements-dev.txt`:
```
-r requirements.txt
pytest>=8.0.0
```

- [ ] **Step 2: Install and verify pytest runs**

Run: `python -m pip install -r requirements-dev.txt`
Then: `python -m pytest tests/ -v` → Expected: "no tests ran" (exit code 5 is fine at this point).

- [ ] **Step 3: Commit**

```bash
git add requirements-dev.txt
git commit -m "chore: add pytest dev requirements"
```

---

### Task 2: Config rewrite — %APPDATA% storage, nickname in config.json, migration, thread safety

**Files:**
- Rewrite: `src/config.py`
- Test: `tests/test_config.py`

Removes: python-dotenv usage, `update_env_value()` (which logged the API key), the dead module-level `config = Config()` singleton, `print()` error path.

- [ ] **Step 1: Write the failing tests**

`tests/test_config.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL — `Config.__init__() got an unexpected keyword argument 'data_dir'` (or import errors).

- [ ] **Step 3: Rewrite `src/config.py`**

```python
"""Configuration management for Faceit Discord Rich Presence."""

import json
import logging
import os
import sys
import threading
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

APP_NAME = "FaceitDiscordStatus"

# Embedded credentials: compiled into the executable so players need zero setup.
EMBEDDED_API_KEY = "d059caf3-bf65-44ee-8391-133a1c49f76b"
EMBEDDED_DISCORD_APP_ID = "1459995747989848238"


def get_app_root() -> Path:
    """Directory containing the exe (frozen) or the project root (dev)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent


def get_data_dir() -> Path:
    """Per-user writable data directory (%APPDATA%\\FaceitDiscordStatus)."""
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home()
    return base / APP_NAME


class Config:
    """User settings stored in config.json under the per-user data directory."""

    DEFAULT_SETTINGS = {
        "faceit_nickname": "",
        "poll_interval": 45,  # seconds between checks while not in a match
        "enabled": True,

        # Match display settings
        "show_map": True,
        "show_score": True,
        "show_elo": True,  # ELO at stake per match
        "show_avg_elo": True,
        "show_kda": True,

        # Player statistics settings
        "show_current_elo": True,
        "show_country": True,
        "show_region_rank": True,
        "show_today_elo": True,
        "show_fpl": True,
    }

    def __init__(self, data_dir: Optional[Path] = None, legacy_dir: Optional[Path] = None):
        self._lock = threading.RLock()
        self.data_dir = data_dir or get_data_dir()
        self.config_path = self.data_dir / "config.json"
        self.faceit_api_key = EMBEDDED_API_KEY
        self.discord_app_id = EMBEDDED_DISCORD_APP_ID
        self.settings = self.DEFAULT_SETTINGS.copy()
        if not self.config_path.exists():
            self._migrate_legacy(legacy_dir or get_app_root())
        self._load()

    def _migrate_legacy(self, legacy_dir: Path) -> None:
        """One-time import from the pre-2.0 layout (.env + config.json next to the exe)."""
        migrated: dict[str, Any] = {}

        legacy_config = legacy_dir / "config.json"
        if legacy_config.exists():
            try:
                with open(legacy_config, "r", encoding="utf-8") as f:
                    data = json.load(f)
                migrated.update(
                    {k: v for k, v in data.items() if k in self.DEFAULT_SETTINGS}
                )
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Could not migrate legacy config.json: {e}")

        legacy_env = legacy_dir / ".env"
        if legacy_env.exists():
            try:
                for line in legacy_env.read_text(encoding="utf-8").splitlines():
                    if line.startswith("FACEIT_NICKNAME="):
                        nickname = line.split("=", 1)[1].strip()
                        if nickname:
                            migrated["faceit_nickname"] = nickname
            except OSError as e:
                logger.warning(f"Could not migrate legacy .env: {e}")

        if migrated:
            logger.info(f"Migrating legacy settings from {legacy_dir}")
            self.settings.update(migrated)
            self._save_settings()

    def _load(self) -> None:
        if not self.config_path.exists():
            return
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.settings = {**self.DEFAULT_SETTINGS, **json.load(f)}
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to load {self.config_path}: {e} - using defaults")
            self.settings = self.DEFAULT_SETTINGS.copy()

    def _save_settings(self) -> bool:
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            tmp_path = self.config_path.with_suffix(".json.tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2)
            tmp_path.replace(self.config_path)
            return True
        except OSError as e:
            logger.error(f"Failed to save settings: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self.settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self.settings[key] = value
            self._save_settings()

    def update(self, values: dict) -> None:
        """Set several settings with a single save."""
        with self._lock:
            self.settings.update(values)
            self._save_settings()

    @property
    def faceit_nickname(self) -> str:
        return self.get("faceit_nickname", "")

    @faceit_nickname.setter
    def faceit_nickname(self, value: str) -> None:
        self.set("faceit_nickname", value)

    @property
    def poll_interval(self) -> int:
        return self.get("poll_interval", 45)

    @property
    def is_enabled(self) -> bool:
        return self.get("enabled", True)

    @is_enabled.setter
    def is_enabled(self, value: bool) -> None:
        self.set("enabled", value)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_config.py -v`
Expected: 5 passed.

Note: other modules (`main.py`) still reference removed APIs — that's fine, they're rewritten in later tasks; only the test suite must pass per task.

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "refactor: store config in %APPDATA%, migrate legacy .env, drop dotenv"
```

---

### Task 3: Slim utils.py — logging to the data dir, drop dead helpers

**Files:**
- Rewrite: `src/utils.py`

`format_elo`, `format_kda`, `calculate_kd_ratio`, and the duplicate `get_app_root` are dead — remove. Logging moves to `%APPDATA%\FaceitDiscordStatus\logs\` with rotation.

- [ ] **Step 1: Rewrite `src/utils.py`**

```python
"""Logging setup for Faceit Discord Rich Presence."""

import logging
import sys
from logging.handlers import RotatingFileHandler

from .config import get_data_dir


def setup_logging(debug: bool = False) -> None:
    """Log to %APPDATA%\\FaceitDiscordStatus\\logs with rotation, plus stdout."""
    level = logging.DEBUG if debug else logging.INFO

    log_dir = get_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            RotatingFileHandler(
                log_dir / "faceit_discord.log",
                maxBytes=1_000_000,
                backupCount=2,
                encoding="utf-8",
            ),
            logging.StreamHandler(sys.stdout),
        ],
    )

    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)
```

- [ ] **Step 2: Verify it imports and tests still pass**

Run: `python -c "from src.utils import setup_logging"` then `python -m pytest tests/ -v`
Expected: import OK, all tests pass.

- [ ] **Step 3: Commit**

```bash
git add src/utils.py
git commit -m "refactor: rotate logs in data dir, remove dead utility helpers"
```

---

### Task 4: faceit_api — shared timestamp parsing, per-host rate limit, single-call match detection

**Files:**
- Modify: `src/faceit_api.py`
- Test: `tests/test_faceit_api.py`

Changes: add `parse_timestamp()` used for both `started_at`/`finished_at`; per-host rate limiter with a lock (lcrypt no longer consumes the official API's slot); `get_ongoing_match()` becomes ONE v4 history request (delete the speculative `/players/{id}` probe and the unofficial v5 endpoint) and **raises** on failure instead of silently returning None; lcrypt outage logged at warning once per outage.

- [ ] **Step 1: Write the failing tests**

`tests/test_faceit_api.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_faceit_api.py -v`
Expected: FAIL — `ImportError: cannot import name 'parse_timestamp'`.

- [ ] **Step 3: Apply the changes to `src/faceit_api.py`**

3a. Imports/constants at the top: add `import threading` and `from datetime import datetime`; delete the `MATCH_HISTORY_URL = "https://api.faceit.com/match-history/v5"` constant. Add below the constants:

```python
def parse_timestamp(value) -> Optional[int]:
    """Normalize a Faceit timestamp (unix int or ISO 8601 string) to a unix int."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(
                datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
            )
        except ValueError:
            return None
    return None
```

3b. In `FaceitAPI.__init__`, replace the rate-limiting fields and add the lcrypt warn flag:

```python
        # Rate limiting (per host, guarded for cross-thread use)
        self._rate_lock = threading.Lock()
        self._last_request_time: dict[str, float] = {}
        self._min_request_interval = 1.0  # seconds between requests per host
        self._lcrypt_warned = False
```

3c. Replace `_rate_limit`:

```python
    def _rate_limit(self, host: str = "official") -> None:
        """Ensure we don't exceed rate limits (tracked per host)."""
        with self._rate_lock:
            elapsed = time.time() - self._last_request_time.get(host, 0)
            if elapsed < self._min_request_interval:
                time.sleep(self._min_request_interval - elapsed)
            self._last_request_time[host] = time.time()
```

3d. In `get_live_match_info`: change `self._rate_limit()` → `self._rate_limit("lcrypt")`, and replace the final `except Exception` block with warn-once behavior. Also reset the flag on success — add `self._lcrypt_warned = False` directly before `return live_info`:

```python
        except Exception as e:
            if not self._lcrypt_warned:
                self._lcrypt_warned = True
                logger.warning(f"Live match API unavailable, falling back to official API: {e}")
            else:
                logger.debug(f"[third-party] Error: {e}")
            return None
```

3e. Replace `get_ongoing_match`, and **delete** `_check_recent_matches_for_ongoing` and `_check_v5_match_history` entirely:

```python
    def get_ongoing_match(self, player_id: str) -> Optional[str]:
        """Return the player's active match ID, or None.

        Raises:
            FaceitAPIError: If the request fails. Callers rely on this to
                distinguish "definitely no match" from a transient API error,
                so a hiccup doesn't wipe the presence.
        """
        data = self._request(
            f"/players/{player_id}/history",
            {"game": CS2_GAME_ID, "limit": 5},
        )
        for match in data.get("items", []):
            status = match.get("status", "").upper()
            if status in ("READY", "ONGOING", "VOTING", "CONFIGURING", "LIVE"):
                return match.get("match_id") or None
        return None
```

3f. In `get_match_details`, replace the timestamp block (the `started_at = data.get(...)` through the ISO-conversion `try/except`) with:

```python
        # Get timestamps (API may return unix ints or ISO strings)
        started_at = parse_timestamp(data.get("started_at"))
        finished_at = parse_timestamp(data.get("finished_at"))
```

(The inline `from datetime import datetime` import disappears with this block.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/ -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/faceit_api.py tests/test_faceit_api.py
git commit -m "refactor: one-call match detection, per-host rate limits, shared timestamp parsing"
```

---

### Task 5: discord_rpc — fix live timer, Train map, ELO-at-stake; only clear when something is shown

**Files:**
- Modify: `src/discord_rpc.py`
- Test: `tests/test_discord_rpc.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_discord_rpc.py`:
```python
"""Tests for Discord presence formatting helpers."""

from src.discord_rpc import format_elo_at_stake, get_map_image


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_discord_rpc.py -v`
Expected: FAIL — cannot import `format_elo_at_stake` / `get_map_image`.

- [ ] **Step 3: Apply the changes to `src/discord_rpc.py`**

3a. Add module-level helpers after the imports (content of the dict copied from the old `_get_map_image`, plus Train):

```python
# Discord asset keys for CS2 maps. Supports both official names (de_mirage)
# and display names (Mirage, Dust II). These must be uploaded to the Discord app.
MAP_IMAGES = {
    "de_mirage": "map_mirage",
    "mirage": "map_mirage",
    "de_inferno": "map_inferno",
    "inferno": "map_inferno",
    "de_dust2": "map_dust2",
    "dust2": "map_dust2",
    "dust ii": "map_dust2",
    "de_nuke": "map_nuke",
    "nuke": "map_nuke",
    "de_overpass": "map_overpass",
    "overpass": "map_overpass",
    "de_ancient": "map_ancient",
    "ancient": "map_ancient",
    "de_anubis": "map_anubis",
    "anubis": "map_anubis",
    "de_vertigo": "map_vertigo",
    "vertigo": "map_vertigo",
    "de_train": "map_train",
    "train": "map_train",
}


def get_map_image(map_name: str) -> str:
    """Get the Discord asset key for a CS2 map, falling back to the Faceit logo."""
    return MAP_IMAGES.get(map_name.lower(), "faceit_logo")


def format_elo_at_stake(elo_at_stake: str) -> Optional[str]:
    """Format the third-party API's "+25/-25" ELO-at-stake string for display.

    Returns "±25" when gain and loss match, the raw "+30/-20" when asymmetric,
    or None when there is nothing to show.
    """
    if not elo_at_stake:
        return None
    parts = [p.strip() for p in elo_at_stake.split("/")]
    gain = parts[0] if parts and parts[0] else ""
    loss = parts[1] if len(parts) > 1 and parts[1] else ""
    if gain and loss:
        if gain.lstrip("+") == loss.lstrip("-"):
            return f"±{gain.lstrip('+')}"
        return f"{gain}/{loss}"
    return gain or loss or None
```

3b. Delete the `_get_map_image` method; replace its four call sites (`update_lobby`, `update_live`, `update_finished`, `update_live_simple`) with `get_map_image(...)` (same arguments).

3c. In `update_live_simple`: add parameter `match_start: Optional[int] = None` (after `fpl_status`); replace the ELO-at-stake block

```python
        if show_elo and elo_at_stake:
            state_parts.append(f"±{elo_at_stake.replace('+', '').replace('-', '').split('/')[0]}")
```
with
```python
        formatted_stake = format_elo_at_stake(elo_at_stake) if elo_at_stake else None
        if show_elo and formatted_stake:
            state_parts.append(formatted_stake)
```
and change `start=int(time.time()),` to `start=match_start,` — **this fixes the elapsed timer resetting every poll**. (`_update` already skips `start` when None.)

3d. Only clear when a presence is actually shown (stops a needless IPC call every idle poll): in `__init__` add `self._presence_set = False`; in `clear()` add at the top, right after the existing connected guard:

```python
        if not self._presence_set:
            return
```
and after the successful `self.rpc.clear()` add `self._presence_set = False`. In `_update`, after the successful `self.rpc.update(**kwargs)` add `self._presence_set = True`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/ -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/discord_rpc.py tests/test_discord_rpc.py
git commit -m "fix: stable live timer, Train map art, asymmetric ELO display, no idle clear spam"
```

---

### Task 6: monitor rewrite — state machine, grace period, adaptive polling, live nickname change

**Files:**
- Rewrite: `src/monitor.py`
- Test: `tests/test_monitor.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_monitor.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_monitor.py -v`
Expected: FAIL — cannot import `GRACE_MISSES` / `parse_duration_to_seconds`.

- [ ] **Step 3: Rewrite `src/monitor.py`**

```python
"""Main monitoring loop for Faceit match status."""

import logging
import threading
import time
from typing import Callable, Optional

from .config import Config
from .discord_rpc import DiscordRPC
from .faceit_api import FaceitAPI, FaceitAPIError, LiveMatchInfo, MatchInfo

logger = logging.getLogger(__name__)

# Poll faster while a match is live so the score stays fresh.
LIVE_POLL_INTERVAL = 20  # seconds
# Consecutive "no match found" polls before an active presence is cleared.
GRACE_MISSES = 3
# How long the post-match result stays on the presence before clearing.
FINISHED_LINGER = 120  # seconds


def parse_duration_to_seconds(duration: str) -> Optional[int]:
    """Parse a "MM:SS" or "H:MM:SS" duration string into seconds."""
    if not duration:
        return None
    try:
        numbers = [int(p) for p in duration.strip().split(":")]
    except ValueError:
        return None
    if len(numbers) == 2:
        return numbers[0] * 60 + numbers[1]
    if len(numbers) == 3:
        return numbers[0] * 3600 + numbers[1] * 60 + numbers[2]
    return None


class MatchMonitor:
    """Monitors Faceit matches and updates Discord presence."""

    def __init__(self, config: Config, faceit: Optional[FaceitAPI] = None):
        self.config = config
        self.faceit = faceit or FaceitAPI(config.faceit_api_key)
        self.discord = DiscordRPC(config.discord_app_id)

        self._running = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self._player_lock = threading.Lock()
        self._player_id: Optional[str] = None
        self._player_nickname: str = config.faceit_nickname

        # Match state
        self._in_live_match = False
        self._current_match_id: Optional[str] = None
        self._last_match_status: Optional[str] = None
        self._match_start: Optional[int] = None
        self._match_url: Optional[str] = None
        self._miss_count = 0
        self._finished_shown_at: Optional[float] = None

        # One-shot notification flags so toasts are not repeated every poll
        self._notified_discord_down = False
        self._notified_player_error = False
        self._notified_api_outage = False

        # Callbacks for UI updates
        self._on_status_change: Optional[Callable[[str], None]] = None
        self._on_error: Optional[Callable[[str], None]] = None
        self._on_notify: Optional[Callable[[str, str], None]] = None

    def set_callbacks(
        self,
        on_status_change: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_notify: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        """Set callbacks: status line, error line, and (title, message) toasts."""
        self._on_status_change = on_status_change
        self._on_error = on_error
        self._on_notify = on_notify

    def _notify_status(self, status: str) -> None:
        if self._on_status_change:
            try:
                self._on_status_change(status)
            except Exception:
                pass

    def _notify_error(self, error: str) -> None:
        if self._on_error:
            try:
                self._on_error(error)
            except Exception:
                pass

    def _notify_toast(self, title: str, message: str) -> None:
        if self._on_notify:
            try:
                self._on_notify(title, message)
            except Exception:
                pass

    def start(self) -> bool:
        """Start the monitoring loop. Discord/player problems are retried inside
        the loop (with a toast), so this only fails when no nickname is set."""
        if self._running:
            return True
        if not self.config.faceit_nickname:
            self._notify_error("No FACEIT username configured")
            return False

        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._monitor_loop, name="match-monitor", daemon=True
        )
        self._thread.start()
        self._notify_status("Starting...")
        logger.info("Match monitor started")
        return True

    def stop(self) -> None:
        """Stop the loop, then clear and disconnect the presence."""
        if not self._running:
            return
        self._running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)
        self.discord.clear()
        self.discord.disconnect()
        self._reset_match_state()
        self._notify_status("Stopped")
        logger.info("Match monitor stopped")

    def is_running(self) -> bool:
        return self._running

    def update_player(self, nickname: str) -> tuple[bool, Optional[str]]:
        """Switch to tracking a different player. Safe to call while running
        (used by the settings window - no app restart needed)."""
        try:
            player = self.faceit.get_player_by_nickname(nickname)
        except FaceitAPIError as e:
            return False, str(e)
        with self._player_lock:
            self._player_id = player.player_id
            self._player_nickname = player.nickname
        self._reset_match_state()
        self.config.faceit_nickname = player.nickname
        self.discord.clear()
        self._notify_status(f"Tracking {player.nickname}")
        logger.info(f"Now tracking {player.nickname}")
        return True, None

    # --- monitor loop -----------------------------------------------------

    def _monitor_loop(self) -> None:
        consecutive_errors = 0
        max_errors = 5

        while self._running:
            interval = self.config.poll_interval
            try:
                if not self.config.is_enabled:
                    self.discord.clear()
                elif self._ensure_player() and self._ensure_discord():
                    self._check_match()
                    consecutive_errors = 0
                    self._notified_api_outage = False
                    if self._in_live_match:
                        interval = min(interval, LIVE_POLL_INTERVAL)
            except FaceitAPIError as e:
                consecutive_errors += 1
                logger.warning(f"Faceit API error: {e}")
                if consecutive_errors >= max_errors:
                    interval = self.config.poll_interval * 2
                    self._notify_error(f"API errors: {e}")
                    if not self._notified_api_outage:
                        self._notified_api_outage = True
                        self._notify_toast(
                            "Can't reach Faceit",
                            "Connection problems - retrying automatically.",
                        )
            except Exception as e:
                consecutive_errors += 1
                logger.exception(f"Unexpected error in monitor loop: {e}")
                if consecutive_errors >= max_errors:
                    interval = self.config.poll_interval * 2
                    self._notify_error(f"Errors: {e}")

            self._stop_event.wait(interval)

    def _ensure_player(self) -> bool:
        """Resolve the configured nickname to a player ID, retrying each poll."""
        with self._player_lock:
            if self._player_id:
                return True
            nickname = self.config.faceit_nickname
        try:
            player = self.faceit.get_player_by_nickname(nickname)
        except FaceitAPIError as e:
            logger.warning(f"Could not look up player '{nickname}': {e}")
            if not self._notified_player_error:
                self._notified_player_error = True
                self._notify_toast(
                    "Faceit player lookup failed",
                    f"Couldn't look up '{nickname}'. Check the spelling in "
                    "Settings, or your internet connection.",
                )
            self._notify_error(f"Player lookup failed: {e}")
            return False
        with self._player_lock:
            self._player_id = player.player_id
            self._player_nickname = player.nickname
        self._notified_player_error = False
        self._notify_status(f"Tracking {player.nickname}")
        logger.info(f"Found player: {player.nickname} (ELO: {player.elo})")
        return True

    def _ensure_discord(self) -> bool:
        """Connect to Discord if needed, toasting once when it's not running."""
        if self.discord.connected:
            return True
        if self.discord.connect():
            self._notified_discord_down = False
            return True
        if not self._notified_discord_down:
            self._notified_discord_down = True
            self._notify_toast(
                "Discord not found",
                "Start Discord and your match status will connect automatically.",
            )
        self._notify_status("Waiting for Discord...")
        return False

    # --- match state machine ----------------------------------------------

    def _check_match(self) -> None:
        with self._player_lock:
            player_id = self._player_id
            nickname = self._player_nickname
        if not player_id:
            return

        # Primary: third-party live API (rich data, one request)
        live_info = self.faceit.get_live_match_info(nickname)
        if live_info and live_info.is_live:
            self._on_live_match(live_info, player_id)
            return

        # Secondary: official API for lobby/ongoing states (one request)
        match_id = self.faceit.get_ongoing_match(player_id)
        if match_id:
            match = self.faceit.get_match_details(match_id, player_id)
            self._on_official_match(match)
            return

        self._on_no_match(player_id)

    def _on_live_match(self, live_info: LiveMatchInfo, player_id: str) -> None:
        self._miss_count = 0
        self._finished_shown_at = None
        if not self._in_live_match:
            logger.info(f"Live match detected: {live_info.map_name}")
            self._in_live_match = True
            elapsed = parse_duration_to_seconds(live_info.duration)
            self._match_start = int(time.time()) - (elapsed or 0)
            self._resolve_match_url(player_id)
        self._update_live_presence(live_info)

    def _resolve_match_url(self, player_id: str) -> None:
        """Best-effort lookup of the match ID/URL (for the tray's View Match
        and the post-match result). Runs once per match."""
        try:
            match_id = self.faceit.get_ongoing_match(player_id)
            if match_id:
                self._current_match_id = match_id
                match = self.faceit.get_match_details(match_id, player_id)
                self._match_url = match.match_url or None
        except FaceitAPIError as e:
            logger.debug(f"Could not resolve match URL: {e}")

    def _on_official_match(self, match: MatchInfo) -> None:
        self._miss_count = 0
        self._finished_shown_at = None
        if match.match_id != self._current_match_id:
            logger.info(f"New match detected: {match.match_id}")
            self._current_match_id = match.match_id
            self._match_url = match.match_url or None
        if match.status != self._last_match_status:
            logger.info(f"Match status changed: {match.status}")
            self._last_match_status = match.status
        if match.status == "ONGOING":
            if not self._in_live_match:
                self._in_live_match = True
                self._match_start = match.started_at or int(time.time())
        else:
            self._in_live_match = False
        self._update_presence(match)

    def _on_no_match(self, player_id: str) -> None:
        if self._finished_shown_at is not None:
            # Post-match result is showing; clear it once the linger expires.
            if time.time() - self._finished_shown_at >= FINISHED_LINGER:
                self._clear_presence()
                self._notify_status("No active match")
            return

        had_match = self._in_live_match or self._current_match_id is not None
        if not had_match:
            self._clear_presence()
            return

        self._miss_count += 1
        if self._miss_count < GRACE_MISSES:
            logger.debug(
                f"No match found ({self._miss_count}/{GRACE_MISSES}), keeping presence"
            )
            return

        # The match really is over - show the final result before clearing.
        if self._current_match_id and self._show_finished(player_id):
            return
        logger.info("Match ended")
        self._clear_presence()
        self._notify_status("No active match")

    def _show_finished(self, player_id: str) -> bool:
        try:
            match = self.faceit.get_match_details(self._current_match_id, player_id)
        except FaceitAPIError:
            return False
        if match.status != "FINISHED":
            return False
        self._in_live_match = False
        self._finished_shown_at = time.time()
        self._update_presence(match)
        self._notify_status(f"Finished: {match.map_name}")
        return True

    def _reset_match_state(self) -> None:
        self._in_live_match = False
        self._current_match_id = None
        self._last_match_status = None
        self._match_start = None
        self._match_url = None
        self._miss_count = 0
        self._finished_shown_at = None

    def _clear_presence(self) -> None:
        self._reset_match_state()
        self.discord.clear()

    # --- presence formatting ------------------------------------------------

    def _update_live_presence(self, live_info: LiveMatchInfo) -> None:
        """Update Discord presence for a live match (third-party API data)."""
        show_map = self.config.get("show_map", True)
        show_score = self.config.get("show_score", True)
        show_elo = self.config.get("show_elo", True)
        show_current_elo = self.config.get("show_current_elo", True)
        show_country = self.config.get("show_country", True)
        show_region_rank = self.config.get("show_region_rank", True)
        show_today_elo = self.config.get("show_today_elo", True)
        show_fpl = self.config.get("show_fpl", True)

        score = f"{live_info.score_team1}:{live_info.score_team2}"
        self._notify_status(f"Live: {live_info.map_name} ({score})")

        # Determine FPL status to display
        fpl_status = None
        if "participate" not in live_info.fpl_status.lower():
            fpl_status = "FPL"
        elif "participate" not in live_info.fplc_status.lower():
            fpl_status = "FPL-C"

        self.discord.update_live_simple(
            map_name=live_info.map_name if show_map else None,
            score=score if show_score else None,
            elo_at_stake=live_info.elo_at_stake if show_elo else None,
            server=live_info.server,
            queue_name=live_info.queue_name,
            current_elo=live_info.current_elo if show_current_elo else None,
            country_flag=live_info.country_flag if show_country else None,
            region_rank=live_info.region_ranking if show_region_rank else None,
            today_elo=live_info.today_elo_change if show_today_elo else None,
            fpl_status=fpl_status if show_fpl else None,
            match_start=self._match_start,
            show_elo=show_elo,
            show_score=show_score,
            show_current_elo=show_current_elo,
            show_country=show_country,
            show_region_rank=show_region_rank,
            show_today_elo=show_today_elo,
            show_fpl=show_fpl,
        )

    def _update_presence(self, match: MatchInfo) -> None:
        """Update Discord presence from official-API match state."""
        show_map = self.config.get("show_map", True)
        show_avg_elo = self.config.get("show_avg_elo", True)
        show_kda = self.config.get("show_kda", True)
        show_elo = self.config.get("show_elo", True)
        show_score = self.config.get("show_score", True)

        if match.status in ("READY", "VOTING", "CONFIGURING"):
            self._notify_status(f"In lobby: {match.map_name}")
            self.discord.update_lobby(
                match,
                show_map=show_map,
                show_avg_elo=show_avg_elo,
            )

        elif match.status == "ONGOING":
            player_stats = None
            with self._player_lock:
                player_id = self._player_id
            if show_kda and player_id:
                player_stats = self.faceit.get_match_stats(match.match_id, player_id)

            score = f"{match.team1_score}-{match.team2_score}"
            self._notify_status(f"Live: {match.map_name} ({score})")
            self.discord.update_live(
                match,
                player_stats=player_stats,
                show_map=show_map,
                show_avg_elo=show_avg_elo,
                show_kda=show_kda,
                show_score=show_score,
            )

        elif match.status == "FINISHED":
            elo_change = None
            with self._player_lock:
                player_id = self._player_id
            if show_elo and player_id:
                elo_change = self.faceit.get_elo_change(player_id, match.match_id)

            self.discord.update_finished(
                match,
                elo_change=elo_change,
                show_elo=show_elo,
                show_score=show_score,
            )

        elif match.status == "CANCELLED":
            self._notify_status("Match cancelled")
            self._clear_presence()

    def get_current_match_url(self) -> Optional[str]:
        """URL for the tray's "View Match" - cached, no API call when known."""
        if self._match_url:
            return self._match_url
        with self._player_lock:
            player_id = self._player_id
        if not self._current_match_id or not player_id:
            return None
        try:
            match = self.faceit.get_match_details(self._current_match_id, player_id)
        except FaceitAPIError:
            return None
        self._match_url = match.match_url or None
        return self._match_url
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/ -v`
Expected: all pass (note: `test_finished_result_shown_then_cleared` exercises `_show_finished` via `_resolve_match_url` having cached `m1` — the FakeAPI returns the FINISHED details).

- [ ] **Step 5: Commit**

```bash
git add src/monitor.py tests/test_monitor.py
git commit -m "refactor: monitor state machine with grace period, adaptive polling, live nickname change"
```

---

### Task 7: autostart module — Start with Windows via HKCU Run key

**Files:**
- Create: `src/autostart.py`
- Test: `tests/test_autostart.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_autostart.py`:
```python
"""Tests for the Start-with-Windows registry helper (winreg mocked)."""

import sys
from unittest import mock

from src import autostart


def test_not_supported_when_not_frozen():
    # Tests never run frozen, so this must be False in dev mode.
    assert autostart.is_supported() is False


def test_enable_refuses_in_dev_mode():
    assert autostart.enable() is False


def test_is_enabled_checks_registry_value():
    with mock.patch("winreg.OpenKey") as open_key, \
         mock.patch("winreg.QueryValueEx") as query:
        open_key.return_value.__enter__.return_value = "key"
        query.return_value = ('"C:\\app.exe"', 1)
        assert autostart.is_enabled() is True

        query.side_effect = FileNotFoundError
        assert autostart.is_enabled() is False


def test_enable_writes_exe_path_when_frozen():
    with mock.patch.object(sys, "frozen", True, create=True), \
         mock.patch.object(sys, "executable", "C:\\app\\FaceitDiscordStatus.exe"), \
         mock.patch("winreg.OpenKey") as open_key, \
         mock.patch("winreg.SetValueEx") as set_value:
        open_key.return_value.__enter__.return_value = "key"
        assert autostart.enable() is True
        args = set_value.call_args[0]
        assert args[1] == "FaceitDiscordStatus"
        assert args[4] == '"C:\\app\\FaceitDiscordStatus.exe"'
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_autostart.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.autostart'`.

- [ ] **Step 3: Create `src/autostart.py`**

```python
"""Start-with-Windows toggle via the HKCU Run registry key."""

import logging
import sys

logger = logging.getLogger(__name__)

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "FaceitDiscordStatus"


def is_supported() -> bool:
    """Auto-start is only offered for the packaged exe on Windows."""
    return sys.platform == "win32" and bool(getattr(sys, "frozen", False))


def is_enabled() -> bool:
    if sys.platform != "win32":
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.QueryValueEx(key, _VALUE_NAME)
        return True
    except OSError:
        return False


def enable() -> bool:
    if not is_supported():
        return False
    import winreg
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, _VALUE_NAME, 0, winreg.REG_SZ, f'"{sys.executable}"')
        logger.info("Auto-start enabled")
        return True
    except OSError as e:
        logger.error(f"Failed to enable auto-start: {e}")
        return False


def disable() -> bool:
    if sys.platform != "win32":
        return False
    import winreg
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, _VALUE_NAME)
        logger.info("Auto-start disabled")
        return True
    except FileNotFoundError:
        return True
    except OSError as e:
        logger.error(f"Failed to disable auto-start: {e}")
        return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/ -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/autostart.py tests/test_autostart.py
git commit -m "feat: start-with-Windows toggle via HKCU Run key"
```

---

### Task 8: gui module — tkinter first-run wizard and settings window

**Files:**
- Create: `src/gui.py`

GUI code is verified by import + manual run; the logic it calls (Config, FaceitAPI, monitor.update_player, autostart) is already tested.

- [ ] **Step 1: Create `src/gui.py`**

```python
"""tkinter windows: first-run setup wizard and the settings window."""

import logging
import threading
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from . import autostart
from .config import Config
from .faceit_api import FaceitAPI, FaceitAPIError

logger = logging.getLogger(__name__)

DISPLAY_OPTIONS = [
    ("show_map", "Map name"),
    ("show_score", "Round score"),
    ("show_elo", "ELO at stake"),
    ("show_avg_elo", "Average lobby ELO"),
    ("show_kda", "K/D/A stats"),
    ("show_current_elo", "Current ELO"),
    ("show_country", "Country flag"),
    ("show_region_rank", "Regional rank"),
    ("show_today_elo", "Today's ELO change"),
    ("show_fpl", "FPL / FPL-C status"),
]


def _validate_nickname(api: FaceitAPI, nickname: str):
    """Look up a nickname on Faceit. Returns (PlayerInfo, None) or (None, error)."""
    try:
        return api.get_player_by_nickname(nickname), None
    except FaceitAPIError as e:
        msg = str(e)
        if "not found" in msg.lower():
            return None, (
                f"No Faceit player named '{nickname}' was found. "
                "Names are case-sensitive."
            )
        return None, (
            f"Couldn't reach Faceit ({msg}). "
            "Check your internet connection and try again."
        )


class FirstRunWizard:
    """Asks for the player's Faceit nickname, validating it before saving."""

    def __init__(self, config: Config, api: FaceitAPI):
        self.config = config
        self.api = api
        self.completed = False

        self.root = tk.Tk()
        self.root.title("Faceit Discord Status - Setup")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)

        frame = ttk.Frame(self.root, padding=20)
        frame.grid()

        ttk.Label(
            frame,
            text="Welcome! Let's get your Faceit status into Discord.",
            font=("Segoe UI", 11, "bold"),
        ).grid(column=0, row=0, columnspan=2, sticky="w")
        ttk.Label(frame, text="Enter your Faceit nickname (case-sensitive):").grid(
            column=0, row=1, columnspan=2, sticky="w", pady=(12, 4)
        )

        self.nickname_var = tk.StringVar()
        entry = ttk.Entry(frame, textvariable=self.nickname_var, width=34)
        entry.grid(column=0, row=2, columnspan=2, sticky="we")
        entry.focus_set()
        entry.bind("<Return>", lambda _e: self._save())

        self.status_var = tk.StringVar()
        ttk.Label(frame, textvariable=self.status_var, wraplength=330).grid(
            column=0, row=3, columnspan=2, sticky="w", pady=(8, 0)
        )

        self.autostart_var = tk.BooleanVar(value=False)
        if autostart.is_supported():
            ttk.Checkbutton(
                frame,
                text="Start automatically with Windows",
                variable=self.autostart_var,
            ).grid(column=0, row=4, columnspan=2, sticky="w", pady=(10, 0))

        self.save_btn = ttk.Button(frame, text="Save & Start", command=self._save)
        self.save_btn.grid(column=1, row=5, sticky="e", pady=(15, 0))

    def _save(self) -> None:
        nickname = self.nickname_var.get().strip()
        if not nickname:
            self.status_var.set("Please enter your nickname.")
            return
        self.save_btn.state(["disabled"])
        self.status_var.set("Checking nickname on Faceit...")

        def worker():
            player, error = _validate_nickname(self.api, nickname)
            self.root.after(0, lambda: self._on_validated(player, error))

        threading.Thread(target=worker, daemon=True).start()

    def _on_validated(self, player, error) -> None:
        if error:
            self.save_btn.state(["!disabled"])
            self.status_var.set(error)
            return
        self.config.update({"faceit_nickname": player.nickname})
        if autostart.is_supported() and self.autostart_var.get():
            autostart.enable()
        self.completed = True
        self.status_var.set(
            f"Found {player.nickname} - Level {player.skill_level}, "
            f"{player.elo:,} ELO. Starting!"
        )
        self.root.after(1200, self.root.destroy)

    def run(self) -> bool:
        """Show the wizard. Returns True once a nickname was saved."""
        self.root.mainloop()
        return self.completed


def run_first_run_wizard(config: Config, api: FaceitAPI) -> bool:
    """Run the first-run wizard on the calling (main) thread."""
    return FirstRunWizard(config, api).run()


class _SettingsWindow:
    """Settings window: nickname, display toggles, auto-start."""

    def __init__(
        self,
        config: Config,
        api: FaceitAPI,
        on_nickname_change: Callable[[str], tuple[bool, Optional[str]]],
    ):
        self.config = config
        self.api = api
        self.on_nickname_change = on_nickname_change

        self.root = tk.Tk()
        self.root.title("Faceit Discord Status - Settings")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)

        frame = ttk.Frame(self.root, padding=15)
        frame.grid()

        ttk.Label(frame, text="Faceit nickname:").grid(column=0, row=0, sticky="w")
        self.nickname_var = tk.StringVar(value=config.faceit_nickname)
        ttk.Entry(frame, textvariable=self.nickname_var, width=28).grid(
            column=1, row=0, sticky="we", padx=(8, 0)
        )

        ttk.Label(frame, text="Show in Discord status:", font=("Segoe UI", 9, "bold")).grid(
            column=0, row=1, columnspan=2, sticky="w", pady=(12, 4)
        )

        self.option_vars: dict[str, tk.BooleanVar] = {}
        row = 2
        for key, label in DISPLAY_OPTIONS:
            var = tk.BooleanVar(value=bool(config.get(key, True)))
            self.option_vars[key] = var
            ttk.Checkbutton(frame, text=label, variable=var).grid(
                column=row % 2, row=2 + (row - 2) // 2, sticky="w"
            )
            row += 1

        next_row = 2 + (row - 2 + 1) // 2

        self.autostart_var = tk.BooleanVar(value=autostart.is_enabled())
        if autostart.is_supported():
            ttk.Checkbutton(
                frame,
                text="Start automatically with Windows",
                variable=self.autostart_var,
            ).grid(column=0, row=next_row, columnspan=2, sticky="w", pady=(12, 0))
        next_row += 1

        self.status_var = tk.StringVar()
        ttk.Label(frame, textvariable=self.status_var, wraplength=330).grid(
            column=0, row=next_row, columnspan=2, sticky="w", pady=(8, 0)
        )
        next_row += 1

        buttons = ttk.Frame(frame)
        buttons.grid(column=0, row=next_row, columnspan=2, sticky="e", pady=(12, 0))
        self.save_btn = ttk.Button(buttons, text="Save", command=self._save)
        self.save_btn.grid(column=0, row=0, padx=(0, 8))
        ttk.Button(buttons, text="Cancel", command=self.root.destroy).grid(
            column=1, row=0
        )

    def _save(self) -> None:
        nickname = self.nickname_var.get().strip()
        if not nickname:
            self.status_var.set("Nickname cannot be empty.")
            return
        self.save_btn.state(["disabled"])
        self.status_var.set("Saving...")

        def worker():
            error = None
            if nickname != self.config.faceit_nickname:
                ok, err = self.on_nickname_change(nickname)
                if not ok:
                    error = (
                        f"Couldn't switch to '{nickname}': {err}. "
                        "Check the spelling (names are case-sensitive)."
                    )
            self.root.after(0, lambda: self._on_saved(error))

        threading.Thread(target=worker, daemon=True).start()

    def _on_saved(self, error: Optional[str]) -> None:
        if error:
            self.save_btn.state(["!disabled"])
            self.status_var.set(error)
            return
        self.config.update(
            {key: var.get() for key, var in self.option_vars.items()}
        )
        if autostart.is_supported():
            if self.autostart_var.get():
                autostart.enable()
            else:
                autostart.disable()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


_settings_lock = threading.Lock()
_settings_open = False


def open_settings_window(
    config: Config,
    api: FaceitAPI,
    on_nickname_change: Callable[[str], tuple[bool, Optional[str]]],
) -> None:
    """Open the settings window in a background thread (one at a time).

    pystray owns the main thread's message loop, so each settings window gets
    its own thread with its own Tk instance and mainloop.
    """
    global _settings_open
    with _settings_lock:
        if _settings_open:
            return
        _settings_open = True

    def runner():
        global _settings_open
        try:
            _SettingsWindow(config, api, on_nickname_change).run()
        except Exception:
            logger.exception("Settings window crashed")
        finally:
            with _settings_lock:
                _settings_open = False

    threading.Thread(target=runner, daemon=True, name="settings-window").start()
```

- [ ] **Step 2: Verify it imports and the suite passes**

Run: `python -c "from src.gui import run_first_run_wizard, open_settings_window"` then `python -m pytest tests/ -v`
Expected: import OK, all tests pass.

- [ ] **Step 3: Commit**

```bash
git add src/gui.py
git commit -m "feat: tkinter first-run wizard and settings window"
```

---

### Task 9: tray rewrite — slim menu, toasts, no VBScript/PowerShell, no restart

**Files:**
- Rewrite: `src/tray.py`

Deletes `_windows_input_box`, `_windows_message_box`, `_windows_checkbox_dialog`, `_restart_application` (os.execv), the per-stat submenus, and the desynced local `_enabled` flag.

- [ ] **Step 1: Rewrite `src/tray.py`**

```python
"""System tray icon and menu."""

import logging
import sys
import webbrowser
from pathlib import Path
from typing import Callable, Optional, TYPE_CHECKING

from PIL import Image
import pystray
from pystray import Menu, MenuItem

from . import autostart

if TYPE_CHECKING:
    from .config import Config

logger = logging.getLogger(__name__)


class SystemTray:
    """Manages the system tray icon, menu, and toast notifications."""

    def __init__(
        self,
        config: "Config",
        on_toggle: Optional[Callable[[bool], None]] = None,
        get_match_url: Optional[Callable[[], Optional[str]]] = None,
        open_settings: Optional[Callable[[], None]] = None,
    ):
        self.config = config
        self.on_toggle = on_toggle
        self.get_match_url = get_match_url
        self.open_settings = open_settings

        self._status = "Starting..."
        self._icon: Optional[pystray.Icon] = None

    def _create_icon_image(self) -> Image.Image:
        """Load the tray icon (bundled in _MEIPASS when frozen)."""
        if getattr(sys, "frozen", False):
            base_path = Path(sys._MEIPASS)
        else:
            base_path = Path(__file__).parent.parent

        icon_path = base_path / "assets" / "tray_icon.png"
        if icon_path.exists():
            try:
                img = Image.open(icon_path)
                if img.mode != "RGBA":
                    img = img.convert("RGBA")
                return img.resize((64, 64), Image.Resampling.LANCZOS)
            except Exception as e:
                logger.warning(f"Failed to load icon: {e}")

        # Fallback: plain orange square (Faceit color)
        return Image.new("RGB", (64, 64), color=(255, 85, 0))

    def _create_menu(self) -> Menu:
        items = [
            MenuItem(lambda text: f"Status: {self._status}", None, enabled=False),
            MenuItem(
                lambda text: f"Tracking: {self.config.faceit_nickname or 'not set'}",
                None,
                enabled=False,
            ),
            Menu.SEPARATOR,
            MenuItem(
                "Show match status in Discord",
                self._toggle_presence,
                checked=lambda item: self.config.is_enabled,
            ),
            MenuItem("View Current Match", self._open_match),
            Menu.SEPARATOR,
            MenuItem("Settings...", self._open_settings),
        ]
        if autostart.is_supported():
            items.append(
                MenuItem(
                    "Start with Windows",
                    self._toggle_autostart,
                    checked=lambda item: autostart.is_enabled(),
                )
            )
        items += [Menu.SEPARATOR, MenuItem("Exit", self._exit)]
        return Menu(*items)

    def _toggle_presence(self, icon: pystray.Icon, item: MenuItem) -> None:
        new_state = not self.config.is_enabled
        if self.on_toggle:
            self.on_toggle(new_state)
        icon.update_menu()
        logger.info(f"Rich presence {'enabled' if new_state else 'disabled'}")

    def _toggle_autostart(self, icon: pystray.Icon, item: MenuItem) -> None:
        if autostart.is_enabled():
            autostart.disable()
        else:
            autostart.enable()
        icon.update_menu()

    def _open_settings(self, icon: pystray.Icon, item: MenuItem) -> None:
        if self.open_settings:
            self.open_settings()

    def _open_match(self, icon: pystray.Icon, item: MenuItem) -> None:
        if self.get_match_url:
            url = self.get_match_url()
            if url:
                webbrowser.open(url)
                logger.info(f"Opened match URL: {url}")
            else:
                self.notify("No active match", "You're not in a match right now.")

    def _exit(self, icon: pystray.Icon, item: MenuItem) -> None:
        logger.info("Exit requested from tray")
        icon.stop()

    def update_status(self, status: str) -> None:
        """Update the status line shown in the tray menu."""
        self._status = status
        if self._icon:
            self._icon.update_menu()

    def notify(self, title: str, message: str) -> None:
        """Show a Windows toast notification from the tray icon."""
        if self._icon:
            try:
                self._icon.notify(message, title)
            except Exception as e:
                logger.debug(f"Toast notification failed: {e}")

    def run(self) -> None:
        """Run the tray icon on the calling thread (blocks until Exit)."""
        self._icon = pystray.Icon(
            "Faceit Discord Status",
            self._create_icon_image(),
            "Faceit Discord Status",
            self._create_menu(),
        )
        self._icon.run()

    def stop(self) -> None:
        if self._icon:
            self._icon.stop()
```

- [ ] **Step 2: Verify import + suite**

Run: `python -c "from src.tray import SystemTray"` then `python -m pytest tests/ -v`
Expected: import OK, all tests pass.

- [ ] **Step 3: Commit**

```bash
git add src/tray.py
git commit -m "refactor: slim tray menu with toasts; drop VBScript/PowerShell dialogs and restart"
```

---

### Task 10: main rewrite — wiring, first-run wizard, ordered shutdown

**Files:**
- Rewrite: `src/main.py`
- Modify: `src/__init__.py` (version bump)

- [ ] **Step 1: Rewrite `src/main.py`**

```python
"""Main entry point for Faceit Discord Rich Presence."""

import logging
import signal
import sys

from .config import Config
from .faceit_api import FaceitAPI
from .gui import open_settings_window, run_first_run_wizard
from .monitor import MatchMonitor
from .tray import SystemTray
from .utils import setup_logging

logger = logging.getLogger(__name__)


def main() -> int:
    """Main entry point. Returns the process exit code."""
    setup_logging(debug="--debug" in sys.argv)
    logger.info("Starting Faceit Discord Rich Presence")

    config = Config()  # loads from %APPDATA%, migrating any legacy .env/config
    api = FaceitAPI(config.faceit_api_key)

    if not config.faceit_nickname:
        logger.info("No nickname configured - showing first-run setup")
        if not run_first_run_wizard(config, api):
            logger.info("Setup cancelled by user")
            return 0

    monitor = MatchMonitor(config, faceit=api)

    def on_toggle(enabled: bool) -> None:
        config.is_enabled = enabled
        tray.update_status(
            "Checking for matches..." if enabled else "Presence disabled"
        )

    tray = SystemTray(
        config=config,
        on_toggle=on_toggle,
        get_match_url=monitor.get_current_match_url,
        open_settings=lambda: open_settings_window(
            config, api, monitor.update_player
        ),
    )

    monitor.set_callbacks(
        on_status_change=tray.update_status,
        on_error=lambda err: tray.update_status(f"Error: {err}"),
        on_notify=tray.notify,
    )

    # Ctrl+C / termination: stop the tray loop; cleanup runs after run() returns.
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}")
        tray.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if not monitor.start():
        logger.error("Failed to start monitor")
        return 1

    logger.info("Running system tray")
    tray.run()  # blocks until Exit is chosen

    monitor.stop()  # clears presence, disconnects Discord, joins the thread
    logger.info("Shutdown complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Bump version in `src/__init__.py`**

Replace the version line with: `__version__ = "2.0.0"`

- [ ] **Step 3: Verify imports + suite**

Run: `python -c "from src.main import main"` then `python -m pytest tests/ -v`
Expected: import OK, all tests pass.

- [ ] **Step 4: Commit**

```bash
git add src/main.py src/__init__.py
git commit -m "refactor: wire first-run wizard, settings window, toasts, ordered shutdown"
```

---

### Task 11: Packaging — requirements, PyInstaller spec, build.bat

**Files:**
- Modify: `requirements.txt` (remove `python-dotenv`)
- Modify: `FaceitDiscordStatus.spec` (remove `.env.example` from `datas`)
- Modify: `build.bat` (remove `dist\.env` creation; refresh dist README text)
- Modify: `.gitignore` (ensure `dist/`, `build/`, `__pycache__/` are ignored)
- Delete from git: `config.json`, `dist/README.txt`, `dist/config.json` (stale committed artifacts; user data now lives in %APPDATA%)

- [ ] **Step 1: requirements.txt** — delete the `python-dotenv>=1.0.0` line; leave the rest unchanged.

- [ ] **Step 2: FaceitDiscordStatus.spec** — in the `datas` list, delete the line `(str(project_root / '.env.example'), '.'),` (keep the tray icon entry and the tkinter hidden imports, which are now genuinely used).

- [ ] **Step 3: build.bat** — delete the whole "Create minimal .env file" block (the `(echo ...) > "dist\.env"` group and its echo lines). Replace the dist README block content with:

```bat
REM Create a README for the dist folder
echo.
echo Creating distribution README...
(
echo Faceit Discord Status
echo =====================
echo.
echo QUICK START:
echo.
echo 1. Run FaceitDiscordStatus.exe
echo 2. Type your FACEIT nickname into the setup window ^(case-sensitive^)
echo 3. Done! The app lives in your system tray ^(near the clock^).
echo.
echo Right-click the tray icon for settings:
echo - Settings... : change nickname and what shows in Discord
echo - Start with Windows : launch automatically on boot
echo - View Current Match : open your match page on Faceit
echo.
echo Your settings and logs are stored in %%APPDATA%%\FaceitDiscordStatus
) > "dist\README.txt"
```

Also update the final summary echoes: remove the line `echo API keys are embedded in the executable.` and `echo Your friend will be prompted for their FACEIT username on first run.`; replace with `echo Share dist\FaceitDiscordStatus.exe - it is fully self-contained.`

- [ ] **Step 4: .gitignore and stale artifacts**

Check `.gitignore` contains `dist/`, `build/`, `__pycache__/`, `logs/`, `.env` — add any missing. Then:

```bash
git rm --cached config.json dist/README.txt dist/config.json
```

(`config.json` at the repo root was the developer's personal settings; v2 reads from %APPDATA% so the file is dead in the repo.)

- [ ] **Step 5: Verify suite still passes** — `python -m pytest tests/ -v`

- [ ] **Step 6: Commit**

```bash
git add requirements.txt FaceitDiscordStatus.spec build.bat .gitignore
git commit -m "chore: drop dotenv, clean packaging, stop committing build artifacts"
```

---

### Task 12: Docs — player-first README, BUILDING.md

**Files:**
- Rewrite: `README.md`
- Create: `BUILDING.md`

- [ ] **Step 1: Rewrite `README.md`**

```markdown
# Faceit Discord Status

Show your live **Faceit CS2 match** in your **Discord status** — map, score, ELO and more, updating automatically while you play.

## Setup (2 minutes, no technical knowledge needed)

1. **Download** `FaceitDiscordStatus.exe` from the [latest release](https://github.com/yourusername/DiscordFaceitStatus/releases).
2. **Run it.** A setup window asks for your Faceit nickname — type it and click **Save & Start**.
3. **That's it.** The app now lives in your system tray (next to the clock). Play a Faceit match and your Discord status updates automatically.

> **Windows SmartScreen warning?** Click "More info" → "Run anyway". The exe is unsigned, which is why Windows shows the warning.

## What it shows

- Current map, live score, and match ELO at stake
- Your current ELO, regional rank, and today's ELO gains/losses
- K/D/A and average lobby ELO
- Win/loss result with ELO change after the match
- A "View Match" button linking to the Faceit match page

Everything is optional — turn any of it off in **Settings**.

## The tray menu

Right-click the tray icon:

| Item | What it does |
|---|---|
| Status / Tracking | Shows what the app is doing and whose matches it follows |
| Show match status in Discord | Master on/off switch |
| View Current Match | Opens your live match page on Faceit |
| Settings... | Change nickname and choose what's shown in Discord |
| Start with Windows | Launch automatically when your PC starts |
| Exit | Close the app |

## Troubleshooting

**Nothing shows in Discord**
- Make sure the **Discord desktop app** is running (not just the browser version).
- In Discord: User Settings → Activity Privacy → enable **"Share your detected activities with others"**.
- You must be in an actual Faceit match — the status appears once the match starts.

**Wrong player being tracked** — Right-click tray icon → Settings → change the nickname (it's case-sensitive).

**"Discord not found" notification** — Start Discord; the app reconnects automatically.

**Where are my settings/logs?** — In `%APPDATA%\FaceitDiscordStatus` (paste that into the File Explorer address bar).

## For developers

See [BUILDING.md](BUILDING.md) to run from source or build the exe yourself.

## License

MIT License
```

- [ ] **Step 2: Create `BUILDING.md`**

```markdown
# Building & Running from Source

## Requirements

- Windows 10/11
- Python 3.10+ (3.13 tested)

## Run from source

```bash
git clone https://github.com/yourusername/DiscordFaceitStatus.git
cd DiscordFaceitStatus
pip install -r requirements.txt
python run.py          # add --debug for verbose logging
```

On first run a setup window asks for the Faceit nickname. Settings and logs live in `%APPDATA%\FaceitDiscordStatus`.

The Faceit API key and Discord application ID are embedded in `src/config.py`
(`EMBEDDED_API_KEY`, `EMBEDDED_DISCORD_APP_ID`). To use your own, replace those
values — the Discord app must have the map image assets (`map_mirage`,
`map_dust2`, ..., `faceit_logo`) uploaded under those names.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

## Build the exe

```cmd
build.bat
```

Output: `dist\FaceitDiscordStatus.exe` — a single self-contained file; that one
file is all users need.

Manual build: `pyinstaller FaceitDiscordStatus.spec --clean`

Note: `build.bat` contains workarounds for Anaconda Python (Pillow DLL
bundling). With a standard python.org install they're harmless no-ops.
```

- [ ] **Step 3: Commit**

```bash
git add README.md BUILDING.md
git commit -m "docs: player-first README, move build instructions to BUILDING.md"
```

---

### Task 13: Final verification

- [ ] **Step 1: Full test suite** — `python -m pytest tests/ -v` → all pass.
- [ ] **Step 2: Byte-compile everything** — `python -m compileall src run.py` → no errors.
- [ ] **Step 3: Grep for leftovers** — search the repo for `dotenv`, `update_env_value`, `_windows_input_box`, `os.execv`, `_check_v5_match_history`: only hits should be in docs/plan files.
- [ ] **Step 4: Smoke test (manual, if possible)** — `python run.py --debug`: first-run wizard appears (config in %APPDATA% is fresh or has nickname), tray icon appears, Settings window opens from the menu, Exit shuts down cleanly. This step requires the user's desktop session; report what was and wasn't verified.
- [ ] **Step 5: Commit any fixes; do not push unless asked.**
```
