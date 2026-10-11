from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from restaurante.models import AppSettings, DeliveryZone, Expense, Order, Product, Table, TableCall
from restaurante.services import license, orders, tables
from restaurante.services.orders import OrderError

from . import factories as f

HX = {'HTTP_HX_REQUEST': 'true'}


class WaiterFlowTests(TestCase):
    """Fluxo pelo navegador: carrinho por mesa -> enviar -> pagar."""

    def setUp(self):
        f.open_store()
        self.waiter = f.user('ana', role='garcom')
        self.client.force_login(self.waiter)
        self.burger = f.product(price='25.00', stock=10)
        Table.objects.create(name='5')

    def test_lancar_e_fechar_mesa(self):
        key = 'mesa:5'
        self.client.post(reverse('cart_add', args=[key, self.burger.pk]), **HX)
        self.client.post(reverse('cart_add', args=[key, self.burger.pk]), {'notes': 'sem cebola'}, **HX)
        response = self.client.post(reverse('cart_send', args=[key]), **HX)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response['HX-Redirect'], reverse('table_order', args=['5']))

        order = Order.objects.get(mesa='5')
        self.assertEqual(order.items.count(), 2)
        self.assertEqual(order.total, Decimal('50.00'))
        self.assertEqual(tables.board()[0].status, 'cozinha')

        response = self.client.post(reverse('add_payment', args=[order.pk]), {'method': 'pix', 'amount': '50,00'}, **HX)
        self.assertEqual(response['HX-Redirect'], reverse('order_paid', args=[order.pk]))
        order.refresh_from_db()
        self.assertEqual(order.status, 'finalizado')

    def test_carrinhos_separados_por_mesa(self):
        self.client.post(reverse('cart_add', args=['mesa:5', self.burger.pk]), **HX)
        response = self.client.get(reverse('table_order', args=['6']))
        self.assertFalse(response.context['cart'])

    def test_erro_de_regra_volta_mensagem(self):
        response = self.client.post(reverse('cart_send', args=['mesa:5']), **HX)
        self.assertEqual(response.status_code, 422)
        self.assertIn('vazio', response.json()['message'])

    def test_garcom_nao_da_desconto(self):
        order, _ = orders.place_order(self.waiter, f.FakeCart((self.burger, 1)), mesa='5', store_settings=f.open_store())
        response = self.client.post(reverse('apply_discount', args=[order.pk]), {'percent': '50', 'reason': 'x'}, **HX)
        self.assertEqual(response.status_code, 403)


class PublicTests(TestCase):
    def setUp(self):
        cache.clear()
        self.store = f.open_store()
        self.table = Table.objects.create(name='9')
        self.burger = f.product(stock=5)

    def test_cardapio_da_mesa_e_chamado(self):
        response = self.client.get(reverse('table_menu', args=[self.table.public_token]))
        self.assertContains(response, self.burger.name)
        self.client.post(reverse('table_call', args=[self.table.public_token, 'conta']), **HX)
        self.client.post(reverse('table_call', args=[self.table.public_token, 'conta']), **HX)
        self.assertEqual(TableCall.objects.filter(table=self.table).count(), 1)  # sem duplicar

    def test_token_errado_nao_abre(self):
        self.assertEqual(self.client.get(reverse('table_menu', args=['inexistente'])).status_code, 404)

    def test_cardapio_desligado(self):
        AppSettings.objects.update(public_menu_enabled=False)
        self.assertEqual(self.client.get(reverse('table_menu', args=[self.table.public_token])).status_code, 404)

    def test_pedido_online_aguarda_e_gerente_aceita(self):
        AppSettings.objects.update(online_orders_enabled=True)
        zone = DeliveryZone.objects.create(name='Centro', fee=Decimal('6.00'))
        self.client.post(reverse('online_cart_add', args=[self.burger.pk]), **HX)
        response = self.client.post(reverse('online_checkout'), {
            'cliente': 'Maria', 'phone': '11999998888', 'address': 'Rua A, 1', 'zone': zone.pk,
        }, **HX)
        self.assertIn('HX-Redirect', response)
        order = Order.objects.get()
        self.assertEqual(order.status, 'pendente')
        self.assertEqual(order.amount_due, Decimal('31.90'))
        self.assertEqual(Product.objects.get(pk=self.burger.pk).stock, 5)  # só baixa ao aceitar

        manager = f.user()
        self.client.force_login(manager)
        self.client.post(reverse('online_order_decide', args=[order.pk, 'aceitar']))
        order.refresh_from_db()
        self.assertEqual(order.status, 'cozinha')
        self.assertEqual(Product.objects.get(pk=self.burger.pk).stock, 4)

    def test_pedido_online_desligado(self):
        self.assertEqual(self.client.get(reverse('online_order')).status_code, 404)


