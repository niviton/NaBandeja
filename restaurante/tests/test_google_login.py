from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.models import SocialAccount, SocialLogin
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from restaurante.models import User
from restaurante.social import SocialAccountAdapter

from . import factories as f


FAKE_GOOGLE = override_settings(
    GOOGLE_LOGIN_ENABLED=True,
    SOCIALACCOUNT_PROVIDERS={'google': {'APPS': [{'client_id': 'teste', 'secret': 'teste', 'key': ''}]}},
)


def google_login(email, verified=True, uid='123'):
    account = SocialAccount(provider='google', uid=uid, extra_data={'email': email, 'email_verified': verified})
    return SocialLogin(account=account, user=User(email=email))


@FAKE_GOOGLE
class GoogleAdapterTests(TestCase):
    def setUp(self):
        self.adapter = SocialAccountAdapter()
        self.request = RequestFactory().get('/accounts/google/login/callback/')
        SessionMiddleware(lambda r: None).process_request(self.request)
        self.request._messages = FallbackStorage(self.request)

    def test_email_cadastrado_vincula_ao_usuario(self):
        waiter = f.user('ana', role='garcom', email='ana@gmail.com')
        sociallogin = google_login('ANA@gmail.com')
        self.adapter.pre_social_login(self.request, sociallogin)
        self.assertEqual(sociallogin.user, waiter)
        self.assertTrue(SocialAccount.objects.filter(user=waiter, provider='google').exists())

    def test_email_desconhecido_e_recusado(self):
        with self.assertRaises(ImmediateHttpResponse):
            self.adapter.pre_social_login(self.request, google_login('estranho@gmail.com'))
        self.assertFalse(User.objects.filter(email='estranho@gmail.com').exists())

    def test_email_nao_verificado_e_recusado(self):
        f.user('ana', role='garcom', email='ana@gmail.com')
        with self.assertRaises(ImmediateHttpResponse):
            self.adapter.pre_social_login(self.request, google_login('ana@gmail.com', verified=False))

    def test_usuario_desativado_e_recusado(self):
        f.user('ana', role='garcom', email='ana@gmail.com', is_active=False)
        with self.assertRaises(ImmediateHttpResponse):
            self.adapter.pre_social_login(self.request, google_login('ana@gmail.com'))

    def test_nao_permite_cadastro_pelo_google(self):
        self.assertFalse(self.adapter.is_open_for_signup(self.request, google_login('x@gmail.com')))


class GoogleButtonTests(TestCase):
    def test_botao_escondido_sem_credenciais(self):
        self.assertNotContains(self.client.get(reverse('login')), 'Entrar com Google')

    @FAKE_GOOGLE
    def test_botao_aparece_com_credenciais(self):
        self.assertContains(self.client.get(reverse('login')), 'Entrar com Google')


class TeamMemberFormTests(TestCase):
    def setUp(self):
        self.manager = f.user()
        self.client.force_login(self.manager)

    def test_cria_membro_com_email(self):
        self.client.post(reverse('user_create'), {
            'username': 'bia', 'first_name': 'Bia', 'email': 'Bia@Gmail.com',
            'role': 'garcom', 'password': 'senha-forte-123',
        })
        user = User.objects.get(username='bia')
        self.assertEqual(user.email, 'bia@gmail.com')
        self.assertTrue(user.check_password('senha-forte-123'))

    def test_edita_sem_trocar_senha(self):
        waiter = f.user('ana', role='garcom')
        self.client.post(reverse('user_edit', args=[waiter.pk]), {
            'first_name': 'Ana', 'email': 'ana@gmail.com', 'role': 'cozinha', 'password': '',
        })
        waiter.refresh_from_db()
        self.assertEqual((waiter.role, waiter.email), ('cozinha', 'ana@gmail.com'))
        self.assertTrue(waiter.check_password('senha-forte-123'))

    def test_email_repetido_e_recusado(self):
        f.user('ana', role='garcom', email='ana@gmail.com')
        response = self.client.post(reverse('user_create'), {
            'username': 'bia', 'email': 'ana@gmail.com', 'role': 'garcom', 'password': 'senha-forte-123',
        })
        self.assertContains(response, 'já está em uso')

    def test_gerente_nao_rebaixa_a_si_mesmo(self):
        self.client.post(reverse('user_edit', args=[self.manager.pk]), {'role': 'garcom', 'email': ''})
        self.manager.refresh_from_db()
        self.assertEqual(self.manager.role, 'gerente')
