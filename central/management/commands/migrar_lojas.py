from django.core.management import call_command
from django.core.management.base import BaseCommand

from central import services
from central.models import Loja


class Command(BaseCommand):
    help = 'Atualiza o banco central e o banco de todas as lojas (rode depois de cada git pull).'

    def handle(self, *args, **options):
        call_command('migrate', database='central', interactive=False, verbosity=0)
        self.stdout.write('Banco central atualizado.')
        for loja in Loja.objects.all():
            services.migrate_store(loja)
            self.stdout.write(f'Loja {loja.code} atualizada.')
