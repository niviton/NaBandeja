"""
Páginas públicas (sem login): cardápio digital da mesa (QR Code) e pedido
online. Têm limite de uso por IP para evitar abuso.
"""

from decimal import Decimal
from urllib.parse import quote

from django.core.cache import cache
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from ..models import AppSettings, DeliveryZone, Order, Product, Table
from ..services import orders as order_service
from ..services import tables as table_service
from ..services.audit import client_ip
from ..services.cart import CartError, SessionCart
from ..services.orders import OrderError
from .orders import error_response, hx_redirect, menu_categories, with_toast

ONLINE_CART = 'online'


def _rate_limited(request, bucket, limit, seconds):
    key = f'public:{bucket}:{client_ip(request)}'
    hits = cache.get(key, 0) + 1
    cache.set(key, hits, seconds)
    return hits > limit


def _store_or_404(flag):
    store = AppSettings.get_settings()
    if not getattr(store, flag):
        raise Http404('Recurso desativado pela loja.')
    return store


# ------------------------------------------------------------------ cardápio da mesa

def table_menu(request, token):
    store = _store_or_404('public_menu_enabled')
    table = get_object_or_404(Table, public_token=token, is_active=True)
    return render(request, 'public/cardapio.html', {
        'store': store,
        'table': table,
        'categories': menu_categories(),
        'online_enabled': store.online_orders_enabled,
    })


def public_menu(request):
    store = _store_or_404('public_menu_enabled')
    return render(request, 'public/cardapio.html', {
        'store': store,
        'table': None,
        'categories': menu_categories(),
        'online_enabled': store.online_orders_enabled,
    })


@require_POST
def table_call(request, token, kind):
    _store_or_404('public_menu_enabled')
    table = get_object_or_404(Table, public_token=token, is_active=True)
    if kind not in ('garcom', 'conta'):
        raise Http404
    if _rate_limited(request, 'call', limit=6, seconds=600):
        return error_response('Muitos chamados seguidos. Aguarde um pouco, o garçom já foi avisado.')
    table_service.create_call(table, kind)
    message = 'Pronto! O garçom foi chamado.' if kind == 'garcom' else 'Pronto! A conta foi pedida.'
    return with_toast(render(request, 'public/_call_done.html', {'kind': kind}), message)


# ------------------------------------------------------------------ pedido online

def online_order(request):
    store = _store_or_404('online_orders_enabled')
    return render(request, 'public/pedir.html', {
        'store': store,
        'categories': menu_categories(),
        'cart': SessionCart(request.session, ONLINE_CART),
        'zones': DeliveryZone.objects.filter(is_active=True),
    })


def _online_cart(request, message=None, kind='success'):
    response = render(request, 'public/_cart.html', {
        'store': AppSettings.get_settings(),
        'cart': SessionCart(request.session, ONLINE_CART),
        'zones': DeliveryZone.objects.filter(is_active=True),
    })
    return with_toast(response, message, kind) if message else response


@require_POST
def online_cart_add(request, product_id):
    _store_or_404('online_orders_enabled')
    cart = SessionCart(request.session, ONLINE_CART)
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    try:
        cart.add(product)
    except CartError as exc:
        return _online_cart(request, str(exc), 'error')
    return _online_cart(request, f'{product.name} no carrinho')


@require_POST
def online_cart_change(request):
    _store_or_404('online_orders_enabled')
    cart = SessionCart(request.session, ONLINE_CART)
    try:
        cart.change(request.POST.get('cart_key', ''), int(request.POST.get('delta', 1)))
    except (CartError, ValueError) as exc:
        return _online_cart(request, str(exc), 'error')
    return _online_cart(request)


@require_POST
def online_checkout(request):
    store = _store_or_404('online_orders_enabled')
    cart = SessionCart(request.session, ONLINE_CART)
    if not cart:
        return error_response('Seu carrinho está vazio.')
    if Decimal(str(cart.total)) < store.min_delivery_order:
        return error_response(f'O pedido mínimo para entrega é R$ {store.min_delivery_order:.2f}.')
    name = request.POST.get('cliente', '').strip()
    phone = request.POST.get('phone', '').strip()
    if not name or len(phone) < 8:
        return error_response('Informe seu nome e um telefone com DDD.')

    zones = DeliveryZone.objects.filter(is_active=True)
    zone = zones.filter(pk=request.POST.get('zone') or 0).first()
    if zones.exists() and zone is None:
        return error_response('Escolha o seu bairro.')
    if _rate_limited(request, 'order', limit=3, seconds=600):
        return error_response('Você já enviou pedidos agora há pouco. Aguarde alguns minutos ou fale pelo WhatsApp.')

    notes = request.POST.get('observacoes', '').strip()
    payment = request.POST.get('pagamento', '').strip()
    if payment:
        notes = f'Pagamento: {payment}' + (f' | {notes}' if notes else '')
    try:
        order, _ = order_service.place_order(
            None, cart,
            order_type='delivery',
            cliente=name,
            customer_phone=phone,
            address=request.POST.get('address', ''),
            platform='Site',
            observacoes=notes,
            delivery_fee=zone.fee if zone else Decimal('0'),
            store_settings=store,
            pending=True,
        )
    except OrderError as exc:
        return error_response(str(exc))
    cart.clear()
    request.session['online_last_order'] = order.id
    return hx_redirect(reverse('online_order_sent', args=[order.id]))


def online_order_sent(request, order_id):
    if request.session.get('online_last_order') != order_id:
        return redirect('online_order')
    store = AppSettings.get_settings()
    order = get_object_or_404(Order.objects.prefetch_related('items'), pk=order_id)
    whatsapp = ''
    if store.whatsapp_number:
        number = ''.join(ch for ch in store.whatsapp_number if ch.isdigit())
        number = number if number.startswith('55') else f'55{number}'
        lines = [f'Olá! Fiz o pedido #{order.id} pelo site:']
        lines += [f'{item.quantity}x {item.name}' for item in order.items.all()]
        lines.append(f'Total: R$ {order.amount_due:.2f}'.replace('.', ','))
        whatsapp = f'https://wa.me/{number}?text={quote(chr(10).join(lines))}'
    return render(request, 'public/pedido_enviado.html', {'store': store, 'order': order, 'whatsapp': whatsapp})
