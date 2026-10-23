"""
Várias lojas no mesmo servidor (NABANDEJA_MULTI_LOJA=true), um banco SQLite por loja.

- O banco "central" guarda as lojas cadastradas, as sessões e os administradores
  do servidor (superusuários que criam e acessam as lojas).
- O alias "default" aponta, a cada requisição, para o banco da loja do endereço
  /l/<código>/... Assim todo o código do restaurante (inclusive
  transaction.atomic() sem using=) continua igual ao da instalação de uma loja só.
- Sem loja (login geral e painel /central/), "default" aponta para um arquivo
  vazio e os modelos vão para o banco central.

Com o modo desligado (instalação na loja), nada aqui é usado.
"""

import contextlib
import contextvars
import re
from pathlib import Path

from django.conf import settings
from django.db import connections
from django.http import HttpResponseNotFound, HttpResponseRedirect
from django.urls import set_script_prefix

SESSION_KEY = 'nb_loja'
CENTRAL_APPS = {'central', 'sessions'}
PREFIX_RE = re.compile(r'^/l/(?P<code>[a-z0-9][a-z0-9-]*)(?P<rest>/.*)?$')

_current = contextvars.ContextVar('nabandeja_loja', default=None)


def enabled():
    return getattr(settings, 'MULTI_TENANT', False)


def current():
    """Loja ativa nesta requisição (ou None)."""
    return _current.get()


def current_code():
    loja = current()
    return loja.code if loja else ''


def database_path(code):
    return Path(settings.TENANTS_DIR) / f'{code}.sqlite3'


def _point_default_to(path):
    """Troca o arquivo do alias default (só nesta thread)."""
    conn = connections['default']
    path = str(path)
    if str(conn.settings_dict['NAME']) != path:
        conn.close()
        conn.settings_dict = {**conn.settings_dict, 'NAME': path}


def activate(loja):
    _current.set(loja)
    if loja is None:
        _point_default_to(settings.TENANTS_DIR / '_sem_loja.sqlite3')
    else:
        _point_default_to(database_path(loja.code))


@contextlib.contextmanager
def using(loja):
    """Executa um trecho dentro do banco de uma loja (fora de transação no default)."""
    previous = current()
    activate(loja)
    try:
        yield loja
    finally:
        activate(previous)


class TenantRouter:
    """Modelos centrais sempre no banco central; o resto na loja ativa."""

    def _db(self, model, **hints):
        if model._meta.app_label in CENTRAL_APPS:
            return 'central'
        return 'default' if current() is not None else 'central'

    db_for_read = _db
    db_for_write = _db

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db == 'default':
            return app_label not in CENTRAL_APPS
        return True


def mark_login(request):
    """Grava na sessão de qual loja é o usuário que acabou de entrar."""
    if enabled():
        request.session[SESSION_KEY] = current_code()


class TenantMiddleware:
    """
    /l/<código>/... ativa a loja, tira o prefixo do caminho e faz o reverse()
    gerar endereços com o prefixo. Uma sessão de outra loja não vale aqui.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from .models import Loja

        match = PREFIX_RE.match(request.path_info)
        session_code = request.session.get(SESSION_KEY) or ''
        logged_in = '_auth_user_id' in request.session

        if match:
            loja = Loja.objects.filter(code=match['code'], is_active=True).first()
            if loja is None:
                activate(None)
                return HttpResponseNotFound('Loja não encontrada ou desativada.')
            if not match['rest']:
                return HttpResponseRedirect(loja.url('/'))
            if logged_in and session_code != loja.code:
                request.session.flush()
            request.path_info = match['rest']
            set_script_prefix(f'/l/{loja.code}/')
            request.urlconf = settings.ROOT_URLCONF
            activate(loja)
        else:
            if logged_in and session_code:
                # Quem está logado numa loja volta para ela; o painel central exige outro login.
                if request.path_info == '/':
                    return HttpResponseRedirect(f'/l/{session_code}/dashboard/')
                if request.path_info.startswith('/central/'):
                    request.session.flush()
            request.urlconf = 'central.urls'
            activate(None)

        request.loja = current()
        try:
            return self.get_response(request)
        finally:
            activate(None)
