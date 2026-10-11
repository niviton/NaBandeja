from django.test import TestCase, override_settings
from django.urls import reverse

from restaurante.models import User
from restaurante.services import orders

from . import factories as f


def new_order(user):
    order, _ = orders.place_order(user, f.FakeCart((f.product(), 1)), mesa='1', store_settings=f.open_store())
    return order


class LoginTests(TestCase):
    def setUp(self):
        f.user('ana', role='garcom')

    def login(self, password):
        return self.client.post(reverse('login'), {'username': 'ana', 'password': password}, follow=True)

    def test_login_leva_para_tela_da_funcao(self):
        self.assertRedirects(self.login('senha-forte-123'), reverse('waiter_view'))

    @override_settings(LOGIN_MAX_ATTEMPTS=3)
    def test_bloqueia_apos_tentativas_erradas(self):
        for _ in range(3):
            self.login('errada')
        response = self.login('senha-forte-123')
        self.assertContains(response, 'Muitas tentativas erradas')
        self.assertFalse(response.context['user'].is_authenticated)

    def test_rota_login_antiga_redireciona(self):
        self.assertRedirects(self.client.get('/login/'), reverse('login'))


class RoleTests(TestCase):
    def setUp(self):
        self.manager = f.user()
        self.waiter = f.user('ana', role='garcom')
        self.cook = f.user('chef', role='cozinha')

    def test_garcom_nao_entra_no_painel(self):
        self.client.force_login(self.waiter)
        self.assertRedirects(self.client.get(reverse('admin_dashboard')), reverse('waiter_view'))

    def test_cozinha_nao_acessa_carrinho(self):
        self.client.force_login(self.cook)
        self.assertEqual(self.client.post(reverse('api_clear_cart')).status_code, 403)

    def test_garcom_nao_cancela_pedido(self):
        order = new_order(self.manager)
        self.client.force_login(self.waiter)
        self.client.post(reverse('cancel_order', args=[order.pk]))
        order.refresh_from_db()
        self.assertEqual(order.status, 'cozinha')

    def test_desativar_usuario_mantem_historico(self):
        self.client.force_login(self.manager)
        self.client.post(reverse('user_delete', args=[self.waiter.pk]))
        self.assertFalse(User.objects.get(pk=self.waiter.pk).is_active)

    def test_nao_desativa_ultimo_gerente(self):
        other = f.user('outro', role='gerente')
        self.client.force_login(other)
        self.client.post(reverse('user_delete', args=[self.manager.pk]))
        self.client.force_login(self.manager)  # desativado: login forçado não vale
        self.client.force_login(other)
        self.client.post(reverse('user_delete', args=[other.pk]))
        self.assertTrue(User.objects.filter(role='gerente', is_active=True).exists())

    def test_redirecionamento_externo_bloqueado(self):
        self.client.force_login(self.manager)
        response = self.client.post(reverse('toggle_store_status'), {'next': 'https://site-malicioso.com'})
        self.assertRedirects(response, reverse('admin_dashboard'))


class SmokeTests(TestCase):
    """Todas as telas principais abrem sem erro."""

    def setUp(self):
        self.manager = f.user()
        self.order = new_order(self.manager)
        self.client.force_login(self.manager)

    def test_telas(self):
        for name, args in [
            ('admin_dashboard', []), ('admin_reports', []), ('admin_menu', []), ('admin_ingredients', []),
            ('admin_users', []), ('admin_settings', []), ('admin_online_orders', []), ('kitchen_view', []),
            ('waiter_view', []), ('manage_order', [self.order.pk]), ('close_order', [self.order.pk]),
            ('print_order', [self.order.pk]), ('product_create', []), ('category_create', []),
            ('ingredient_create', []), ('user_create', []), ('pwa_manifest', []), ('pwa_service_worker', []),
        ]:
            with self.subTest(name):
                self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200)

    def test_exportacoes(self):
        orders.close(self.order, 'pix', self.manager)
        for export, content_type in [('csv', 'text/csv'), ('pdf', 'application/pdf')]:
            with self.subTest(export):
                response = self.client.get(reverse('admin_reports'), {'export': export})
                self.assertTrue(response['Content-Type'].startswith(content_type))
