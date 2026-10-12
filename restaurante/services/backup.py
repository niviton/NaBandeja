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

logger = logging.getLogger('nabandeja.backup')


def backup_dir():
    return Path(settings.DATA_DIR) / 'backups' / 'auto'


def is_sqlite():
    return settings.DATABASES['default']['ENGINE'].endswith('sqlite3')


def db_path():
    return Path(settings.DATABASES['default']['NAME'])


def sqlite_snapshot(source_path, target_path):
    """Cópia consistente de um banco SQLite, mesmo com o sistema gravando."""
    source = sqlite3.connect(source_path)
    destination = sqlite3.connect(target_path)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()


def run_backup(keep=None):
    """Cria uma cópia do banco e apaga as mais antigas. Retorna o caminho ou None."""
    if not is_sqlite():
        return None
    keep = keep or int(getattr(settings, 'BACKUP_KEEP', 48))
    source_path = db_path()
    if not source_path.exists():
        return None

    folder = backup_dir()
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f'db_{datetime.now():%Y-%m-%d_%H%M%S}.sqlite3'
    sqlite_snapshot(source_path, target)

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
