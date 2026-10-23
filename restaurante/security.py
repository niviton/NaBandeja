"""Proteção do login contra tentativa e erro de senha."""

import logging

from django.conf import settings
from django.core.cache import cache

from .services.audit import client_ip

logger = logging.getLogger('nabandeja.security')


def _key(request, username):
    from central.tenancy import current_code

    return f'login-fail:{current_code()}:{client_ip(request)}:{(username or "").strip().lower()}'


def is_locked(request, username):
    return cache.get(_key(request, username), 0) >= settings.LOGIN_MAX_ATTEMPTS


def register_failure(request, username):
    key = _key(request, username)
    attempts = cache.get(key, 0) + 1
    cache.set(key, attempts, settings.LOGIN_LOCKOUT_SECONDS)
    if attempts >= settings.LOGIN_MAX_ATTEMPTS:
        logger.warning('Login bloqueado: usuário=%s ip=%s', username, client_ip(request))
    return attempts


def reset(request, username):
    cache.delete(_key(request, username))
