"""
Backup externo criptografado: PC da loja -> repositório Git privado da empresa.

Cada empresa tem o SEU repositório de dados (nunca o do código) e a loja só
tem a chave de envio dele. O conteúdo vai cifrado com a chave pública do
painel master (services/cofre.py):

    manifest.json            versão, data e origem do backup (sem dados da loja)
    atual.nbk                último backup (banco + fotos, cifrado)
    diario/AAAA-MM-DD.nbk    um por dia, últimos BACKUP_REMOTO_DIAS

Cada envio é um commit novo SEM histórico, enviado com push --force: o
repositório não cresce para sempre e os pontos de restauração são os
arquivos de diario/.
"""

import base64
import hashlib
import io
import json
import logging
import os
import shutil
import subprocess
import tempfile
import threading
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

from django.conf import settings
from django.utils import timezone

from . import cofre
from .backup import db_path, is_sqlite, sqlite_snapshot

logger = logging.getLogger('nabandeja.backup')

GIT_TIMEOUT = 300
GIT_IDENTITY = ['-c', 'user.name=NaBandeja', '-c', 'user.email=backup@nabandeja.local']


class BackupError(Exception):
    pass


# ------------------------------------------------------------------ git

def _friendly(stderr):
    text = stderr.lower()
    if 'permission denied' in text or 'publickey' in text or 'authentication failed' in text or ' 403' in text:
        return 'O repositório recusou a chave de envio. Fale com o suporte NaBandeja.'
    if 'could not resolve host' in text or 'unable to access' in text or 'connection timed out' in text:
        return 'Sem conexão com a internet (ou o GitHub está fora do ar). Tentaremos de novo mais tarde.'
    if 'repository not found' in text or 'does not appear to be a git repository' in text:
        return 'Repositório de backup não encontrado. Fale com o suporte NaBandeja.'
    return stderr.strip().splitlines()[-1][:300] if stderr.strip() else 'Erro desconhecido no Git.'


