"""
Regras de negócio dos pedidos: criar, alterar itens, cozinha, fechar e cancelar.

As views só traduzem HTTP <-> estas funções. Erros de regra viram OrderError
com uma mensagem pronta para mostrar ao usuário.
"""

from decimal import Decimal

from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.utils import timezone

from ..models import Order, OrderItem, Product
from . import stock

PAYMENT_METHODS = dict(Order.PAYMENT_CHOICES)
DELIVERY_PLATFORMS = ['Whatsapp', 'iFood', 'Rappi', 'Telefone', 'Balcão', 'Site']


class OrderError(Exception):
    pass


# ------------------------------------------------------------------ consultas

def active_order_for_table(mesa):
    if not mesa or mesa == 'SEM MESA':
        return None
    return (
        Order.objects.filter(mesa=mesa, order_type='dine-in', status__in=Order.ACTIVE_STATUSES)
        .order_by('-updated_at', '-id')
        .first()
    )


def ensure_active(order):
    if not order.is_active:
        raise OrderError('Pedido finalizado ou cancelado não pode ser alterado.')


# ------------------------------------------------------------------ totais e status

def recalculate(order):
    """Recalcula o total a partir dos itens (fonte única da verdade)."""
    line_total = ExpressionWrapper(F('quantity') * F('unit_price'), output_field=DecimalField(max_digits=12, decimal_places=2))
    total = order.items.aggregate(total=Sum(line_total))['total'] or Decimal('0')
    order.total = total.quantize(Decimal('0.01'))
    order.save(update_fields=['total', 'updated_at'])
    return order.total


def sync_kitchen_status(order):
    """Pedido vai para 'cozinha' se há algo a preparar, senão 'pronto'."""
    if not order.is_active:
        return
    if not order.items.exists():
        order.status = 'cancelado'
        order.save(update_fields=['status', 'updated_at'])
        return
    target = 'cozinha' if order.items.filter(pending_quantity__gt=0).exists() else 'pronto'
    if order.status != target:
        order.status = target
        order.save(update_fields=['status', 'updated_at'])


# ------------------------------------------------------------------ itens

def _add_line(order, product, quantity, notes, user):
    stock.consume(product, quantity, user=user, reason=f'Pedido #{order.id}')
    item = order.items.filter(product=product, notes=notes, unit_price=product.price).first()
    if item:
        OrderItem.objects.filter(pk=item.pk).update(
            quantity=F('quantity') + quantity,
            pending_quantity=F('pending_quantity') + quantity,
        )
        item.refresh_from_db()
        # post_save não roda em update(); salva para avisar o tempo real.
        item.save(update_fields=['quantity'])
        return item
    return OrderItem.objects.create(
        order=order,
        product=product,
        product_name=product.name,
        notes=notes,
        quantity=quantity,
        pending_quantity=quantity,
        unit_price=product.price,
    )


def add_product(order, product, user, quantity=1, notes=''):
    ensure_active(order)
    if not product.is_active:
        raise OrderError(f'{product.name} não está disponível.')
    try:
        _add_line(order, product, quantity, (notes or '').strip()[:200], user)
    except stock.OutOfStock as exc:
        raise OrderError(str(exc)) from exc
    recalculate(order)
    sync_kitchen_status(order)
    return order


def change_item(order, item, action, user):
    """action: 'add' (+1), 'remove' (-1) ou 'delete' (remove a linha)."""
    ensure_active(order)
    product = item.product
    if action == 'add':
        try:
            stock.consume(product, 1, user=user, reason=f'Pedido #{order.id}')
        except stock.OutOfStock as exc:
            raise OrderError(str(exc)) from exc
        item.quantity += 1
        item.pending_quantity += 1
        item.save(update_fields=['quantity', 'pending_quantity'])
    elif action in ('remove', 'delete'):
        units = 1 if action == 'remove' else item.quantity
        # Só devolve ao estoque o que a cozinha ainda não preparou.
        to_restore = min(units, item.pending_quantity)
        stock.restore(product, to_restore, user=user, reason=f'Removido do pedido #{order.id}')
        item.quantity -= units
        item.pending_quantity -= to_restore
        if item.quantity <= 0:
            item.delete()
        else:
            item.pending_quantity = min(item.pending_quantity, item.quantity)
            item.save(update_fields=['quantity', 'pending_quantity'])
    else:
        raise OrderError('Ação inválida.')
    recalculate(order)
    sync_kitchen_status(order)
    return order


# ------------------------------------------------------------------ criação

