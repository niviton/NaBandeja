"""Fluxo do dia: abrir/fechar, caixa, delivery, balcão pago antes, reabrir conta e abas das configurações."""

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from restaurante.models import AppSettings, CashSession, Order
from restaurante.services import cash, day, orders, payments

from . import factories as f

HX = {'HTTP_HX_REQUEST': 'true'}


class DayTests(TestCase):
    def setUp(self):
        self.manager = f.user()
        self.store = f.open_store()
        self.store.is_store_open = False
        self.store.save()
        self.burger = f.product(stock=50)

    def test_abrir_dia_abre_caixa_e_loja(self):
        session = day.open_day(self.manager, '50,00')
        self.assertEqual(session.opening_amount, Decimal('50.00'))
        self.assertTrue(AppSettings.get_settings().is_store_open)
        self.assertTrue(day.status()['is_open'])

    def test_fechar_dia_com_mesa_aberta_pede_confirmacao(self):
        day.open_day(self.manager, '0')
        orders.place_order(self.manager, f.FakeCart((self.burger, 1)), mesa='4', store_settings=AppSettings.get_settings())
        self.assertEqual(day.pending_items()[0][0], 'Mesas com conta aberta')
        with self.assertRaises(day.DayError):
            day.close_day(self.manager, '0')
        session, _ = day.close_day(self.manager, '0', force=True)
        self.assertEqual(session.status, 'closed')
        self.assertFalse(AppSettings.get_settings().is_store_open)

    def test_sangria_e_suprimento_entram_na_gaveta(self):
        session = day.open_day(self.manager, '100')
        cash.add_movement(self.manager, 'sangria', '30', 'Gás')
        cash.add_movement(self.manager, 'suprimento', '10', 'Troco')
        self.assertEqual(cash.summary(session)['expected_in_drawer'], Decimal('80'))
        with self.assertRaises(cash.CashError):
            cash.add_movement(self.manager, 'sangria', '0', 'nada')

    def test_telas_do_dia(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('admin_dashboard'))
        self.assertContains(response, 'Abrir o dia')
        self.client.post(reverse('open_day'), {'opening_amount': '20,00'})
        self.assertContains(self.client.get(reverse('admin_dashboard')), 'Fechar o dia')
        self.client.post(reverse('cash_movement'), {'kind': 'sangria', 'amount': '5', 'reason': 'Gelo'})
        session = CashSession.get_open_session()
        self.assertEqual(session.movements.count(), 1)
        response = self.client.post(reverse('close_day'), {'closing_amount': '15,00'})
        self.assertRedirects(response, reverse('cash_session_detail', args=[session.pk]))
        session.refresh_from_db()
        self.assertEqual(session.difference_amount, Decimal('0.00'))
        self.assertContains(self.client.get(reverse('cash_history')), 'R$ 15,00')


class ReopenTests(TestCase):
    def setUp(self):
        self.manager = f.user()
        self.store = f.open_store()
        self.burger = f.product(stock=50)
        self.client.force_login(self.manager)

    def paid_order(self):
        order, _ = orders.place_order(self.manager, f.FakeCart((self.burger, 1)), mesa='2', store_settings=self.store)
        orders.close(order, 'pix', self.manager)
        order.refresh_from_db()
        return order

    def test_reabre_com_caixa_aberto(self):
        cash.open_session(self.manager, '0')
        order = self.paid_order()
        self.assertTrue(orders.can_reopen(order))
        response = self.client.post(reverse('reopen_order', args=[order.pk]), {'reason': 'Forma errada'})
        order.refresh_from_db()
        self.assertIn(order.status, Order.ACTIVE_STATUSES)
        self.assertEqual(order.payments.count(), 0)
        self.assertRedirects(response, reverse('table_order', args=['2']), fetch_redirect_response=False)

    def test_nao_reabre_depois_de_fechar_o_caixa(self):
        cash.open_session(self.manager, '0')
        order = self.paid_order()
        cash.close_session(self.manager, '0')
        self.assertFalse(orders.can_reopen(order))
        self.client.post(reverse('reopen_order', args=[order.pk]), {'reason': 'x'})
        order.refresh_from_db()
        self.assertEqual(order.status, 'finalizado')


