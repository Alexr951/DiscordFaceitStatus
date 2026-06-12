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
