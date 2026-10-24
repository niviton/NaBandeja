"""
Importa um cardápio (categorias, produtos, nome, slogan e logo da loja) de um arquivo JSON.

    python manage.py importar_cardapio cardapios/billa-burger.json
    python manage.py importar_cardapio cardapios/billa-burger.json --loja billar   (modo várias lojas)

Pode rodar de novo: atualiza preço e descrição pelo nome do produto e não apaga nada.
"""

import contextlib
import json
from decimal import Decimal
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from restaurante.models import AppSettings, Category, Product

STORE_FIELDS = ('store_name', 'slogan', 'whatsapp_number', 'phone')


class Command(BaseCommand):
    help = 'Importa um cardápio de um arquivo JSON (veja a pasta cardapios/).'

    def add_arguments(self, parser):
        parser.add_argument('arquivo')
        parser.add_argument('--loja', default='', help='Código da loja (só no modo várias lojas).')

    def handle(self, *args, **options):
        path = Path(options['arquivo'])
        if not path.exists():
            raise CommandError(f'Arquivo não encontrado: {path}')
        data = json.loads(path.read_text(encoding='utf-8'))

        with self._store_context(options['loja']):
            created, updated = self._import(data, path.parent)
        self.stdout.write(self.style.SUCCESS(
            f'Cardápio importado: {created} produto(s) novo(s), {updated} atualizado(s).'
        ))

    def _store_context(self, code):
        from django.conf import settings

        if not settings.MULTI_TENANT:
            if code:
                raise CommandError('--loja só vale no modo várias lojas (NABANDEJA_MULTI_LOJA=true).')
            return contextlib.nullcontext()
        if not code:
            raise CommandError('Informe a loja: --loja <código>.')
        from central import tenancy
        from central.models import Loja

        loja = Loja.objects.filter(code=code).first()
        if loja is None:
            raise CommandError(f'Loja "{code}" não existe. Veja os códigos no painel /central/.')
        return tenancy.using(loja)

    @transaction.atomic
    def _import(self, data, base_dir):
        store = AppSettings.get_settings()
        info = data.get('loja', {})
        for field in STORE_FIELDS:
            if info.get(field):
                setattr(store, field, info[field])
        logo_path = base_dir / info['logo'] if info.get('logo') else None
        already = store.logo and Path(store.logo.name).name.startswith(logo_path.stem) if logo_path else True
        if not already:
            with logo_path.open('rb') as handle:
                store.logo.save(logo_path.name, File(handle), save=False)
        store.save()

        default_stock = int(data.get('estoque_padrao', 0))
        created = updated = 0
        for order, group in enumerate(data.get('categorias', []), start=1):
            category, _ = Category.objects.update_or_create(
                name=group['nome'],
                defaults={'icon': group.get('icone', '🍽️'), 'order': order, 'is_active': True},
            )
            for item in group.get('produtos', []):
                product = Product.objects.filter(name=item['nome'], category=category).first()
                fields = {'price': Decimal(item['preco']), 'description': item.get('descricao', ''), 'is_active': True}
                if product is None:
                    Product.objects.create(name=item['nome'], category=category,
                                           stock=int(item.get('estoque', default_stock)), **fields)
                    created += 1
                else:
                    for key, value in fields.items():
                        setattr(product, key, value)
                    product.save()
                    updated += 1
        return created, updated
