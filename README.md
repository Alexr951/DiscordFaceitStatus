# Faceit Discord Status

Show your live **Faceit CS2 match** in your **Discord status** — map, score, ELO and more, updating automatically while you play.

## Setup (under a minute, nothing to configure)

1. **Download** `FaceitDiscordStatus.exe` from the [latest release](https://github.com/yourusername/DiscordFaceitStatus/releases).
2. **Run it.** It finds your Faceit account automatically through your Steam login and shows it to you — just click **Save & Start**.
3. **Let Discord show it** (one-time): in Discord go to **User Settings → Activity Privacy** and turn on **"Share your detected activities with others"**.
4. **That's it.** The app lives in your system tray (next to the clock). Play a Faceit match and your Discord status updates by itself.

> **Windows SmartScreen warning?** Click "More info" → "Run anyway". The exe is unsigned, which is why Windows shows the warning.

## What it shows

- Current map, live score, and match ELO at stake
- Your current ELO, regional rank, and today's ELO gains/losses
- K/D/A and average lobby ELO
- Win/loss result with ELO change after the match
- A "View Match" button linking to the Faceit match page

Everything is optional — turn any of it off in **Settings**.

## How it knows it's really you

Your Faceit account is linked to your Steam account, and the app reads which Steam user is logged in on your PC. That's the account it tracks — so nobody can run around with s1mple's ELO in their status. If you enter a nickname that isn't linked to your Steam login, the app corrects it to your real account (or refuses to show a status until it's fixed). If Steam isn't installed, it falls back to plain nickname entry.

## The tray menu

Right-click the tray icon:

| Item | What it does |
|---|---|
| Status / Tracking | Shows what the app is doing and whose matches it follows |
| Show match status in Discord | Master on/off switch |
| View Current Match | Opens your live match page on Faceit |
| Settings... | Choose what's shown in Discord, change account |
| Start with Windows | Launch automatically when your PC starts |
| Exit | Close the app |

## Troubleshooting

**Nothing shows in Discord**
- Make sure the **Discord desktop app** is running (not just the browser version).
- In Discord: User Settings → **Activity Privacy** → enable **"Share your detected activities with others"** (and don't set your status to Invisible).
- You must be in an actual Faceit match — the status appears once the match starts.

**It detected the wrong account** — It tracks the Faceit account linked to the Steam user currently logged in on this PC. Log into Steam with the right account and restart the app.

**"Account mismatch" notification** — The configured nickname isn't linked to your Steam login. Open Settings and use your own nickname.

**"Discord not found" notification** — Start Discord; the app reconnects automatically.

**Where are my settings/logs?** — In `%APPDATA%\FaceitDiscordStatus` (paste that into the File Explorer address bar).

## For developers

See [BUILDING.md](BUILDING.md) to run from source or build the exe yourself.

## License

MIT License
