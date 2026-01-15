"""System tray integration for the application."""

import logging
import os
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Callable, Optional, TYPE_CHECKING

from PIL import Image
import pystray
from pystray import MenuItem, Menu

if TYPE_CHECKING:
    from .config import Config

logger = logging.getLogger(__name__)


def _get_tk_root():
    """Get or create a hidden tkinter root window."""
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    # Ensure the window appears on top
    root.attributes('-topmost', True)
    root.update()
    return root


class UsernameDialog:
    """Dialog for changing the FACEIT username."""

    def __init__(self, parent, current_username: str = ""):
        import tkinter as tk
        from tkinter import ttk

        self.result = None
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Change FACEIT Username")
        self.dialog.geometry("400x150")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Center on screen
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() - 400) // 2
        y = (self.dialog.winfo_screenheight() - 150) // 2
        self.dialog.geometry(f"+{x}+{y}")

        # Make dialog appear on top
        self.dialog.attributes('-topmost', True)

        # Main frame with padding
        frame = ttk.Frame(self.dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # Label
        ttk.Label(frame, text="Enter new FACEIT username:").pack(anchor=tk.W)

        # Entry field
        self.entry = ttk.Entry(frame, width=40)
        self.entry.insert(0, current_username)
        self.entry.pack(fill=tk.X, pady=(5, 15))
        self.entry.select_range(0, tk.END)
        self.entry.focus_set()

        # Buttons frame
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text="Cancel", command=self._cancel).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(btn_frame, text="Save", command=self._save).pack(side=tk.RIGHT)

        # Bind Enter key
        self.entry.bind('<Return>', lambda e: self._save())
        self.dialog.bind('<Escape>', lambda e: self._cancel())

        # Wait for dialog to close
        self.dialog.wait_window()

    def _save(self):
        self.result = self.entry.get().strip()
        self.dialog.destroy()

    def _cancel(self):
        self.result = None
        self.dialog.destroy()


class StatsConfigDialog:
    """Multi-select dialog for configuring display stats."""

    MATCH_SETTINGS = [
        ("show_map", "Show Map Name"),
        ("show_score", "Show Round Score"),
        ("show_elo", "Show ELO at Stake"),
        ("show_avg_elo", "Show Average ELO"),
        ("show_kda", "Show K/D/A Stats"),
    ]

    PLAYER_SETTINGS = [
        ("show_current_elo", "Show Current ELO"),
        ("show_country", "Show Country"),
        ("show_region_rank", "Show Regional Rank"),
        ("show_today_elo", "Show Today's ELO Change"),
        ("show_fpl", "Show FPL/FPL-C Status"),
    ]

    def __init__(self, parent, config: "Config"):
        import tkinter as tk
        from tkinter import ttk

        self.result = None
        self.config = config
        self.vars = {}

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Configure Display Stats")
        self.dialog.geometry("350x420")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Center on screen
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() - 350) // 2
        y = (self.dialog.winfo_screenheight() - 420) // 2
        self.dialog.geometry(f"+{x}+{y}")

        # Make dialog appear on top
        self.dialog.attributes('-topmost', True)

        # Main frame with padding
        frame = ttk.Frame(self.dialog, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)

        # Match Display Section
        ttk.Label(frame, text="Match Display", font=('TkDefaultFont', 10, 'bold')).pack(anchor=tk.W)
        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(2, 5))

        for key, label in self.MATCH_SETTINGS:
            var = tk.BooleanVar(value=config.get(key, True))
            self.vars[key] = var
            cb = ttk.Checkbutton(frame, text=label, variable=var)
            cb.pack(anchor=tk.W, padx=10, pady=2)

        # Spacer
        ttk.Frame(frame, height=15).pack()

        # Player Statistics Section
        ttk.Label(frame, text="Player Statistics", font=('TkDefaultFont', 10, 'bold')).pack(anchor=tk.W)
        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(2, 5))

        for key, label in self.PLAYER_SETTINGS:
            var = tk.BooleanVar(value=config.get(key, True))
            self.vars[key] = var
            cb = ttk.Checkbutton(frame, text=label, variable=var)
            cb.pack(anchor=tk.W, padx=10, pady=2)

        # Spacer
        ttk.Frame(frame, height=15).pack()

        # Buttons frame
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)

        ttk.Button(btn_frame, text="Cancel", command=self._cancel).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(btn_frame, text="Save", command=self._save).pack(side=tk.RIGHT)

        # Bind Escape key
        self.dialog.bind('<Escape>', lambda e: self._cancel())

        # Wait for dialog to close
        self.dialog.wait_window()

    def _save(self):
        self.result = {key: var.get() for key, var in self.vars.items()}
        self.dialog.destroy()

    def _cancel(self):
        self.result = None
        self.dialog.destroy()


