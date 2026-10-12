"""DATABASE_URL (Railway, Render, Heroku...) -> configuração do Django, sem dependências."""

from urllib.parse import parse_qsl, unquote, urlsplit

POSTGRES_SCHEMES = ('postgres', 'postgresql', 'pgsql')


def parse_database_url(url, conn_max_age=60):
    parts = urlsplit(url)
    if parts.scheme not in POSTGRES_SCHEMES:
        raise ValueError(f'DATABASE_URL não suportada: {parts.scheme!r} (use postgres://).')
    return {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': unquote(parts.path.lstrip('/')),
        'USER': unquote(parts.username or ''),
        'PASSWORD': unquote(parts.password or ''),
        'HOST': parts.hostname or '',
        'PORT': str(parts.port or ''),
        'CONN_MAX_AGE': conn_max_age,
        'CONN_HEALTH_CHECKS': True,
        'ATOMIC_REQUESTS': True,
        'OPTIONS': dict(parse_qsl(parts.query)),
    }
