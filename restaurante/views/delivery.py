"""
Quadro de delivery (garçom e gerente): um lugar só para todo pedido de entrega.

Colunas: Aguardando (pedido online) → Na cozinha → Pronto para sair → Na rua.
Ao entregar: se já estava pago, encerra; senão, abre o recebimento.
"""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from ..models import Order
from ..modules import is_enabled
from ..permissions import service_required
from ..services import orders as order_service
from ..services.audit import audit
from ..services.menu_qr import public_url
from ..services.orders import OrderError
from .orders import error_response, hx_redirect, is_htmx, with_toast


def _board_context(request):
    deliveries = (
        Order.objects.filter(order_type='delivery', status__in=Order.ACTIVE_STATUSES)
        .prefetch_related('items', 'payments').order_by('created_at')
    )
    columns = {'cozinha': [], 'pronto': [], 'rua': []}
    for order in deliveries:
        if order.dispatched_at:
            columns['rua'].append(order)
        elif order.status == 'pronto':
            columns['pronto'].append(order)
        else:
            columns['cozinha'].append(order)
    return {
        'pending': Order.objects.filter(status='pendente').prefetch_related('items').order_by('created_at')
        if is_enabled('online') else [],
        'columns': [
            ('cozinha', 'Na cozinha', columns['cozinha']),
            ('pronto', 'Pronto para sair', columns['pronto']),
            ('rua', 'Na rua', columns['rua']),
        ],
        'online_url': public_url(request, reverse('online_order')),
    }


def _require_delivery_modules():
    if not (is_enabled('delivery') or is_enabled('online')):
        from django.http import Http404
        raise Http404('Delivery desativado para esta loja.')


@service_required
def delivery_board(request):
    _require_delivery_modules()
    return render(request, 'app/delivery.html', {**_board_context(request), 'active_tab': 'delivery'})


@service_required
def delivery_board_partial(request):
    _require_delivery_modules()
    return render(request, 'app/_delivery_board.html', _board_context(request))


def _board_response(request, message, kind='success'):
    if is_htmx(request):
        return with_toast(render(request, 'app/_delivery_board.html', _board_context(request)), message, kind)
    getattr(messages, kind)(request, message)
    return redirect('delivery_board')


@service_required
@require_POST
def dispatch_order(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    try:
        order_service.dispatch(order)
    except OrderError as exc:
        return error_response(str(exc))
    return _board_response(request, f'#{order.id} saiu para entrega.')


@service_required
@require_POST
def deliver_order(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    try:
        order_service.mark_delivered(order, request.user)
    except OrderError as exc:
        return error_response(str(exc))
    order.refresh_from_db()
    if order.status == 'finalizado':
        return _board_response(request, f'#{order.id} entregue e encerrado.')
    # Ainda falta receber: vai para o recebimento.
    url = reverse('close_order', args=[order.id])
    return hx_redirect(url) if is_htmx(request) else redirect(url)


@service_required
@require_POST
def decide_online_order(request, order_id, decision):
    if not is_enabled('online'):
        from django.http import Http404
        raise Http404
    order = get_object_or_404(Order, pk=order_id)
    try:
        if decision == 'aceitar':
            order_service.accept_pending(order, request.user)
            message, kind = f'Pedido #{order.id} aceito e enviado para a cozinha.', 'success'
        else:
            order_service.reject_pending(order, request.user)
            message, kind = f'Pedido #{order.id} recusado.', 'warning'
    except OrderError as exc:
        return error_response(str(exc))
    audit(request, f'online.{decision}', f'Pedido online #{order.id}: {decision}.', order)
    return _board_response(request, message, kind)
