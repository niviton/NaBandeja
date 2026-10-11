"""Abertura e fechamento de caixa (turno)."""

from decimal import Decimal, InvalidOperation

from django.db.models import Count, Sum
from django.utils import timezone

from ..models import CashSession, Order


class CashError(Exception):
    pass


def parse_amount(raw):
    try:
        value = Decimal(str(raw or '0').replace('R$', '').replace(' ', '').replace(',', '.'))
    except InvalidOperation as exc:
        raise CashError('Valor inválido.') from exc
    if value < 0:
        raise CashError('O valor não pode ser negativo.')
    return value.quantize(Decimal('0.01'))


def orders_in_session(session, until=None):
    """Pedidos pagos durante o turno (pela data de fechamento da conta)."""
    return Order.objects.filter(
        status='finalizado',
        closed_at__gte=session.opened_at,
        closed_at__lte=until or session.closed_at or timezone.now(),
    )


def summary(session, until=None):
    """Totais do turno por forma de pagamento e quanto deve haver na gaveta."""
    orders = orders_in_session(session, until)
    by_method = {
        row['payment_method']: {'total': row['total'] or Decimal('0'), 'count': row['count']}
        for row in orders.values('payment_method').annotate(total=Sum('total'), count=Count('id'))
    }
    labels = dict(Order.PAYMENT_CHOICES)
    methods = [
        {'method': key, 'label': labels[key], **by_method.get(key, {'total': Decimal('0'), 'count': 0})}
        for key in labels
    ]
    cash_sales = by_method.get('dinheiro', {}).get('total', Decimal('0'))
    return {
        'methods': methods,
        'total_sales': sum((m['total'] for m in methods), Decimal('0')),
        'orders_count': sum(m['count'] for m in methods),
        'cash_sales': cash_sales,
        # Só dinheiro em espécie fica na gaveta; PIX e cartão vão para o banco.
        'expected_in_drawer': session.opening_amount + cash_sales,
    }


def open_session(user, opening_amount, notes=''):
    if CashSession.get_open_session():
        raise CashError('Já existe um caixa aberto.')
    return CashSession.objects.create(
        opened_by=user,
        opening_amount=parse_amount(opening_amount),
        notes=(notes or '').strip(),
        status='open',
    )


def close_session(user, counted_amount, notes=''):
    session = CashSession.get_open_session()
    if not session:
        raise CashError('Não há caixa aberto para fechar.')
    counted = parse_amount(counted_amount)
    closed_at = timezone.now()
    totals = summary(session, until=closed_at)

    session.closing_amount = counted
    session.expected_amount = totals['expected_in_drawer']
    session.difference_amount = counted - totals['expected_in_drawer']
    session.status = 'closed'
    session.closed_by = user
    session.closed_at = closed_at
    notes = (notes or '').strip()
    if notes:
        session.notes = f'{session.notes}\n{notes}'.strip()
    session.save()
    return session, totals
