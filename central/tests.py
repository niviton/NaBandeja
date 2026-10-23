"""
Modo várias lojas. Rode com:  NABANDEJA_MULTI_LOJA=1 python manage.py test central
(sem a variável, estes testes são pulados).
"""

import shutil
import tempfile
import unittest
from pathlib import Path

from django.conf import settings
from django.db import connections
from django.test import TransactionTestCase, override_settings

if settings.MULTI_TENANT:  # o app central só existe no modo várias lojas
    from . import services, tenancy


@unittest.skipUnless(settings.MULTI_TENANT, 'Rode com NABANDEJA_MULTI_LOJA=1')
class MultiStoreTests(TransactionTestCase):
    databases = {'default', 'central'} if settings.MULTI_TENANT else {'default'}

    def setUp(self):
        from restaurante.models import User

        self.original_db = connections['default'].settings_dict
        self.tmp = Path(tempfile.mkdtemp())
        self.override = override_settings(TENANTS_DIR=self.tmp)
        self.override.enable()
        self.addCleanup(self._cleanup)
        tenancy.activate(None)
        User.objects.db_manager('central').create_superuser('dono', 'dono@x.com', 'Central-Teste-2026', role='gerente')
        self.a = services.create_store('Loja A', 'loja-a', 'gerente', 'Gerente-Teste-2026')
        self.b = services.create_store('Loja B', 'loja-b', 'gerente', 'Gerente-Teste-2026')

    def _cleanup(self):
        tenancy.activate(None)
        connections['default'].close()
        connections['default'].settings_dict = self.original_db
        self.override.disable()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def login(self, empresa, username='gerente', password='Gerente-Teste-2026'):
        return self.client.post('/', {'empresa': empresa, 'username': username, 'password': password})

    def test_cada_loja_tem_o_seu_banco(self):
        from restaurante.models import AppSettings, Category

        with tenancy.using(self.a):
            Category.objects.create(name='Só na A')
            self.assertEqual(AppSettings.get_settings().store_name, 'Loja A')
        with tenancy.using(self.b):
            self.assertFalse(Category.objects.filter(name='Só na A').exists())
            self.assertEqual(AppSettings.get_settings().store_name, 'Loja B')

    def test_gerente_entra_pela_empresa(self):
        response = self.login('Loja A')
        self.assertRedirects(response, '/l/loja-a/dashboard/', fetch_redirect_response=False)
        page = self.client.get('/l/loja-a/admin-panel/', follow=True)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, '/l/loja-a/')  # links da loja levam o prefixo

    def test_sessao_de_uma_loja_nao_vale_na_outra(self):
        self.login('loja-a')
        response = self.client.get('/l/loja-b/garcom/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/l/loja-b/', response['Location'])
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_empresa_errada_nao_entra(self):
        response = self.login('nao-existe')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_admin_central_cria_e_entra_na_loja(self):
        response = self.login('central', 'dono', 'Central-Teste-2026')
        self.assertRedirects(response, '/central/', fetch_redirect_response=False)
        self.assertContains(self.client.get('/central/'), 'Loja B')

        response = self.client.post('/central/nova/', {
            'name': 'Loja C', 'code': 'loja-c', 'username': 'ana', 'password': 'Gerente-Teste-2026',
        })
        self.assertRedirects(response, '/central/', fetch_redirect_response=False)
        self.assertTrue((self.tmp / 'loja-c.sqlite3').exists())

        response = self.client.post('/central/loja-c/entrar/')
        self.assertRedirects(response, '/l/loja-c/dashboard/', fetch_redirect_response=False)
        support = self.client.get('/l/loja-c/suporte/')
        self.assertEqual(support.status_code, 200)

    def test_gerente_da_loja_nao_abre_o_painel_central(self):
        self.login('loja-a')
        response = self.client.get('/central/')
        self.assertEqual(response.status_code, 302)

    def test_loja_desativada(self):
        self.a.is_active = False
        self.a.save()
        self.assertEqual(self.client.get('/l/loja-a/').status_code, 404)
        self.login('loja-a')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_codigo_reservado_ou_repetido(self):
        with self.assertRaises(services.StoreError):
            services.create_store('X', 'central', 'g', 'Gerente-Teste-2026')
        with self.assertRaises(services.StoreError):
            services.create_store('X', 'loja-a', 'g', 'Gerente-Teste-2026')
