"""
Telas da equipe: salão (mapa de mesas), pedido (cardápio + carrinho + conta
aberta), pagamento, cozinha e impressões.

As partes que mudam (carrinho, conta, mapa, cozinha) são fragmentos HTML
atualizados pelo htmx; os fragmentos começam com "_" em templates/app/.
"""

import json
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.db.models import Prefetch
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST

from ..modules import is_enabled
from ..models import AppSettings, Category, DeliveryZone, Order, OrderItem, Payment, Product, Table
from ..permissions import (
    get_order_or_403,
    home_for,
    kitchen_required,
    manager_required,
    service_required,
)
from ..services import orders as order_service
from ..services import payments as payment_service
from ..services import tables as table_service
from ..services.audit import audit
from ..services.cart import CartError, SessionCart
from ..services.orders import DELIVERY_PLATFORMS, OrderError, normalize_mesa
from ..services.pix import pix_for_order, pix_for_amount


# ------------------------------------------------------------------ utilidades

def is_htmx(request):
    return request.headers.get('HX-Request') == 'true'


def with_toast(response, message, kind='success'):
    response['HX-Trigger'] = json.dumps({'nb:toast': {'message': message, 'type': kind}})
    return response


def hx_redirect(url, request=None, message=None, kind='success'):
    """Redireciona a página inteira (htmx) mostrando a mensagem na tela seguinte."""
    if request is not None and message:
        getattr(messages, kind)(request, message)
    response = HttpResponse(status=204)
    response['HX-Redirect'] = url
    return response


def error_response(message):
    response = HttpResponse(json.dumps({'message': message}), status=422, content_type='application/json')
    return response


def menu_categories():
    """Categorias ativas com os produtos ativos (cardápio do garçom e público)."""
    active_products = Product.objects.filter(is_active=True).prefetch_related('recipe_items__ingredient')
    return [
        category for category in
        Category.objects.filter(is_active=True).prefetch_related(Prefetch('products', queryset=active_products))
        if category.products.all()
    ]


# ------------------------------------------------------------------ alvo do pedido

class Target:
    """
    Para onde vai o carrinho:
      mesa:<nome>      mesa sem conta aberta (o envio cria o pedido)
      pedido:<id>      conta aberta (o envio acrescenta itens)
      novo:balcao      pedido de balcão sem mesa
      novo:delivery    pedido de delivery
    """

    def __init__(self, key):
        self.key = key
        self.kind, _, self.ref = key.partition(':')
        if self.kind not in ('mesa', 'pedido', 'novo') or not self.ref:
            raise ValueError(key)
        if self.kind == 'novo' and self.ref not in ('balcao', 'delivery'):
            raise ValueError(key)

    def order(self, user):
        if self.kind == 'pedido':
            return get_order_or_403(user, int(self.ref))
        if self.kind == 'mesa':
            return order_service.active_order_for_table(self.ref)
        return None

    @property
    def title(self):
        if self.kind == 'mesa':
            return f'Mesa {self.ref}'
        if self.kind == 'novo':
            return 'Novo delivery' if self.ref == 'delivery' else 'Pedido de balcão'
        return f'Pedido #{self.ref}'


def target_for_order(order):
    if order.order_type == 'dine-in' and order.mesa != 'SEM MESA':
        return Target(f'mesa:{order.mesa}')
    return Target(f'pedido:{order.id}')


def workspace_url(order):
    target = target_for_order(order)
    if target.kind == 'mesa':
        return reverse('table_order', args=[target.ref])
    return reverse('order_workspace', args=[order.id])


def _get_target(key):
    try:
        return Target(key)
    except ValueError:
        from django.http import Http404
        raise Http404('Pedido inválido.')


# ------------------------------------------------------------------ salão

@service_required
def waiter_view(request):
    return render(request, 'app/salao.html', {**_salao_context(), 'active_tab': 'salao'})


