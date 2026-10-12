import os
import secrets

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Cria o usuário gerente inicial quando ainda não existe nenhum gerente ativo.'

    def handle(self, *args, **options):
        user_model = get_user_model()
        if user_model.objects.filter(role='gerente', is_active=True, is_superuser=False).exists():
            self.stdout.write('Já existe gerente ativo; nada a fazer.')
            return

        username = os.getenv('NABANDEJA_INIT_ADMIN_USERNAME') or os.getenv('BILLAR_INIT_ADMIN_USERNAME') or 'gerente'
        password = (os.getenv('NABANDEJA_INIT_ADMIN_PASSWORD') or os.getenv('BILLAR_INIT_ADMIN_PASSWORD') or '').strip()
        generated = not password
        if generated:
            password = secrets.token_urlsafe(9)

        user, _ = user_model.objects.get_or_create(username=username)
        user.role = 'gerente'
        user.is_active = True
        user.is_staff = False
        user.is_superuser = False
        user.set_password(password)
        user.save()

        self.stdout.write(self.style.SUCCESS(f'Usuário gerente pronto: {username}'))
        if generated:
            self.stdout.write(self.style.WARNING(f'Senha gerada: {password}  (anote e troque após entrar)'))
        else:
            self.stdout.write('Senha: a definida em NABANDEJA_INIT_ADMIN_PASSWORD no .env')
