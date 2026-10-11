from django.test import TestCase
from django.urls import reverse

from restaurante.models import Category, Product

from . import factories as f


class ProductFormTests(TestCase):
    def setUp(self):
        self.client.force_login(f.user())
        self.category = Category.objects.create(name='Lanches')

    def post(self, url, **extra):
        data = {'name': 'X-Salada', 'category': self.category.pk, 'price': '22.50', 'cost_price': '8.00',
                'stock': '10', 'icon': '🍔'}
        data.update(extra)
        return self.client.post(url, data)

    def test_produto_salvo_fica_disponivel(self):
        self.post(reverse('product_create'), is_active='on')
        self.assertTrue(Product.objects.get(name='X-Salada').is_active)

    def test_desmarcar_esconde_do_garcom(self):
        product = f.product(category=self.category)
        self.post(reverse('product_edit', args=[product.pk]))
        product.refresh_from_db()
        self.assertFalse(product.is_active)
        self.client.force_login(f.user('ana', role='garcom'))
        self.assertNotContains(self.client.get(reverse('waiter_view')), product.name)

    def test_receita_obrigatoria_com_estoque_por_ingrediente(self):
        response = self.post(reverse('product_create'), is_active='on', use_ingredient_stock='on')
        self.assertContains(response, 'Defina ao menos 1 ingrediente')
        self.assertFalse(Product.objects.exists())
