"""System tray integration for the application."""

import logging
import os
import subprocess
import sys
import tempfile
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


def _windows_input_box(title: str, prompt: str, default: str = "") -> Optional[str]:
    """Show a Windows input dialog using VBScript.

    Args:
        title: Dialog title
        prompt: Prompt text
        default: Default value

    Returns:
        User input or None if cancelled
    """
    # Create VBScript for input box
    vbs_script = f'''
Dim result
result = InputBox("{prompt}", "{title}", "{default}")
If result = "" And Not IsEmpty(result) Then
    WScript.Echo ""
ElseIf IsEmpty(result) Then
    WScript.Echo "::CANCELLED::"
Else
    WScript.Echo result
End If
'''

    try:
        # Write script to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.vbs', delete=False) as f:
            f.write(vbs_script)
            vbs_path = f.name

        # Run the script
        result = subprocess.run(
            ['cscript', '//Nologo', vbs_path],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )

        # Clean up
        os.unlink(vbs_path)

        output = result.stdout.strip()
        if output == "::CANCELLED::":
            return None
        return output

    except Exception as e:
        logger.error(f"Failed to show input dialog: {e}")
        return None


def _windows_message_box(title: str, message: str, buttons: int = 0) -> int:
    """Show a Windows message box using VBScript.

    Args:
        title: Dialog title
        message: Message text
        buttons: Button type (0=OK, 1=OK/Cancel, 4=Yes/No)

    Returns:
        Button clicked (1=OK, 2=Cancel, 6=Yes, 7=No)
    """
    # Escape quotes in message
    message = message.replace('"', '""').replace('\n', '" & vbCrLf & "')

    vbs_script = f'''
Dim result
result = MsgBox("{message}", {buttons}, "{title}")
WScript.Echo result
'''

    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.vbs', delete=False) as f:
            f.write(vbs_script)
            vbs_path = f.name

        result = subprocess.run(
            ['cscript', '//Nologo', vbs_path],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )

        os.unlink(vbs_path)
        return int(result.stdout.strip())

    except Exception as e:
        logger.error(f"Failed to show message box: {e}")
        return 0


