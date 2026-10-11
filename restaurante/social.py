"""
Login com Google (django-allauth).

Regra: o Google não cria contas. Ele só entra em um usuário ATIVO que o
gerente cadastrou com o mesmo e-mail (verificado pelo Google). Depois do
primeiro login, a conta Google fica vinculada ao usuário.
"""

import logging

from allauth.account.adapter import DefaultAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib import messages
from django.shortcuts import redirect

from .models import User

logger = logging.getLogger('nabandeja.security')


def _deny(request, message):
    messages.error(request, message)
    raise ImmediateHttpResponse(redirect('login'))


def verified_google_email(sociallogin):
    data = sociallogin.account.extra_data or {}
    email = (data.get('email') or '').strip().lower()
    if email and data.get('email_verified', data.get('verified_email')):
        return email
    return ''


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return False


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request, sociallogin):
        return False

    def pre_social_login(self, request, sociallogin):
        if sociallogin.is_existing:
            if not sociallogin.user.is_active:
                _deny(request, 'Este usuário está desativado. Fale com o gerente.')
            return

        email = verified_google_email(sociallogin)
        if not email:
            _deny(request, 'O Google não confirmou o e-mail desta conta.')

        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user is None:
            logger.warning('Login Google recusado: e-mail não cadastrado (%s)', email)
            _deny(request, f'O e-mail {email} não está cadastrado. Peça ao gerente para cadastrá-lo em Equipe.')

        sociallogin.connect(request, user)
        logger.info('Conta Google vinculada ao usuário %s', user.username)

    def on_authentication_error(self, request, provider, error=None, exception=None, extra_context=None):
        logger.warning('Falha no login Google: %s %s', error, exception)
        _deny(request, 'Não foi possível entrar com o Google. Tente de novo ou use usuário e senha.')
