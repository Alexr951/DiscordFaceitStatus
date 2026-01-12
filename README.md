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

## Installation

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
- **Enable/Disable Rich Presence** - Toggle the Discord status
- **View Current Match** - Open match page in browser
- **Exit** - Close the application

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

## License

MIT License