@service_required
def salao_board(request):
    return render(request, 'app/_salao_board.html', _salao_context())


def _salao_context():
    return {
        'tables': table_service.board(),
        'counter_orders': table_service.counter_orders(),
        'pending_online': table_service.pending_online_orders().count(),
        'calls': table_service.pending_calls(),
    }


@service_required
@require_POST
def resolve_table_calls(request, mesa):
    table_service.resolve_calls(mesa, request.user)
    if is_htmx(request):
        return with_toast(render(request, 'app/_salao_board.html', _salao_context()), f'Mesa {mesa} atendida.')
    return redirect('waiter_view')


# ------------------------------------------------------------------ tela do pedido

@service_required
def table_order(request, mesa):
    mesa = normalize_mesa(mesa)
    order = order_service.active_order_for_table(mesa)
    target = Target(f'mesa:{mesa}')
    return _workspace(request, target, order)


@service_required
def order_workspace(request, order_id):
    order = get_order_or_403(request.user, order_id)
    if not order.is_active:
        messages.info(request, f'O pedido #{order.id} já foi encerrado.')
        return redirect(home_for(request.user))
    if order.order_type == 'dine-in' and order.mesa != 'SEM MESA':
        return redirect('table_order', mesa=order.mesa)
    return _workspace(request, Target(f'pedido:{order.id}'), order)


@service_required
def new_order(request, kind):
    if kind not in ('balcao', 'delivery'):
        return redirect('waiter_view')
    if kind == 'delivery' and not is_enabled('delivery'):
        raise Http404('Delivery desativado para esta loja.')
    return _workspace(request, Target(f'novo:{kind}'), None)


def manage_order(request, order_id):
    """Endereço antigo: leva para a tela nova do pedido."""
    return redirect('order_workspace', order_id=order_id)


def _workspace(request, target, order):
    store = AppSettings.get_settings()
    if order is not None:
        order = Order.objects.prefetch_related('items__product', 'payments').get(pk=order.pk)
    return render(request, 'app/pedido.html', {
        'active_tab': 'salao',
        'target': target,
        'order': order,
        'categories': menu_categories(),
        'cart': SessionCart(request.session, target.key),
        'quick_notes': store.quick_notes_list,
        'delivery_zones': DeliveryZone.objects.filter(is_active=True),
        'platforms': DELIVERY_PLATFORMS,
        'tables': Table.objects.filter(is_active=True),
    })


@service_required
def order_panel(request, key):
    target = _get_target(key)
    order = target.order(request.user)
    return render(request, 'app/_order_panel.html', _panel_context(target, order))


def _panel_context(target, order):
    if order is not None:
        order = Order.objects.prefetch_related('items__product', 'payments').get(pk=order.pk)
    return {'target': target, 'order': order, 'tables': Table.objects.filter(is_active=True)}


# ------------------------------------------------------------------ carrinho

def _cart_response(request, target, cart, message=None, kind='success'):
    response = render(request, 'app/_cart.html', {
        'target': target,
        'cart': cart,
        'order': target.order(request.user),
        'quick_notes': AppSettings.get_settings().quick_notes_list,
        'delivery_zones': DeliveryZone.objects.filter(is_active=True),
        'platforms': DELIVERY_PLATFORMS,
    })
    return with_toast(response, message, kind) if message else response


@service_required
@require_POST
def cart_add(request, key, product_id):
    target = _get_target(key)
    cart = SessionCart(request.session, target.key)
    product = get_object_or_404(Product, pk=product_id)
    try:
        cart.add(product, notes=request.POST.get('notes', ''))
    except CartError as exc:
        return _cart_response(request, target, cart, str(exc), 'error')
    return _cart_response(request, target, cart, f'{product.name} no pedido')


