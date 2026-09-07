# -*- mode: python ; coding: utf-8 -*-
import sys
import os

block_cipher = None

added_files = [
    ('ui/assets/icons', 'ui/assets/icons'),
    ('storage/warmup_campaigns', 'storage/warmup_campaigns'),
    ('oxbrowser.ico', '.'),
    ('README.md', '.'),
]

hidden_imports = [
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'PyQt6.QtNetwork',
    'PyQt6.QtSvg',
    'qasync',
    'asyncio',
    'aiohttp',
    'aiohttp_socks',
    'cryptography',
    'cryptography.hazmat.primitives.ciphers.aead',
    'cryptography.hazmat.backends.openssl',
    'curl_cffi',
    'curl_cffi.requests',
    'psutil',
    'pydantic',
    'PIL',
    'PIL.Image',
    'engine',
    'engine.browser',
    'engine.proxy_checker',
    'engine.google_proxy_checker',
    'engine.browser_downloader',
    'engine.platform_helper',
    'engine.sandbox',
    'engine.sandbox.sandbox_manager',
    'engine.sandbox.sandbox_installer',
    'engine.sandbox.container_sandbox',
    'storage',
    'storage.profile_manager',
    'storage.proxy_manager',
    'storage.secrets_manager',
    'storage.cloud_sync_manager',
    'storage.crypto_vault',
    'storage.warmup_campaign_manager',
    'storage.vector_store',
    'ui',
    'ui.main_window',
    'ui.views',
    'ui.components',
]

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=added_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy'],
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
    name='OXBROWSER',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='oxbrowser.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='OXBROWSER',
)
