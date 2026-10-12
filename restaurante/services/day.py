"""
Dia de trabalho: abrir (caixa + loja) e fechar (checklist + caixa + loja).

Abrir o dia:  abre o caixa com o troco da gaveta (se o módulo Caixa estiver
              ligado) e abre a loja para pedidos.
Fechar o dia: confere o que ficou pendente (mesas abertas, pedidos online,
              entregas na rua), fecha o caixa com o dinheiro contado e fecha a
              loja.
"""

from django.utils import timezone

from ..models import AppSettings, CashSession, Order
from ..modules import is_enabled
from . import cash as cash_service


class DayError(Exception):
    pass


def pending_items():
    """O que impede fechar o dia sem conferir: lista de (rótulo, quantidade, pedidos)."""
    active = Order.objects.filter(status__in=Order.ACTIVE_STATUSES)
    groups = [
        ('Mesas com conta aberta', active.filter(order_type='dine-in').exclude(mesa='SEM MESA')),
        ('Pedidos de balcão abertos', active.filter(order_type='dine-in', mesa='SEM MESA')),
        ('Entregas não finalizadas', active.filter(order_type='delivery')),
        ('Pedidos online aguardando', Order.objects.filter(status='pendente')),
    ]
    return [(label, list(qs.order_by('created_at'))) for label, qs in groups if qs.exists()]


def status():
    store = AppSettings.get_settings()
    session = CashSession.get_open_session() if is_enabled('caixa', store) else None
    return {
        'store_open': store.is_store_open,
        'cash_enabled': is_enabled('caixa', store),
        'session': session,
        'summary': cash_service.summary(session) if session else None,
        'is_open': store.is_store_open and (session is not None or not is_enabled('caixa', store)),
    }


def open_day(user, opening_amount='0', notes=''):
    store = AppSettings.get_settings()
    session = None
    if is_enabled('caixa', store):
        session = CashSession.get_open_session()
        if session is None:
            try:
                session = cash_service.open_session(user, opening_amount, notes)
            except cash_service.CashError as exc:
                raise DayError(str(exc)) from exc
    store.is_store_open = True
    store.save(update_fields=['is_store_open'])
    return session


def close_day(user, counted_amount='0', notes='', force=False):
    """
    Fecha caixa e loja. Sem force, recusa se houver pendências (o gerente
    confirma vendo a lista). Retorna (sessão de caixa ou None, totais ou None).
    """
    pending = pending_items()
    if pending and not force:
        total = sum(len(orders) for _, orders in pending)
        raise DayError(f'Há {total} pedido(s) em aberto. Confira a lista antes de fechar o dia.')

    store = AppSettings.get_settings()
    session = totals = None
    if is_enabled('caixa', store) and CashSession.get_open_session():
        try:
            session, totals = cash_service.close_session(user, counted_amount, notes)
        except cash_service.CashError as exc:
            raise DayError(str(exc)) from exc
    store.is_store_open = False
    store.save(update_fields=['is_store_open'])
    return session, totals


def recent_paid_orders(limit=8):
    """Últimas contas fechadas hoje (as que ainda podem ser conferidas e reabertas)."""
    day_start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        Order.objects.filter(status='finalizado', closed_at__gte=day_start)
        .select_related('closed_by')
        .order_by('-closed_at')[:limit]
    )
