"""
Pagamentos como acontecem no balcão e na mesa.

Quem paga (modo):
- tudo:    uma pessoa paga o que falta;
- dividir: N pessoas em partes iguais, cada uma na sua forma ("Pessoa 2 de 3");
- itens:   cada um paga o que consumiu (marca os itens; o valor já leva
           desconto e serviço proporcionais);
- valor:   um valor qualquer.

Como paga (forma): dinheiro (com valor recebido e troco), PIX, crédito,
débito e vale-refeição. Só o dinheiro aceita receber mais que o valor.

Cada pagamento é um registro (Payment). Quando a soma paga cobre a conta, o
pedido é finalizado automaticamente.
"""

from decimal import ROUND_DOWN, Decimal, InvalidOperation

from django.utils import timezone

from ..models import Order, Payment
from .orders import OrderError, ensure_active

METHODS = {key: label for key, label in Order.PAYMENT_CHOICES if key != 'misto'}
MODES = ('tudo', 'dividir', 'itens', 'valor')
CENT = Decimal('0.01')
MAX_PEOPLE = 30
SPLIT_PREFIX = 'Pessoa '


def parse_money(raw):
    text = str(raw or '').replace('R$', '').replace(' ', '')
    if ',' in text:
        text = text.replace('.', '').replace(',', '.')
    try:
        value = Decimal(text).quantize(CENT)
    except InvalidOperation as exc:
        raise OrderError('Valor inválido.') from exc
    if value <= 0:
        raise OrderError('O valor deve ser maior que zero.')
    return value


def split_evenly(amount, people):
    """Divide o valor em partes iguais; os centavos que sobram vão para as primeiras."""
    people = max(1, int(people))
    base = (amount / people).quantize(CENT, rounding=ROUND_DOWN)
    parts = [base] * people
    leftover = int((amount - base * people) / CENT)
    for index in range(leftover):
        parts[index] += CENT
    return parts


def _money(value):
    return value.quantize(CENT) if isinstance(value, Decimal) else parse_money(value)


# ------------------------------------------------------------------ dividir igual

def split_progress(order, people):
    """(próxima pessoa, total de pessoas, valor da parte dela) na divisão igual."""
    people = max(2, min(MAX_PEOPLE, int(people or 2)))
    paid = sum(1 for payment in order.payments.all() if payment.label.startswith(SPLIT_PREFIX))
    left = max(1, people - paid)
    remaining = order.amount_remaining
    share = split_evenly(remaining, left)[0] if remaining > 0 else Decimal('0.00')
    return min(paid + 1, people), people, share


# ------------------------------------------------------------------ cada um paga o seu

def paid_quantities(order):
    """{id do item: quantidade já paga} somando os pagamentos por itens."""
    paid = {}
    for payment in order.payments.all():
        for item_id, qty in (payment.items or {}).items():
            paid[int(item_id)] = paid.get(int(item_id), 0) + int(qty)
    return paid


def item_factor(order):
    """Quanto vale R$ 1 de item na conta: aplica desconto e serviço proporcionais."""
    if not order.total:
        return Decimal('1')
    return (order.subtotal_after_discount + order.service_fee) / order.total


def open_items(order):
    """Itens com o que ainda falta pagar de cada um (para a tela 'cada um paga o seu')."""
    paid = paid_quantities(order)
    factor = item_factor(order)
    rows = []
    for item in order.items.all():
        left = max(item.quantity - paid.get(item.id, 0), 0)
        rows.append({'item': item, 'left': left, 'unit_charge': (item.unit_price * factor).quantize(CENT)})
    return rows


def _selection(order, raw):
    """Valida {id: qtd} contra o que ainda falta pagar de cada item."""
    paid = paid_quantities(order)
    items = {item.id: item for item in order.items.all()}
    selection = {}
    for item_id, qty in (raw or {}).items():
        try:
            item_id, qty = int(item_id), int(qty)
        except (TypeError, ValueError):
            raise OrderError('Seleção de itens inválida.')
        if qty <= 0:
            continue
        item = items.get(item_id)
        if item is None:
            raise OrderError('Item não pertence a esta conta.')
        if qty > item.quantity - paid.get(item_id, 0):
            raise OrderError(f'{item.name}: só falta pagar {item.quantity - paid.get(item_id, 0)}.')
        selection[item_id] = qty
    if not selection:
        raise OrderError('Marque os itens que esta pessoa vai pagar.')
    return selection, items, paid


