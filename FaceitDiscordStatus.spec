# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for Faceit Discord Status."""

import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

# Get the project root directory
project_root = Path(SPECPATH)

# Collect ALL PIL/Pillow components
pil_datas, pil_binaries, pil_hiddenimports = collect_all('PIL')

# Find Anaconda Library\bin DLLs that PIL needs
# These are image format libraries that _imaging.pyd depends on
anaconda_bin = None
for path in sys.path:
    candidate = Path(path).parent / 'Library' / 'bin'
    if candidate.exists():
        anaconda_bin = candidate
        break

# Also check common Anaconda locations
if anaconda_bin is None:
    for base in [
        Path(os.environ.get('USERPROFILE', '')) / 'anaconda3',
        Path(os.environ.get('USERPROFILE', '')) / 'miniconda3',
        Path('D:/Users') / os.environ.get('USERNAME', '') / 'anaconda3',
        Path('C:/ProgramData/Anaconda3'),
    ]:
        candidate = base / 'Library' / 'bin'
        if candidate.exists():
            anaconda_bin = candidate
            break

extra_binaries = []
if anaconda_bin:
    # DLLs that Pillow's _imaging needs
    needed_dlls = [
        'libjpeg*.dll',
        'libpng*.dll',
        'libtiff*.dll',
        'libwebp*.dll',
        'zlib*.dll',
        'libzstd*.dll',
        'liblzma*.dll',
        'libopenjp2*.dll',
        'lcms2*.dll',
    ]
    import glob
    for pattern in needed_dlls:
        for dll_path in anaconda_bin.glob(pattern):
            extra_binaries.append((str(dll_path), '.'))

# Define data files to include
datas = [
    (str(project_root / 'assets' / 'tray_icon.png'), 'assets'),
    (str(project_root / '.env.example'), '.'),
]

# Hidden imports that PyInstaller might miss
hiddenimports = [
    'pystray._win32',
    'tkinter',
    'tkinter.ttk',
    'tkinter.messagebox',
] + pil_hiddenimports

a = Analysis(
    [str(project_root / 'run.py')],
    pathex=[str(project_root)],
    binaries=pil_binaries + extra_binaries,
    datas=datas + pil_datas,
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
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / 'assets' / 'tray_icon.png'),
)
