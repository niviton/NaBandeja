"""Abertura e fechamento de caixa (turno)."""

from decimal import Decimal, InvalidOperation

from django.db.models import Count, Sum
from django.utils import timezone

from ..models import CashMovement, CashSession, Order, Payment


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


def payments_in_session(session, until=None):
    """Pagamentos recebidos durante o turno (contas divididas contam por parte)."""
    return Payment.objects.filter(
        created_at__gte=session.opened_at,
        created_at__lte=until or session.closed_at or timezone.now(),
    )


def summary(session, until=None):
    """Totais do turno por forma de pagamento e quanto deve haver na gaveta."""
    payments = payments_in_session(session, until)
    by_method = {
        row['method']: {'total': row['total'] or Decimal('0'), 'count': row['count']}
        for row in payments.values('method').annotate(total=Sum('amount'), count=Count('id'))
    }
    labels = {key: label for key, label in Order.PAYMENT_CHOICES if key != 'misto'}
    methods = [
        {'method': key, 'label': labels[key], **by_method.get(key, {'total': Decimal('0'), 'count': 0})}
        for key in labels
    ]
    cash_sales = by_method.get('dinheiro', {}).get('total', Decimal('0'))
    movements = list(session.movements.select_related('created_by')) if session.pk else []
    supplies = sum((m.amount for m in movements if m.kind == 'suprimento'), Decimal('0'))
    withdrawals = sum((m.amount for m in movements if m.kind == 'sangria'), Decimal('0'))
    return {
        'methods': methods,
        'total_sales': sum((m['total'] for m in methods), Decimal('0')),
        'orders_count': payments.values('order').distinct().count(),
        'cash_sales': cash_sales,
        'movements': movements,
        'supplies': supplies,
        'withdrawals': withdrawals,
        # Só dinheiro em espécie fica na gaveta; PIX e cartão vão para o banco.
        'expected_in_drawer': session.opening_amount + cash_sales + supplies - withdrawals,
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


def add_movement(user, kind, amount, reason):
    """Sangria (retirada) ou suprimento (troco colocado) no caixa aberto."""
    session = CashSession.get_open_session()
    if not session:
        raise CashError('Abra o caixa antes de registrar sangria ou suprimento.')
    if kind not in dict(CashMovement.KIND_CHOICES):
        raise CashError('Tipo de movimentação inválido.')
    reason = (reason or '').strip()[:200]
    if not reason:
        raise CashError('Informe o motivo.')
    value = parse_amount(amount)
    if value <= 0:
        raise CashError('O valor deve ser maior que zero.')
    return CashMovement.objects.create(session=session, kind=kind, amount=value, reason=reason, created_by=user)
