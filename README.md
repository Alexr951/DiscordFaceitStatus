# Faceit Discord Rich Presence

Display your Faceit CS2 match information in your Discord status.

## Features

- Shows current match status (lobby, live, finished)
- Displays map, score, and average lobby ELO
- Shows your K/D/A stats during matches
- Displays ELO change after matches
- Clickable link to view match on Faceit
- Runs silently in system tray
- Privacy options to hide specific information
- Change FACEIT username directly from the tray menu
- Multi-select stats configuration dialog
- Standalone executable option (no Python required)

## Installation

### Option 1: Standalone Executable (Recommended for most users)

1. Download the latest release from the [Releases](https://github.com/yourusername/DiscordFaceitStatus/releases) page
2. Extract the files to a folder of your choice
3. Copy `.env.example` to `.env` and fill in your credentials
4. Run `FaceitDiscordStatus.exe`

### Option 2: From Source

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/DiscordFaceitStatus.git
   cd DiscordFaceitStatus
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and fill in your credentials:
   ```bash
   cp .env.example .env
   ```

4. Generate the tray icon (optional):
   ```bash
   python scripts/generate_icon.py
   ```

## Configuration

### Getting Your Faceit API Key

1. Go to [Faceit Developers](https://developers.faceit.com/)
2. Sign in with your Faceit account
3. Create a new application or use an existing one
4. Copy your API key (Client-side API key)

### Environment Variables

Edit your `.env` file:

```env
FACEIT_API_KEY=your_faceit_api_key_here
FACEIT_NICKNAME=your_faceit_nickname
DISCORD_APP_ID=your_discord_application_id
```

### User Settings

Settings are stored in `config.json` (created automatically):

```json
{
  "poll_interval": 45,
  "show_elo": true,
  "show_avg_elo": true,
  "show_kda": true,
  "show_map": true,
  "enabled": true
}
```

## Usage

Run the application:

```bash
python run.py
```

Or with debug logging:

```bash
python run.py --debug
```

The application will:
1. Appear in your system tray
2. Automatically detect when you're in a Faceit match
3. Update your Discord status with match information

### System Tray Menu

Right-click the tray icon for options:
- **Status** - Shows current monitoring status
- **Tracking** - Shows which FACEIT user is being tracked
- **Enable/Disable Tracking** - Toggle the Discord status
- **Match Display** - Submenu to toggle match-related display options
- **Player Statistics** - Submenu to toggle player stat display options
- **Change FACEIT Username** - Change the tracked user without editing files
- **Configure Stats** - Multi-select dialog to configure all display options at once
- **View Current Match** - Open match page in browser
- **Exit** - Close the application

### Changing FACEIT Username

You can change the tracked FACEIT username directly from the tray menu:
1. Right-click the tray icon
2. Click "Change FACEIT Username..."
3. Enter the new username in the dialog
4. Click "Save"
5. Choose to restart the application when prompted

### Configuring Display Stats

To configure multiple display options at once:
1. Right-click the tray icon
2. Click "Configure Stats..."
3. Check/uncheck the options you want
4. Click "Save" to apply all changes

## Troubleshooting

### "Discord not found" error
Make sure Discord desktop app is running (not just the web version).

### "Invalid API key" error
Check that your Faceit API key is correct in `.env`.

### No status appearing in Discord
1. Ensure "Activity Status" is enabled in Discord settings
2. Check that the Discord Application ID is correct
3. Make sure you're in an active Faceit match

### Rate limit errors
The app respects Faceit API rate limits. If you see these errors, the app will automatically retry after a delay.

## Building the Executable

To create a standalone executable from source:

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Build Steps

**Windows:**
1. Open a command prompt in the project directory
2. Run the build script:
   ```cmd
   build.bat
   ```
3. The executable will be created in the `dist` folder

**Manual Build (all platforms):**
1. Install PyInstaller:
   ```bash
   pip install pyinstaller
   ```
2. Install project dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Build using the spec file:
   ```bash
   pyinstaller FaceitDiscordStatus.spec --clean
   ```
4. The executable will be in the `dist` folder

### Distribution

After building, the `dist` folder will contain:
- `FaceitDiscordStatus.exe` - The standalone executable
- `.env.example` - Template for configuration
- `README.txt` - Setup instructions for end users

To distribute:
1. Copy the contents of the `dist` folder
2. Users must create a `.env` file from the `.env.example` template
3. The `config.json` and `logs` folder will be created automatically

## License

MIT License
