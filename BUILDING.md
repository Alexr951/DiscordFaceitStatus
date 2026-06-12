# Building & Running from Source

## Requirements

- Windows 10/11
- Python 3.10+ (3.13 tested)

## Run from source

```bash
git clone https://github.com/yourusername/DiscordFaceitStatus.git
cd DiscordFaceitStatus
pip install -r requirements.txt
python run.py          # add --debug for verbose logging
```

On first run a setup window detects the Faceit account linked to the local
Steam login (`src/steam.py`), falling back to manual nickname entry. Settings
and logs live in `%APPDATA%\FaceitDiscordStatus`.

The Faceit API key and Discord application ID are embedded in `src/config.py`
(`EMBEDDED_API_KEY`, `EMBEDDED_DISCORD_APP_ID`). To use your own, replace those
values — the Discord app must have the map image assets (`map_mirage`,
`map_dust2`, ..., `faceit_logo`) uploaded under those names.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

## Manual testing without playing a match (test mode)

`--test` runs against a throwaway temp profile — your real config in
`%APPDATA%` is never read or written, so there is nothing to revert. It also
skips the Steam ownership check, polls every 10s, and forces debug logging.

```bash
# Watch any player who is currently in a live match (find one on faceit.com):
python run.py --test someNickname

# Exercise the first-run wizard (with Steam auto-detection):
python run.py --test
```

Close the normal instance first — the single-instance guard allows only one
copy at a time. Exit via the tray when done; the temp profile is abandoned.

## Build the exe

```cmd
build.bat
```

Output: `dist\FaceitDiscordStatus.exe` — a single self-contained file; that one
file is all users need.

Manual build: `pyinstaller FaceitDiscordStatus.spec --clean`

Note: `build.bat` contains workarounds for Anaconda Python (Pillow DLL
bundling). With a standard python.org install they're harmless no-ops.
