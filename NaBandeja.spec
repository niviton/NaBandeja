# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

# SPECPATH é definido pelo PyInstaller: pasta onde está este .spec
BASE_DIR = Path(SPECPATH).resolve()

# Collect all template files
def collect_data_files():
    datas = []
    
    # Static files, media, templates
    for folder in ['templates', 'static', 'media']:
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
    for fname in ['db.sqlite3', 'requirements.txt', '.env.example']:
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
        'daphne',
        'channels',
        'channels.routing',
        'channels.auth',
        'channels_redis',
        'redis',
        'psycopg2',
        'qrcode',
        'PIL',
        'crispy_forms',
        'crispy_forms.templatetags',
        'crispy_forms.templatetags.crispy_forms_tags',
        'crispy_forms.templatetags.crispy_forms_field',
        'crispy_bootstrap5',
        'crispy_bootstrap5.bootstrap5',
        'nabandeja_project.settings',
        'nabandeja_project.urls',
        'nabandeja_project.wsgi',
        'nabandeja_project.asgi',
        'nabandeja_project.routing',
        'restaurante.models',
        'restaurante.views',
        'restaurante.admin',
        'restaurante.forms',
        'restaurante.urls',
        'restaurante.consumers',
        'restaurante.realtime',
        'restaurante.signals',
        'restaurante.context_processors',
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
