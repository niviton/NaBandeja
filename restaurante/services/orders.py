"""
Regras de negócio dos pedidos: criar, alterar itens, cozinha, fechar e cancelar.

As views só traduzem HTTP <-> estas funções. Erros de regra viram OrderError
com uma mensagem pronta para mostrar ao usuário.
"""

from decimal import Decimal

from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.utils import timezone

from ..models import Order, OrderItem, Product
from . import license as license_service
from . import stock

PAYMENT_METHODS = dict(Order.PAYMENT_CHOICES)
DELIVERY_PLATFORMS = ['Whatsapp', 'iFood', 'Rappi', 'Telefone', 'Balcão', 'Site']


class OrderError(Exception):
    pass


# ------------------------------------------------------------------ consultas

def normalize_mesa(mesa):
    """'01' e '1' são a mesma mesa; nomes ficam em maiúsculas."""
    mesa = (mesa or '').strip().upper()[:20]
    return str(int(mesa)) if mesa.isdigit() else mesa


def active_order_for_table(mesa):
    mesa = normalize_mesa(mesa)
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
        if target == 'cozinha':
            order.served_at = None
        order.save(update_fields=['status', 'served_at', 'updated_at'])


# ------------------------------------------------------------------ itens

def _add_line(order, product, quantity, notes, user, consume_stock=True):
    if consume_stock:
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
        unit_cost=product.unit_cost,
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
                address='', platform='', store_settings=None, pending=False,
                customer_phone='', delivery_fee=Decimal('0')):
    """
    Cria o pedido a partir do carrinho. Na mesma mesa com conta aberta, os
    itens entram na conta existente. Retorna (order, juntou_em_conta_aberta).

    pending=True: pedido online aguardando o gerente aceitar (não baixa
    estoque nem vai para a cozinha até ser aceito).
    """
    if store_settings is not None:
        if not store_settings.is_store_open:
            raise OrderError('Loja fechada no momento. Aguarde o gerente abrir novamente.')
        license_status = license_service.status(store_settings.license_key)
        if license_status.blocks_new_orders:
            raise OrderError(license_status.message)
    if not cart:
        raise OrderError('O carrinho está vazio.')

    order_type = order_type if order_type in ('dine-in', 'delivery') else 'dine-in'
    mesa = normalize_mesa(mesa)
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

    order = active_order_for_table(mesa) if order_type == 'dine-in' and not pending else None
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
            customer_phone=(customer_phone or '').strip()[:30],
            delivery_fee=delivery_fee or Decimal('0'),
            waiter=user,
            status='pendente' if pending else 'cozinha',
        )

    try:
        for cart_item in cart.items:
            _add_line(order, products[cart_item['id']], cart_item['qty'], cart_item.get('notes', ''), user,
                      consume_stock=not pending)
    except stock.OutOfStock as exc:
        # A view está numa transação (ATOMIC_REQUESTS): nada fica gravado.
        raise OrderError(str(exc)) from exc

    recalculate(order)
    if merged:
        order.status = 'cozinha'
        order.bill_requested_at = None
        order.save(update_fields=['status', 'bill_requested_at', 'updated_at'])
    return order, merged


def update_info(order, mesa='', cliente='', observacoes=''):
    ensure_active(order)
    if order.order_type == 'delivery':
        mesa = 'DELIVERY'
    else:
        mesa = normalize_mesa(mesa)
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
    order.served_at = None
    order.save(update_fields=['status', 'served_at', 'updated_at'])
    return order


def mark_served(order):
    """Garçom confirma que levou à mesa o que estava pronto."""
    ensure_active(order)
    order.served_at = timezone.now()
    order.save(update_fields=['served_at', 'updated_at'])
    return order


def items_to_print(order):
    """Itens (e quantidades) ainda não impressos na comanda da cozinha."""
    lines = []
    for item in order.items.select_related('product').order_by('id'):
        new_units = min(item.quantity - item.printed_quantity, item.pending_quantity)
        if new_units > 0:
            lines.append((item, new_units))
    return lines


def mark_printed(order):
    order.items.update(printed_quantity=F('quantity'))


def close(order, payment_method, user):
    """Fecha a conta pagando o que falta numa forma de pagamento só."""
    from .payments import pay_remaining

    ensure_active(order)
    if not order.items.exists():
        raise OrderError('Pedido sem itens não pode ser fechado.')
    pay_remaining(order, payment_method, user)
    order.refresh_from_db()
    return order


