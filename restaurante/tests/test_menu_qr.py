from django.test import TestCase, override_settings
from django.urls import reverse

from restaurante.models import AppSettings
from restaurante.services.menu_qr import wifi_payload

from . import factories as f


class WifiPayloadTests(TestCase):
    def test_formato_wpa(self):
        self.assertEqual(wifi_payload('Loja Clientes', 'senha123'), 'WIFI:T:WPA;S:Loja Clientes;P:senha123;;')

    def test_rede_aberta(self):
        self.assertEqual(wifi_payload('Livre'), 'WIFI:T:nopass;S:Livre;;')

    def test_escapa_caracteres_especiais(self):
        self.assertEqual(wifi_payload('Bar;Zé', 'a:b,c"d'), 'WIFI:T:WPA;S:Bar\\;Zé;P:a\\:b\\,c\\"d;;')

    def test_sem_rede(self):
        self.assertEqual(wifi_payload(''), '')


class MenuCardTests(TestCase):
    def setUp(self):
        self.store = f.open_store()
        self.client.force_login(f.user())

    def test_cartao_com_wifi_tem_dois_qr(self):
        AppSettings.objects.update(wifi_ssid='Clientes', wifi_password='12345678')
        response = self.client.get(reverse('menu_qr_sheet'), {'copias': 2})
        self.assertEqual(response.content.decode().count('Conecte ao Wi-Fi'), 2)
        self.assertTrue(response.context['wifi_svg'].startswith('<svg'))

    def test_cartao_sem_wifi_tem_um_qr(self):
        response = self.client.get(reverse('menu_qr_sheet'))
        self.assertEqual(response.context['wifi_svg'], '')
        self.assertContains(response, 'Wi-Fi da loja')

    @override_settings(PUBLIC_BASE_URL='https://cardapio.minhaloja.com.br')
    def test_endereco_publico_configurado(self):
        response = self.client.get(reverse('menu_qr_sheet'))
        self.assertEqual(response.context['menu_url'], 'https://cardapio.minhaloja.com.br/cardapio/')


class PublicMenuTests(TestCase):
    def setUp(self):
        f.open_store()
        self.client.logout()

    def test_cardapio_so_para_consulta(self):
        f.product(name='X-Bacon', description='Pão brioche e bacon crocante')
        response = self.client.get(reverse('public_menu'))
        self.assertContains(response, 'Pão brioche e bacon crocante')
        self.assertContains(response, 'faça o pedido com o garçom')
        html = response.content.decode()
        self.assertNotIn('hx-post', html)
        self.assertNotIn('<form', html)

    def test_cardapio_desligado(self):
        AppSettings.objects.update(public_menu_enabled=False)
        self.assertEqual(self.client.get(reverse('public_menu')).status_code, 404)


class PublicUrlTests(TestCase):
    @override_settings(PUBLIC_BASE_URL='', LOCAL_IP='192.168.0.10', ALLOWED_HOSTS=['localhost', '192.168.0.20'])
    def test_localhost_vira_ip_da_rede(self):
        from django.test import RequestFactory
        from restaurante.services.menu_qr import public_url
        request = RequestFactory().get('/', HTTP_HOST='localhost:8000')
        self.assertEqual(public_url(request, '/cardapio/'), 'http://192.168.0.10:8000/cardapio/')
        request = RequestFactory().get('/', HTTP_HOST='192.168.0.20:8000')
        self.assertEqual(public_url(request, '/cardapio/'), 'http://192.168.0.20:8000/cardapio/')
