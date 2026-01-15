# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for Faceit Discord Status."""

import os
from pathlib import Path

block_cipher = None

# Get the project root directory
project_root = Path(SPECPATH)

# Define data files to include
datas = [
    # Include the tray icon
    (str(project_root / 'assets' / 'tray_icon.png'), 'assets'),
    # Include .env.example as a template
    (str(project_root / '.env.example'), '.'),
]

# Hidden imports that PyInstaller might miss
hiddenimports = [
    'pystray._win32',
    'PIL._tkinter_finder',
    'tkinter',
    'tkinter.ttk',
    'tkinter.messagebox',
]

a = Analysis(
    [str(project_root / 'run.py')],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='FaceitDiscordStatus',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window (GUI app)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / 'assets' / 'tray_icon.png'),  # Application icon
)
