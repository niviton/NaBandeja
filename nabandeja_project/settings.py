"""
Configurações do NaBandeja.

Tudo que muda por instalação vem do arquivo .env (veja .env.example e
docs/seguranca.md). Os valores padrão são seguros: DEBUG desligado.
"""

import importlib.util
import os
import socket
import sys
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# No executável (PyInstaller) os arquivos ficam em _internal/, mas o .env, o
# banco e os uploads ficam ao lado do .exe para sobreviver a atualizações.
IS_FROZEN = getattr(sys, 'frozen', False)
if IS_FROZEN:
    DATA_DIR = Path(sys.executable).resolve().parent
    BASE_DIR = DATA_DIR / '_internal'
else:
    DATA_DIR = BASE_DIR

from .envfile import is_master_mode, master_dir  # noqa: E402

try:
    from dotenv import load_dotenv
    if is_master_mode():
        # Painel master: o .env dele (token do GitHub etc.) fica fora do repositório.
        load_dotenv(master_dir() / '.env')
    load_dotenv(DATA_DIR / '.env')
except ImportError:
    pass


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on')


def env_list(name, default=''):
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(',') if item.strip()]


def env_path(name, default):
    value = os.getenv(name, '').strip()
    return Path(value) if value else Path(default)


# ---------------------------------------------------------------- Modo
# loja:   o sistema do restaurante (padrão).
# master: o painel do dono do NaBandeja, que cria as empresas e acompanha os
#         backups delas (docs/master.md). Guarda tudo em MASTER_DIR, fora do
#         repositório: chaves, bancos das empresas e pacotes de instalação.
NABANDEJA_MODO = os.getenv('NABANDEJA_MODO', 'loja').strip().lower()
IS_MASTER = NABANDEJA_MODO == 'master'
MASTER_DIR = master_dir()

# Empresa aberta pelo painel master (processo separado, nabandeja_project/espelho.py).
ESPELHO_NOME = os.getenv('NABANDEJA_ESPELHO_NOME', '').strip()
ESPELHO_SSO_KEY = os.getenv('NABANDEJA_ESPELHO_SSO_KEY', '').strip()
ESPELHO_MASTER_URL = os.getenv('NABANDEJA_ESPELHO_MASTER_URL', '').strip()
SOMENTE_LEITURA = env_bool('NABANDEJA_SOMENTE_LEITURA', False)


