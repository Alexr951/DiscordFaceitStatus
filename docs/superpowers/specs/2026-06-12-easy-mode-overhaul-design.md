# DiscordFaceitStatus v2.0 — "Easy Mode" Overhaul Design

**Date:** 2026-06-12
**Status:** Approved direction (portable exe, embedded API key, full overhaul)

## Goal

An average (non-technical) Faceit player downloads a single `.exe`, double-clicks it,
types their Faceit nickname into a friendly window, and their CS2 match status appears
in Discord. It survives reboots (optional auto-start), network blips, and Discord
restarts, and tells the user clearly when something is wrong.

## Decisions (locked)

| Decision | Choice |
|---|---|
| Distribution | Portable single exe + "Start with Windows" toggle (HKCU Run key). No installer. |
| Faceit API key | Stays embedded in the app (zero user setup). Never logged. README stops telling users to create their own. |
| Scope | Full overhaul: bugs, UX, optimization, code structure. |

## User-Facing Changes

### First-run setup (new, `src/gui.py`)
- tkinter window (not VBScript InputBox): asks for Faceit nickname.
- Validates live against the Faceit API; shows the matched player
  ("**nickname** — Level 10 · 2,341 ELO. Is this you?") before saving.
- Clear error text for: nickname not found, no internet.
- Includes a "Start with Windows" checkbox.
- Shown when no nickname is configured; otherwise app goes straight to tray.