class LicenseTests(TestCase):
    def setUp(self):
        self.private = Ed25519PrivateKey.generate()
        from cryptography.hazmat.primitives import serialization
        self.public_pem = self.private.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        patcher = mock.patch.object(license, 'PUBLIC_KEY_PEM', self.public_pem)
        patcher.start()
        self.addCleanup(patcher.stop)

    def key(self, days):
        expires = date.today() + timedelta(days=days)
        return license.encode({'cliente': 'Teste', 'slug': 't', 'expira': expires.isoformat()}, self.private)

    def test_estados(self):
        self.assertEqual(license.status('').state, 'sem_licenca')
        self.assertEqual(license.status(self.key(60)).state, 'valida')
        self.assertEqual(license.status(self.key(5)).state, 'vencendo')
        self.assertEqual(license.status(self.key(-3)).state, 'tolerancia')
        self.assertEqual(license.status(self.key(-30)).state, 'bloqueada')
        self.assertEqual(license.status('lixo.lixo').state, 'invalida')

    def test_assinatura_de_outra_chave_e_invalida(self):
        other = Ed25519PrivateKey.generate()
        fake = license.encode({'cliente': 'X', 'expira': '2099-01-01'}, other)
        self.assertEqual(license.status(fake).state, 'invalida')

    def test_licenca_vencida_bloqueia_novos_pedidos(self):
        store = f.open_store()
        store.license_key = self.key(-30)
        with self.assertRaisesMessage(OrderError, 'Licença vencida'):
            orders.place_order(f.user(), f.FakeCart((f.product(), 1)), mesa='1', store_settings=store)

    def test_nao_troca_por_licenca_mais_curta(self):
        store = f.open_store()
        license.install(store, self.key(300))
        with self.assertRaises(ValueError):
            license.install(store, self.key(30))


class ManagerPagesTests(TestCase):
    def setUp(self):
        self.store = f.open_store()
        self.client.force_login(f.user())

    def test_assistente_aparece_na_primeira_vez(self):
        AppSettings.objects.update(setup_completed=False)
        self.assertRedirects(self.client.get(reverse('admin_dashboard')), reverse('setup_wizard', args=['loja']))

    def test_assistente_cria_mesas_e_categorias(self):
        self.client.post(reverse('setup_wizard', args=['mesas']), {'count': 5})
        self.client.post(reverse('setup_wizard', args=['cardapio']), {'categories': 'Lanches, Bebidas'})
        self.assertEqual(Table.objects.count(), 5)
        self.assertTrue(AppSettings.get_settings().setup_completed)

    def test_contas_a_pagar(self):
        self.client.post(reverse('expense_create'), {
            'description': 'Aluguel', 'category': 'aluguel', 'amount': '1500.00', 'due_date': date.today().isoformat(),
        })
        expense = Expense.objects.get()
        self.client.post(reverse('expense_pay', args=[expense.pk]))
        expense.refresh_from_db()
        self.assertEqual(expense.paid_at, date.today())

    def test_mesa_desmarcada_fica_inativa(self):
        table = Table.objects.create(name='3')
        self.client.post(reverse('table_edit', args=[table.pk]), {'name': '3', 'seats': '4', 'is_active_sent': '1'})
        table.refresh_from_db()
        self.assertFalse(table.is_active)

    def test_exportar_excel(self):
        manager = f.user('dono', role='gerente')
        order, _ = orders.place_order(manager, f.FakeCart((f.product(), 2)), mesa='1', store_settings=self.store)
        orders.close(order, 'pix', manager)
        response = self.client.get(reverse('admin_reports'), {'export': 'xlsx'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b'PK'))  # arquivo .xlsx (zip)

    @override_settings(BACKUP_KEEP=2)
    def test_backup_manual(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            with mock.patch('restaurante.services.backup.backup_dir', return_value=Path(folder)), \
                 mock.patch('restaurante.services.backup.is_sqlite', return_value=True):
                db = Path(folder) / 'origem.sqlite3'
                import sqlite3
                from contextlib import closing
                with closing(sqlite3.connect(db)) as connection:
                    connection.execute('create table t (x int)')
                with self.settings(DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': db}}):
                    from restaurante.services.backup import run_backup
                    self.assertTrue(run_backup().exists())
