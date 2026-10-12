"""
Cria o arquivo .env na primeira execução em um PC novo.

Gera uma chave secreta própria e uma senha inicial para o gerente. Nunca
sobrescreve um .env existente.
"""

import os
import secrets
from pathlib import Path

TEMPLATE = """# Gerado automaticamente pelo NaBandeja em {data_dir}
# Veja docs/seguranca.md para todas as opções.
DJANGO_DEBUG=false
DJANGO_SECRET_KEY={secret_key}
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
AUTO_ALLOW_LOCAL_HOSTS=true

DB_ENGINE=sqlite
ENABLE_REALTIME=true
APP_PORT=8000

# Senha do usuário "gerente" criado no primeiro início. Troque após entrar.
NABANDEJA_INIT_ADMIN_PASSWORD={admin_password}

# Login com Google (opcional): veja docs/login-google.md
# GOOGLE_CLIENT_ID=
# GOOGLE_CLIENT_SECRET=
"""


MASTER_TEMPLATE = """# Painel master do NaBandeja (gerado em {data_dir}). Contém segredos: fica fora do repositório.
DJANGO_DEBUG=false
DJANGO_SECRET_KEY={secret_key}

# Repositórios de backup das empresas (docs/master.md)
# NABANDEJA_GITHUB_OWNER=seu-usuario-ou-organizacao
# NABANDEJA_GITHUB_TOKEN=github_pat_...
# NABANDEJA_REPOS_DIR=D:\\Backups\\NaBandeja
"""


def is_master_mode():
    return os.getenv('NABANDEJA_MODO', '').strip().lower() == 'master'


def master_dir():
    value = os.getenv('NABANDEJA_MASTER_DIR', '').strip()
    return Path(value) if value else Path.home() / 'NaBandejaMaster'


def ensure_master_env_file():
    """.env do painel master, em MASTER_DIR (nunca na pasta do código)."""
    folder = master_dir()
    env_path = folder / '.env'
    if not env_path.exists():
        folder.mkdir(parents=True, exist_ok=True)
        env_path.write_text(
            MASTER_TEMPLATE.format(data_dir=folder.resolve(), secret_key=secrets.token_urlsafe(50)), encoding='utf-8',
        )
    return env_path


def ensure_env_file(data_dir):
    """Retorna a senha inicial gerada, ou None se o .env já existia."""
    env_path = Path(data_dir) / '.env'
    if env_path.exists():
        return None
    admin_password = secrets.token_urlsafe(9)
    env_path.write_text(
        TEMPLATE.format(
            data_dir=Path(data_dir).resolve(),
            secret_key=secrets.token_urlsafe(50),
            admin_password=admin_password,
        ),
        encoding='utf-8',
    )
    return admin_password


if __name__ == '__main__':
    import sys

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
    password = ensure_env_file(target)
    if password:
        print(f'.env criado em {target}. Senha inicial do gerente: {password}')
    else:
        print('.env já existe; nada foi alterado.')