def _windows_checkbox_dialog(title: str, settings: list, config: "Config") -> Optional[dict]:
    """Show a Windows checkbox dialog using PowerShell/WPF.

    Args:
        title: Dialog title
        settings: List of (key, label) tuples
        config: Config object to get current values

    Returns:
        Dictionary of {key: bool} or None if cancelled
    """
    # Build checkbox definitions
    checkbox_defs = []
    for key, label in settings:
        checked = "True" if config.get(key, True) else "False"
        checkbox_defs.append(f'@{{Key="{key}"; Label="{label}"; Checked=${checked}}}')

    checkboxes_array = ",".join(checkbox_defs)

    ps_script = f'''
Add-Type -AssemblyName PresentationFramework
Add-Type -AssemblyName PresentationCore
Add-Type -AssemblyName WindowsBase

$settings = @({checkboxes_array})

[xml]$xaml = @"
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        Title="{title}" Height="450" Width="380" WindowStartupLocation="CenterScreen"
        ResizeMode="NoResize" Topmost="True">
    <Grid Margin="15">
        <Grid.RowDefinitions>
            <RowDefinition Height="Auto"/>
            <RowDefinition Height="*"/>
            <RowDefinition Height="Auto"/>
        </Grid.RowDefinitions>

        <TextBlock Grid.Row="0" Text="Select display options:" FontWeight="Bold" Margin="0,0,0,10"/>

        <ScrollViewer Grid.Row="1" VerticalScrollBarVisibility="Auto">
            <StackPanel Name="CheckboxPanel"/>
        </ScrollViewer>

        <StackPanel Grid.Row="2" Orientation="Horizontal" HorizontalAlignment="Right" Margin="0,15,0,0">
            <Button Name="SaveBtn" Content="Save" Width="75" Margin="0,0,10,0"/>
            <Button Name="CancelBtn" Content="Cancel" Width="75"/>
        </StackPanel>
    </Grid>
</Window>
"@

$reader = New-Object System.Xml.XmlNodeReader $xaml
$window = [Windows.Markup.XamlReader]::Load($reader)

$panel = $window.FindName("CheckboxPanel")
$checkboxes = @{{}}

foreach ($setting in $settings) {{
    $cb = New-Object System.Windows.Controls.CheckBox
    $cb.Content = $setting.Label
    $cb.IsChecked = $setting.Checked
    $cb.Margin = "0,5,0,5"
    $panel.Children.Add($cb) | Out-Null
    $checkboxes[$setting.Key] = $cb
}}

$result = $null

$window.FindName("SaveBtn").Add_Click({{
    $script:result = @{{}}
    foreach ($key in $checkboxes.Keys) {{
        $script:result[$key] = $checkboxes[$key].IsChecked
    }}
    $window.Close()
}})

$window.FindName("CancelBtn").Add_Click({{
    $window.Close()
}})

$window.ShowDialog() | Out-Null

if ($result) {{
    $output = @()
    foreach ($key in $result.Keys) {{
        $val = if ($result[$key]) {{ "1" }} else {{ "0" }}
        $output += "$key=$val"
    }}
    $output -join "|"
}} else {{
    "::CANCELLED::"
}}
'''

    try:
        result = subprocess.run(
            ['powershell', '-ExecutionPolicy', 'Bypass', '-Command', ps_script],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )

        output = result.stdout.strip()
        if output == "::CANCELLED::" or not output:
            return None

        # Parse output
        settings_dict = {}
        for item in output.split("|"):
            if "=" in item:
                key, val = item.split("=", 1)
                settings_dict[key] = val == "1"

        return settings_dict

    except Exception as e:
        logger.error(f"Failed to show checkbox dialog: {e}")
        return None


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
            try:
                current_username = self.config.faceit_nickname if self.config else ""

                new_username = _windows_input_box(
                    "Change FACEIT Username",
                    "Enter new FACEIT username:",
                    current_username
                )

                if new_username is None:
                    # User cancelled
                    return

                new_username = new_username.strip()

                if not new_username:
                    _windows_message_box("Error", "Username cannot be empty.", 0)
                    return

                if new_username == current_username:
                    return

                # Update the .env file
                if self.config:
                    success, error = self.config.update_env_value("FACEIT_NICKNAME", new_username)

                    if success:
                        logger.info(f"Username changed to: {new_username}")

                        # Ask user to restart (4 = Yes/No buttons)
                        result = _windows_message_box(
                            "Restart Required",
                            f"Username changed to '{new_username}'.\n\n"
                            "The application needs to restart to apply this change.\n\n"
                            "Restart now?",
                            4
                        )

                        if result == 6:  # Yes clicked
                            self._restart_application()
                    else:
                        _windows_message_box("Error", f"Failed to save username:\n{error}", 0)

            except Exception as e:
                logger.error(f"Error in username dialog: {e}")
                _windows_message_box("Error", f"An error occurred: {e}", 0)

        # Run dialog in a separate thread to avoid blocking the tray
        threading.Thread(target=show_dialog, daemon=True).start()

    def _configure_stats(self, icon: pystray.Icon, item: MenuItem) -> None:
        """Show dialog to configure display stats."""
        # All settings to display
        ALL_SETTINGS = [
            ("show_map", "Show Map Name"),
            ("show_score", "Show Round Score"),
            ("show_elo", "Show ELO at Stake"),
            ("show_avg_elo", "Show Average ELO"),
            ("show_kda", "Show K/D/A Stats"),
            ("show_current_elo", "Show Current ELO"),
            ("show_country", "Show Country"),
            ("show_region_rank", "Show Regional Rank"),
            ("show_today_elo", "Show Today's ELO Change"),
            ("show_fpl", "Show FPL/FPL-C Status"),
        ]

        def show_dialog():
            try:
                result = _windows_checkbox_dialog(
                    "Configure Display Stats",
                    ALL_SETTINGS,
                    self.config
                )

                if result is not None:
                    # Apply all changes
                    changes_made = False
                    for key, value in result.items():
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

            except Exception as e:
                logger.error(f"Error in stats config dialog: {e}")
                _windows_message_box("Error", f"An error occurred: {e}", 0)

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