def place_order(user, cart, *, order_type='dine-in', mesa='', cliente='', observacoes='',
                address='', platform='', store_settings=None):
    """
    Cria o pedido a partir do carrinho. Na mesma mesa com conta aberta, os
    itens entram na conta existente. Retorna (order, juntou_em_conta_aberta).
    """
    if store_settings is not None and not store_settings.is_store_open:
        raise OrderError('Loja fechada no momento. Aguarde o gerente abrir novamente.')
    if not cart:
        raise OrderError('O carrinho está vazio.')

    order_type = order_type if order_type in ('dine-in', 'delivery') else 'dine-in'
    mesa = (mesa or '').strip().upper()[:50]
    cliente = (cliente or '').strip()[:200]
    observacoes = (observacoes or '').strip()
    address = (address or '').strip()

    if order_type == 'delivery':
        if not address:
            raise OrderError('Informe o endereço de entrega.')
        mesa = 'DELIVERY'
        platform = platform if platform in DELIVERY_PLATFORMS else 'Whatsapp'
    else:
        if not mesa and not cliente:
            raise OrderError('Informe o número da mesa ou o nome do cliente.')
        mesa = mesa or 'SEM MESA'
        platform = ''

    products = Product.objects.prefetch_related('recipe_items').in_bulk([item['id'] for item in cart.items])
    for cart_item in cart.items:
        if cart_item['id'] not in products:
            raise OrderError(f"Produto removido do cardápio: {cart_item['name']}.")

    order = active_order_for_table(mesa) if order_type == 'dine-in' else None
    merged = order is not None
    if merged:
        if observacoes:
            order.observacoes = f'{order.observacoes} | {observacoes}' if order.observacoes else observacoes
        if cliente and not order.cliente:
            order.cliente = cliente
        order.save(update_fields=['observacoes', 'cliente', 'updated_at'])
    else:
        order = Order.objects.create(
            mesa=mesa,
            cliente=cliente or ('Cliente delivery' if order_type == 'delivery' else ''),
            observacoes=observacoes,
            order_type=order_type,
            address=address,
            platform=platform,
            waiter=user,
            status='cozinha',
        )

    try:
        for cart_item in cart.items:
            _add_line(order, products[cart_item['id']], cart_item['qty'], cart_item.get('notes', ''), user)
    except stock.OutOfStock as exc:
        # A view está numa transação (ATOMIC_REQUESTS): nada fica gravado.
        raise OrderError(str(exc)) from exc

    recalculate(order)
    if merged:
        order.status = 'cozinha'
        order.save(update_fields=['status', 'updated_at'])
    return order, merged


def update_info(order, mesa='', cliente='', observacoes=''):
    ensure_active(order)
    if order.order_type == 'delivery':
        mesa = 'DELIVERY'
    else:
        mesa = (mesa or '').strip().upper()[:50]
        if not mesa:
            raise OrderError('Informe o número da mesa.')
    order.mesa = mesa
    order.cliente = (cliente or '').strip()[:200]
    order.observacoes = (observacoes or '').strip()
    order.save(update_fields=['mesa', 'cliente', 'observacoes', 'updated_at'])
    return order


# ------------------------------------------------------------------ cozinha, fechamento

def mark_ready(order):
    if order.status != 'cozinha':
        raise OrderError('Este pedido não está na cozinha.')
    order.items.update(pending_quantity=0)
    order.status = 'pronto'
    order.save(update_fields=['status', 'updated_at'])
    return order


def close(order, payment_method, user):
    ensure_active(order)
    if payment_method not in PAYMENT_METHODS:
        raise OrderError('Forma de pagamento inválida.')
    if not order.items.exists():
        raise OrderError('Pedido sem itens não pode ser fechado.')
    order.status = 'finalizado'
    order.payment_method = payment_method
    order.closed_at = timezone.now()
    order.closed_by = user
    order.save(update_fields=['status', 'payment_method', 'closed_at', 'closed_by', 'updated_at'])
    return order


def cancel(order, user):
    ensure_active(order)
    for item in order.items.select_related('product'):
        stock.restore(item.product, item.pending_quantity, user=user, reason=f'Pedido #{order.id} cancelado')
    order.items.update(pending_quantity=0)
    order.status = 'cancelado'
    order.closed_at = timezone.now()
    order.closed_by = user
    order.save(update_fields=['status', 'closed_at', 'closed_by', 'updated_at'])
    return order


# ------------------------------------------------------------------ JSON

def snapshot(order):
    return {
        'id': order.id,
        'mesa': order.mesa,
        'cliente': order.cliente,
        'observacoes': order.observacoes or '',
        'status': order.status,
        'total': float(order.total),
        'items': [
            {
                'id': item.id,
                'product_name': item.name,
                'product_icon': item.product.icon or '🍽️',
                'notes': item.notes,
                'quantity': item.quantity,
                'pending_quantity': item.pending_quantity,
                'unit_price': float(item.unit_price),
                'subtotal': float(item.subtotal),
            }
            for item in order.items.select_related('product').order_by('id')
        ],
    }
