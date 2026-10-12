"""Gerente: tela Hoje, abrir/fechar o dia, caixa (sangria/suprimento, histórico) e reabrir conta."""

from django.contrib import messages
from django.db.models import F, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ..models import AppSettings, CashSession, Expense, Ingredient, Order, OrderItem, Payment, TableCall
from ..modules import module_required
from ..permissions import manager_required
from ..services import cash as cash_service
from ..services import day as day_service
from ..services import orders as order_service
from ..services.audit import audit
from ..services.orders import OrderError


@manager_required
def today(request):
    store = AppSettings.get_settings()
    if not store.setup_completed:
        return redirect('setup_wizard', step='loja')

    now = timezone.localtime()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    paid_today = Order.objects.filter(status='finalizado', closed_at__gte=day_start)
    revenue = Payment.objects.filter(order__in=paid_today).aggregate(total=Sum('amount'))['total'] or 0
    count_today = paid_today.count()
    active_orders = list(
        Order.objects.filter(status__in=Order.ACTIVE_STATUSES).select_related('waiter').order_by('-created_at')
    )
    recent = list(day_service.recent_paid_orders())
    for order in recent:
        order.reopenable = order_service.can_reopen(order)

    return render(request, 'app/hoje.html', {
        'active_tab': 'hoje',
        'day': day_service.status(),
        'vendas_hoje': revenue,
        'pedidos_hoje': count_today,
        'ticket_medio': revenue / count_today if count_today else 0,
        'active_orders': active_orders,
        'mesas_ativas': len({o.mesa for o in active_orders if o.order_type == 'dine-in' and o.mesa != 'SEM MESA'}),
        'recent_paid': recent,
        'pending_online': Order.objects.filter(status='pendente').count(),
        'calls': TableCall.objects.filter(resolved_at__isnull=True).select_related('table'),
        'overdue_expenses': Expense.objects.filter(paid_at__isnull=True, due_date__lte=timezone.localdate()),
        'low_stock_ingredients': Ingredient.objects.filter(
            is_active=True, low_stock_alert__gt=0, stock_quantity__lte=F('low_stock_alert'),
        ).order_by('stock_quantity')[:5],
        'top_products': OrderItem.objects.filter(order__in=paid_today)
            .values('product_name').annotate(total_qty=Sum('quantity')).order_by('-total_qty')[:5],
    })


@manager_required
@require_POST
def open_day(request):
    try:
        session = day_service.open_day(request.user, request.POST.get('opening_amount', '0'), request.POST.get('notes', ''))
    except day_service.DayError as exc:
        messages.error(request, str(exc))
    else:
        audit(request, 'day.open', 'Dia aberto.', session, opening_amount=getattr(session, 'opening_amount', ''))
        messages.success(request, 'Dia aberto! A loja está recebendo pedidos.')
    return redirect('admin_dashboard')


@manager_required
def close_day(request):
    """Checklist de pendências + contagem da gaveta + confirmação."""
    pending = day_service.pending_items()
    day = day_service.status()
    if request.method == 'POST':
        try:
            session, _ = day_service.close_day(
                request.user, request.POST.get('closing_amount', '0'), request.POST.get('notes', ''),
                force=request.POST.get('force') == '1',
            )
        except day_service.DayError as exc:
            messages.error(request, str(exc))
        else:
            audit(request, 'day.close', 'Dia fechado.', session,
                  difference=getattr(session, 'difference_amount', ''))
            messages.success(request, 'Dia fechado. Bom descanso!')
            if session:
                return redirect('cash_session_detail', session_id=session.pk)
            return redirect('admin_dashboard')
    return render(request, 'app/fechar_dia.html', {'active_tab': 'hoje', 'pending': pending, 'day': day})


@manager_required
@require_POST
@module_required('caixa')
def cash_movement(request):
    try:
        movement = cash_service.add_movement(
            request.user, request.POST.get('kind'), request.POST.get('amount'), request.POST.get('reason'),
        )
    except cash_service.CashError as exc:
        messages.error(request, str(exc))
    else:
        audit(request, f'cash.{movement.kind}', f'{movement.get_kind_display()}: R$ {movement.amount:.2f}.', movement,
              reason=movement.reason)
        messages.success(request, f'{movement.get_kind_display()} de R$ {movement.amount:.2f} registrada.'.replace('.', ',', 1))
    return redirect('admin_dashboard')


@manager_required
@module_required('caixa')
def cash_history(request):
    sessions = CashSession.objects.select_related('opened_by', 'closed_by')[:60]
    return render(request, 'restaurante/admin/cash_history.html', {'sessions': sessions, 'active_menu': 'cash'})


@manager_required
@module_required('caixa')
def cash_session_detail(request, session_id):
    session = get_object_or_404(CashSession.objects.select_related('opened_by', 'closed_by'), pk=session_id)
    return render(request, 'restaurante/admin/cash_detail.html', {
        'session': session,
        'summary': cash_service.summary(session),
        'active_menu': 'cash',
    })


@manager_required
@require_POST
def reopen_order(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    reason = request.POST.get('reason', '')
    try:
        order_service.reopen(order, request.user, reason)
    except OrderError as exc:
        messages.error(request, str(exc))
        return redirect(request.POST.get('next') or 'admin_dashboard')
    audit(request, 'order.reopen', f'Conta #{order.id} reaberta.', order, reason=reason)
    messages.warning(request, f'Conta #{order.id} reaberta. Os pagamentos foram estornados.')
    from .orders import workspace_url
    return redirect(workspace_url(order))


@manager_required
def management_home(request):
    return render(request, 'restaurante/admin/gestao.html', {'active_menu': 'gestao'})
