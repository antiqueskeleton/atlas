# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Atlas AI
# Run:  pyinstaller atlas.spec --clean --noconfirm

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# Collect all PySide6 and backend sub-packages so nothing is missed
hidden = (
    collect_submodules("PySide6")
    + collect_submodules("backend")
    + collect_submodules("desktop")
    + [
        "anthropic",
        "openai",
        "google.genai",
        "matplotlib.backends.backend_qtagg",
        "matplotlib.figure",
        "matplotlib.ticker",
        "matplotlib.lines",
        "sqlite3",
        "csv",
        "uuid",
    ]
)

a = Analysis(
    ["desktop/main.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("data",   "data"),
        ("config", "config"),
    ],
    hiddenimports=hidden,
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
    [],
    exclude_binaries=True,
    name="Atlas AI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,                  # windowless GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon="installer/atlas.ico",   # uncomment when icon is ready
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Atlas AI",
)