@service_required
@require_POST
def cart_change(request, key):
    target = _get_target(key)
    cart = SessionCart(request.session, target.key)
    try:
        if 'notes' in request.POST:
            cart.set_notes(request.POST.get('cart_key', ''), request.POST['notes'])
        else:
            cart.change(request.POST.get('cart_key', ''), int(request.POST.get('delta', 1)))
    except (CartError, ValueError) as exc:
        return _cart_response(request, target, cart, str(exc), 'error')
    return _cart_response(request, target, cart)


@service_required
@require_POST
def cart_clear(request, key):
    target = _get_target(key)
    cart = SessionCart(request.session, target.key)
    cart.clear()
    return _cart_response(request, target, cart)


@service_required
@require_POST
def cart_send(request, key):
    """Envia o carrinho para a cozinha (cria o pedido ou acrescenta à conta)."""
    target = _get_target(key)
    cart = SessionCart(request.session, target.key)
    if not cart:
        return error_response('O carrinho está vazio.')
    store = AppSettings.get_settings()
    order = target.order(request.user)

    try:
        if order is not None:
            for line in cart.items:
                product = get_object_or_404(Product, pk=line['id'])
                order_service.add_product(order, product, request.user, quantity=line['qty'], notes=line.get('notes', ''))
            message = f'Itens enviados para a cozinha ({order.display_name}).'
        else:
            zone = None
            if target.ref == 'delivery' and request.POST.get('zone'):
                zone = DeliveryZone.objects.filter(pk=request.POST['zone'], is_active=True).first()
            order, merged = order_service.place_order(
                request.user,
                cart,
                order_type='delivery' if target.ref == 'delivery' else 'dine-in',
                mesa=target.ref if target.kind == 'mesa' else '',
                cliente=request.POST.get('cliente', '') or ('Balcão' if target.ref == 'balcao' else ''),
                observacoes=request.POST.get('observacoes', ''),
                address=request.POST.get('address', ''),
                platform=request.POST.get('platform', ''),
                customer_phone=request.POST.get('phone', ''),
                delivery_fee=zone.fee if zone else Decimal('0'),
                store_settings=store,
            )
            message = f'Pedido #{order.id} enviado para a cozinha!'
    except OrderError as exc:
        return error_response(str(exc))

    cart.clear()
    if target.kind == 'novo':
        return hx_redirect(reverse('waiter_view'), request, message)
    return hx_redirect(workspace_url(order), request, message)


# ------------------------------------------------------------------ ações na conta aberta

def _panel(request, order, message=None, kind='success'):
    response = render(request, 'app/_order_panel.html', _panel_context(target_for_order(order), order))
    return with_toast(response, message, kind) if message else response


def _order_action(request, order_id, action, message, manager_only=False):
    order = get_order_or_403(request.user, order_id)
    if manager_only and request.user.role != 'gerente':
        return error_response('Só o gerente pode fazer isso.')
    try:
        result = action(order)
    except OrderError as exc:
        return error_response(str(exc))
    return result if isinstance(result, HttpResponse) else _panel(request, order, message)


@service_required
@require_POST
def change_order_item_qty(request, order_id, item_id):
    order = get_order_or_403(request.user, order_id)
    item = get_object_or_404(OrderItem, pk=item_id, order=order)
    action = request.POST.get('action')
    if action == 'delete' and item.quantity > item.pending_quantity and request.user.role != 'gerente':
        return error_response('Item já preparado: só o gerente pode remover.')
    try:
        order_service.change_item(order, item, action, request.user)
    except OrderError as exc:
        return error_response(str(exc))
    order.refresh_from_db()
    if not order.is_active:
        return hx_redirect(reverse('waiter_view'), request, 'Pedido sem itens foi cancelado.', 'info')
    return _panel(request, order)


@service_required
@require_POST
def request_bill(request, order_id):
    return _order_action(request, order_id, order_service.request_bill, 'Conta pedida. A mesa aparece em roxo no salão.')


@service_required
@require_POST
def mark_served(request, order_id):
    return _order_action(request, order_id, order_service.mark_served, 'Marcado como servido.')


