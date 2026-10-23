from django.core.management.base import BaseCommand, CommandError

from central import services


class Command(BaseCommand):
    help = 'Cria uma loja: python manage.py criar_loja "Billá Burger" billa-burguer gerente SenhaForte123'

    def add_arguments(self, parser):
        parser.add_argument('nome')
        parser.add_argument('codigo')
        parser.add_argument('usuario')
        parser.add_argument('senha')

    def handle(self, *args, **options):
        try:
            loja = services.create_store(options['nome'], options['codigo'], options['usuario'], options['senha'])
        except services.StoreError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f'Loja criada: {loja.url()} (empresa "{loja.code}")'))
