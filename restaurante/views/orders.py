"""Garçom, gestão de pedidos, cozinha, fechamento e cupom."""

from datetime import timedelta

from django.contrib import messages
from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ..models import AppSettings, Category, Order, OrderItem, Product
from ..permissions import (
    get_order_or_403,
    home_for,
    kitchen_required,
    manager_required,
    role_required,
    service_required,
    wants_json,
)
from ..services import orders as order_service
from ..services.audit import audit
from ..services.cart import SessionCart
from ..services.orders import OrderError
from ..services.pix import pix_for_order

KITCHEN_LATE_MINUTES = 15


def menu_categories():
    """Categorias ativas com seus produtos ativos (para o cardápio do garçom)."""
    active_products = Product.objects.filter(is_active=True).prefetch_related('recipe_items__ingredient')
    return Category.objects.filter(is_active=True).prefetch_related(
        Prefetch('products', queryset=active_products)
    )


def _order_response(request, order, message, redirect_to='manage_order', status=200):
    if wants_json(request):
        payload = {'success': status < 400, 'message': message}
        if order is not None and status < 400:
            payload['order'] = order_service.snapshot(order)
        return JsonResponse(payload, status=status)
    if status < 400:
        messages.success(request, message)
    else:
        messages.error(request, message)
    if redirect_to == 'manage_order' and order is not None:
        return redirect('manage_order', order_id=order.id)
    return redirect(redirect_to)


# ------------------------------------------------------------------ garçom

@service_required
def waiter_view(request):
    cart = SessionCart(request.session)
    return render(request, 'restaurante/waiter.html', {
        'categories': menu_categories(),
        'cart': cart.items,
        'cart_total': cart.total,
    })


@service_required
@require_POST
def submit_order(request):
    cart = SessionCart(request.session)
    try:
        order, merged = order_service.place_order(
            request.user,
            cart,
            order_type=request.POST.get('order_type', 'dine-in'),
            mesa=request.POST.get('mesa', ''),
            cliente=request.POST.get('cliente', ''),
            observacoes=request.POST.get('observacoes', ''),
            address=request.POST.get('address', ''),
            platform=request.POST.get('platform', ''),
            store_settings=AppSettings.get_settings(),
        )
    except OrderError as exc:
        messages.error(request, str(exc))
        return redirect(request.POST.get('next') or home_for(request.user))

    cart.clear()
    if merged:
        messages.success(request, f'Itens adicionados à conta da mesa {order.mesa}.')
    else:
        messages.success(request, f'Pedido #{order.id} enviado para a cozinha!')
    return redirect(request.POST.get('next') or home_for(request.user))


# ------------------------------------------------------------------ alterar pedido

@service_required
def manage_order(request, order_id):
    order = get_order_or_403(request.user, order_id)
    if not order.is_active:
        messages.error(request, 'Não é possível alterar um pedido finalizado/cancelado.')
        return redirect(home_for(request.user))
    return render(request, 'restaurante/manage_order.html', {
        'order': Order.objects.prefetch_related('items__product').get(pk=order.pk),
        'categories': menu_categories(),
    })


@service_required
@require_POST
def update_order_info(request, order_id):
    order = get_order_or_403(request.user, order_id)
    try:
        order_service.update_info(
            order,
            mesa=request.POST.get('mesa', ''),
            cliente=request.POST.get('cliente', ''),
            observacoes=request.POST.get('observacoes', ''),
        )
    except OrderError as exc:
        return _order_response(request, order, str(exc), status=400)
    return _order_response(request, order, 'Dados do pedido atualizados.')


@service_required
@require_POST
def add_product_to_order(request, order_id, product_id):
    order = get_order_or_403(request.user, order_id)
    product = get_object_or_404(Product, pk=product_id)
    try:
        order_service.add_product(order, product, request.user, notes=request.POST.get('notes', ''))
    except OrderError as exc:
        return _order_response(request, order, str(exc), status=400)
    return _order_response(request, order, f'{product.name} adicionado ao pedido.')


