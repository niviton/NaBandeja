"""Painel do suporte NaBandeja (superusuário): empresa, módulos, licença e senhas."""

import secrets

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from ..management.commands.suporte_nabandeja import SUPPORT_USERNAME
from ..models import AppSettings, User
from ..modules import MODULES, enabled_modules
from ..permissions import support_required
from ..services import license
from ..services.audit import audit
from ..services.company import normalize


@support_required
def support_panel(request):
    store = AppSettings.get_settings()
    modules = enabled_modules(store)
    return render(request, 'restaurante/admin/support.html', {
        'store': store,
        'modules': [(key, label, help_text, modules[key]) for key, label, help_text in MODULES],
        'license': license.status(store.license_key),
        'team': User.objects.filter(is_superuser=False).order_by('-is_active', 'role', 'username'),
        'google_callback': request.build_absolute_uri('/accounts/google/login/callback/').replace('127.0.0.1', 'localhost'),
        'active_menu': 'support',
    })


@support_required
@require_POST
def support_save(request):
    store = AppSettings.get_settings()
    code = request.POST.get('company_code', '').strip()[:40]
    if not normalize(code):
        messages.error(request, 'O código da empresa precisa ter letras ou números.')
        return redirect('support_panel')
    store.company_code = code
    store.modules = {key: f'module_{key}' in request.POST for key, _, _ in MODULES}
    store.save(update_fields=['company_code', 'modules'])
    audit(request, 'support.modules', 'Empresa e módulos atualizados pelo suporte.', store,
          company_code=code, modules=store.modules)
    messages.success(request, 'Configuração do cliente salva.')
    return redirect('support_panel')


@support_required
@require_POST
def support_license(request):
    store = AppSettings.get_settings()
    try:
        payload = license.install(store, request.POST.get('license_key', ''))
    except ValueError as exc:
        messages.error(request, str(exc))
    else:
        audit(request, 'license.install', f'Licença instalada até {payload["expira"]:%d/%m/%Y}.')
        messages.success(request, f'Licença de {payload["cliente"]} válida até {payload["expira"]:%d/%m/%Y}.')
    return redirect('support_panel')


_used_tokens = set()


@never_cache
def espelho_login(request, token):
    """Entrada do painel master numa empresa aberta por ele (link de uso único, 60 s)."""
    from ..services.espelho import SSO_SALT

    if not settings.ESPELHO_SSO_KEY:
        raise Http404
    try:
        signing.loads(token, key=settings.ESPELHO_SSO_KEY, salt=SSO_SALT, max_age=60)
    except signing.BadSignature as exc:
        raise PermissionDenied('Link de acesso inválido ou expirado. Entre de novo pelo painel master.') from exc
    if token in _used_tokens:
        raise PermissionDenied('Este link de acesso já foi usado. Entre de novo pelo painel master.')
    _used_tokens.add(token)

    user, created = User.objects.get_or_create(username=SUPPORT_USERNAME)
    if created or not (user.is_superuser and user.is_active):
        if created:
            user.set_unusable_password()
        user.first_name = 'Suporte NaBandeja'
        user.role = 'gerente'
        user.is_active = user.is_staff = user.is_superuser = True
        user.save()
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    return redirect('admin_dashboard')


@support_required
@require_POST
def support_reset_password(request, user_id):
    member = get_object_or_404(User, pk=user_id, is_superuser=False)
    password = secrets.token_urlsafe(8)
    member.set_password(password)
    member.is_active = True
    member.save(update_fields=['password', 'is_active'])
    audit(request, 'support.reset_password', f'Senha de "{member.username}" redefinida pelo suporte.', member)
    messages.success(request, f'Nova senha de {member.username}: {password}  (passe para a pessoa e peça para trocar)')
    return redirect('support_panel')
