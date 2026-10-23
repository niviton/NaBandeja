"""
Backup automático do banco SQLite.

Usa a API de backup do SQLite, que gera uma cópia consistente mesmo com o
sistema em uso. Roda no launcher a cada BACKUP_INTERVAL_MINUTES e mantém as
últimas BACKUP_KEEP cópias em backups/auto/.
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.db import connections

logger = logging.getLogger('nabandeja.backup')


def backup_dir():
    from central.tenancy import current_code

    folder = Path(settings.DATA_DIR) / 'backups' / 'auto'
    return folder / current_code() if current_code() else folder


def database_settings():
    """Banco atual: no modo várias lojas, o da loja ativa."""
    from central.tenancy import enabled

    return connections['default'].settings_dict if enabled() else settings.DATABASES['default']


def is_sqlite():
    return database_settings()['ENGINE'].endswith('sqlite3')


def run_backup(keep=None):
    """Cria uma cópia do banco e apaga as mais antigas. Retorna o caminho ou None."""
    if not is_sqlite():
        return None
    keep = keep or int(getattr(settings, 'BACKUP_KEEP', 48))
    source_path = Path(database_settings()['NAME'])
    if not source_path.exists():
        return None

    folder = backup_dir()
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f'db_{datetime.now():%Y-%m-%d_%H%M%S}.sqlite3'
    source = sqlite3.connect(source_path)
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()

    for old in sorted(folder.glob('db_*.sqlite3'))[:-keep]:
        old.unlink(missing_ok=True)
    logger.info('Backup criado: %s', target.name)
    return target


def last_backup():
    """(caminho, data) do backup mais recente, ou (None, None)."""
    folder = backup_dir()
    files = sorted(folder.glob('db_*.sqlite3')) if folder.exists() else []
    if not files:
        return None, None
    newest = files[-1]
    return newest, datetime.fromtimestamp(newest.stat().st_mtime)
