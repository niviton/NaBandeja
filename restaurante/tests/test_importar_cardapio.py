import shutil
import tempfile
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings

from restaurante.models import AppSettings, Category, Product


class ImportMenuTests(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)

    def test_importa_e_pode_repetir(self):
        with override_settings(MEDIA_ROOT=self.media):
            call_command('importar_cardapio', 'cardapios/dogao-canaa.json', stdout=StringIO())
            call_command('importar_cardapio', 'cardapios/dogao-canaa.json', stdout=StringIO())
        store = AppSettings.get_settings()
        self.assertEqual(store.store_name, 'Dogão Canaã')
        self.assertTrue(store.logo.name.endswith('dogao-canaa-logo.png'))
        self.assertEqual(Product.objects.count(), 22)
        self.assertEqual(Category.objects.count(), 5)
        dog = Product.objects.get(name='Dogão Canaã')
        self.assertEqual(str(dog.price), '10.00')
        self.assertEqual(dog.stock, 999)


class ManualTests(TestCase):
    def test_ajuda_abre_para_toda_a_equipe(self):
        from restaurante.tests import factories as f

        for role in ('garcom', 'cozinha', 'gerente'):
            self.client.force_login(f.user(f'u-{role}', role=role))
            response = self.client.get('/ajuda/')
            self.assertContains(response, 'Balcão: para quem')
        self.client.logout()
        self.assertEqual(self.client.get('/ajuda/').status_code, 302)

    def test_exporta_manual(self):
        import os

        target = os.path.join(tempfile.mkdtemp(), 'manual.html')
        call_command('exportar_manual', target, stdout=StringIO())
        with open(target, encoding='utf-8') as handle:
            html = handle.read()
        self.assertIn('<title>Manual do NaBandeja</title>', html)
        self.assertIn('data:image/svg+xml;base64,', html)