@service_required
@require_POST
def update_order_info(request, order_id):
    def action(order):
        return order_service.update_info(
            order, mesa=request.POST.get('mesa', order.mesa),
            cliente=request.POST.get('cliente', ''), observacoes=request.POST.get('observacoes', ''),
        )
    return _order_action(request, order_id, action, 'Dados do pedido atualizados.')


@service_required
@require_POST
def transfer_order(request, order_id):
    order = get_order_or_403(request.user, order_id)
    try:
        result = order_service.transfer(order, request.POST.get('mesa', ''), request.user)
    except OrderError as exc:
        return error_response(str(exc))
    audit(request, 'order.transfer', f'Pedido #{order.id} transferido para a mesa {result.mesa}.', order)
    return hx_redirect(workspace_url(result), request, f'Pedido agora está na mesa {result.mesa}.')


@manager_required
@require_POST
def apply_discount(request, order_id):
    def action(order):
        order_service.apply_discount(order, request.POST.get('value'), request.POST.get('percent'), request.POST.get('reason'))
        audit(request, 'order.discount', f'Desconto de R$ {order.discount:.2f} no pedido #{order.id}.', order,
              reason=order.discount_reason)
    return _order_action(request, order_id, action, 'Desconto aplicado.', manager_only=True)


@manager_required
@require_POST
def remove_discount(request, order_id):
    return _order_action(request, order_id, order_service.remove_discount, 'Desconto removido.', manager_only=True)


