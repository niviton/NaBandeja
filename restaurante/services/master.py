"""
Painel master: as empresas vendidas, seus backups e pacotes de instalação.

Tudo fica em MASTER_DIR (fora do repositório do código):

    chaves/backup-privada.pem     abre os backups das lojas. FAÇA CÓPIA EM LUGAR SEGURO:
                                  sem ela nenhum backup pode ser restaurado.
    chaves/backup-publica.txt     vai no .env de cada loja (só cifra)
    empresas/<codigo>/
        empresa.json              cadastro e situação do último backup
        implantacao/              banco e fotos enquanto a empresa é preparada aqui
        espelho/                  último backup recebido da loja (aberto só para leitura)
        repo/                     cópia local do repositório de dados da empresa
        chave-envio               chave SSH da loja: só escreve no repositório DELA
        pacotes/                  instaladores gerados (contêm segredos)

Repositórios de dados, um por empresa:
    GitHub   NABANDEJA_GITHUB_TOKEN + NABANDEJA_GITHUB_OWNER: cria repositório
             privado e cadastra a chave de envio da loja (deploy key).
    Pasta    NABANDEJA_REPOS_DIR: repositórios git numa pasta (ex.: disco de rede).
"""

import io
import json
import logging
import os
import secrets
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify

from . import backup_remoto, cofre
from .backup import sqlite_snapshot

logger = logging.getLogger('nabandeja.master')

REPO_PREFIX = 'nabandeja-dados-'
LATE_AFTER = timedelta(days=2)
SQLITE_HEADER = b'SQLite format 3\x00'


class MasterError(Exception):
    pass


# ------------------------------------------------------------------ pastas e chaves

def master_dir():
    return Path(settings.MASTER_DIR)


def empresas_dir():
    return master_dir() / 'empresas'


def _keys_dir():
    return master_dir() / 'chaves'


def private_key_path():
    return _keys_dir() / 'backup-privada.pem'