def git(args, cwd, env=None, check=True):
    full_env = {**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'GCM_INTERACTIVE': 'never', **(env or {})}
    command = ['git', '-c', 'core.autocrlf=false', '-c', 'commit.gpgsign=false', '-c', 'gc.auto=0', *args]
    try:
        result = subprocess.run(
            command, cwd=cwd, env=full_env, capture_output=True, timeout=GIT_TIMEOUT,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
    except FileNotFoundError as exc:
        raise BackupError('O Git não está instalado neste computador (git-scm.com).') from exc
    except subprocess.TimeoutExpired as exc:
        raise BackupError('O envio demorou demais. Tentaremos de novo mais tarde.') from exc
    if check and result.returncode:
        stderr = result.stderr.decode('utf-8', 'replace')
        logger.warning('git %s falhou: %s', args[0], stderr.strip())
        raise BackupError(_friendly(stderr))
    return result


def auth_env(ssh_key=None, token=None):
    """Variáveis de ambiente para o git autenticar sem guardar nada em disco."""
    env = {}
    if ssh_key:
        key = Path(ssh_key).as_posix()
        env['GIT_SSH_COMMAND'] = (
            f'ssh -i "{key}" -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=accept-new'
        )
    if token:
        basic = base64.b64encode(f'x-access-token:{token}'.encode()).decode()
        env.update({
            'GIT_CONFIG_COUNT': '2',
            'GIT_CONFIG_KEY_0': 'http.https://github.com/.extraheader',
            'GIT_CONFIG_VALUE_0': f'Authorization: Basic {basic}',
            'GIT_CONFIG_KEY_1': 'credential.helper',
            'GIT_CONFIG_VALUE_1': '',
        })
    return env


def _ensure_repo(work_dir):
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    if not (work_dir / '.git').exists():
        git(['init', '-q'], work_dir)
    return work_dir


# ------------------------------------------------------------------ pacote (banco + fotos)

def build_archive(source_db, media_dir):
    """Zip com uma cópia consistente do banco e a pasta media/."""
    buffer = io.BytesIO()
    with tempfile.TemporaryDirectory() as tmp:
        snapshot = Path(tmp) / 'db.sqlite3'
        sqlite_snapshot(source_db, snapshot)
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.write(snapshot, 'db.sqlite3')
            media_dir = Path(media_dir)
            if media_dir.exists():
                for path in sorted(media_dir.rglob('*')):
                    if path.is_file():
                        archive.write(path, f'media/{path.relative_to(media_dir).as_posix()}')
    return buffer.getvalue()


def extract_archive(data, destination):
    """Restaura banco e fotos em destination/ (substitui o que existir lá)."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        if 'db.sqlite3' not in names:
            raise BackupError('Backup sem banco de dados.')
        for name in names:
            parts = PurePosixPath(name).parts
            if name.startswith('/') or '..' in parts or ':' in name or not (name == 'db.sqlite3' or parts[0] == 'media'):
                raise BackupError(f'Arquivo inesperado no backup: {name}')
        media = destination / 'media'
        if media.exists():
            shutil.rmtree(media)
        for name in names:
            if name.endswith('/'):
                continue
            target = destination / PurePosixPath(name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(name))
    return destination / 'db.sqlite3'


def make_manifest(blob, origem):
    return {
        'formato': 1,
        'versao': settings.NABANDEJA_VERSION,
        'criado_em': timezone.now().isoformat(timespec='seconds'),
        'origem': origem,
        'computador': settings.MACHINE_NAME,
        'tamanho': len(blob),
        'sha256': hashlib.sha256(blob).hexdigest(),
    }


# ------------------------------------------------------------------ enviar e buscar

def publish(work_dir, remote, blob, manifest, keep_days=14, env=None, today=None):
    """Grava o backup no repositório local e envia (commit único, push --force)."""
    work_dir = _ensure_repo(work_dir)
    today = today or timezone.localdate()
    (work_dir / 'atual.nbk').write_bytes(blob)
    daily = work_dir / 'diario'
    daily.mkdir(exist_ok=True)
    (daily / f'{today:%Y-%m-%d}.nbk').write_bytes(blob)
    for old in sorted(daily.glob('*.nbk'))[:-max(1, keep_days)]:
        old.unlink()
    (work_dir / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    (work_dir / 'LEIA-ME.txt').write_text(
        'Backup criptografado do NaBandeja. Só o painel master consegue abrir estes arquivos.\n',
        encoding='utf-8',
    )

    git(['add', '-A'], work_dir)
    tree = git(['write-tree'], work_dir).stdout.decode().strip()
    message = f'backup {manifest["criado_em"]} ({manifest["origem"]})'
    commit = git([*GIT_IDENTITY, 'commit-tree', tree, '-m', message], work_dir).stdout.decode().strip()
    # O commit anterior (refs/heads/main) continua aqui durante o push: o git
    # só envia o que o servidor ainda não tem (os arquivos diários repetidos não sobem de novo).
    git(['push', '--force', '--quiet', remote, f'{commit}:refs/heads/main'], work_dir, env=env)
    git(['update-ref', 'refs/heads/main', commit], work_dir)
    git(['reflog', 'expire', '--expire=now', '--all'], work_dir, check=False)
    git(['gc', '--prune=now', '--quiet'], work_dir, check=False)
    return commit


def fetch(work_dir, remote, env=None):
    """Baixa o último backup: {'manifest', 'atual', 'diarios'}. Usado pelo painel master."""
    work_dir = _ensure_repo(work_dir)
    ref = 'refs/remotes/empresa/main'
    git(['fetch', '--quiet', '--depth', '1', '--force', remote, f'+refs/heads/main:{ref}'], work_dir, env=env)
    manifest = json.loads(git(['cat-file', 'blob', f'{ref}:manifest.json'], work_dir).stdout)
    listing = git(['ls-tree', '--name-only', ref, 'diario/'], work_dir).stdout.decode().split()
    return {
        'manifest': manifest,
        'atual': git(['cat-file', 'blob', f'{ref}:atual.nbk'], work_dir).stdout,
        'diarios': sorted((PurePosixPath(name).name for name in listing), reverse=True),
    }


def read_daily(work_dir, name):
    if not name.endswith('.nbk') or '/' in name or '\\' in name or '..' in name:
        raise BackupError('Ponto de restauração inválido.')
    return git(['cat-file', 'blob', f'refs/remotes/empresa/main:diario/{name}'], Path(work_dir)).stdout


# ------------------------------------------------------------------ rotina da loja

_lock = threading.Lock()


def configured():
    return bool(settings.BACKUP_REMOTO_REPO and settings.BACKUP_REMOTO_CHAVE_PUBLICA)


def _base_dir():
    return Path(settings.DATA_DIR) / 'backups' / 'remoto'


def _status_file():
    return _base_dir() / 'status.json'


def status():
    """{'configurado', 'em_andamento', 'ultimo_ok', 'ultima_tentativa', 'erro'}"""
    data = {'configurado': configured(), 'em_andamento': _lock.locked()}
    try:
        saved = json.loads(_status_file().read_text(encoding='utf-8'))
    except (OSError, ValueError):
        saved = {}
    for key in ('ultimo_ok', 'ultima_tentativa'):
        value = saved.get(key)
        data[key] = datetime.fromisoformat(value) if value else None
    data['erro'] = saved.get('erro', '')
    return data


def _save_status(**changes):
    path = _status_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        saved = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        saved = {}
    saved.update(changes)
    path.write_text(json.dumps(saved, ensure_ascii=False), encoding='utf-8')


def run():
    """Envia o backup criptografado da loja. Retorna True, False (erro) ou None (não configurado/ocupado)."""
    if not configured() or not is_sqlite() or not db_path().exists():
        return None
    if not _lock.acquire(blocking=False):
        return None
    now = timezone.now().isoformat(timespec='seconds')
    try:
        blob = cofre.encrypt(build_archive(db_path(), settings.MEDIA_ROOT), settings.BACKUP_REMOTO_CHAVE_PUBLICA)
        ssh_key = settings.BACKUP_REMOTO_CHAVE_SSH if Path(settings.BACKUP_REMOTO_CHAVE_SSH).exists() else None
        publish(_base_dir() / 'repo', settings.BACKUP_REMOTO_REPO, blob, make_manifest(blob, 'loja'),
                keep_days=settings.BACKUP_REMOTO_DIAS, env=auth_env(ssh_key=ssh_key))
    except (BackupError, cofre.CofreError, OSError) as exc:
        logger.error('Backup externo falhou: %s', exc)
        _save_status(ultima_tentativa=now, erro=str(exc))
        return False
    finally:
        _lock.release()
    logger.info('Backup externo enviado (%s KB).', len(blob) // 1024)
    _save_status(ultima_tentativa=now, ultimo_ok=now, erro='')
    return True


def run_in_background():
    if configured() and not _lock.locked():
        threading.Thread(target=run, name='backup-remoto', daemon=True).start()
        return True
    return False