@manager_required
@require_POST
def cancel_order(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    try:
        order_service.cancel(order, request.user)
    except OrderError as exc:
        if is_htmx(request):
            return error_response(str(exc))
        messages.error(request, str(exc))
        return redirect('admin_dashboard')
    audit(request, 'order.cancel', f'Pedido #{order.id} cancelado.', order,
          total=order.total, mesa=order.mesa, cliente=order.cliente)
    if is_htmx(request):
        return hx_redirect(reverse('waiter_view'), request, f'Pedido #{order.id} cancelado.', 'warning')
    messages.warning(request, f'Pedido #{order.id} cancelado.')
    return redirect(request.POST.get('next') or 'admin_dashboard')


# ------------------------------------------------------------------ pagamento

@service_required
def close_order(request, order_id):
    order = get_order_or_403(request.user, order_id)
    if not order.is_active:
        messages.info(request, 'Este pedido já foi encerrado.')
        return redirect(home_for(request.user))
    return render(request, 'app/conta.html', _payment_context(order))


def _payment_context(order):
    order = Order.objects.prefetch_related('items__product', 'payments__created_by').get(pk=order.pk)
    remaining = order.amount_remaining
    return {
        'order': order,
        'remaining': remaining,
        'methods': payment_service.METHODS,
        'split_options': [2, 3, 4, 5, 6],
        'pix': pix_for_order(order, AppSettings.get_settings()) if remaining > 0 else None,
    }


@service_required
@require_POST
def add_payment(request, order_id):
    order = get_order_or_403(request.user, order_id)
    try:
        payment, change, finished = payment_service.add_payment(
            order, request.POST.get('method', ''), request.POST.get('amount', ''), request.user,
        )
    except OrderError as exc:
        return error_response(str(exc))

    if finished:
        audit(request, 'order.close', f'Pedido #{order.id} pago e finalizado.', order, total=order.amount_due)
        message = f'Conta paga! Troco: R$ {change:.2f}'.replace('.', ',') if change else 'Conta paga e finalizada!'
        return hx_redirect(reverse('order_paid', args=[order.id]), request, message)

    message = f'Recebido R$ {payment.amount:.2f}'.replace('.', ',')
    if change:
        message += f' · troco R$ {change:.2f}'.replace('.', ',')
    response = render(request, 'app/_payments.html', _payment_context(order))
    return with_toast(response, message)


@manager_required
@require_POST
def remove_payment(request, payment_id):
    payment = get_object_or_404(Payment.objects.select_related('order'), pk=payment_id)
    order = payment.order
    try:
        payment_service.remove_payment(payment)
    except OrderError as exc:
        return error_response(str(exc))
    audit(request, 'payment.remove', f'Pagamento estornado no pedido #{order.id}.', order,
          method=payment.method, amount=payment.amount)
    return with_toast(render(request, 'app/_payments.html', _payment_context(order)), 'Pagamento estornado.', 'warning')


@service_required
def pix_amount(request, order_id):
    """QR Code PIX de um valor específico (ex.: parte de uma conta dividida)."""
    order = get_order_or_403(request.user, order_id)
    try:
        amount = payment_service.parse_money(request.GET.get('valor', ''))
    except OrderError as exc:
        return error_response(str(exc))
    pix = pix_for_amount(order, amount, AppSettings.get_settings())
    return render(request, 'app/_pix.html', {'pix': pix, 'amount': amount, 'order': order})


@service_required
def order_paid(request, order_id):
    order = get_order_or_403(request.user, order_id)
    return render(request, 'app/conta_paga.html', {'order': order})


# ------------------------------------------------------------------ cozinha

@kitchen_required
def kitchen_view(request):
    return render(request, 'app/cozinha.html', {**_kitchen_context(), 'active_tab': 'cozinha'})


@kitchen_required
def kitchen_board(request):
    return render(request, 'app/_cozinha_board.html', _kitchen_context())


def _kitchen_context():
    store = AppSettings.get_settings()
    items = Prefetch('items', queryset=OrderItem.objects.select_related('product').order_by('id'))
    preparing = []
    for order in Order.objects.filter(status='cozinha').prefetch_related(items).order_by('updated_at'):
        order.pending_items = [item for item in order.items.all() if item.pending_quantity > 0]
        if order.pending_items:
            preparing.append(order)
    recent = timezone.now() - timedelta(minutes=30)
    ready = Order.objects.filter(status='pronto', served_at__isnull=True, updated_at__gte=recent).order_by('-updated_at')
    return {
        'orders_cozinha': preparing,
        'orders_pronto': ready,
        'late_minutes': store.kitchen_late_minutes,
        'auto_print': store.kitchen_auto_print,
    }


@kitchen_required
@require_POST
def mark_order_ready(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    try:
        order_service.mark_ready(order)
    except OrderError as exc:
        if is_htmx(request):
            return error_response(str(exc))
        messages.error(request, str(exc))
        return redirect('kitchen_view')
    if is_htmx(request):
        return with_toast(render(request, 'app/_cozinha_board.html', _kitchen_context()), f'{order.display_name} pronto!')
    messages.success(request, f'Pedido #{order.id} marcado como pronto!')
    return redirect('kitchen_view')


@xframe_options_sameorigin
@kitchen_required
def kitchen_ticket(request, order_id):
    """Comanda da cozinha: só os itens ainda não impressos (ou todos com ?todos=1)."""
    order = get_object_or_404(Order, pk=order_id)
    if request.GET.get('todos'):
        lines = [(item, item.quantity) for item in order.items.select_related('product').order_by('id')]
    else:
        lines = order_service.items_to_print(order)
    if request.GET.get('marcar'):
        order_service.mark_printed(order)
    return render(request, 'app/comanda.html', {'order': order, 'lines': lines, 'auto': bool(request.GET.get('auto'))})


# ------------------------------------------------------------------ cupom do cliente

@service_required
def print_order(request, order_id):
    order = get_order_or_403(request.user, order_id)
    store = AppSettings.get_settings()
    audit(request, 'order.print', f'Cupom do pedido #{order.id} impresso.', order, status=order.status)
    pix = None
    if store.show_pix_on_receipt and order.status != 'cancelado' and order.amount_remaining > 0:
        pix = pix_for_order(order, store)
    return render(request, 'restaurante/print_order.html', {'order': order, 'settings': store, 'pix': pix})