def _restrict(path):
    """No Windows, deixa o arquivo legível só pelo usuário atual."""
    if os.name == 'nt':
        subprocess.run(
            ['icacls', str(path), '/inheritance:r', '/grant:r', f'{os.environ.get("USERNAME", "")}:F'],
            capture_output=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
    else:
        os.chmod(path, 0o600)


def _write_secret(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    _restrict(path)


def has_master_key():
    return private_key_path().exists()


def ensure_master_key():
    """Cria a chave mestra na primeira vez. Retorna a chave pública (texto)."""
    path = private_key_path()
    if not path.exists():
        pem, public = cofre.generate_master_key()
        _write_secret(path, pem)
        (_keys_dir() / 'backup-publica.txt').write_text(public + '\n', encoding='utf-8')
        logger.info('Chave mestra de backup criada em %s', path)
    return master_public_key()


def master_private_key():
    if not has_master_key():
        raise MasterError('Chave mestra não encontrada. Ela é criada ao abrir o painel pela primeira vez.')
    return cofre.load_private_key(private_key_path().read_bytes())


def master_public_key():
    return cofre.public_text(master_private_key())


# ------------------------------------------------------------------ onde ficam os repositórios

def remote_mode():
    if settings.GITHUB_TOKEN and settings.GITHUB_OWNER:
        return 'github'
    if settings.REPOS_DIR:
        return 'pasta'
    return ''


def _master_git_env():
    return backup_remoto.auth_env(token=settings.GITHUB_TOKEN) if remote_mode() == 'github' else {}


def _github(method, path, payload=None):
    request = urllib.request.Request(
        f'https://api.github.com{path}', method=method,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={
            'Authorization': f'Bearer {settings.GITHUB_TOKEN}',
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': 'NaBandeja-master',
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
            return response.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read()
        try:
            data = json.loads(body) if body else {}
        except ValueError:
            data = {}
        return exc.code, data
    except urllib.error.URLError as exc:
        raise MasterError(f'Sem conexão com o GitHub: {exc.reason}') from exc


def _create_github_repo(name, deploy_key_line, label):
    owner = settings.GITHUB_OWNER
    status, me = _github('GET', '/user')
    if status != 200:
        raise MasterError('O token do GitHub foi recusado. Confira NABANDEJA_GITHUB_TOKEN.')
    endpoint = '/user/repos' if me.get('login', '').lower() == owner.lower() else f'/orgs/{owner}/repos'
    status, repo = _github('POST', endpoint, {
        'name': name, 'private': True, 'description': f'Backup criptografado NaBandeja: {label}',
        'has_issues': False, 'has_projects': False, 'has_wiki': False, 'auto_init': False,
    })
    if status == 422:  # já existe: só reaproveita se for privado
        status, repo = _github('GET', f'/repos/{owner}/{name}')
    if status not in (200, 201):
        raise MasterError(f'O GitHub não criou o repositório {owner}/{name} ({repo.get("message", status)}).')
    if not repo.get('private'):
        raise MasterError(f'O repositório {owner}/{name} é PÚBLICO. Torne-o privado ou apague antes de continuar.')
    status, key = _github('POST', f'/repos/{owner}/{name}/keys', {
        'title': f'Loja {label} (envio de backup)', 'key': deploy_key_line, 'read_only': False,
    })
    if status not in (200, 201):
        raise MasterError(f'O GitHub não aceitou a chave de envio da loja ({key.get("message", status)}).')
    return f'git@github.com:{owner}/{name}.git', f'https://github.com/{owner}/{name}.git'


def _create_folder_repo(name):
    path = Path(settings.REPOS_DIR) / f'{name}.git'
    if not path.exists():
        path.mkdir(parents=True)
        backup_remoto.git(['init', '--bare', '--quiet'], path)
    return str(path), str(path)


# ------------------------------------------------------------------ cadastro

@dataclass
class Empresa:
    codigo: str
    data: dict = field(default_factory=dict)

    @property
    def folder(self):
        return empresas_dir() / self.codigo

    @property
    def nome(self):
        return self.data.get('nome', self.codigo)

    @property
    def implantacao(self):
        return self.folder / 'implantacao'

    @property
    def espelho(self):
        return self.folder / 'espelho'

    @property
    def ssh_key(self):
        return self.folder / 'chave-envio'

    @property
    def tem_repositorio(self):
        return bool(self.data.get('repo_loja'))

    @property
    def ultimo_backup_loja(self):
        return self._when('ultimo_backup_loja')

    def _when(self, key):
        value = self.data.get(key)
        return datetime.fromisoformat(value) if value else None

    @property
    def ultima_verificacao(self):
        return self._when('ultima_verificacao')

    @property
    def ultimo_pacote(self):
        return self._when('ultimo_pacote')

    @property
    def em_producao(self):
        """A loja já mandou backup: a partir daí os dados de verdade estão no PC dela."""
        return self.ultimo_backup_loja is not None

    @property
    def situacao(self):
        """(chave, rótulo) para a tela."""
        if not self.tem_repositorio:
            return 'sem_repositorio', 'Sem backup configurado'
        if not self.em_producao:
            return 'implantacao', 'Em implantação'
        if timezone.now() - self.ultimo_backup_loja > LATE_AFTER:
            return 'atrasada', 'Backup atrasado'
        return 'ativa', 'Ativa'

    @property
    def resumo(self):
        return self.data.get('resumo') or {}

    def save(self):
        self.folder.mkdir(parents=True, exist_ok=True)
        tmp = self.folder / 'empresa.json.tmp'
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(self.folder / 'empresa.json')


def listar():
    folder = empresas_dir()
    if not folder.exists():
        return []
    result = []
    for path in sorted(folder.iterdir()):
        info = path / 'empresa.json'
        if info.exists():
            result.append(Empresa(path.name, json.loads(info.read_text(encoding='utf-8'))))
    return sorted(result, key=lambda empresa: empresa.nome.lower())


def obter(codigo):
    info = empresas_dir() / codigo / 'empresa.json'
    if not codigo or codigo != slugify(codigo) or not info.exists():
        raise MasterError('Empresa não encontrada.')
    return Empresa(codigo, json.loads(info.read_text(encoding='utf-8')))


def normalizar_codigo(texto):
    return slugify(texto or '')[:40].strip('-')


# ------------------------------------------------------------------ banco das empresas

def _run_preparar(db_path, media_dir, log_dir, config):
    env = {
        **os.environ,
        'NABANDEJA_MODO': 'loja', 'SQLITE_PATH': str(db_path), 'MEDIA_ROOT': str(media_dir),
        'LOG_DIR': str(log_dir), 'DB_ENGINE': 'sqlite', 'DJANGO_DEBUG': 'false',
        'DJANGO_SECRET_KEY': secrets.token_urlsafe(50), 'NABANDEJA_GITHUB_TOKEN': '',
        'NABANDEJA_BACKUP_REPO': '', 'PYTHONIOENCODING': 'utf-8',
    }
    result = subprocess.run(
        [sys.executable, str(Path(settings.BASE_DIR) / 'manage.py'), 'preparar_empresa'],
        input=json.dumps(config).encode(), env=env, cwd=settings.BASE_DIR, capture_output=True, timeout=600,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
    )
    if result.returncode:
        logger.error('preparar_empresa falhou: %s', result.stderr.decode('utf-8', 'replace'))
        tail = result.stderr.decode('utf-8', 'replace').strip().splitlines()[-1:] or ['erro desconhecido']
        raise MasterError(f'Não foi possível preparar o banco da empresa: {tail[0][:300]}')


def resumo_banco(db_path):
    """Números da loja lidos direto do banco (somente leitura)."""
    db_path = Path(db_path)
    if not db_path.exists():
        return {}
    summary = {}
    connection = sqlite3.connect(f'file:{db_path.as_posix()}?mode=ro', uri=True)
    try:
        def one(sql, *params):
            try:
                return connection.execute(sql, params).fetchone()
            except sqlite3.Error:
                return None

        row = one('SELECT store_name, company_code FROM restaurante_appsettings WHERE id = 1')
        if row:
            summary['loja'], summary['codigo_login'] = row
        since = (timezone.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
        row = one("SELECT COUNT(*), COALESCE(SUM(total), 0) FROM restaurante_order "
                  "WHERE status = 'finalizado' AND closed_at >= ?", since)
        if row:
            summary['pedidos_30d'], summary['vendas_30d'] = row[0], round(float(row[1]), 2)
        row = one('SELECT MAX(created_at) FROM restaurante_order')
        if row and row[0]:
            summary['ultimo_pedido'] = str(row[0])[:16]
        row = one('SELECT COUNT(*) FROM restaurante_user WHERE is_active = 1 AND is_superuser = 0')
        if row:
            summary['equipe'] = row[0]
        row = one('SELECT COUNT(*) FROM restaurante_product')
        if row:
            summary['produtos'] = row[0]
    finally:
        connection.close()
    return summary


def _validate_sqlite(path):
    with open(path, 'rb') as handle:
        if handle.read(16) != SQLITE_HEADER:
            raise MasterError('O arquivo enviado não é um banco do NaBandeja (SQLite).')


# ------------------------------------------------------------------ criar e configurar

def criar(nome, codigo, gerente_usuario, gerente_senha, modulos, banco_importado=None):
    """Cria a empresa: banco próprio, gerente, repositório privado e primeiro backup."""
    nome = (nome or '').strip()[:200]
    codigo = normalizar_codigo(codigo or nome)
    if not nome or not codigo:
        raise MasterError('Informe o nome da empresa.')
    empresa = Empresa(codigo)
    if empresa.folder.exists():
        raise MasterError(f'Já existe uma empresa com o código "{codigo}".')
    ensure_master_key()

    empresa.implantacao.mkdir(parents=True)
    (empresa.implantacao / 'media').mkdir()
    db_path = empresa.implantacao / 'db.sqlite3'
    try:
        config = {'nome': nome, 'codigo': codigo, 'modulos': modulos}
        if banco_importado:
            with open(db_path, 'wb') as target:
                for chunk in banco_importado.chunks():
                    target.write(chunk)
            _validate_sqlite(db_path)
            config.pop('nome')  # banco importado mantém o nome da loja
        if gerente_usuario:
            config.update(gerente_usuario=gerente_usuario, gerente_senha=gerente_senha)
        _run_preparar(db_path, empresa.implantacao / 'media', empresa.folder / 'logs', config)
    except Exception:
        shutil.rmtree(empresa.folder, ignore_errors=True)
        raise

    empresa.data = {
        'nome': nome, 'codigo': codigo, 'criada_em': timezone.now().isoformat(timespec='seconds'),
        'gerente_usuario': gerente_usuario, 'modulos': modulos, 'importada': bool(banco_importado),
    }
    empresa.data['resumo'] = resumo_banco(db_path)
    empresa.save()

    if remote_mode():
        try:
            configurar_repositorio(empresa)
        except (MasterError, backup_remoto.BackupError) as exc:
            empresa.data['erro'] = str(exc)
            empresa.save()
    return empresa


def configurar_repositorio(empresa):
    """Cria o repositório privado da empresa, a chave de envio da loja e o primeiro backup."""
    mode = remote_mode()
    if not mode:
        raise MasterError('Configure NABANDEJA_GITHUB_TOKEN e NABANDEJA_GITHUB_OWNER (ou NABANDEJA_REPOS_DIR) no .env do master.')
    name = f'{REPO_PREFIX}{empresa.codigo}'
    if not empresa.ssh_key.exists():
        private_key, public_line = cofre.generate_ssh_key(f'nabandeja-{empresa.codigo}')
        _write_secret(empresa.ssh_key, private_key)
        (empresa.folder / 'chave-envio.pub').write_text(public_line + '\n', encoding='utf-8')
    public_line = (empresa.folder / 'chave-envio.pub').read_text(encoding='utf-8').strip()

    if mode == 'github':
        repo_loja, repo_master = _create_github_repo(name, public_line, empresa.nome)
    else:
        repo_loja, repo_master = _create_folder_repo(name)
    empresa.data.update(repo_loja=repo_loja, repo_master=repo_master, repo_tipo=mode, erro='')
    empresa.save()
    publicar(empresa)
    return empresa


def publicar(empresa):
    """Envia o banco de implantação (cifrado). Bloqueado depois que a loja já está em produção."""
    if empresa.em_producao:
        raise MasterError('A loja já envia os próprios backups: publicar daqui apagaria os dados dela.')
    if not empresa.tem_repositorio:
        raise MasterError('Esta empresa ainda não tem repositório de backup.')
    db_path = empresa.implantacao / 'db.sqlite3'
    blob = cofre.encrypt(backup_remoto.build_archive(db_path, empresa.implantacao / 'media'), master_public_key())
    manifest = backup_remoto.make_manifest(blob, 'master')
    backup_remoto.publish(empresa.folder / 'repo', empresa.data['repo_master'], blob, manifest,
                          keep_days=settings.BACKUP_REMOTO_DIAS, env=_master_git_env())
    empresa.data.update(publicado_em=manifest['criado_em'], resumo=resumo_banco(db_path), erro='')
    empresa.save()


def atualizar(empresa):
    """Busca o último backup no Git; se veio da loja, abre e guarda no espelho."""
    now = timezone.now().isoformat(timespec='seconds')
    try:
        if not empresa.tem_repositorio:
            raise MasterError('Esta empresa ainda não tem repositório de backup.')
        fetched = backup_remoto.fetch(empresa.folder / 'repo', empresa.data['repo_master'], env=_master_git_env())
        manifest = fetched['manifest']
        empresa.data['diarios'] = fetched['diarios']
        if manifest.get('origem') == 'loja':
            _abrir_no_espelho(empresa, fetched['atual'])
            empresa.data.update(
                ultimo_backup_loja=manifest['criado_em'], computador=manifest.get('computador', ''),
                versao_loja=manifest.get('versao', ''), resumo=resumo_banco(empresa.espelho / 'db.sqlite3'),
            )
    except (MasterError, backup_remoto.BackupError, cofre.CofreError, OSError) as exc:
        empresa.data.update(ultima_verificacao=now, erro=str(exc))
        empresa.save()
        raise MasterError(str(exc)) from exc
    empresa.data.update(ultima_verificacao=now, erro='')
    empresa.save()
    return empresa


def _abrir_no_espelho(empresa, blob):
    data = cofre.decrypt(blob, master_private_key())
    staging = empresa.folder / 'espelho.novo'
    shutil.rmtree(staging, ignore_errors=True)
    backup_remoto.extract_archive(data, staging)
    shutil.rmtree(empresa.espelho, ignore_errors=True)
    staging.replace(empresa.espelho)


def restaurar_ponto(empresa, nome_arquivo):
    """Abre um backup diário antigo no espelho (para consultar ou reinstalar)."""
    blob = backup_remoto.read_daily(empresa.folder / 'repo', nome_arquivo)
    _abrir_no_espelho(empresa, blob)
    empresa.data.update(espelho_de=nome_arquivo.removesuffix('.nbk'), resumo=resumo_banco(empresa.espelho / 'db.sqlite3'))
    empresa.save()


# ------------------------------------------------------------------ pacote de instalação

ENV_TEMPLATE = """# NaBandeja · {nome}
# Gerado pelo painel master em {data}. Contém segredos: não compartilhe.
DJANGO_DEBUG=false
DJANGO_SECRET_KEY={secret}
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
AUTO_ALLOW_LOCAL_HOSTS=true
DB_ENGINE=sqlite
ENABLE_REALTIME=true
APP_PORT=8000

# Backup externo criptografado (só o painel master consegue abrir)
NABANDEJA_BACKUP_REPO={repo}
NABANDEJA_BACKUP_CHAVE_PUBLICA={chave}
{suporte}"""

LEIA_ME = """NaBandeja · {nome}
==========================================

Instalação no PC da loja
1. Instale o Git (git-scm.com) e o Python 3.12 ou mais novo.
2. Baixe o sistema NaBandeja (pasta do código) neste computador.
3. Extraia TODO o conteúdo deste zip dentro da pasta do sistema
   (ao lado do manage.py), substituindo o que já existir.
4. Rode deploy\\windows\\start_system.bat.

Acesso
- Empresa: {codigo}
- Usuário: {gerente}  (senha definida no painel master)

Backup
- O sistema envia sozinho um backup criptografado a cada hora e também
  quando o gerente clica em "Salvar dados" no rodapé.
- O arquivo chave-backup só dá acesso ao repositório desta loja.

Este pacote contém segredos (chave de envio e senha do sistema).
Leve em pendrive ou por um canal privado e apague depois de instalar.
"""


def gerar_pacote(empresa):
    """Zip para instalar (ou reinstalar) a loja: .env, chave de envio, banco e fotos."""
    if not empresa.tem_repositorio:
        raise MasterError('Configure o backup da empresa antes de gerar o pacote.')
    source = empresa.espelho if empresa.em_producao else empresa.implantacao
    if not (source / 'db.sqlite3').exists():
        raise MasterError('Atualize do Git antes: ainda não há cópia do banco desta loja aqui.')

    suporte = os.getenv('NABANDEJA_SUPPORT_HASH', '').strip()
    env_text = ENV_TEMPLATE.format(
        nome=empresa.nome, data=timezone.localtime().strftime('%d/%m/%Y %H:%M'), secret=secrets.token_urlsafe(50),
        repo=empresa.data['repo_loja'], chave=master_public_key(),
        suporte=f'NABANDEJA_SUPPORT_HASH={suporte}\n' if suporte else '',
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('.env', env_text)
        archive.writestr('LEIA-ME-INSTALACAO.txt', LEIA_ME.format(
            nome=empresa.nome, codigo=empresa.data.get('codigo', empresa.codigo),
            gerente=empresa.data.get('gerente_usuario') or 'gerente'))
        if empresa.ssh_key.exists():
            archive.write(empresa.ssh_key, 'chave-backup')
        with tempfile.TemporaryDirectory() as tmp:
            snapshot = Path(tmp) / 'db.sqlite3'
            sqlite_snapshot(source / 'db.sqlite3', snapshot)
            archive.write(snapshot, 'db.sqlite3')
        media = source / 'media'
        if media.exists():
            for path in sorted(media.rglob('*')):
                if path.is_file():
                    archive.write(path, f'media/{path.relative_to(media).as_posix()}')

    folder = empresa.folder / 'pacotes'
    folder.mkdir(exist_ok=True)
    target = folder / f'nabandeja-{empresa.codigo}-{timezone.localtime():%Y%m%d-%H%M}.zip'
    _write_secret(target, buffer.getvalue())
    empresa.data['ultimo_pacote'] = timezone.now().isoformat(timespec='seconds')
    empresa.save()
    return target
