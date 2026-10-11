from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from restaurante.models import AppSettings, Category, Order, OrderItem, Product, User


class PixReceiptTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user('gerente', password='senha-forte-123', role='gerente')
        settings = AppSettings.get_settings()
        settings.store_name = 'Billá Burger'
        settings.pix_key = '52998224725'
        settings.pix_name = 'Billa Burger'
        settings.pix_city = 'Sao Paulo'
        settings.save()
        category = Category.objects.create(name='Lanches')
        product = Product.objects.create(name='X-Burger', category=category, price=Decimal('25.90'), stock=10)
        self.order = Order.objects.create(mesa='5', total=Decimal('51.80'), waiter=self.manager)
        OrderItem.objects.create(order=self.order, product=product, quantity=2, unit_price=product.price)
        self.client.force_login(self.manager)

    def test_cupom_tem_qr_com_valor_exato(self):
        response = self.client.get(reverse('print_order', args=[self.order.id]))
        self.assertContains(response, '<svg')
        self.assertContains(response, 'R$ 51,80')

    def test_fechar_conta_gera_pix_do_total(self):
        response = self.client.get(reverse('close_order', args=[self.order.id]))
        payload = response.context['pix']['payload']
        self.assertIn('540551.80', payload)
        self.assertIn('PEDIDO' + str(self.order.id), payload)

    def test_pix_de_parte_da_conta(self):
        response = self.client.get(reverse('pix_amount', args=[self.order.id]), {'valor': '25,90'})
        self.assertIn('540525.90', response.context['pix']['payload'])
        self.assertContains(response, 'Copiar PIX copia e cola')

    def test_sem_chave_nao_quebra(self):
        AppSettings.objects.update(pix_key='')
        response = self.client.get(reverse('print_order', args=[self.order.id]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'PAGUE COM PIX')

    def test_configuracao_invalida_e_recusada(self):
        response = self.client.post(reverse('admin_settings'), {
            'store_name': 'Loja', 'slogan': '', 'primary_color': '#ef4444', 'secondary_color': '#fbbf24',
            'background_color': '#f8f9fa', 'text_color': '#1e293b',
            'pix_key': '111.111.111-11', 'pix_key_type': 'cpf', 'pix_name': 'X', 'pix_city': 'Y',
        }, follow=True)
        self.assertContains(response, 'CPF da chave PIX é inválido')
