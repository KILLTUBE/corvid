# -*- mode: python ; coding: utf-8 -*-
import os

# pylib.pyd (SourceIO) imports MSVCP140.dll, which isn't guaranteed to exist on the user's machine
msvcp140 = os.path.join(os.environ.get('SYSTEMROOT', 'C:/Windows'), 'System32', 'MSVCP140.dll')

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[('SourceIO/library/utils/pylib/windows/pylib.pyd', 'SourceIO/library/utils/pylib/windows'), (msvcp140, '.')],
    datas=[],
    hiddenimports=['glm'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Corvid',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['res\\icon.ico'],
)
