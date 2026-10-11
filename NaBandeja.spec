# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

# SPECPATH é definido pelo PyInstaller: pasta onde está este .spec
BASE_DIR = Path(SPECPATH).resolve()

# Collect all template files
def collect_data_files():
    datas = []
    
    # Static files, media, templates
    for folder in ['templates', 'static']:
        folder_path = BASE_DIR / folder
        if folder_path.exists():
            for f in folder_path.rglob('*'):
                if f.is_file():
                    rel = str(f.relative_to(BASE_DIR))
                    datas.append((str(f), str(Path(rel).parent)))
    
    # Migrations
    migrations_path = BASE_DIR / 'restaurante' / 'migrations'
    for f in migrations_path.rglob('*'):
        if f.is_file():
            rel = str(f.relative_to(BASE_DIR))
            datas.append((str(f), str(Path(rel).parent)))
    
    # Other data files
    for fname in ['requirements.txt', '.env.example']:
        fpath = BASE_DIR / fname
        if fpath.exists():
            datas.append((str(fpath), '.'))
    
    return datas


a = Analysis(
    [str(BASE_DIR / 'deploy' / 'windows' / 'launcher.py')],
    pathex=[
        str(BASE_DIR / 'deploy' / 'windows'),
        str(BASE_DIR),
    ],
    binaries=[],
    datas=collect_data_files(),
    hiddenimports=[
        'django.contrib.admin',
        'django.contrib.sessions',
        'django.core.management.commands',
        'django.db.backends.sqlite3',
        'django.db.backends.postgresql',
        'daphne', 'daphne.cli', 'daphne.server',
        'twisted.internet.asyncioreactor',
        'channels', 'channels.routing', 'channels.auth', 'channels.layers',
        'whitenoise', 'whitenoise.middleware', 'whitenoise.runserver_nostatic',
        'psycopg2',
        'qrcode', 'qrcode.image.svg',
        'PIL',
        'dotenv',
        'nabandeja_project.settings',
        'nabandeja_project.urls',
        'nabandeja_project.asgi',
        'nabandeja_project.routing',
        'nabandeja_project.envfile',
        'restaurante.apps',
        'restaurante.signals',
        'restaurante.context_processors',
        'restaurante.management.commands.ensure_initial_access',
        'setup_desktop_shortcut',
    ],
    excludes=[
        'matplotlib', 'numpy', 'pandas', 'scipy', 'tkinter', 'jupyter', 'notebook', '__main__',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NaBandeja',
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
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='NaBandeja',
)