def cancel(order, user):
    if order.status == 'pendente':
        return reject_pending(order, user)
    ensure_active(order)
    if order.payments.exists():
        raise OrderError('Este pedido já tem pagamentos. Estorne os pagamentos antes de cancelar.')
    for item in order.items.select_related('product'):
        stock.restore(item.product, item.pending_quantity, user=user, reason=f'Pedido #{order.id} cancelado')
    order.items.update(pending_quantity=0)
    order.status = 'cancelado'
    order.closed_at = timezone.now()
    order.closed_by = user
    order.save(update_fields=['status', 'closed_at', 'closed_by', 'updated_at'])
    return order


# ------------------------------------------------------------------ conta, desconto, mesas

def request_bill(order):
    ensure_active(order)
    order.bill_requested_at = timezone.now()
    order.save(update_fields=['bill_requested_at', 'updated_at'])
    return order


def apply_discount(order, value='', percent='', reason=''):
    """Desconto em reais ou em % sobre os itens. 100% = cortesia."""
    from .payments import parse_money

    ensure_active(order)
    reason = (reason or '').strip()[:200]
    if not reason:
        raise OrderError('Informe o motivo do desconto.')
    if str(percent or '').strip():
        try:
            pct = Decimal(str(percent).replace(',', '.'))
        except ArithmeticError as exc:
            raise OrderError('Percentual inválido.') from exc
        if not 0 < pct <= 100:
            raise OrderError('O percentual deve ser entre 0 e 100.')
        discount = (order.total * pct / 100).quantize(Decimal('0.01'))
    else:
        discount = parse_money(value)
    if discount > order.total:
        raise OrderError('O desconto não pode ser maior que o total dos itens.')
    if discount > order.total - order.amount_paid + order.discount:
        raise OrderError('O desconto passa do valor que ainda falta pagar.')
    order.discount = discount
    order.discount_reason = reason
    order.save(update_fields=['discount', 'discount_reason', 'updated_at'])
    return order


def remove_discount(order):
    ensure_active(order)
    order.discount = Decimal('0')
    order.discount_reason = ''
    order.save(update_fields=['discount', 'discount_reason', 'updated_at'])
    return order


def transfer(order, target_mesa, user):
    """
    Muda o pedido para outra mesa. Se a mesa de destino já tem conta aberta,
    junta os itens nela (e o pedido de origem é encerrado como 'cancelado'
    sem devolver estoque, porque os itens continuam valendo no destino).
    Retorna o pedido que ficou com os itens.
    """
    ensure_active(order)
    if order.order_type != 'dine-in':
        raise OrderError('Só pedidos de mesa podem ser transferidos.')
    target_mesa = normalize_mesa(target_mesa)
    if not target_mesa:
        raise OrderError('Informe a mesa de destino.')
    if target_mesa == order.mesa:
        raise OrderError('O pedido já está nessa mesa.')
    if order.payments.exists():
        raise OrderError('Pedido com pagamento parcial não pode ser transferido.')

    target = active_order_for_table(target_mesa)
    if target is None:
        order.mesa = target_mesa
        order.save(update_fields=['mesa', 'updated_at'])
        return order

    for item in order.items.all():
        twin = target.items.filter(product_id=item.product_id, notes=item.notes, unit_price=item.unit_price).first()
        if twin:
            twin.quantity += item.quantity
            twin.pending_quantity += item.pending_quantity
            twin.save(update_fields=['quantity', 'pending_quantity'])
            item.delete()
        else:
            item.order = target
            item.save(update_fields=['order'])
    if order.observacoes:
        target.observacoes = f'{target.observacoes} | {order.observacoes}'.strip(' |')
    target.discount += order.discount
    target.save(update_fields=['observacoes', 'discount', 'updated_at'])
    recalculate(target)
    sync_kitchen_status(target)

    order.refresh_from_db()
    order.total = Decimal('0')
    order.discount = Decimal('0')
    order.status = 'cancelado'
    order.observacoes = f'Juntado na mesa {target_mesa} (pedido #{target.id})'
    order.closed_at = timezone.now()
    order.closed_by = user
    order.save(update_fields=['total', 'discount', 'status', 'observacoes', 'closed_at', 'closed_by', 'updated_at'])
    return target


# ------------------------------------------------------------------ pedidos online

def accept_pending(order, user):
    if order.status != 'pendente':
        raise OrderError('Este pedido não está aguardando confirmação.')
    try:
        for item in order.items.select_related('product'):
            stock.consume(item.product, item.quantity, user=user, reason=f'Pedido online #{order.id}')
    except stock.OutOfStock as exc:
        raise OrderError(str(exc)) from exc
    order.status = 'cozinha'
    order.waiter = user
    order.save(update_fields=['status', 'waiter', 'updated_at'])
    return order


def reject_pending(order, user):
    if order.status != 'pendente':
        raise OrderError('Este pedido não está aguardando confirmação.')
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
