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

try:
    from dotenv import load_dotenv
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

if '*' in ALLOWED_HOSTS and not DEBUG:
    raise ImproperlyConfigured('Não use "*" em DJANGO_ALLOWED_HOSTS em produção.')

# O Django já aceita POSTs da mesma origem; esta lista é só para origens extras.
CSRF_TRUSTED_ORIGINS = env_list('DJANGO_CSRF_TRUSTED_ORIGINS')

# HTTPS: só force quando houver certificado (deploy/windows/setup_ssl.bat).
USE_HTTPS = env_bool('USE_HTTPS', False)
SECURE_SSL_REDIRECT = env_bool('SECURE_SSL_REDIRECT', USE_HTTPS)
SESSION_COOKIE_SECURE = env_bool('SESSION_COOKIE_SECURE', USE_HTTPS)
CSRF_COOKIE_SECURE = env_bool('CSRF_COOKIE_SECURE', USE_HTTPS)
if USE_HTTPS:
    SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '0'))
if env_bool('TRUST_X_FORWARDED_PROTO', False):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = env_bool('USE_X_FORWARDED_HOST', False)

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = int(os.getenv('SESSION_COOKIE_AGE', str(60 * 60 * 16)))  # um turno

# Bloqueio de login após tentativas erradas (restaurante/security.py)
LOGIN_MAX_ATTEMPTS = int(os.getenv('LOGIN_MAX_ATTEMPTS', '5'))
LOGIN_LOCKOUT_SECONDS = int(os.getenv('LOGIN_LOCKOUT_SECONDS', '300'))

# ---------------------------------------------------------------- Aplicação
ENABLE_REALTIME = env_bool('ENABLE_REALTIME', True)

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
    CHANNEL_LAYERS = {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
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
DB_ENGINE = os.getenv('DB_ENGINE', 'sqlite').strip().lower()

if DB_ENGINE == 'postgres':
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
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.getenv('SQLITE_PATH') or DATA_DIR / 'db.sqlite3',
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
MEDIA_ROOT = DATA_DIR / 'media'
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

# ---------------------------------------------------------------- Logs
LOG_DIR = DATA_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)

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
NABANDEJA_VERSION = '2.2.0'
BACKUP_KEEP = int(os.getenv('BACKUP_KEEP', '48'))
