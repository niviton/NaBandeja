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
