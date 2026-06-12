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

On first run a setup window asks for the Faceit nickname. Settings and logs live in `%APPDATA%\FaceitDiscordStatus`.

The Faceit API key and Discord application ID are embedded in `src/config.py`
(`EMBEDDED_API_KEY`, `EMBEDDED_DISCORD_APP_ID`). To use your own, replace those
values — the Discord app must have the map image assets (`map_mirage`,
`map_dust2`, ..., `faceit_logo`) uploaded under those names.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

## Build the exe

```cmd
build.bat
```

Output: `dist\FaceitDiscordStatus.exe` — a single self-contained file; that one
file is all users need.

Manual build: `pyinstaller FaceitDiscordStatus.spec --clean`

Note: `build.bat` contains workarounds for Anaconda Python (Pillow DLL
bundling). With a standard python.org install they're harmless no-ops.
