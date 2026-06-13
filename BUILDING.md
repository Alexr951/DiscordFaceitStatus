# Building & Running from Source

## Requirements

- Windows 10/11
- Python 3.10+ (3.13 tested)

## Run from source

```bash
git clone https://github.com/Alexr951/DiscordFaceitStatus.git
cd DiscordFaceitStatus
pip install -r requirements.txt
python run.py          # add --debug for verbose logging
```

On first run a setup window detects the Faceit account linked to the local
Steam login (`src/steam.py`). There is no manual nickname entry by design;
the tracked account is always the one tied to the Steam login. Settings and
logs live in `%APPDATA%\FaceitDiscordStatus`.

The Faceit API key and Discord application ID are embedded in `src/config.py`
(`EMBEDDED_API_KEY`, `EMBEDDED_DISCORD_APP_ID`). To use your own, replace those
values. The Discord app must have the map image assets (`map_mirage`,
`map_dust2`, ..., `faceit_logo`) uploaded under those names.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

## Manual testing without playing a match (test mode)

`--test` runs against a throwaway temp profile. Your real config in
`%APPDATA%` is never read or written, so there is nothing to revert. It also
skips the Steam identity check, polls every 10s, and forces debug logging.

The packaged exe ignores `--test` entirely. It only works when running from
source, so it can't be used to impersonate other players with the shipped app.

```bash
# Watch any player who is currently in a live match (find one on faceit.com):
python run.py --test someNickname

# Exercise the first-run wizard (with Steam detection):
python run.py --test
```

Close the normal instance first, since only one copy runs at a time. Exit via
the tray when done; the temp profile is abandoned.

## Build the exe

```cmd
build.bat
```

Output: `dist\FaceitDiscordStatus.exe`, a single self-contained file. That one
file is all users need.

Manual build: `pyinstaller FaceitDiscordStatus.spec --clean`

Releases are built automatically by GitHub Actions when you push a version
tag: `git tag v2.0.0 && git push origin v2.0.0`.

Note: `build.bat` contains workarounds for Anaconda Python (Pillow DLL
bundling). With a standard python.org install they are harmless no-ops.