### Settings window (new, replaces PowerShell/WPF + VBScript dialogs)
- One tkinter window opened from the tray: username (with the same live validation),
  all display toggles (map, score, ELO, avg ELO, KDA, current ELO, country,
  region rank, today's ELO, FPL), auto-start checkbox.
- Save applies immediately — username change re-resolves the player ID in the
  running monitor; **no app restart** (`os.execv` removed).
- Tray menu keeps quick toggles (Enable/Disable presence, View Match, Settings, Exit)
  but the per-stat submenus are replaced by the Settings window.

### Auto-start with Windows (new, `src/autostart.py`)
- `winreg` HKCU `Software\Microsoft\Windows\CurrentVersion\Run` entry pointing at the
  current exe path (only offered when frozen; in dev mode the toggle is hidden/disabled).
- Toggleable from first-run wizard and Settings.

### Error feedback (new)
- pystray `icon.notify()` toast notifications (no new dependency) for actionable events:
  - "Faceit user 'xyz' not found — check the spelling in Settings."
  - "Discord isn't running. Start Discord and I'll connect automatically."
  - "Can't reach Faceit — retrying." (shown once per outage, not spammed)
- Tray tooltip/status line still shows current state.

### Config location & format
- Config moves to `%APPDATA%\FaceitDiscordStatus\config.json`
  (fixes: exe in a protected folder can't write; exe can be moved freely).
- `faceit_nickname` lives in config.json. `.env` and `python-dotenv` are **removed**.
- Migration on startup: if old `.env` / local `config.json` exists next to the exe,
  import values into the new location once.
- Logs also move to `%APPDATA%\FaceitDiscordStatus\logs\`.

### README
- Rewritten for players: Download → Run → Enter nickname → Done. Troubleshooting
  section (Discord not showing status, wrong account, antivirus/SmartScreen note).
- Build-from-source instructions move to `BUILDING.md`.
- Remove the misleading "create your own Faceit API key" instructions.

## Bug Fixes

1. **Elapsed timer resets every poll** (`discord_rpc.py:295`): capture match start once
   on the idle→live transition (derive from lcrypt `duration` when available,
   else first-seen time); pass the same `start` on every update.
2. **Presence cleared on single API hiccup mid-match**: require 3 consecutive
   "not in match / error" polls before clearing a live presence.
3. **Train map missing** from `_get_map_image` lookup → add `de_train`/`train`.
4. **`finished_at`** not ISO-converted like `started_at` → shared conversion helper.
5. **ELO-at-stake display**: guard empty string; show both halves when asymmetric.
6. **API key logged in plaintext** by `update_env_value` logging → never log secret
   values (function disappears anyway with `.env` removal).
7. **`print()` instead of `logger.error`** in `_save_settings`.
8. **Temp `.vbs` files leaked on dialog errors** → moot (VBScript dialogs removed).
9. **Unsafe shutdown**: ordered shutdown — clear presence → disconnect RPC →
   stop monitor (`join`) → exit; signal handler delegates to one shutdown path.

## Optimization

- **API calls per tick: up to 4 → ~1.** lcrypt is the primary live detector.
  Official-API fallback chain (`/players/{id}` → v5 history → v4 history) runs only
  when lcrypt errors (not merely "no live match"), and the `/players/{id}` result is
  cached. Match details are fetched on state transitions / score changes, not every tick.
- **"View Match" tray action** reuses the monitor's cached match URL — no fresh API call.
- **Adaptive polling**: ~20s while in a match, 45s while idle (config keeps a single
  `poll_interval` for idle; in-match interval is a constant). Discord updates still
  rate-limited to 15s.
- **Per-host rate limiting**: lcrypt requests no longer consume the official API's
  rate-limit slot; rate limiter gets a lock.
- **Discord reconnect with backoff** on `PipeClosed`/connection loss instead of
  silent failure.

## Code Structure

```
run.py            entry point (unchanged role)
src/
  main.py         startup wiring: migrate config → first-run wizard if needed →
                  start monitor → run tray (main thread)
  config.py       Config: thread-safe get/set (one lock), %APPDATA% paths, migration,
                  defaults. Module-level singleton and duplicate get_app_root removed.
  faceit_api.py   FaceitAPI (official v4 + v5 fallback) and lcrypt client; per-host
                  rate limits; player cache; shared ISO-timestamp helper.
  monitor.py      MatchMonitor: explicit state machine (IDLE / LIVE / FINISHED),
                  grace-period counter, match-start tracking, adaptive interval,
                  set_nickname() for live username changes.
  discord_rpc.py  DiscordRPC: formatting + 15s rate limit + reconnect/backoff.
  tray.py         SystemTray: icon, menu, notify() helper. No dialog code.
  gui.py          NEW: first-run wizard + settings window (tkinter, stdlib).
  autostart.py    NEW: is_enabled()/enable()/disable() via winreg (stdlib).
```

Removed: `src/utils.py` dead formatters (`utils.py` keeps only `setup_logging()`,
now pointed at the %APPDATA% logs dir), module-level `config = Config()`, duplicate `get_app_root()`,
VBScript/PowerShell dialog functions, `python-dotenv` dependency, tkinter hidden-import
mystery (now genuinely used), `.env.example` reference in the spec file.

## Packaging

- `FaceitDiscordStatus.spec`: keep one-file, `console=False`; keep tkinter hidden
  imports (now used); drop `.env.example` from datas; keep tray icon asset.
- `build.bat`: stop creating `dist/.env`; still writes `dist/README.txt` (player-focused).

## Error Handling Summary

| Failure | Behavior |
|---|---|
| Nickname not found | Wizard/Settings shows inline error; if it breaks at runtime (renamed account), toast + tray status. |
| No internet / Faceit down | Backoff (existing 5-failure → 2× interval logic kept), one toast per outage, presence kept during grace period. |
| Discord not running | Toast once; reconnect attempts with backoff; presence resumes automatically. |
| lcrypt down | Silent fallback to official API path (reduced detail), logged at warning. |
| Config unwritable | Toast with the path; app continues with in-memory settings. |

## Testing

`tests/` (pytest), covering pure logic only — no live API/Discord/tray in tests:
- Presence string formatting (all toggle combinations, truncation, ELO-at-stake edge cases).
- Monitor state machine: idle→live→finished transitions, grace period, timer capture
  (API + RPC faked).
- Config: defaults, load/save round-trip, migration from `.env` + old config.json.
- Map image lookup (incl. Train).
- ISO timestamp helper.

GUI (tkinter windows) and tray are verified manually; they stay thin.

## Out of Scope

- Installer (Inno Setup), code signing, auto-update.
- Linux/macOS support (Windows-only, as today).
- Replacing the lcrypt third-party API (kept as primary; official API remains fallback).
- Rotating the already-public API key (owner's call, separate from this work).
