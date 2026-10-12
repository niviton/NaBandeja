"""
Cria (ou atualiza a senha do) administrador do painel master e a chave mestra.

Só funciona com NABANDEJA_MODO=master (o banco é o master.sqlite3, nunca o de uma loja).

    python manage.py admin_master --email voce@exemplo.com          (pede a senha)
    python manage.py admin_master --email voce@exemplo.com --senha-stdin < arquivo
"""

import getpass
import sys

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from restaurante.models import User
from restaurante.services import master


class Command(BaseCommand):
    help = 'Cria o administrador do painel master (NABANDEJA_MODO=master).'

    def add_arguments(self, parser):
        parser.add_argument('--email', required=True)
        parser.add_argument('--senha-stdin', action='store_true', help='Lê a senha da entrada padrão.')

    def handle(self, *args, **options):
        if not settings.IS_MASTER:
            raise CommandError('Rode com NABANDEJA_MODO=master: o administrador fica no banco do master, não no de uma loja.')
        email = options['email'].strip().lower()
        if options['senha_stdin']:
            # utf-8-sig: o PowerShell manda um BOM na frente do texto pelo pipe.
            password = sys.stdin.buffer.readline().decode('utf-8-sig').rstrip('\r\n')
        else:
            password = getpass.getpass('Senha do painel master: ')
            if password != getpass.getpass('Repita a senha: '):
                raise CommandError('As senhas não conferem.')

        user = User.objects.filter(username=email).first() or User(username=email)
        try:
            validate_password(password, user)
        except ValidationError as exc:
            raise CommandError(' '.join(exc.messages)) from exc

        created = user.pk is None
        user.email = email
        user.role = 'gerente'
        user.is_active = user.is_staff = user.is_superuser = True
        user.set_password(password)
        user.save()

        master.ensure_master_key()
        self.stdout.write(self.style.SUCCESS(f'Administrador {email} {"criado" if created else "atualizado"}.'))
        self.stdout.write(f'Pasta do master: {settings.MASTER_DIR}')
        self.stdout.write(self.style.WARNING(
            f'Faça uma cópia segura da chave mestra: {master.private_key_path()}\n'
            'Sem ela, nenhum backup das lojas pode ser aberto.'
        ))
