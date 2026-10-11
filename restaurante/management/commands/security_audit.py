from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Executa auditoria de segurança do Django para ambiente de produção.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Iniciando auditoria de segurança...'))

        # Checagens nativas do Django para produção.
        call_command('check', '--deploy')

        # Checagens adicionais específicas do projeto.
        warnings = []
        if settings.DEBUG:
            warnings.append('DJANGO_DEBUG está ativo. Não use DEBUG=true em produção.')

        if '*' in settings.ALLOWED_HOSTS:
            warnings.append('ALLOWED_HOSTS contém "*". Restrinja hosts em produção.')

        db_engine = settings.DATABASES['default']['ENGINE']
        if db_engine.endswith('sqlite3'):
            warnings.append('Banco em SQLite detectado. Para produção, prefira PostgreSQL.')

        if warnings:
            self.stdout.write(self.style.WARNING('Avisos adicionais encontrados:'))
            for item in warnings:
                self.stdout.write(f'- {item}')
        else:
            self.stdout.write(self.style.SUCCESS('Sem avisos adicionais do projeto.'))

        self.stdout.write(self.style.SUCCESS('Auditoria concluída.'))
