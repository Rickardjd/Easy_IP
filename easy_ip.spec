# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Easy IP TUI
Run via build.bat (which sets EASYIP_TEXTUAL_DIR / EASYIP_RICH_DIR first).
"""

import os, sys

# ── Package paths supplied by build.bat via environment variables ─────────────
# build.bat resolves these using the launcher Python, which has full access to
# user site-packages even on the Microsoft Store Python.
TEXTUAL_DIR = os.environ.get('EASYIP_TEXTUAL_DIR', '').strip()
RICH_DIR    = os.environ.get('EASYIP_RICH_DIR',    '').strip()

if not TEXTUAL_DIR or not os.path.isdir(TEXTUAL_DIR):
    raise RuntimeError(
        "EASYIP_TEXTUAL_DIR is not set or invalid.\n"
        "Run the build through build.bat, not directly via pyinstaller."
    )
if not RICH_DIR or not os.path.isdir(RICH_DIR):
    raise RuntimeError(
        "EASYIP_RICH_DIR is not set or invalid.\n"
        "Run the build through build.bat, not directly via pyinstaller."
    )

SITE_PKGS = os.path.dirname(TEXTUAL_DIR)

print(f"[spec] textual  -> {TEXTUAL_DIR}")
print(f"[spec] rich     -> {RICH_DIR}")
print(f"[spec] site-pkg -> {SITE_PKGS}")

# Copy entire package trees into the bundle so runtime imports resolve.
datas = [
    (TEXTUAL_DIR, 'textual'),
    (RICH_DIR,    'rich'),
]

block_cipher = None

a = Analysis(
    ['easy_ip_tui.py'],
    pathex=['.', SITE_PKGS],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'textual',
        'textual.app',
        'textual.screen',
        'textual.widget',
        'textual.widgets',
        'textual.binding',
        'textual.containers',
        'textual.reactive',
        'textual.message',
        'textual.worker',
        'rich',
        'rich.text',
        'rich.panel',
        'rich.table',
        'rich.console',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas', 'scipy'],
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
    name='Easy_IP',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',
    version_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Easy_IP',
)