@service_required
@require_POST
def change_order_item_qty(request, order_id, item_id):
    order = get_order_or_403(request.user, order_id)
    item = get_object_or_404(OrderItem, pk=item_id, order=order)
    try:
        order_service.change_item(order, item, request.POST.get('action'), request.user)
    except OrderError as exc:
        return _order_response(request, order, str(exc), status=400)
    order.refresh_from_db()
    return _order_response(request, order, 'Pedido atualizado.')


# ------------------------------------------------------------------ cozinha

@kitchen_required
def kitchen_view(request):
    now = timezone.now()
    late_limit = now - timedelta(minutes=KITCHEN_LATE_MINUTES)
    items = Prefetch('items', queryset=OrderItem.objects.select_related('product').order_by('id'))

    orders_cozinha = []
    for order in Order.objects.filter(status='cozinha').prefetch_related(items).order_by('updated_at'):
        order.pending_items = [item for item in order.items.all() if item.pending_quantity > 0]
        if not order.pending_items:
            continue
        # Pedido alterado conta o tempo a partir do último envio à cozinha.
        order.kitchen_reference_time = order.updated_at
        order.is_late = order.updated_at < late_limit
        order.wait_minutes = int((now - order.updated_at).total_seconds() // 60)
        orders_cozinha.append(order)

    orders_pronto = list(Order.objects.filter(status='pronto').prefetch_related(items).order_by('updated_at'))
    for order in orders_pronto:
        order.wait_minutes = int((now - order.created_at).total_seconds() // 60)

    return render(request, 'restaurante/kitchen.html', {
        'orders_cozinha': orders_cozinha,
        'orders_pronto': orders_pronto,
        'now': now,
    })


@kitchen_required
@require_POST
def mark_order_ready(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    try:
        order_service.mark_ready(order)
    except OrderError as exc:
        return _order_response(request, None, str(exc), redirect_to='kitchen_view', status=400)
    return _order_response(request, None, f'Pedido #{order.id} marcado como pronto!', redirect_to='kitchen_view')


# ------------------------------------------------------------------ fechar / cancelar / cupom

@service_required
def close_order(request, order_id):
    order = get_order_or_403(request.user, order_id)
    if request.method == 'POST':
        payment_method = request.POST.get('payment_method', '')
        try:
            order_service.close(order, payment_method, request.user)
        except OrderError as exc:
            messages.error(request, str(exc))
            return redirect('close_order', order_id=order.id)
        audit(request, 'order.close', f'Pedido #{order.id} finalizado.', order,
              payment_method=payment_method, total=order.total)
        messages.success(request, f'Conta fechada! Pagamento: {order.get_payment_method_display()}')
        return redirect(home_for(request.user))

    if not order.is_active:
        messages.error(request, 'Este pedido já foi encerrado.')
        return redirect(home_for(request.user))
    return render(request, 'restaurante/close_order.html', {
        'order': order,
        'pix': pix_for_order(order, AppSettings.get_settings()),
    })


@manager_required
@require_POST
def cancel_order(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    try:
        order_service.cancel(order, request.user)
    except OrderError as exc:
        messages.error(request, str(exc))
        return redirect('admin_dashboard')
    audit(request, 'order.cancel', f'Pedido #{order.id} cancelado.', order,
          total=order.total, mesa=order.mesa, cliente=order.cliente)
    messages.warning(request, f'Pedido #{order.id} cancelado.')
    return redirect('admin_dashboard')


@role_required('garcom', 'gerente')
def print_order(request, order_id):
    order = get_order_or_403(request.user, order_id)
    store_settings = AppSettings.get_settings()
    audit(request, 'order.print', f'Cupom do pedido #{order.id} impresso.', order, status=order.status)
    pix = None
    if store_settings.show_pix_on_receipt and order.status != 'cancelado':
        pix = pix_for_order(order, store_settings)
    return render(request, 'restaurante/print_order.html', {
        'order': order,
        'settings': store_settings,
        'pix': pix,
    })
