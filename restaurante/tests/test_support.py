from django.contrib.auth.hashers import make_password
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from restaurante.models import AppSettings, User
from restaurante.modules import enabled_modules

from . import factories as f


class CompanyLoginTests(TestCase):
    def setUp(self):
        store = f.open_store()
        store.company_code = 'billa-burger'
        store.save()
        f.user('ana', role='garcom')

    def login(self, empresa):
        return self.client.post(reverse('login'), {'empresa': empresa, 'username': 'ana', 'password': 'senha-forte-123'})

    def test_empresa_certa_entra(self):
        for variant in ['billa-burger', 'Billá Burger', 'BILLA BURGER']:
            with self.subTest(variant):
                self.client.logout()
                self.assertRedirects(self.login(variant), reverse('waiter_view'), fetch_redirect_response=False)

    def test_empresa_errada_nao_entra(self):
        response = self.login('outra-loja')
        self.assertContains(response, 'Empresa, usuário ou senha incorretos')
        self.assertNotIn('_auth_user_id', self.client.session)


class SupportUserTests(TestCase):
    def setUp(self):
        f.open_store()
        self.manager = f.user()
        call_command('suporte_nabandeja', hash=make_password('senha-super-forte-2026'), verbosity=0)
        self.support = User.objects.get(username='nabandeja')

    def test_suporte_e_superusuario_e_some_da_equipe(self):
        self.assertTrue(self.support.is_superuser)
        self.assertTrue(self.support.check_password('senha-super-forte-2026'))
        self.client.force_login(self.manager)
        response = self.client.get(reverse('admin_users'))
        self.assertNotContains(response, '@nabandeja')
        self.assertEqual(self.client.get(reverse('user_edit', args=[self.support.pk])).status_code, 404)

    def test_gerente_nao_acessa_painel_do_suporte(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(reverse('support_panel')).status_code, 403)
        self.assertNotEqual(self.client.get('/admin/').status_code, 200)

    def test_suporte_desliga_modulos(self):
        self.client.force_login(self.support)
        self.client.post(reverse('support_save'), {'company_code': 'billa', 'module_delivery': 'on', 'module_pix': 'on'})
        store = AppSettings.get_settings()
        modules = enabled_modules(store)
        self.assertEqual(store.company_code, 'billa')
        self.assertTrue(modules['delivery'])
        self.assertFalse(modules['financeiro'])
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(reverse('expenses')).status_code, 404)
        self.assertNotContains(self.client.get(reverse('admin_dashboard')), 'Contas a pagar')

    def test_suporte_redefine_senha(self):
        self.client.force_login(self.support)
        response = self.client.post(reverse('support_reset_password', args=[self.manager.pk]), follow=True)
        self.assertContains(response, 'Nova senha de gerente')
        self.manager.refresh_from_db()
        self.assertFalse(self.manager.check_password('senha-forte-123'))

    def test_gerente_inicial_nao_e_superusuario(self):
        User.objects.all().delete()
        call_command('ensure_initial_access', verbosity=0)
        manager = User.objects.get(role='gerente')
        self.assertFalse(manager.is_superuser)
