"""
Prepara o banco de uma empresa nova (ou importada) para o painel master.

Roda num processo separado, com SQLITE_PATH apontando para o banco da
empresa, e recebe a configuração em JSON pela entrada padrão:

    {"nome": "...", "codigo": "...", "modulos": {...},
     "gerente_usuario": "...", "gerente_senha": "..."}

Todos os campos são opcionais: num banco importado só o que vier é alterado.
"""

import json
import sys

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from restaurante.models import AppSettings, User
from restaurante.modules import MODULE_KEYS


class Command(BaseCommand):
    help = 'Aplica as migrações e configura loja e gerente (uso interno do painel master).'

    def handle(self, *args, **options):
        config = json.loads(sys.stdin.read() or '{}')
        call_command('migrate', interactive=False, verbosity=0)

        with transaction.atomic():
            store = AppSettings.get_settings()
            if config.get('nome'):
                store.store_name = config['nome'][:200]
            if config.get('codigo'):
                store.company_code = config['codigo'][:40]
            if isinstance(config.get('modulos'), dict):
                store.modules = {key: bool(config['modulos'].get(key, True)) for key in MODULE_KEYS}
            store.save()

            username = (config.get('gerente_usuario') or '').strip()
            if username:
                user, _ = User.objects.get_or_create(username=username)
                user.role = 'gerente'
                user.is_active = True
                user.is_staff = False
                user.is_superuser = False
                user.set_password(config['gerente_senha'])
                user.save()

        self.stdout.write(json.dumps({'loja': store.store_name, 'codigo': store.company_code}))
