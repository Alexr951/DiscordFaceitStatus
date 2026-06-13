"""tkinter windows: first-run setup wizard and the settings window."""

import logging
import threading
import tkinter as tk
from tkinter import ttk

from . import autostart, steam
from .config import Config
from .faceit_api import FaceitAPI, FaceitAPIError

logger = logging.getLogger(__name__)

# Settings the user can toggle. show_country / show_today_elo / show_fpl
# still exist in config but are hidden here: their data source (the
# third-party live-stats API) is offline, so toggling them does nothing.
DISPLAY_OPTIONS = [
    ("show_map", "Map name"),
    ("show_score", "Round score"),
    ("show_current_elo", "Current ELO"),
    ("show_region_rank", "Regional rank"),
    ("show_kda", "K/D/A stats"),
    ("show_avg_elo", "Average lobby ELO"),
    ("show_elo", "ELO change after match"),
]


class FirstRunWizard:
    """Detects the player's Faceit account through their Steam login.

    There is deliberately no nickname entry: the account shown in Discord is
    always the one linked to the Steam user logged in on this PC, so the app
    can't be used to impersonate someone else.
    """

    def __init__(self, config: Config, api: FaceitAPI):
        self.config = config
        self.api = api
        self.completed = False
        self.detected_player = None

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

        self.status_var = tk.StringVar(value="Looking up your account via Steam...")
        ttk.Label(frame, textvariable=self.status_var, wraplength=340).grid(
            column=0, row=1, columnspan=2, sticky="w", pady=(12, 0)
        )

        self.autostart_var = tk.BooleanVar(value=False)
        if autostart.is_supported():
            ttk.Checkbutton(
                frame,
                text="Start automatically with Windows",
                variable=self.autostart_var,
            ).grid(column=0, row=2, columnspan=2, sticky="w", pady=(10, 0))

        buttons = ttk.Frame(frame)
        buttons.grid(column=0, row=3, columnspan=2, sticky="e", pady=(15, 0))
        self.retry_btn = ttk.Button(buttons, text="Retry", command=self._retry)
        self.retry_btn.grid(column=0, row=0, padx=(0, 8))
        self.retry_btn.state(["disabled"])
        self.save_btn = ttk.Button(buttons, text="Save & Start", command=self._save)
        self.save_btn.grid(column=1, row=0)
        self.save_btn.state(["disabled"])

        threading.Thread(target=self._detect_worker, daemon=True).start()

    def _detect_worker(self) -> None:
        player = None
        error = None
        steam64 = steam.get_logged_in_steam64()
        if not steam64:
            error = (
                "Steam wasn't found on this PC. The app identifies your "
                "Faceit account through your Steam login, so Steam must be "
                "installed and logged in. Start Steam and press Retry."
            )
        else:
            try:
                player = self.api.get_player_by_steam_id(steam64)
            except FaceitAPIError as e:
                logger.info(f"No Faceit account found for local Steam login: {e}")
                if "not found" in str(e).lower():
                    error = (
                        "No Faceit account is linked to the Steam account "
                        "logged in on this PC. Log into Steam with the "
                        "account you play Faceit on, then press Retry."
                    )
                else:
                    error = (
                        "Couldn't reach Faceit. Check your internet "
                        "connection and press Retry."
                    )
        try:
            self.root.after(0, lambda: self._on_detected(player, error))
        except RuntimeError:
            pass  # window already closed

    def _on_detected(self, player, error) -> None:
        if player:
            self.detected_player = player
            self.save_btn.state(["!disabled"])
            self.retry_btn.state(["disabled"])
            self.status_var.set(
                f"Found your account: {player.nickname} - Level "
                f"{player.skill_level}, {player.elo:,} ELO.\n"
                "Wrong account? Log into Steam with yours and press Retry."
            )
            self.retry_btn.state(["!disabled"])
        else:
            self.retry_btn.state(["!disabled"])
            self.status_var.set(error or "Detection failed. Press Retry.")

    def _retry(self) -> None:
        self.retry_btn.state(["disabled"])
        self.save_btn.state(["disabled"])
        self.detected_player = None
        self.status_var.set("Looking up your account via Steam...")
        threading.Thread(target=self._detect_worker, daemon=True).start()

    def _save(self) -> None:
        if self.detected_player is None:
            return
        self.config.update({"faceit_nickname": self.detected_player.nickname})
        if autostart.is_supported() and self.autostart_var.get():
            autostart.enable()
        self.completed = True
        self.root.destroy()

    def run(self) -> bool:
        """Show the wizard. Returns True once an account was confirmed."""
        self.root.mainloop()
        return self.completed


def run_first_run_wizard(config: Config, api: FaceitAPI) -> bool:
    """Run the first-run wizard on the calling (main) thread."""
    return FirstRunWizard(config, api).run()


class _SettingsWindow:
    """Settings window: display toggles and auto-start.

    The tracked account is not editable: it is always the Faceit account
    linked to the local Steam login.
    """

    def __init__(self, config: Config):
        self.config = config

        self.root = tk.Tk()
        self.root.title("Faceit Discord Status - Settings")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)

        frame = ttk.Frame(self.root, padding=15)
        frame.grid()

        account = config.faceit_nickname or "not detected yet"
        ttk.Label(frame, text=f"Account: {account} (detected via your Steam login)").grid(
            column=0, row=0, columnspan=2, sticky="w"
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

        buttons = ttk.Frame(frame)
        buttons.grid(column=0, row=next_row, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="Save", command=self._save).grid(
            column=0, row=0, padx=(0, 8)
        )
        ttk.Button(buttons, text="Cancel", command=self.root.destroy).grid(
            column=1, row=0
        )

    def _save(self) -> None:
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


def open_settings_window(config: Config) -> None:
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
            _SettingsWindow(config).run()
        except Exception:
            logger.exception("Settings window crashed")
        finally:
            with _settings_lock:
                _settings_open = False

    threading.Thread(target=runner, daemon=True, name="settings-window").start()
