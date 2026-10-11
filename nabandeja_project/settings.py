"""
Django settings for nabandeja_project project.
NaBandeja - sistema modular de gestão para restaurantes
"""

from pathlib import Path
import os
import socket
import sys
from django.core.exceptions import ImproperlyConfigured

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Detecta se está rodando como executável PyInstaller
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).resolve().parent / '_internal'


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on')

# SECURITY WARNING: keep the secret key used in production secret!
DEFAULT_SECRET_KEY = 'django-insecure-nabandeja-change-this-in-production'
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', DEFAULT_SECRET_KEY)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env_bool('DJANGO_DEBUG', True)

if not DEBUG and SECRET_KEY == DEFAULT_SECRET_KEY:
    raise ImproperlyConfigured('Defina DJANGO_SECRET_KEY com um valor forte em produção.')

raw_allowed_hosts = os.getenv('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost').strip()
ALLOWED_HOSTS = [host.strip() for host in raw_allowed_hosts.split(',') if host.strip()]

AUTO_ALLOW_LOCAL_HOSTS = env_bool('AUTO_ALLOW_LOCAL_HOSTS', DEBUG)


def split_csv_env(name):
    raw = os.getenv(name, '').strip()
    return [item.strip() for item in raw.split(',') if item.strip()]

# Detecta IP local automaticamente para acesso em rede local
def get_local_ip():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(('8.8.8.8', 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except Exception:
        return None

local_ip = get_local_ip()
if AUTO_ALLOW_LOCAL_HOSTS and local_ip and local_ip not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(local_ip)

machine_name = socket.gethostname().strip().lower()
if AUTO_ALLOW_LOCAL_HOSTS and machine_name and machine_name not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(machine_name)

# Aceita qualquer IP local em modo executável (para facilitar acesso em rede)
if getattr(sys, 'frozen', False) and env_bool('ALLOW_ANY_HOST_FROZEN', False):
    ALLOWED_HOSTS.append('*')

ENABLE_REALTIME = os.getenv('ENABLE_REALTIME', 'true').strip().lower() == 'true'

# Em desenvolvimento (localhost + Codespaces), aceitar variações de host/porta
# evita falhas intermitentes de CSRF no login e nos POSTs AJAX.
CSRF_TRUSTED_ORIGINS = []
if DEBUG:
    CSRF_TRUSTED_ORIGINS.extend([
        'http://localhost',
        'https://localhost',
        'http://127.0.0.1',
        'https://127.0.0.1',
        'http://localhost:8000',
        'https://localhost:8000',
        'http://127.0.0.1:8000',
        'https://127.0.0.1:8000',
        'https://*.app.github.dev',
        'https://*.githubpreview.dev',
    ])

CSRF_TRUSTED_ORIGINS.extend(split_csv_env('DJANGO_CSRF_TRUSTED_ORIGINS'))

if local_ip and DEBUG:
    CSRF_TRUSTED_ORIGINS.extend([
        f'http://{local_ip}',
        f'https://{local_ip}',
        f'http://{local_ip}:8000',
        f'https://{local_ip}:8000',
    ])

if machine_name and DEBUG:
    CSRF_TRUSTED_ORIGINS.extend([
        f'http://{machine_name}',
        f'https://{machine_name}',
        f'http://{machine_name}:8000',
        f'https://{machine_name}:8000',
    ])

codespace_name = os.getenv('CODESPACE_NAME', '').strip()
forward_domain = os.getenv('GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN', '').strip()
if DEBUG and codespace_name and forward_domain:
    CSRF_TRUSTED_ORIGINS.append(f'https://{codespace_name}-*.{forward_domain}')

CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(CSRF_TRUSTED_ORIGINS))

# Em desenvolvimento, manter token CSRF por cookie é mais compatível com os
# fluxos AJAX já existentes no projeto.
CSRF_USE_SESSIONS = False

# Ajustes para execução atrás do proxy HTTPS do Codespaces.
if os.getenv('CODESPACES', '').lower() == 'true':
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    USE_X_FORWARDED_HOST = True
    # Compatível com acesso por localhost/http e também por URL https do Codespaces.
    SECURE_SSL_REDIRECT = False
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_SECURE = False

if env_bool('TRUST_X_FORWARDED_PROTO', False):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

if env_bool('USE_X_FORWARDED_HOST', False):
    USE_X_FORWARDED_HOST = True

if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool('SECURE_SSL_REDIRECT', True)
    SESSION_COOKIE_SECURE = env_bool('SESSION_COOKIE_SECURE', True)
    CSRF_COOKIE_SECURE = env_bool('CSRF_COOKIE_SECURE', True)
    SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '31536000'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', True)
    SECURE_HSTS_PRELOAD = env_bool('SECURE_HSTS_PRELOAD', True)
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_REFERRER_POLICY = 'same-origin'
    SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'

if not DEBUG:
    if SECRET_KEY == DEFAULT_SECRET_KEY:
        raise ImproperlyConfigured('Defina DJANGO_SECRET_KEY com um valor forte em produção.')
    if not ALLOWED_HOSTS:
        raise ImproperlyConfigured('Defina DJANGO_ALLOWED_HOSTS em produção.')
    if '*' in ALLOWED_HOSTS:
        raise ImproperlyConfigured('Nao use "*" em DJANGO_ALLOWED_HOSTS em produção.')
    if not CSRF_TRUSTED_ORIGINS:
        raise ImproperlyConfigured('Defina DJANGO_CSRF_TRUSTED_ORIGINS em produção.')

SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'crispy_forms',
    'crispy_bootstrap5',
    'restaurante',
]

try:
    import channels  # noqa: F401
    HAS_CHANNELS = True
except Exception:
    HAS_CHANNELS = False

if ENABLE_REALTIME and HAS_CHANNELS:
    INSTALLED_APPS.append('channels')

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'nabandeja_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'restaurante.context_processors.settings_processor',
            ],
        },
    },
]

WSGI_APPLICATION = 'nabandeja_project.wsgi.application'
ASGI_APPLICATION = 'nabandeja_project.asgi.application'

# Database
DB_ENGINE = os.getenv('DB_ENGINE', 'sqlite').strip().lower()

if DB_ENGINE == 'postgres':
    db_sslmode = os.getenv('POSTGRES_SSLMODE', 'prefer').strip()
    db_options = {}
    if db_sslmode:
        db_options['sslmode'] = db_sslmode

    sslrootcert = os.getenv('POSTGRES_SSLROOTCERT', '').strip()
    sslcert = os.getenv('POSTGRES_SSLCERT', '').strip()
    sslkey = os.getenv('POSTGRES_SSLKEY', '').strip()
    if sslrootcert:
        db_options['sslrootcert'] = sslrootcert
    if sslcert:
        db_options['sslcert'] = sslcert
    if sslkey:
        db_options['sslkey'] = sslkey

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
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
            'ATOMIC_REQUESTS': True,
            'OPTIONS': {
                'timeout': int(os.getenv('SQLITE_TIMEOUT', '20')),
            },
        }
    }

REDIS_URL = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/1')

if ENABLE_REALTIME and HAS_CHANNELS:
    # Usa InMemoryChannelLayer para funcionar sem Redis
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        },
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Crispy Forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# Login/Logout URLs
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'

# Custom User Model
AUTH_USER_MODEL = 'restaurante.User'
