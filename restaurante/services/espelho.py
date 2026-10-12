"""
"Entrar na empresa" pelo painel master.

Cada empresa abre num processo próprio (nabandeja_project/espelho.py), numa
porta livre do 127.0.0.1, com o banco e as fotos dela:

- em implantação: o banco de implantação, editável (é o que vai no pacote);
- em produção: uma cópia de trabalho do último backup, SOMENTE LEITURA.
  Os dados de verdade estão no PC da loja; nada feito aqui volta para lá.

O painel entra com um link de uso único assinado com uma chave sorteada
para aquele processo (válido por 60 segundos), como o suporte NaBandeja.
"""

import os
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

from django.conf import settings
from django.core import signing

from .backup import sqlite_snapshot
from .master import MasterError

SSO_SALT = 'nabandeja.espelho'
START_TIMEOUT = 90

_processes = {}  # codigo -> {'proc', 'port', 'key', 'somente_leitura'}
_lock = threading.Lock()


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def _alive(info):
    return info and info['proc'].poll() is None


def _wait_ready(proc, port, log_path):
    started = time.monotonic()
    while time.monotonic() - started < START_TIMEOUT:
        if proc.poll() is not None:
            tail = log_path.read_text(encoding='utf-8', errors='replace').strip().splitlines()[-3:]
            raise MasterError('A empresa não abriu: ' + (' '.join(tail)[-300:] or 'erro desconhecido'))
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            if sock.connect_ex(('127.0.0.1', port)) == 0:
                return
        time.sleep(0.3)
    proc.kill()
    raise MasterError('A empresa demorou demais para abrir.')


def _start(empresa, somente_leitura, master_url):
    if somente_leitura:
        source = empresa.espelho / 'db.sqlite3'
        if not source.exists():
            raise MasterError('Ainda não há backup desta loja aqui. Clique em "Atualizar do Git".')
        work = empresa.folder / 'trabalho'
        shutil.rmtree(work, ignore_errors=True)
        work.mkdir(parents=True)
        db_path = work / 'db.sqlite3'
        sqlite_snapshot(source, db_path)  # cópia descartável: o espelho nunca é tocado
        media = empresa.espelho / 'media'
    else:
        db_path = empresa.implantacao / 'db.sqlite3'
        media = empresa.implantacao / 'media'

    port = _free_port()
    key = secrets.token_urlsafe(32)
    cookie = f'nbe_{empresa.codigo.replace("-", "_")}'
    log_dir = empresa.folder / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        'NABANDEJA_MODO': 'loja', 'DB_ENGINE': 'sqlite', 'SQLITE_PATH': str(db_path), 'MEDIA_ROOT': str(media),
        'LOG_DIR': str(log_dir), 'DJANGO_DEBUG': 'false', 'DJANGO_SECRET_KEY': secrets.token_urlsafe(50),
        'DJANGO_ALLOWED_HOSTS': '127.0.0.1,localhost', 'AUTO_ALLOW_LOCAL_HOSTS': 'false',
        'USE_HTTPS': 'false', 'SESSION_COOKIE_NAME': f'{cookie}_sessao', 'CSRF_COOKIE_NAME': f'{cookie}_csrf',
        'NABANDEJA_ESPELHO_NOME': empresa.nome, 'NABANDEJA_ESPELHO_SSO_KEY': key,
        'NABANDEJA_ESPELHO_MASTER_URL': master_url, 'NABANDEJA_SOMENTE_LEITURA': 'true' if somente_leitura else 'false',
        # Nunca envia backup nem usa credenciais do master a partir daqui.
        'NABANDEJA_BACKUP_REPO': '', 'NABANDEJA_GITHUB_TOKEN': '', 'NABANDEJA_SUPPORT_HASH': '',
        'PYTHONIOENCODING': 'utf-8',
    }
    log_path = log_dir / 'espelho.log'
    with open(log_path, 'wb') as log:
        proc = subprocess.Popen(
            [sys.executable, '-m', 'nabandeja_project.espelho', str(port)],
            cwd=settings.BASE_DIR, env=env, stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
    _wait_ready(proc, port, Path(log_path))
    return {'proc': proc, 'port': port, 'key': key, 'somente_leitura': somente_leitura}


def abrir(empresa, master_url):
    """Abre (ou reaproveita) a empresa e devolve o link de entrada de uso único."""
    somente_leitura = empresa.em_producao
    with _lock:
        info = _processes.get(empresa.codigo)
        if not _alive(info) or info['somente_leitura'] != somente_leitura:
            if _alive(info):
                _stop(info)
            info = _start(empresa, somente_leitura, master_url)
            _processes[empresa.codigo] = info
    token = signing.dumps({'n': secrets.token_hex(8)}, key=info['key'], salt=SSO_SALT)
    return f'http://127.0.0.1:{info["port"]}/suporte/espelho/{token}/'


def _stop(info):
    try:
        info['proc'].stdin.close()  # o processo fecha sozinho ao perder a entrada
        info['proc'].wait(timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        info['proc'].kill()


def fechar(codigo):
    with _lock:
        info = _processes.pop(codigo, None)
    if _alive(info):
        _stop(info)
        return True
    return False


def abertas():
    with _lock:
        return {codigo: info['port'] for codigo, info in _processes.items() if _alive(info)}
