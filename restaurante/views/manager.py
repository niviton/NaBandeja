"""Painel do gerente: dashboard, caixa, loja, delivery, configurações e equipe."""

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.db.models import F, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from django.conf import settings as django_settings

from ..forms import AppSettingsForm, TeamMemberForm
from ..models import AppSettings, CashSession, Expense, Ingredient, Order, OrderItem, Payment, TableCall, User
from ..permissions import manager_required
from ..services import cash as cash_service
from ..services.audit import audit
from ..services.pix import pix_preview


# ------------------------------------------------------------------ dashboard

@manager_required
def admin_dashboard(request):
    store = AppSettings.get_settings()
    if not store.setup_completed:
        return redirect('setup_wizard', step='loja')
    now = timezone.localtime()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    paid_today = Order.objects.filter(status='finalizado', closed_at__gte=day_start)
    revenue = Payment.objects.filter(order__in=paid_today).aggregate(total=Sum('amount'))['total'] or 0
    count_today = paid_today.count()

    active_orders = list(
        Order.objects.filter(status__in=Order.ACTIVE_STATUSES)
        .select_related('waiter').prefetch_related('items__product').order_by('-created_at')
    )
    cash_session = CashSession.get_open_session()

    return render(request, 'restaurante/admin/dashboard.html', {
        'vendas_hoje': revenue,
        'pedidos_hoje': count_today,
        'ticket_medio': revenue / count_today if count_today else 0,
        'pedidos_ativos': len(active_orders),
        'active_orders': active_orders,
        'mesas_ativas': len({o.mesa for o in active_orders if o.order_type == 'dine-in'}),
        'low_stock_ingredients': Ingredient.objects.filter(
            is_active=True, low_stock_alert__gt=0, stock_quantity__lte=F('low_stock_alert'),
        ).order_by('stock_quantity')[:5],
        'top_products': OrderItem.objects.filter(order__in=paid_today)
            .values('product_name').annotate(total_qty=Sum('quantity')).order_by('-total_qty')[:5],
        'cash_session': cash_session,
        'cash_summary': cash_service.summary(cash_session) if cash_session else None,
        'pending_online': Order.objects.filter(status='pendente').count(),
        'calls': TableCall.objects.filter(resolved_at__isnull=True).select_related('table'),
        'overdue_expenses': Expense.objects.filter(paid_at__isnull=True, due_date__lte=timezone.localdate()),
        'active_menu': 'dashboard',
    })


# ------------------------------------------------------------------ caixa

@manager_required
@require_POST
def open_cash_session(request):
    try:
        session = cash_service.open_session(request.user, request.POST.get('opening_amount'), request.POST.get('notes'))
    except cash_service.CashError as exc:
        messages.error(request, str(exc))
        return redirect('admin_dashboard')
    audit(request, 'cash.open', f'Caixa aberto com R$ {session.opening_amount:.2f}.', session,
          opening_amount=session.opening_amount)
    messages.success(request, 'Caixa aberto com sucesso!')
    return redirect('admin_dashboard')


@manager_required
@require_POST
def close_cash_session(request):
    try:
        session, totals = cash_service.close_session(
            request.user, request.POST.get('closing_amount'), request.POST.get('close_notes')
        )
    except cash_service.CashError as exc:
        messages.error(request, str(exc))
        return redirect('admin_dashboard')
    audit(request, 'cash.close', f'Caixa fechado. Diferença: R$ {session.difference_amount:.2f}.', session,
          closing_amount=session.closing_amount, expected_amount=session.expected_amount,
          difference_amount=session.difference_amount, total_sales=totals['total_sales'])
    if session.difference_amount == 0:
        messages.success(request, 'Caixa fechado sem diferenças.')
    else:
        messages.warning(request, f'Caixa fechado com diferença de R$ {session.difference_amount:.2f}.')
    return redirect('admin_dashboard')


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

@manager_required
def admin_settings(request):
    store = AppSettings.get_settings()
    form = AppSettingsForm(request.POST or None, request.FILES or None, instance=store)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            audit(request, 'settings.update', 'Configurações da loja atualizadas.', store)
            messages.success(request, 'Configurações salvas!')
            return redirect('admin_settings')
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
        'active_menu': 'settings',
        'local_ip': local_ip,
        'access_links': {
            'local': f'{scheme}://localhost:{port}',
            'network': f'{scheme}://{local_ip}:{port}',
        },
        'pix_preview': pix_preview(store),
    })


# ------------------------------------------------------------------ equipe

@manager_required
def admin_users(request):
    return render(request, 'restaurante/admin/users.html', {
        'users': User.objects.filter(is_active=True).prefetch_related('socialaccount_set').order_by('role', 'username'),
        'active_menu': 'users',
    })


@manager_required
def user_create(request):
    return _member_edit(request, None)


@manager_required
def user_edit(request, user_id):
    return _member_edit(request, get_object_or_404(User, pk=user_id, is_active=True))


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
    user = get_object_or_404(User, pk=user_id, is_active=True)
    if user.role == 'gerente' and not User.objects.filter(role='gerente', is_active=True).exclude(pk=user.pk).exists():
        messages.error(request, 'É preciso manter pelo menos um gerente ativo.')
        return redirect('admin_users')
    user.is_active = False
    user.save(update_fields=['is_active'])
    audit(request, 'user.deactivate', f'Usuário "{user.username}" desativado.', user, role=user.role)
    messages.success(request, f'Usuário "{user.username}" desativado.')
    return redirect('admin_users')
