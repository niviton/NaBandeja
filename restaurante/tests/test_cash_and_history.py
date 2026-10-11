from decimal import Decimal

from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse

from restaurante.models import Category, OrderItem, Product
from restaurante.services import cash, orders

from . import factories as f


class CashTests(TestCase):
    def setUp(self):
        self.manager = f.user()
        self.store = f.open_store()
        self.burger = f.product(stock=50)

    def sell(self, mesa, qty, method):
        order, _ = orders.place_order(
            self.manager, f.FakeCart((self.burger, qty)), mesa=mesa, store_settings=self.store
        )
        orders.close(order, method, self.manager)
        return order

    def test_gaveta_considera_so_dinheiro(self):
        cash.open_session(self.manager, '100,00')
        self.sell('1', 2, 'dinheiro')   # 51,80
        self.sell('2', 1, 'pix')        # 25,90
        self.sell('3', 1, 'credito')    # 25,90
        session, totals = cash.close_session(self.manager, '151,80')
        self.assertEqual(totals['total_sales'], Decimal('103.60'))
        self.assertEqual(session.expected_amount, Decimal('151.80'))
        self.assertEqual(session.difference_amount, Decimal('0.00'))

    def test_nao_abre_dois_caixas(self):
        cash.open_session(self.manager, '0')
        with self.assertRaises(cash.CashError):
            cash.open_session(self.manager, '0')

    def test_valor_invalido(self):
        with self.assertRaises(cash.CashError):
            cash.open_session(self.manager, '-5')


class HistoryProtectionTests(TestCase):
    def setUp(self):
        self.manager = f.user()
        self.client.force_login(self.manager)
        self.burger = f.product(stock=5)
        order, _ = orders.place_order(
            self.manager, f.FakeCart((self.burger, 1)), mesa='1', store_settings=f.open_store()
        )
        orders.close(order, 'dinheiro', self.manager)

    def test_banco_impede_apagar_produto_vendido(self):
        with self.assertRaises(ProtectedError):
            self.burger.delete()

    def test_excluir_produto_vendido_desativa(self):
        self.client.post(reverse('product_delete', args=[self.burger.pk]))
        self.burger.refresh_from_db()
        self.assertFalse(self.burger.is_active)
        self.assertEqual(OrderItem.objects.count(), 1)

    def test_excluir_produto_sem_venda_apaga(self):
        other = f.product(name='Novo')
        self.client.post(reverse('product_delete', args=[other.pk]))
        self.assertFalse(Product.objects.filter(pk=other.pk).exists())

    def test_excluir_categoria_com_produtos_desativa(self):
        category = self.burger.category
        self.client.post(reverse('category_delete', args=[category.pk]))
        category.refresh_from_db()
        self.assertFalse(category.is_active)
        self.assertTrue(Category.objects.filter(pk=category.pk).exists())

    def test_nome_do_produto_fica_na_venda(self):
        self.burger.name = 'X-Burger Novo'
        self.burger.save()
        self.assertEqual(OrderItem.objects.get().name, 'X-Burger')
