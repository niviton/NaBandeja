"""Painel do gerente: dashboard, caixa, loja, delivery, configurações e equipe."""

from django.contrib import messages
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_slug
from django.db.models import Avg, F, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from django.conf import settings as django_settings

from ..forms import AppSettingsForm
from ..models import AppSettings, CashSession, Ingredient, Order, OrderItem, User
from ..permissions import manager_required
from ..services import cash as cash_service
from ..services import orders as order_service
from ..services.audit import audit
from ..services.cart import SessionCart
from ..services.orders import OrderError
from ..services.pix import pix_preview
from .orders import menu_categories


# ------------------------------------------------------------------ dashboard

@manager_required
def admin_dashboard(request):
    now = timezone.localtime()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    paid_today = Order.objects.filter(status='finalizado', closed_at__gte=day_start)
    totals = paid_today.aggregate(revenue=Sum('total'), avg_ticket=Avg('total'))

    active_orders = list(
        Order.objects.filter(status__in=Order.ACTIVE_STATUSES)
        .select_related('waiter').prefetch_related('items__product').order_by('-created_at')
    )
    cash_session = CashSession.get_open_session()

    return render(request, 'restaurante/admin/dashboard.html', {
        'vendas_hoje': totals['revenue'] or 0,
        'pedidos_hoje': paid_today.count(),
        'ticket_medio': totals['avg_ticket'] or 0,
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


# ------------------------------------------------------------------ delivery

@manager_required
def admin_online_orders(request):
    cart = SessionCart(request.session)
    if request.method == 'POST':
        try:
            order, _ = order_service.place_order(
                request.user,
                cart,
                order_type='delivery',
                cliente=request.POST.get('cliente', ''),
                address=request.POST.get('address', ''),
                platform=request.POST.get('platform', ''),
                observacoes=request.POST.get('observacoes', ''),
                store_settings=AppSettings.get_settings(),
            )
        except OrderError as exc:
            messages.error(request, str(exc))
        else:
            cart.clear()
            messages.success(request, f'Pedido #{order.id} enviado para a cozinha!')
        return redirect('admin_online_orders')

    return render(request, 'restaurante/admin/online.html', {
        'categories': menu_categories(),
        'cart': cart.items,
        'cart_total': cart.total,
        'delivery_orders': Order.objects.filter(order_type='delivery', status__in=Order.ACTIVE_STATUSES)
            .order_by('-created_at'),
        'active_menu': 'online',
    })


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
        'users': User.objects.filter(is_active=True).order_by('role', 'username'),
        'active_menu': 'users',
    })


@manager_required
def user_create(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        role = request.POST.get('role', 'garcom')
        error = None
        if role not in dict(User.ROLE_CHOICES):
            error = 'Função inválida.'
        elif not username:
            error = 'Informe o nome de usuário.'
        else:
            try:
                validate_slug(username)
            except ValidationError:
                error = 'Usuário inválido. Use apenas letras, números, hífen ou underline.'
        if not error and User.objects.filter(username__iexact=username).exists():
            error = 'Este usuário já existe.'
        if not error:
            try:
                validate_password(password)
            except ValidationError as exc:
                error = ' '.join(exc.messages)
        if error:
            messages.error(request, error)
            return render(request, 'restaurante/admin/user_form.html', {
                'title': 'Novo Usuário', 'active_menu': 'users', 'values': request.POST,
            })

        user = User.objects.create_user(
            username=username,
            password=password,
            role=role,
            email=request.POST.get('email', '').strip(),
        )
        audit(request, 'user.create', f'Usuário "{username}" criado.', user, role=role)
        messages.success(request, f'Usuário "{username}" criado com sucesso!')
        return redirect('admin_users')

    return render(request, 'restaurante/admin/user_form.html', {'title': 'Novo Usuário', 'active_menu': 'users'})


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
