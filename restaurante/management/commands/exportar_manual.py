"""
Gera o manual do sistema como uma página HTML única, para compartilhar.

    python manage.py exportar_manual manual-nabandeja.html

O conteúdo é o mesmo da página Ajuda (templates/ajuda/_conteudo.html).
"""

import base64
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string


def _svg_data_uri(name):
    data = (Path(settings.BASE_DIR) / 'static' / 'brand' / name).read_bytes()
    return 'data:image/svg+xml;base64,' + base64.b64encode(data).decode('ascii')


class Command(BaseCommand):
    help = 'Gera o manual do NaBandeja em um arquivo HTML para compartilhar.'

    def add_arguments(self, parser):
        parser.add_argument('saida', nargs='?', default='manual-nabandeja.html')

    def handle(self, *args, **options):
        html = render_to_string('ajuda/standalone.html', {
            'nabandeja_version': settings.NABANDEJA_VERSION,
            'logo_light': _svg_data_uri('nabandeja-logo-horizontal.svg'),
            'logo_dark': _svg_data_uri('nabandeja-logo-horizontal-escuro.svg'),
        })
        target = Path(options['saida'])
        target.write_text(html, encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(f'Manual gerado: {target.resolve()}'))
