"""
Regras por modo de operação.

- Painel master: só as telas /master/ (o resto do sistema é das lojas).
- Empresa aberta pelo master só para leitura: nada pode ser alterado, porque
  é uma cópia do último backup (a loja de verdade continua no PC do cliente).
"""

from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme

from .permissions import wants_json

MASTER_PATHS = ('/master/', '/static/', '/logout/', '/manifest.webmanifest', '/sw.js')
READ_ONLY_ALLOWED = ('/logout/', '/suporte/espelho/')
SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS')


class ModoMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if settings.IS_MASTER:
            if path != '/' and not path.startswith(MASTER_PATHS):
                return redirect('master_home')
        elif settings.SOMENTE_LEITURA and request.method not in SAFE_METHODS and not path.startswith(READ_ONLY_ALLOWED):
            text = 'Somente leitura: esta é a cópia do último backup da loja. Nada foi alterado.'
            if wants_json(request):
                return JsonResponse({'success': False, 'message': text}, status=403)
            messages.warning(request, text)
            back = request.META.get('HTTP_REFERER', '')
            if not url_has_allowed_host_and_scheme(back, allowed_hosts={request.get_host()}):
                back = '/dashboard/'
            return redirect(back)
        return self.get_response(request)
