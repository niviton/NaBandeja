import os
import secrets

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Garante que exista um usuário gerente padrão para primeiro acesso.'

    def handle(self, *args, **options):
        user_model = get_user_model()
        username = os.getenv('NABANDEJA_INIT_ADMIN_USERNAME') or os.getenv('BILLAR_INIT_ADMIN_USERNAME', 'gerente')
        password = (os.getenv('NABANDEJA_INIT_ADMIN_PASSWORD') or os.getenv('BILLAR_INIT_ADMIN_PASSWORD', '')).strip()

        if not password:
            if settings.DEBUG:
                # Em desenvolvimento, gera senha forte automaticamente para evitar padrão previsível.
                password = secrets.token_urlsafe(12)
            else:
                raise RuntimeError(
                    'Defina NABANDEJA_INIT_ADMIN_PASSWORD para criar o usuário inicial em produção.'
                )

        user, created = user_model.objects.get_or_create(
            username=username,
            defaults={
                'role': 'gerente',
                'is_staff': True,
                'is_superuser': True,
            },
        )

        if created:
            user.set_password(password)
            user.save(update_fields=['password'])
            self.stdout.write(self.style.SUCCESS(f'Usuário inicial criado: {username}'))
            self.stdout.write(self.style.WARNING(f'Senha inicial: {password}'))
            return

        self.stdout.write(f'Usuário inicial já existe: {username}')
