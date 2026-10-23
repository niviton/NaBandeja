from django.core.management.base import BaseCommand

from central import services


class Command(BaseCommand):
    help = 'Faz backup do banco de todas as lojas (agende como tarefa diária no PythonAnywhere).'

    def handle(self, *args, **options):
        for target in services.backup_all():
            self.stdout.write(str(target))
