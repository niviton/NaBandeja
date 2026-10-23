"""Criar, migrar e fazer backup das lojas hospedadas."""

import logging
import re

from django.core.management import call_command
from django.db import transaction

from . import tenancy
from .models import Loja

logger = logging.getLogger('nabandeja.central')

RESERVED = {'central', 'admin', 'static', 'media', 'nabandeja'}


class StoreError(Exception):
    pass


def validate_code(code):
    code = (code or '').strip().lower()
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,38}', code):
        raise StoreError('Código inválido: use de 2 a 39 letras minúsculas, números ou hífen (ex.: billa-burguer).')
    if code in RESERVED:
        raise StoreError(f'O código "{code}" é reservado. Escolha outro.')
    if Loja.objects.filter(code=code).exists() or tenancy.database_path(code).exists():
        raise StoreError(f'Já existe uma loja com o código "{code}".')
    return code


def migrate_store(loja):
    with tenancy.using(loja):
        call_command('migrate', database='default', interactive=False, verbosity=0)


def create_store(name, code, username, password, first_name=''):
    """Cria o banco da loja, as configurações e o gerente. Retorna a Loja."""
    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError

    from restaurante.models import AppSettings, User

    name = (name or '').strip()
    username = (username or '').strip()
    if not name:
        raise StoreError('Informe o nome da loja.')
    if not username:
        raise StoreError('Informe o usuário do gerente.')
    code = validate_code(code)
    try:
        validate_password(password)
    except ValidationError as exc:
        raise StoreError(' '.join(exc.messages)) from exc

    loja = Loja(code=code, name=name)
    tenancy.database_path(code).parent.mkdir(parents=True, exist_ok=True)
    try:
        migrate_store(loja)
        with tenancy.using(loja), transaction.atomic():
            store = AppSettings.get_settings()
            store.store_name = name
            store.company_code = code
            store.save()
            User.objects.create_user(username, password=password, role='gerente', first_name=first_name)
    except Exception:
        tenancy.database_path(code).unlink(missing_ok=True)
        raise
    loja.save()
    logger.info('Loja criada: %s', code)
    return loja


def support_user(loja):
    """Usuário de suporte dentro da loja (entra só pelo painel central, sem senha)."""
    from restaurante.models import User

    with tenancy.using(loja):
        user, _ = User.objects.get_or_create(username='nabandeja', defaults={'first_name': 'Suporte NaBandeja'})
        user.is_superuser = user.is_staff = user.is_active = True
        user.role = 'gerente'
        user.set_unusable_password()
        user.save()
        return user


def backup_all(keep=None):
    from restaurante.services.backup import run_backup

    done = []
    for loja in Loja.objects.all():
        with tenancy.using(loja):
            target = run_backup(keep)
        if target:
            done.append(target)
    return done
