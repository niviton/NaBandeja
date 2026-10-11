from decimal import Decimal

from django.test import TestCase

from restaurante.models import Order, Product
from restaurante.services import orders
from restaurante.services.orders import OrderError

from . import factories as f


class PlaceOrderTests(TestCase):
    def setUp(self):
        self.waiter = f.user('ana', role='garcom')
        self.store = f.open_store()
        self.burger = f.product(stock=5)

    def place(self, *lines, **kwargs):
        params = dict(mesa='7', store_settings=self.store)
        params.update(kwargs)
        return orders.place_order(self.waiter, f.FakeCart(*lines), **params)

    def test_cria_pedido_e_baixa_estoque(self):
        order, merged = self.place((self.burger, 2))
        self.assertFalse(merged)
        self.assertEqual(order.total, Decimal('51.80'))
        self.assertEqual(order.items.get().product_name, 'X-Burger')
        self.burger.refresh_from_db()
        self.assertEqual(self.burger.stock, 3)

    def test_total_usa_preco_atual_do_produto(self):
        cart = f.FakeCart((self.burger, 1))
        cart.items[0]['price'] = 1.00  # preço velho guardado no carrinho
        order, _ = orders.place_order(self.waiter, cart, mesa='1', store_settings=self.store)
        self.assertEqual(order.total, Decimal('25.90'))

    def test_mesma_mesa_junta_na_conta_aberta(self):
        first, _ = self.place((self.burger, 1))
        second, merged = self.place((self.burger, 1))
        self.assertTrue(merged)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(second.items.get().quantity, 2)

    def test_observacao_diferente_vira_outra_linha(self):
        order, _ = self.place((self.burger, 1), (self.burger, 1, 'sem cebola'))
        self.assertEqual(order.items.count(), 2)
        self.assertEqual(order.total, Decimal('51.80'))

    def test_sem_estoque_nao_grava_nada(self):
        with self.assertRaises(OrderError):
            self.place((self.burger, 6))
        self.burger.refresh_from_db()
        self.assertEqual(self.burger.stock, 5)

    def test_loja_fechada(self):
        self.store.is_store_open = False
        with self.assertRaisesMessage(OrderError, 'Loja fechada'):
            self.place((self.burger, 1))

    def test_delivery_exige_endereco_e_guarda_plataforma(self):
        with self.assertRaises(OrderError):
            self.place((self.burger, 1), order_type='delivery')
        order, _ = self.place((self.burger, 1), order_type='delivery', address='Rua A, 10', platform='iFood')
        self.assertEqual(order.mesa, 'DELIVERY')
        self.assertEqual(order.platform, 'iFood')

    def test_receita_baixa_ingredientes(self):
        juice, fruit = f.product_with_recipe(ingredient_stock='1000', per_unit='300')
        self.place((juice, 3))
        fruit.refresh_from_db()
        self.assertEqual(fruit.stock_quantity, Decimal('100'))
        with self.assertRaises(OrderError):
            self.place((juice, 1), mesa='8')
        self.assertEqual(fruit.stock_movements.filter(movement_type='consumo').count(), 1)


class ChangeAndCloseTests(TestCase):
    def setUp(self):
        self.manager = f.user()
        self.store = f.open_store()
        self.burger = f.product(stock=10)
        self.order, _ = orders.place_order(
            self.manager, f.FakeCart((self.burger, 3)), mesa='2', store_settings=self.store
        )
        self.item = self.order.items.get()

    def stock(self):
        return Product.objects.get(pk=self.burger.pk).stock

    def test_remover_item_pendente_devolve_estoque(self):
        orders.change_item(self.order, self.item, 'remove', self.manager)
        self.assertEqual(self.stock(), 8)
        self.assertEqual(self.order.total, Decimal('51.80'))

    def test_remover_item_ja_preparado_nao_devolve(self):
        orders.mark_ready(self.order)
        self.item.refresh_from_db()
        orders.change_item(self.order, self.item, 'remove', self.manager)
        self.assertEqual(self.stock(), 7)

    def test_excluir_ultimo_item_cancela(self):
        orders.change_item(self.order, self.item, 'delete', self.manager)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'cancelado')

    def test_fechar_registra_quem_e_quando(self):
        orders.close(self.order, 'pix', self.manager)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'finalizado')
        self.assertIsNotNone(self.order.closed_at)
        self.assertEqual(self.order.closed_by, self.manager)

    def test_nao_fecha_pedido_cancelado(self):
        orders.cancel(self.order, self.manager)
        with self.assertRaises(OrderError):
            orders.close(self.order, 'dinheiro', self.manager)

    def test_forma_de_pagamento_invalida(self):
        with self.assertRaises(OrderError):
            orders.close(self.order, 'fiado', self.manager)

    def test_cancelar_devolve_so_o_pendente(self):
        orders.cancel(self.order, self.manager)
        self.assertEqual(self.stock(), 10)
        with self.assertRaises(OrderError):
            orders.cancel(self.order, self.manager)

    def test_marcar_pronto_so_da_cozinha(self):
        orders.mark_ready(self.order)
        self.assertEqual(Order.objects.get(pk=self.order.pk).status, 'pronto')
        with self.assertRaises(OrderError):
            orders.mark_ready(self.order)
