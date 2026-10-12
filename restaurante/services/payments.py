"""
Pagamentos: conta dividida, várias formas de pagamento e troco.

Cada pagamento é um registro (Payment). Quando a soma paga cobre o valor da
conta, o pedido é finalizado automaticamente.
"""

from decimal import ROUND_DOWN, Decimal, InvalidOperation

from django.utils import timezone

from ..models import Order, Payment
from .orders import OrderError, ensure_active

METHODS = {key: label for key, label in Order.PAYMENT_CHOICES if key != 'misto'}
CENT = Decimal('0.01')


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


def add_payment(order, method, amount, user):
    """
    Registra um pagamento. Em dinheiro, o valor recebido pode passar do que
    falta: registra só o necessário e devolve o troco.
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
    amount = parse_money(amount) if not isinstance(amount, Decimal) else amount.quantize(CENT)

    change = Decimal('0.00')
    if amount > remaining:
        if method != 'dinheiro':
            raise OrderError(f'O valor passa do que falta pagar (R$ {remaining:.2f}).')
        change = amount - remaining
        amount = remaining

    payment = Payment.objects.create(order=order, method=method, amount=amount, created_by=user)
    finished = order.amount_remaining <= 0
    if finished:
        finished = settle(order, user)
    return payment, change, finished


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
