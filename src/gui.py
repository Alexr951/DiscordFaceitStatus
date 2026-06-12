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
