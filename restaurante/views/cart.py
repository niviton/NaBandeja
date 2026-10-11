"""API do carrinho (AJAX). Respostas: {'success', 'cart', 'total', 'message'?}."""

import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from ..models import Product
from ..permissions import service_required
from ..services.cart import CartError, SessionCart


def _json_body(request):
    try:
        return json.loads(request.body or b'{}')
    except ValueError:
        return {}


def _error(cart, message):
    return JsonResponse({**cart.as_json(), 'success': False, 'message': message})


@service_required
def api_get_cart(request):
    return JsonResponse(SessionCart(request.session).as_json())


@service_required
@require_POST
def api_add_to_cart(request, product_id):
    cart = SessionCart(request.session)
    product = get_object_or_404(Product, pk=product_id)
    body = _json_body(request)
    try:
        cart.add(product, quantity=max(1, int(body.get('qty', 1))), notes=body.get('notes', ''))
    except (CartError, ValueError) as exc:
        return _error(cart, str(exc))
    return JsonResponse(cart.as_json())


@service_required
@require_POST
def api_remove_from_cart(request, product_id):
    cart = SessionCart(request.session)
    cart_key = _json_body(request).get('cart_key') or str(product_id)
    cart.change(cart_key, -1)
    return JsonResponse(cart.as_json())


@service_required
@require_POST
def api_change_cart_item(request):
    cart = SessionCart(request.session)
    body = _json_body(request)
    try:
        if 'notes' in body:
            cart.set_notes(body.get('cart_key', ''), body['notes'])
        else:
            cart.change(body.get('cart_key', ''), int(body.get('delta', 1)))
    except (CartError, ValueError) as exc:
        return _error(cart, str(exc))
    return JsonResponse(cart.as_json())


@service_required
@require_POST
def api_clear_cart(request):
    cart = SessionCart(request.session)
    cart.clear()
    return JsonResponse(cart.as_json())