class DeliveryFlowTests(TestCase):
    def setUp(self):
        self.manager = f.user()
        self.store = f.open_store()
        self.burger = f.product(stock=50)
        self.client.force_login(self.manager)

    def delivery(self):
        order, _ = orders.place_order(
            self.manager, f.FakeCart((self.burger, 1)), order_type='delivery', cliente='Ana',
            address='Rua 1', store_settings=self.store,
        )
        return order

    def test_paga_na_entrega(self):
        order = self.delivery()
        with self.assertRaises(orders.OrderError):
            orders.dispatch(order)  # ainda na cozinha
        orders.mark_ready(order)
        self.client.post(reverse('dispatch_order', args=[order.pk]), **HX)
        order.refresh_from_db()
        self.assertIsNotNone(order.dispatched_at)
        response = self.client.post(reverse('deliver_order', args=[order.pk]), **HX)
        self.assertEqual(response['HX-Redirect'], reverse('close_order', args=[order.pk]))
        order.refresh_from_db()
        self.assertEqual(order.status, 'pronto')
        payments.add_payment(order, 'dinheiro', '30', self.manager)
        order.refresh_from_db()
        self.assertEqual(order.status, 'finalizado')

    def test_pago_antes_encerra_ao_entregar(self):
        order = self.delivery()
        payments.add_payment(order, 'pix', str(order.amount_due), self.manager)
        order.refresh_from_db()
        self.assertEqual(order.status, 'cozinha')
        self.assertIsNotNone(order.paid_at)
        orders.mark_ready(order)
        orders.dispatch(order)
        orders.mark_delivered(order, self.manager)
        order.refresh_from_db()
        self.assertEqual(order.status, 'finalizado')

    def test_quadro_mostra_colunas(self):
        order = self.delivery()
        response = self.client.get(reverse('delivery_board'))
        self.assertContains(response, 'Na cozinha')
        self.assertContains(response, f'#{order.id}')

    def test_quadro_some_sem_modulos(self):
        AppSettings.objects.update(modules={'delivery': False, 'online': False})
        self.assertEqual(self.client.get(reverse('delivery_board')).status_code, 404)


class CounterPrepaidTests(TestCase):
    def setUp(self):
        self.waiter = f.user('garcom', role='garcom')
        self.store = f.open_store()
        self.burger = f.product(stock=50)
        self.client.force_login(self.waiter)

    def test_enviar_e_receber_agora(self):
        self.client.post(reverse('cart_add', args=['novo:balcao', self.burger.pk]), **HX)
        response = self.client.post(reverse('cart_send', args=['novo:balcao']), {'cliente': 'João', 'pay_now': '1'}, **HX)
        order = Order.objects.get()
        self.assertEqual(response['HX-Redirect'], reverse('close_order', args=[order.pk]))

        response = self.client.post(reverse('add_payment', args=[order.pk]), {'method': 'pix', 'amount': '25,90'}, **HX)
        self.assertEqual(response['HX-Redirect'], reverse('waiter_view'))
        order.refresh_from_db()
        self.assertEqual(order.status, 'cozinha')
        self.assertIsNotNone(order.paid_at)
        self.assertContains(self.client.get(reverse('salao_board')), 'Entregar ao cliente')

        self.client.post(reverse('handoff_order', args=[order.pk]), **HX)
        order.refresh_from_db()
        self.assertEqual(order.status, 'finalizado')

    def test_nao_entrega_sem_pagar(self):
        order, _ = orders.place_order(self.waiter, f.FakeCart((self.burger, 1)), mesa='SEM MESA', store_settings=self.store)
        with self.assertRaises(orders.OrderError):
            orders.handoff(order, self.waiter)


class SettingsTabsTests(TestCase):
    def setUp(self):
        self.manager = f.user()
        self.store = f.open_store()
        self.client.force_login(self.manager)

    def test_aba_nao_zera_checkbox_de_outra(self):
        AppSettings.objects.update(kitchen_auto_print=True, public_menu_enabled=True)
        self.client.post(reverse('admin_settings'), {
            'aba': 'loja', 'store_name': 'Nova', 'primary_color': '#ef4444', 'secondary_color': '#fbbf24',
            'background_color': '#f8f9fa', 'text_color': '#1e293b',
        })
        store = AppSettings.get_settings()
        self.assertEqual(store.store_name, 'Nova')
        self.assertTrue(store.kitchen_auto_print)
        self.assertTrue(store.public_menu_enabled)

    def test_aba_desligada_volta_para_loja(self):
        AppSettings.objects.update(modules={'pix': False})
        response = self.client.get(reverse('admin_settings'), {'aba': 'pagamento'})
        self.assertEqual(response.context['tab'], 'loja')