def get_local_ip():
    """IP da máquina na rede local (não envia nada para a internet)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(('8.8.8.8', 80))
            return sock.getsockname()[0]
    except OSError:
        return None


# ---------------------------------------------------------------- Segurança
DEBUG = env_bool('DJANGO_DEBUG', False)

DEFAULT_SECRET_KEY = 'django-insecure-nabandeja-apenas-desenvolvimento'
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', DEFAULT_SECRET_KEY)
if not DEBUG and SECRET_KEY == DEFAULT_SECRET_KEY:
    raise ImproperlyConfigured(
        'Defina DJANGO_SECRET_KEY no .env (o INICIAR_PC_NOVO.bat gera uma automaticamente).'
    )

ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost')

# Libera o IP e o nome do PC na rede local, que podem mudar (DHCP).
AUTO_ALLOW_LOCAL_HOSTS = env_bool('AUTO_ALLOW_LOCAL_HOSTS', True)
LOCAL_IP = get_local_ip()
MACHINE_NAME = socket.gethostname().strip().lower()
if AUTO_ALLOW_LOCAL_HOSTS:
    # <ip>.sslip.io aponta para o IP local: dá um domínio ao sistema para o
    # login com Google funcionar nos celulares (o Google não aceita IP).
    for host in (LOCAL_IP, MACHINE_NAME, f'{LOCAL_IP}.sslip.io' if LOCAL_IP else None):
        if host and host not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(host)

# Railway informa o domínio público e fica atrás de um proxy HTTPS.
RAILWAY_DOMAIN = os.getenv('RAILWAY_PUBLIC_DOMAIN', '').strip()
if RAILWAY_DOMAIN:
    ALLOWED_HOSTS.append(RAILWAY_DOMAIN)

if '*' in ALLOWED_HOSTS and not DEBUG:
    raise ImproperlyConfigured('Não use "*" em DJANGO_ALLOWED_HOSTS em produção.')

# O Django já aceita POSTs da mesma origem; esta lista é só para origens extras.
CSRF_TRUSTED_ORIGINS = env_list('DJANGO_CSRF_TRUSTED_ORIGINS')
if RAILWAY_DOMAIN:
    CSRF_TRUSTED_ORIGINS.append(f'https://{RAILWAY_DOMAIN}')

# HTTPS: só force quando houver certificado (deploy/windows/setup_ssl.bat).
USE_HTTPS = env_bool('USE_HTTPS', False)
SECURE_SSL_REDIRECT = env_bool('SECURE_SSL_REDIRECT', USE_HTTPS)
SESSION_COOKIE_SECURE = env_bool('SESSION_COOKIE_SECURE', USE_HTTPS)
CSRF_COOKIE_SECURE = env_bool('CSRF_COOKIE_SECURE', USE_HTTPS)
if USE_HTTPS:
    SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '0'))
if env_bool('TRUST_X_FORWARDED_PROTO', bool(RAILWAY_DOMAIN)):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = env_bool('USE_X_FORWARDED_HOST', False)

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = int(os.getenv('SESSION_COOKIE_AGE', str(60 * 60 * 16)))  # um turno
# Cookies não separam por porta: cada empresa aberta pelo painel master usa os seus.
SESSION_COOKIE_NAME = os.getenv('SESSION_COOKIE_NAME', 'sessionid')
CSRF_COOKIE_NAME = os.getenv('CSRF_COOKIE_NAME', 'csrftoken')

# Bloqueio de login após tentativas erradas (restaurante/security.py)
LOGIN_MAX_ATTEMPTS = int(os.getenv('LOGIN_MAX_ATTEMPTS', '5'))
LOGIN_LOCKOUT_SECONDS = int(os.getenv('LOGIN_LOCKOUT_SECONDS', '300'))

# ---------------------------------------------------------------- Aplicação
# Tempo real (restaurante/realtime.py). O mesmo código serve qualquer ambiente:
# - NABANDEJA_SERVIDOR é marcado por asgi.py / wsgi.py: em WSGI é sempre polling;
# - REALTIME_TRANSPORT: auto (WebSocket com polling de reserva), websocket, polling ou off;
# - ENABLE_REALTIME=false desliga só o WebSocket (as telas usam polling).
ENABLE_REALTIME = env_bool('ENABLE_REALTIME', True)
NABANDEJA_SERVIDOR = os.getenv('NABANDEJA_SERVIDOR', '').strip().lower()
REALTIME_TRANSPORT = os.getenv('REALTIME_TRANSPORT', 'auto').strip().lower()
REALTIME_POLL_SECONDS = max(2, int(os.getenv('REALTIME_POLL_SECONDS', '4')))
# Vários processos/servidores (Railway, VPS com mais de um worker): Redis para o WebSocket.
REDIS_URL = os.getenv('REDIS_URL', '').strip()

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'whitenoise.runserver_nostatic',
    'django.contrib.staticfiles',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'restaurante',
]

HAS_CHANNELS = importlib.util.find_spec('channels') is not None

if ENABLE_REALTIME and HAS_CHANNELS:
    INSTALLED_APPS.append('channels')
    if REDIS_URL and importlib.util.find_spec('channels_redis') is not None:
        CHANNEL_LAYERS = {'default': {'BACKEND': 'channels_redis.core.RedisChannelLayer', 'CONFIG': {'hosts': [REDIS_URL]}}}
    else:
        # Um processo só (PC da loja, Termux): em memória, sem Redis. Com vários
        # processos sem Redis o WebSocket só avisa quem está no mesmo processo,
        # mas o polling de reserva entrega o resto (o registro fica no banco).
        CHANNEL_LAYERS = {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'restaurante.middleware.ModoMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'nabandeja_project.urls'
WSGI_APPLICATION = 'nabandeja_project.wsgi.application'
ASGI_APPLICATION = 'nabandeja_project.asgi.application'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'restaurante.context_processors.settings_processor',
            ],
        },
    },
]

# ---------------------------------------------------------------- Banco
DATABASE_URL = os.getenv('DATABASE_URL', '').strip()
DB_ENGINE = os.getenv('DB_ENGINE', 'postgres' if DATABASE_URL else 'sqlite').strip().lower()

if DB_ENGINE == 'postgres' and DATABASE_URL:
    from .dburl import parse_database_url
    DATABASES = {'default': parse_database_url(DATABASE_URL, int(os.getenv('DB_CONN_MAX_AGE', '60')))}
elif DB_ENGINE == 'postgres':
    db_options = {}
    for option, env_name in [
        ('sslmode', 'POSTGRES_SSLMODE'),
        ('sslrootcert', 'POSTGRES_SSLROOTCERT'),
        ('sslcert', 'POSTGRES_SSLCERT'),
        ('sslkey', 'POSTGRES_SSLKEY'),
    ]:
        value = os.getenv(env_name, 'prefer' if option == 'sslmode' else '').strip()
        if value:
            db_options[option] = value

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('POSTGRES_DB', 'nabandeja'),
            'USER': os.getenv('POSTGRES_USER', 'nabandeja'),
            'PASSWORD': os.getenv('POSTGRES_PASSWORD', ''),
            'HOST': os.getenv('POSTGRES_HOST', '127.0.0.1'),
            'PORT': os.getenv('POSTGRES_PORT', '5432'),
            'CONN_MAX_AGE': int(os.getenv('DB_CONN_MAX_AGE', '60')),
            'CONN_HEALTH_CHECKS': True,
            'ATOMIC_REQUESTS': True,
            'OPTIONS': db_options,
        }
    }
elif DB_ENGINE == 'sqlite':
    if IS_MASTER:
        MASTER_DIR.mkdir(parents=True, exist_ok=True)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            # O master nunca usa SQLITE_PATH: um .env de loja não pode apontá-lo para o banco da loja.
            'NAME': (os.getenv('NABANDEJA_MASTER_DB') or MASTER_DIR / 'master.sqlite3') if IS_MASTER
                    else (os.getenv('SQLITE_PATH') or DATA_DIR / 'db.sqlite3'),
            'ATOMIC_REQUESTS': True,
            'OPTIONS': {
                'timeout': int(os.getenv('SQLITE_TIMEOUT', '20')),
                # IMMEDIATE evita "database is locked" quando dois garçons
                # gravam ao mesmo tempo (a transação já nasce com a trava).
                'transaction_mode': 'IMMEDIATE',
            },
        }
    }
else:
    raise ImproperlyConfigured(f'DB_ENGINE inválido: {DB_ENGINE!r} (use sqlite ou postgres).')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'restaurante.User'

CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# ---------------------------------------------------------------- Login com Google
# Crie as credenciais em https://console.cloud.google.com (docs/login-google.md).
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '').strip()
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '').strip()
GOOGLE_LOGIN_ENABLED = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APPS': [{'client_id': GOOGLE_CLIENT_ID, 'secret': GOOGLE_CLIENT_SECRET, 'key': ''}]
        if GOOGLE_LOGIN_ENABLED else [],
        'SCOPE': ['openid', 'email', 'profile'],
        'AUTH_PARAMS': {'prompt': 'select_account'},
    },
}
ACCOUNT_ADAPTER = 'restaurante.social.AccountAdapter'
SOCIALACCOUNT_ADAPTER = 'restaurante.social.SocialAccountAdapter'
SOCIALACCOUNT_LOGIN_ON_GET = False      # o botão faz POST (protegido por CSRF)
SOCIALACCOUNT_AUTO_SIGNUP = False
SOCIALACCOUNT_STORE_TOKENS = False
ACCOUNT_EMAIL_VERIFICATION = 'none'     # o e-mail já vem verificado pelo Google
ACCOUNT_LOGIN_METHODS = {'username'}

# ---------------------------------------------------------------- Idioma
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = os.getenv('TIME_ZONE', 'America/Sao_Paulo')
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------- Arquivos
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = DATA_DIR / 'staticfiles'
# Serve direto de static/ sem precisar de collectstatic (rede local).
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = DEBUG

MEDIA_URL = '/media/'
MEDIA_ROOT = env_path('MEDIA_ROOT', DATA_DIR / 'media')
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

# ---------------------------------------------------------------- Logs
LOG_DIR = env_path('LOG_DIR', DATA_DIR / 'logs')
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {'format': '{asctime} {levelname} {name}: {message}', 'style': '{'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'default'},
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'nabandeja.log',
            'maxBytes': 2 * 1024 * 1024,
            'backupCount': 5,
            'encoding': 'utf-8',
            'formatter': 'default',
        },
    },
    'root': {'handlers': ['console', 'file'], 'level': 'INFO'},
    'loggers': {
        'django.request': {'level': 'ERROR', 'propagate': True},
        'django.server': {'level': 'WARNING', 'propagate': True},
    },
}

# ---------------------------------------------------------------- Produto
NABANDEJA_VERSION = '3.2.0'
BACKUP_KEEP = int(os.getenv('BACKUP_KEEP', '48'))

# Backup externo criptografado (restaurante/services/backup_remoto.py). Os
# valores vêm prontos no pacote de instalação gerado pelo painel master.
BACKUP_REMOTO_REPO = os.getenv('NABANDEJA_BACKUP_REPO', '').strip()
BACKUP_REMOTO_CHAVE_PUBLICA = os.getenv('NABANDEJA_BACKUP_CHAVE_PUBLICA', '').strip()
BACKUP_REMOTO_CHAVE_SSH = env_path('NABANDEJA_BACKUP_CHAVE_SSH', DATA_DIR / 'chave-backup')
BACKUP_REMOTO_DIAS = int(os.getenv('BACKUP_REMOTO_DIAS', '14'))

# Painel master: onde criar os repositórios de dados das empresas.
# GitHub (recomendado): token com permissão de criar repositórios privados.
# Pasta (alternativa, ex.: disco de rede): NABANDEJA_REPOS_DIR.
GITHUB_TOKEN = os.getenv('NABANDEJA_GITHUB_TOKEN', '').strip()
GITHUB_OWNER = os.getenv('NABANDEJA_GITHUB_OWNER', '').strip()
REPOS_DIR = os.getenv('NABANDEJA_REPOS_DIR', '').strip()
# Endereço usado nos QR Codes impressos (ex.: https://cardapio.minhaloja.com.br).
# Vazio: usa o endereço pelo qual o gerente acessou o sistema.
PUBLIC_BASE_URL = os.getenv('PUBLIC_BASE_URL', '').strip().rstrip('/')