def charge_for_items(order, raw_selection):
    """(valor, descrição, seleção) de quem paga só os itens marcados."""
    selection, items, paid = _selection(order, raw_selection)
    factor = item_factor(order)
    amount = sum((items[item_id].unit_price * qty for item_id, qty in selection.items()), Decimal('0'))
    amount = (amount * factor).quantize(CENT)
    # Quem paga os últimos itens leva o resto (centavos do arredondamento e a entrega).
    everything_paid = all(item.quantity <= paid.get(item.id, 0) + selection.get(item.id, 0) for item in items.values())
    remaining = order.amount_remaining
    if everything_paid or amount > remaining:
        amount = remaining
    label = ', '.join(f'{qty}× {items[item_id].name}' for item_id, qty in selection.items())
    return amount, label[:120], selection


# ------------------------------------------------------------------ registrar

def charge(order, mode, *, amount=None, people=None, items=None):
    """Quanto cobrar agora em cada modo. Retorna (valor, descrição, itens)."""
    if mode not in MODES:
        raise OrderError('Escolha quem está pagando.')
    if mode == 'tudo':
        return order.amount_remaining, '', None
    if mode == 'dividir':
        person, total, share = split_progress(order, people)
        return share, f'{SPLIT_PREFIX}{person} de {total}', None
    if mode == 'itens':
        return charge_for_items(order, items)
    return _money(amount), '', None


def add_payment(order, method, amount, user, *, received=None, label='', items=None):
    """
    Registra um pagamento de `amount` na forma `method`.

    Dinheiro: `received` é o que o cliente entregou (troco = recebido - valor).
    Sem `received`, um valor acima do que falta conta como recebido (troco).
    Retorna (payment, troco, pedido_finalizado).
    """
    ensure_active(order)
    if method not in METHODS:
        raise OrderError('Forma de pagamento inválida.')
    if not order.items.exists():
        raise OrderError('Pedido sem itens não pode ser pago.')

    remaining = order.amount_remaining
    if remaining <= 0:
        raise OrderError('Esta conta já está paga.')
    amount = _money(amount)
    received = _money(received) if received not in (None, '') and method == 'dinheiro' else None

    if amount > remaining:
        if method == 'dinheiro' and received is None:
            received = amount
            amount = remaining
        else:
            raise OrderError(f'O valor passa do que falta pagar (R$ {remaining:.2f}).')

    change = Decimal('0.00')
    if received is not None:
        if received < amount:
            raise OrderError(f'Recebido (R$ {received:.2f}) é menor que o valor a pagar (R$ {amount:.2f}).')
        change = received - amount

    payment = Payment.objects.create(
        order=order, method=method, amount=amount, created_by=user, received=received, change=change,
        label=label[:120], items={str(key): value for key, value in (items or {}).items()},
    )
    finished = order.amount_remaining <= 0
    if finished:
        finished = settle(order, user)
    return payment, change, finished


def set_service(order, percent):
    """Liga/desliga a taxa de serviço da conta (só antes do primeiro pagamento)."""
    ensure_active(order)
    if order.payments.exists():
        raise OrderError('A taxa de serviço só pode mudar antes do primeiro pagamento.')
    order.service_percent = Decimal(percent).quantize(CENT)
    order.save(update_fields=['service_percent', 'updated_at'])
    return order


def waits_after_payment(order):
    """
    Pedido quitado que ainda não deve ser encerrado:
    - balcão pago antes, com itens ainda na cozinha (entrega depois);
    - delivery pago antes de ser entregue.
    Mesas encerram ao quitar.
    """
    if order.order_type == 'delivery':
        return order.delivered_at is None
    if order.mesa == 'SEM MESA':
        return order.status == 'cozinha' or order.items.filter(pending_quantity__gt=0).exists()
    return False


def settle(order, user):
    """Conta quitada: encerra, ou marca como paga e aguarda a entrega. Retorna se encerrou."""
    if waits_after_payment(order):
        order.paid_at = timezone.now()
        order.save(update_fields=['paid_at', 'updated_at'])
        return False
    finalize(order, user)
    return True


def pay_remaining(order, method, user):
    """Paga tudo o que falta numa forma só (o 'fechar conta' tradicional)."""
    if method not in METHODS:
        raise OrderError('Forma de pagamento inválida.')
    remaining = order.amount_remaining
    if remaining <= 0:
        settle(order, user)
        return None
    payment, _, _ = add_payment(order, method, remaining, user)
    return payment


def remove_payment(payment):
    order = payment.order
    ensure_active(order)
    payment.delete()
    if order.paid_at:
        order.paid_at = None
        order.save(update_fields=['paid_at', 'updated_at'])


def finalize(order, user):
    methods = set(order.payments.values_list('method', flat=True))
    order.status = 'finalizado'
    order.payment_method = methods.pop() if len(methods) == 1 else 'misto'
    order.closed_at = timezone.now()
    order.closed_by = user
    order.paid_at = order.paid_at or order.closed_at
    order.items.filter(pending_quantity__gt=0).update(pending_quantity=0)
    order.save(update_fields=['status', 'payment_method', 'closed_at', 'closed_by', 'paid_at', 'updated_at'])
    return order