class SystemTray:
    """Manages the system tray icon and menu."""

    def __init__(
        self,
        config: Optional["Config"] = None,
        on_toggle: Optional[Callable[[bool], None]] = None,
        on_exit: Optional[Callable[[], None]] = None,
        get_match_url: Optional[Callable[[], Optional[str]]] = None,
        on_setting_change: Optional[Callable[[str, bool], None]] = None,
        on_username_change: Optional[Callable[[str], None]] = None,
    ):
        """Initialize system tray.

        Args:
            config: Configuration object for reading/writing settings
            on_toggle: Callback when presence is toggled (receives new state)
            on_exit: Callback when exit is clicked
            get_match_url: Callback to get current match URL
            on_setting_change: Callback when a display setting changes (key, value)
            on_username_change: Callback when username is changed (receives new username)
        """
        self.config = config
        self.on_toggle = on_toggle
        self.on_exit = on_exit
        self.get_match_url = get_match_url
        self.on_setting_change = on_setting_change
        self.on_username_change = on_username_change

        self._enabled = config.is_enabled if config else True
        self._status = "Starting..."
        self._icon: Optional[pystray.Icon] = None
        self._thread: Optional[threading.Thread] = None

    def _create_icon_image(self) -> Image.Image:
        """Create or load the tray icon image.

        Returns:
            PIL Image for the tray icon
        """
        # Handle both development and PyInstaller bundled paths
        if getattr(sys, 'frozen', False):
            # Running as compiled executable - look in _MEIPASS for bundled assets
            base_path = Path(sys._MEIPASS)
        else:
            # Running as script
            base_path = Path(__file__).parent.parent

        icon_path = base_path / "assets" / "tray_icon.png"

        if icon_path.exists():
            try:
                img = Image.open(icon_path)
                # Convert to RGBA for proper transparency support
                if img.mode != "RGBA":
                    img = img.convert("RGBA")
                # Resize for consistent display across DPI settings
                img = img.resize((64, 64), Image.Resampling.LANCZOS)
                return img
            except Exception as e:
                logger.warning(f"Failed to load icon: {e}")

        # Create a simple orange square as fallback (Faceit color)
        img = Image.new("RGB", (64, 64), color=(255, 85, 0))
        return img

    def _get_setting(self, key: str, default: bool = True) -> bool:
        """Get a setting value from config.

        Args:
            key: Setting key
            default: Default value if not found

        Returns:
            Setting value
        """
        if self.config:
            return self.config.get(key, default)
        return default

    def _toggle_setting(self, key: str) -> Callable:
        """Create a toggle handler for a setting.

        Args:
            key: Setting key to toggle

        Returns:
            Click handler function
        """
        def handler(icon: pystray.Icon, item: MenuItem) -> None:
            if self.config:
                new_value = not self.config.get(key, True)
                self.config.set(key, new_value)
                logger.info(f"Setting '{key}' changed to {new_value}")
                if self.on_setting_change:
                    self.on_setting_change(key, new_value)
                icon.update_menu()
        return handler

    def _change_username(self, icon: pystray.Icon, item: MenuItem) -> None:
        """Show dialog to change FACEIT username."""
        def show_dialog():
            import tkinter.messagebox as messagebox

            try:
                root = _get_tk_root()
                current_username = self.config.faceit_nickname if self.config else ""

                dialog = UsernameDialog(root, current_username)

                if dialog.result is not None:
                    new_username = dialog.result

                    if not new_username:
                        messagebox.showerror("Error", "Username cannot be empty.", parent=root)
                        root.destroy()
                        return

                    if new_username == current_username:
                        root.destroy()
                        return

                    # Update the .env file
                    if self.config:
                        success, error = self.config.update_env_value("FACEIT_NICKNAME", new_username)

                        if success:
                            logger.info(f"Username changed to: {new_username}")

                            # Ask user to restart
                            restart = messagebox.askyesno(
                                "Restart Required",
                                f"Username changed to '{new_username}'.\n\n"
                                "The application needs to restart to apply this change.\n\n"
                                "Restart now?",
                                parent=root
                            )

                            if restart:
                                root.destroy()
                                self._restart_application()
                                return
                        else:
                            messagebox.showerror("Error", f"Failed to save username:\n{error}", parent=root)

                root.destroy()

            except Exception as e:
                logger.error(f"Error in username dialog: {e}")
                try:
                    import tkinter.messagebox as mb
                    mb.showerror("Error", f"An error occurred: {e}")
                except:
                    pass

        # Run dialog in a separate thread to avoid blocking the tray
        threading.Thread(target=show_dialog, daemon=True).start()

    def _configure_stats(self, icon: pystray.Icon, item: MenuItem) -> None:
        """Show dialog to configure display stats."""
        def show_dialog():
            import tkinter.messagebox as messagebox

            try:
                root = _get_tk_root()

                dialog = StatsConfigDialog(root, self.config)

                if dialog.result is not None:
                    # Apply all changes
                    changes_made = False
                    for key, value in dialog.result.items():
                        current_value = self.config.get(key, True)
                        if current_value != value:
                            self.config.set(key, value)
                            changes_made = True
                            logger.info(f"Setting '{key}' changed to {value}")
                            if self.on_setting_change:
                                self.on_setting_change(key, value)

                    if changes_made:
                        icon.update_menu()
                        logger.info("Stats configuration updated")

                root.destroy()

            except Exception as e:
                logger.error(f"Error in stats config dialog: {e}")
                try:
                    import tkinter.messagebox as mb
                    mb.showerror("Error", f"An error occurred: {e}")
                except:
                    pass

        # Run dialog in a separate thread to avoid blocking the tray
        threading.Thread(target=show_dialog, daemon=True).start()

    def _restart_application(self) -> None:
        """Restart the application."""
        logger.info("Restarting application...")

        # Stop the current instance
        if self.on_exit:
            self.on_exit()

        if self._icon:
            self._icon.stop()

        # Get the executable path
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            executable = sys.executable
            os.execv(executable, [executable])
        else:
            # Running as script
            python = sys.executable
            os.execv(python, [python] + sys.argv)

    def _create_menu(self) -> Menu:
        """Create the tray menu.

        Returns:
            pystray Menu object
        """
        # Match display settings submenu
        match_settings = Menu(
            MenuItem(
                "Show Map Name",
                self._toggle_setting("show_map"),
                checked=lambda item: self._get_setting("show_map"),
            ),
            MenuItem(
                "Show Round Score",
                self._toggle_setting("show_score"),
                checked=lambda item: self._get_setting("show_score"),
            ),
            MenuItem(
                "Show ELO at Stake",
                self._toggle_setting("show_elo"),
                checked=lambda item: self._get_setting("show_elo"),
            ),
            MenuItem(
                "Show Average ELO",
                self._toggle_setting("show_avg_elo"),
                checked=lambda item: self._get_setting("show_avg_elo"),
            ),
            MenuItem(
                "Show K/D/A Stats",
                self._toggle_setting("show_kda"),
                checked=lambda item: self._get_setting("show_kda"),
            ),
        )

        # Player statistics settings submenu
        player_settings = Menu(
            MenuItem(
                "Show Current ELO",
                self._toggle_setting("show_current_elo"),
                checked=lambda item: self._get_setting("show_current_elo"),
            ),
            MenuItem(
                "Show Country",
                self._toggle_setting("show_country"),
                checked=lambda item: self._get_setting("show_country"),
            ),
            MenuItem(
                "Show Regional Rank",
                self._toggle_setting("show_region_rank"),
                checked=lambda item: self._get_setting("show_region_rank"),
            ),
            MenuItem(
                "Show Today's ELO Change",
                self._toggle_setting("show_today_elo"),
                checked=lambda item: self._get_setting("show_today_elo"),
            ),
            MenuItem(
                "Show FPL/FPL-C Status",
                self._toggle_setting("show_fpl"),
                checked=lambda item: self._get_setting("show_fpl"),
            ),
        )

        return Menu(
            MenuItem(
                lambda text: f"Status: {self._status}",
                None,
                enabled=False,
            ),
            MenuItem(
                lambda text: f"Tracking: {self.config.faceit_nickname}" if self.config else "Tracking: Unknown",
                None,
                enabled=False,
            ),
            Menu.SEPARATOR,
            MenuItem(
                lambda text: "Disable Tracking" if self._enabled else "Enable Tracking",
                self._toggle_presence,
                checked=lambda item: self._enabled,
            ),
            MenuItem(
                "Match Display",
                match_settings,
            ),
            MenuItem(
                "Player Statistics",
                player_settings,
            ),
            Menu.SEPARATOR,
            MenuItem(
                "Change FACEIT Username...",
                self._change_username,
            ),
            MenuItem(
                "Configure Stats...",
                self._configure_stats,
            ),
            Menu.SEPARATOR,
            MenuItem(
                "View Current Match",
                self._open_match,
                enabled=lambda item: self.get_match_url is not None,
            ),
            Menu.SEPARATOR,
            MenuItem("Exit", self._exit),
        )

    def _toggle_presence(self, icon: pystray.Icon, item: MenuItem) -> None:
        """Toggle rich presence on/off."""
        self._enabled = not self._enabled

        if self.on_toggle:
            self.on_toggle(self._enabled)

        # Update menu
        icon.update_menu()

        logger.info(f"Rich presence {'enabled' if self._enabled else 'disabled'}")

    def _open_match(self, icon: pystray.Icon, item: MenuItem) -> None:
        """Open current match in browser."""
        if self.get_match_url:
            url = self.get_match_url()
            if url:
                webbrowser.open(url)
                logger.info(f"Opened match URL: {url}")
            else:
                logger.info("No active match to view")

    def _exit(self, icon: pystray.Icon, item: MenuItem) -> None:
        """Exit the application."""
        logger.info("Exit requested from tray")

        if self.on_exit:
            self.on_exit()

        icon.stop()

    def update_status(self, status: str) -> None:
        """Update the status shown in the tray menu.

        Args:
            status: New status string
        """
        self._status = status
        if self._icon:
            self._icon.update_menu()

    def set_enabled(self, enabled: bool) -> None:
        """Set the enabled state.

        Args:
            enabled: Whether rich presence is enabled
        """
        self._enabled = enabled
        if self._icon:
            self._icon.update_menu()

    def run(self, blocking: bool = True) -> None:
        """Run the system tray.

        Args:
            blocking: If True, blocks the current thread. If False, runs in background.
        """
        self._icon = pystray.Icon(
            "Faceit Discord Status",
            self._create_icon_image(),
            "Faceit Discord Status",
            self._create_menu(),
        )

        if blocking:
            self._icon.run()
        else:
            self._thread = threading.Thread(target=self._icon.run, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        """Stop the system tray."""
        if self._icon:
            self._icon.stop()
