# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for RetroMetaSync
# Build: pyinstaller RetroMetaSync.spec

import os

import customtkinter

# Resolve paths relative to this spec file (SPEC is provided by PyInstaller)
PROJECT_ROOT = os.path.dirname(os.path.abspath(SPEC))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")

# CustomTkinter data files (required for themes, fonts, etc.)
ctk_dir = os.path.dirname(customtkinter.__file__)
ctk_datas = [(ctk_dir, "customtkinter")]

a = Analysis(
    [os.path.join(SRC_DIR, "retrometasync", "app.py")],
    pathex=[SRC_DIR, PROJECT_ROOT],
    binaries=[],
    datas=ctk_datas,
    hiddenimports=[
        "customtkinter",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

# onedir mode (required for CustomTkinter - has .json, .otf data files)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RetroMetaSync",
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
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="RetroMetaSync",
)
