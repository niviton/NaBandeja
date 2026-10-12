"""Gerente: loja aberta/fechada, configurações e equipe."""

from django.conf import settings as django_settings
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.forms import modelform_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from ..forms import SETTINGS_TABS, AppSettingsForm, TeamMemberForm
from ..models import AppSettings, DeliveryZone, User
from ..modules import enabled_modules
from ..permissions import manager_required
from ..services.audit import audit
from ..services.pix import pix_preview



# ------------------------------------------------------------------ loja aberta/fechada

@manager_required
@require_POST
def toggle_store_status(request):
    store = AppSettings.get_settings()
    store.is_store_open = not store.is_store_open
    store.save(update_fields=['is_store_open'])
    audit(request, 'settings.store_toggle', 'Status da loja alterado.', store, is_store_open=store.is_store_open)
    if store.is_store_open:
        messages.success(request, 'Loja aberta com sucesso.')
    else:
        messages.warning(request, 'Loja fechada para novos pedidos.')

    next_url = request.POST.get('next', '')
    if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect('admin_dashboard')


# ------------------------------------------------------------------ configurações

def _settings_tabs(modules):
    tabs = [('loja', 'Loja', 'bi-shop')]
    if modules['pix']:
        tabs.append(('pagamento', 'Pagamento', 'bi-qr-code'))
    tabs.append(('salao', 'Salão e cozinha', 'bi-fire'))
    if modules['cardapio_digital']:
        tabs.append(('cardapio', 'Cardápio digital', 'bi-phone'))
    if modules['delivery'] or modules['online']:
        tabs.append(('delivery', 'Delivery', 'bi-scooter'))
    return tabs


@manager_required
def admin_settings(request):
    store = AppSettings.get_settings()
    tabs = _settings_tabs(enabled_modules(store))
    tab = request.POST.get('aba') or request.GET.get('aba') or 'loja'
    if tab not in {key for key, _, _ in tabs}:
        tab = 'loja'
    form_class = modelform_factory(AppSettings, form=AppSettingsForm, fields=SETTINGS_TABS[tab])
    form = form_class(request.POST or None, request.FILES or None, instance=store)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            audit(request, 'settings.update', 'Configurações da loja atualizadas.', store, aba=tab)
            messages.success(request, 'Configurações salvas!')
            return redirect(f"{reverse('admin_settings')}?aba={tab}")
        for error in form.non_field_errors():
            messages.error(request, error)
        for field_name, errors in form.errors.items():
            if field_name != '__all__':
                messages.error(request, f'{form.fields[field_name].label}: {" ".join(errors)}')

    port = request.get_port() or '8000'
    scheme = 'https' if request.is_secure() else 'http'
    local_ip = django_settings.LOCAL_IP or '127.0.0.1'
    return render(request, 'restaurante/admin/settings.html', {
        'form': form,
        'settings': store,
        'tab': tab,
        'tabs': tabs,
        'active_menu': 'settings',
        'local_ip': local_ip,
        'access_links': {
            'local': f'{scheme}://localhost:{port}',
            'network': f'{scheme}://{local_ip}:{port}',
        },
        'pix_preview': pix_preview(store) if tab == 'pagamento' else None,
        'delivery_zones': DeliveryZone.objects.all() if tab == 'delivery' else [],
        'color_fields': [
            ('primary_color', 'Principal', store.primary_color),
            ('secondary_color', 'Destaque', store.secondary_color),
            ('background_color', 'Fundo', store.background_color),
            ('text_color', 'Texto', store.text_color),
        ],
    })


# ------------------------------------------------------------------ equipe

@manager_required
def admin_users(request):
    return render(request, 'restaurante/admin/users.html', {
        'users': User.objects.filter(is_active=True, is_superuser=False).prefetch_related('socialaccount_set').order_by('role', 'username'),
        'active_menu': 'users',
    })


@manager_required
def user_create(request):
    return _member_edit(request, None)


@manager_required
def user_edit(request, user_id):
    return _member_edit(request, get_object_or_404(User, pk=user_id, is_active=True, is_superuser=False))


def _member_edit(request, member):
    form = TeamMemberForm(request.POST or None, instance=member)
    if request.method == 'POST' and form.is_valid():
        if member and member.pk == request.user.pk and form.cleaned_data['role'] != 'gerente':
            form.add_error('role', 'Você não pode tirar a sua própria função de gerente.')
        else:
            saved = form.save()
            action = 'user.update' if member else 'user.create'
            audit(request, action, f'Usuário "{saved.username}" salvo.', saved, role=saved.role)
            if member and member.pk == request.user.pk and form.cleaned_data.get('password'):
                update_session_auth_hash(request, saved)
            messages.success(request, f'Usuário "{saved.username}" salvo!')
            return redirect('admin_users')
    return render(request, 'restaurante/admin/user_form.html', {
        'form': form,
        'member': member,
        'title': 'Editar Membro' if member else 'Novo Membro',
        'active_menu': 'users',
    })


@manager_required
@require_POST
def user_delete(request, user_id):
    """Desativa o usuário (o histórico de vendas continua com o nome dele)."""
    if request.user.id == user_id:
        messages.error(request, 'Você não pode desativar a si mesmo.')
        return redirect('admin_users')
    user = get_object_or_404(User, pk=user_id, is_active=True, is_superuser=False)
    if user.role == 'gerente' and not User.objects.filter(role='gerente', is_active=True, is_superuser=False).exclude(pk=user.pk).exists():
        messages.error(request, 'É preciso manter pelo menos um gerente ativo.')
        return redirect('admin_users')
    user.is_active = False
    user.save(update_fields=['is_active'])
    audit(request, 'user.deactivate', f'Usuário "{user.username}" desativado.', user, role=user.role)
    messages.success(request, f'Usuário "{user.username}" desativado.')
    return redirect('admin_users')
