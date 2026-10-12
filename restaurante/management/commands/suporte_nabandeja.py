"""
Cria ou atualiza o superusuário do suporte NaBandeja nesta instalação.

    python manage.py suporte_nabandeja                 (pede a senha)
    python manage.py suporte_nabandeja --gerar-hash    (gera o hash da senha, para reutilizar)
    python manage.py suporte_nabandeja --hash "<hash>" (usa um hash gerado antes)

Use a mesma senha (ou o mesmo hash) em todos os clientes para entrar em
qualquer loja com o mesmo usuário. O hash pode ficar no .env de cada loja
(NABANDEJA_SUPPORT_HASH) sem expor a senha.
"""

import getpass
import os

from django.contrib.auth.hashers import identify_hasher, make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from restaurante.models import User

SUPPORT_USERNAME = 'nabandeja'


def ensure_support_user(password_hash):
    user, created = User.objects.get_or_create(username=SUPPORT_USERNAME)
    user.first_name = 'Suporte NaBandeja'
    user.role = 'gerente'
    user.is_active = True
    user.is_staff = True
    user.is_superuser = True
    user.password = password_hash
    user.save()
    return user, created


class Command(BaseCommand):
    help = 'Cria/atualiza o superusuário do suporte NaBandeja.'

    def add_arguments(self, parser):
        parser.add_argument('--hash', help='Hash de senha gerado com --gerar-hash.')
        parser.add_argument('--gerar-hash', action='store_true', help='Só gera o hash da senha e mostra na tela.')

    def _ask_password(self):
        password = getpass.getpass('Senha do suporte NaBandeja: ')
        if password != getpass.getpass('Repita a senha: '):
            raise CommandError('As senhas não conferem.')
        try:
            validate_password(password)
        except ValidationError as exc:
            raise CommandError(' '.join(exc.messages)) from exc
        if len(password) < 12:
            raise CommandError('Use pelo menos 12 caracteres: este usuário acessa todas as lojas.')
        return password

    def handle(self, *args, **options):
        if options['gerar_hash']:
            self.stdout.write(make_password(self._ask_password()))
            return

        password_hash = options['hash'] or os.getenv('NABANDEJA_SUPPORT_HASH', '').strip()
        if password_hash:
            try:
                identify_hasher(password_hash)
            except ValueError as exc:
                raise CommandError('Hash inválido. Gere com --gerar-hash.') from exc
        else:
            password_hash = make_password(self._ask_password())

        _, created = ensure_support_user(password_hash)
        action = 'criado' if created else 'atualizado'
        self.stdout.write(self.style.SUCCESS(f'Superusuário "{SUPPORT_USERNAME}" {action}.'))
