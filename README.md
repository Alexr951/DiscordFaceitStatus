# Faceit Discord Status

[![CI](https://github.com/Alexr951/DiscordFaceitStatus/actions/workflows/ci.yml/badge.svg)](https://github.com/Alexr951/DiscordFaceitStatus/actions/workflows/ci.yml)

Shows your live Faceit CS2 match in your Discord status. Map, score, ELO and rank, updated automatically while you play.

## Setup

1. Download `FaceitDiscordStatus.exe` from the [latest release](https://github.com/Alexr951/DiscordFaceitStatus/releases/latest).
2. Run it. It finds your Faceit account through your Steam login and shows it to you. Click **Save & Start**.
3. In Discord, open **User Settings > Activity Privacy** and turn on **"Share your detected activities with others"**.

Done. The app sits in your system tray next to the clock. When you play a Faceit match, your Discord status updates on its own.

If Windows SmartScreen warns you, click "More info" and then "Run anyway". The exe is unsigned, which is the only reason for the warning.

## What it shows

While you're in a match your status looks like this:

```
de_anubis | 6 - 7 | ELO: 2,010
NA Rank #6,264
12:34 elapsed
```

- Map, live score and elapsed time
- Your current ELO and regional rank
- Average lobby ELO and K/D/A when Faceit provides them
- Win or loss with ELO change after the match
- A View Match button that links to the Faceit match room

You can turn any of these off in Settings.

## Why you can't fake it

The app only ever tracks the Faceit account linked to the Steam user logged in on your PC. There is no way to type in someone else's name, so nobody can use it to pose as a pro player or anyone else. If Steam isn't running, or your Steam account has no Faceit account linked, the app tells you and shows nothing.

## The tray menu

Right-click the tray icon:

| Item | What it does |
|---|---|
| Status / Tracking | What the app is doing and whose matches it follows |
| Show match status in Discord | Master on/off switch |
| View Current Match | Opens your live match page on Faceit |
| Settings... | Choose what gets shown in Discord |
| Start with Windows | Launch automatically when your PC starts |
| Exit | Close the app |

## Troubleshooting

**Nothing shows in Discord**
- The Discord desktop app must be running, not just the browser version.
- Check Discord: User Settings > Activity Privacy > "Share your detected activities with others". Also make sure your status isn't set to Invisible.
- The status appears once you're in an actual Faceit match.

**It detected the wrong account.** The app tracks the Faceit account linked to whoever is logged into Steam on this PC. Log into Steam with the right account and restart the app.

**"Steam not found" notification.** Install Steam or log into it, then restart the app.

**"Discord not found" notification.** Start Discord. The app reconnects on its own.

**Where are my settings and logs?** In `%APPDATA%\FaceitDiscordStatus`. Paste that into the File Explorer address bar.

## For developers

See [BUILDING.md](BUILDING.md) to run from source or build the exe yourself.

## License

MIT License
