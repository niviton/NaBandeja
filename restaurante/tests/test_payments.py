from decimal import Decimal

from django.test import TestCase

from restaurante.models import Order
from restaurante.services import cash, orders, payments
from restaurante.services.orders import OrderError

from . import factories as f


class PaymentTests(TestCase):
    def setUp(self):
        self.manager = f.user()
        self.store = f.open_store()
        self.burger = f.product(price='30.00', stock=50)
        self.order, _ = orders.place_order(self.manager, f.FakeCart((self.burger, 3)), mesa='4', store_settings=self.store)

    def test_dividir_em_tres_formas(self):
        payments.add_payment(self.order, 'pix', Decimal('30.00'), self.manager)
        payments.add_payment(self.order, 'credito', Decimal('30.00'), self.manager)
        _, change, finished = payments.add_payment(self.order, 'dinheiro', Decimal('50.00'), self.manager)
        self.assertTrue(finished)
        self.assertEqual(change, Decimal('20.00'))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'finalizado')
        self.assertEqual(self.order.payment_method, 'misto')
        self.assertEqual(self.order.amount_paid, Decimal('90.00'))

    def test_cartao_nao_aceita_valor_maior(self):
        with self.assertRaises(OrderError):
            payments.add_payment(self.order, 'credito', Decimal('100.00'), self.manager)

    def test_valor_com_virgula(self):
        payments.add_payment(self.order, 'pix', '45,50', self.manager)
        self.assertEqual(self.order.amount_remaining, Decimal('44.50'))

    def test_divisao_igual_fecha_os_centavos(self):
        parts = payments.split_evenly(Decimal('100.00'), 3)
        self.assertEqual(parts, [Decimal('33.34'), Decimal('33.33'), Decimal('33.33')])
        self.assertEqual(sum(parts), Decimal('100.00'))

    def test_estorno_reabre_saldo(self):
        payment, _, _ = payments.add_payment(self.order, 'pix', Decimal('40.00'), self.manager)
        payments.remove_payment(payment)
        self.assertEqual(self.order.amount_remaining, Decimal('90.00'))

    def test_nao_cancela_com_pagamento_parcial(self):
        payments.add_payment(self.order, 'pix', Decimal('10.00'), self.manager)
        with self.assertRaises(OrderError):
            orders.cancel(self.order, self.manager)

    def test_caixa_conta_so_a_parte_em_dinheiro(self):
        session = cash.open_session(self.manager, '50')
        payments.add_payment(self.order, 'pix', Decimal('60.00'), self.manager)
        payments.add_payment(self.order, 'dinheiro', Decimal('30.00'), self.manager)
        totals = cash.summary(session)
        self.assertEqual(totals['cash_sales'], Decimal('30.00'))
        self.assertEqual(totals['expected_in_drawer'], Decimal('80.00'))
        self.assertEqual(totals['total_sales'], Decimal('90.00'))


class DiscountAndTableTests(TestCase):
    def setUp(self):
        self.manager = f.user()
        self.store = f.open_store()
        self.burger = f.product(price='20.00', stock=50)

    def open(self, mesa, qty=2):
        order, _ = orders.place_order(self.manager, f.FakeCart((self.burger, qty)), mesa=mesa, store_settings=self.store)
        return order

    def test_desconto_percentual_e_cortesia(self):
        order = self.open('1')
        orders.apply_discount(order, percent='10', reason='Cliente fiel')
        self.assertEqual(order.amount_due, Decimal('36.00'))
        orders.apply_discount(order, percent='100', reason='Cortesia aniversário')
        self.assertEqual(order.amount_due, Decimal('0.00'))
        payments.pay_remaining(order, 'dinheiro', self.manager)
        order.refresh_from_db()
        self.assertEqual(order.status, 'finalizado')

    def test_desconto_exige_motivo(self):
        with self.assertRaises(OrderError):
            orders.apply_discount(self.open('1'), value='5', reason='')

    def test_transferir_para_mesa_livre(self):
        order = self.open('1')
        moved = orders.transfer(order, '7', self.manager)
        self.assertEqual(moved.pk, order.pk)
        self.assertEqual(moved.mesa, '7')

    def test_juntar_com_mesa_ocupada(self):
        first = self.open('1', qty=1)
        second = self.open('2', qty=2)
        target = orders.transfer(first, '2', self.manager)
        self.assertEqual(target.pk, second.pk)
        self.assertEqual(target.items.get().quantity, 3)
        self.assertEqual(target.total, Decimal('60.00'))
        first.refresh_from_db()
        self.assertEqual(first.status, 'cancelado')
        self.assertEqual(first.total, Decimal('0'))

    def test_mesa_zero_a_esquerda_e_a_mesma(self):
        first = self.open('01')
        second, merged = orders.place_order(self.manager, f.FakeCart((self.burger, 1)), mesa='1', store_settings=self.store)
        self.assertTrue(merged)
        self.assertEqual(first.pk, second.pk)

    def test_pronto_e_servido(self):
        order = self.open('3')
        orders.mark_ready(order)
        self.assertIsNone(Order.objects.get(pk=order.pk).served_at)
        orders.mark_served(order)
        self.assertIsNotNone(Order.objects.get(pk=order.pk).served_at)
        orders.add_product(order, self.burger, self.manager)
        order.refresh_from_db()
        self.assertEqual(order.status, 'cozinha')
        self.assertIsNone(order.served_at)

    def test_comanda_imprime_so_itens_novos(self):
        order = self.open('5', qty=2)
        self.assertEqual([qty for _, qty in orders.items_to_print(order)], [2])
        orders.mark_printed(order)
        self.assertEqual(orders.items_to_print(order), [])
        orders.add_product(order, self.burger, self.manager)
        self.assertEqual([qty for _, qty in orders.items_to_print(order)], [1])

    def test_custo_congelado_no_item(self):
        self.burger.cost_price = Decimal('7.50')
        self.burger.save()
        order = self.open('6')
        self.assertEqual(order.items.get().unit_cost, Decimal('7.50'))
