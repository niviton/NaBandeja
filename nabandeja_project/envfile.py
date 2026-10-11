"""
Cria o arquivo .env na primeira execução em um PC novo.

Gera uma chave secreta própria e uma senha inicial para o gerente. Nunca
sobrescreve um .env existente.
"""

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
"""


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
