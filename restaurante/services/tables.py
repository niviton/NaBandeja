"""Mapa de mesas do salão e chamados feitos pelo QR Code da mesa."""

from dataclasses import dataclass, field
from datetime import timedelta

from django.db.models import Prefetch, Q
from django.utils import timezone

from ..models import Order, OrderItem, Table, TableCall
from ..realtime import publish_event
from .orders import normalize_mesa

CALL_COOLDOWN = timedelta(minutes=2)

# status -> (rótulo, classes Tailwind do cartão)
STATUS_STYLE = {
    'livre': ('Livre', 'bg-papel border-linha text-carvao'),
    'ocupada': ('Servida', 'bg-cebola-50 border-cebola/40 text-cebola'),
    'cozinha': ('Na cozinha', 'bg-mostarda-50 border-mostarda text-[#7A4F0F]'),
    'pronto': ('Pronto p/ servir', 'bg-manjericao-50 border-manjericao text-manjericao'),
    'conta': ('Pediu a conta', 'bg-uva-50 border-uva text-uva'),
}


@dataclass
class TableState:
    table: Table
    order: Order | None = None
    calls: list = field(default_factory=list)

    @property
    def status(self):
        if self.order is None:
            return 'livre'
        if self.order.bill_requested_at or any(call.kind == 'conta' for call in self.calls):
            return 'conta'
        if self.order.status == 'pronto':
            return 'pronto'
        if self.order.status == 'cozinha':
            return 'cozinha'
        return 'ocupada'

    @property
    def label(self):
        return STATUS_STYLE[self.status][0]

    @property
    def css(self):
        return STATUS_STYLE[self.status][1]

    @property
    def calling_waiter(self):
        return any(call.kind == 'garcom' for call in self.calls)

    @property
    def minutes_open(self):
        if not self.order:
            return 0
        return int((timezone.now() - self.order.created_at).total_seconds() // 60)


def board():
    """Todas as mesas ativas com o pedido aberto e os chamados pendentes."""
    tables = list(Table.objects.filter(is_active=True))
    open_orders = (
        Order.objects.filter(order_type='dine-in', status__in=Order.ACTIVE_STATUSES)
        .select_related('waiter')
        .prefetch_related(Prefetch('items', queryset=OrderItem.objects.only('id', 'order_id', 'quantity')))
        .order_by('created_at')
    )
    by_mesa = {}
    for order in open_orders:
        by_mesa.setdefault(order.mesa, order)
    calls = {}
    for call in TableCall.objects.filter(resolved_at__isnull=True).select_related('table'):
        calls.setdefault(call.table_id, []).append(call)

    states = [TableState(table, by_mesa.pop(table.name, None), calls.get(table.id, [])) for table in tables]
    # Pedidos em mesas que não estão cadastradas (ex.: "Balcão 2") aparecem no fim.
    for mesa, order in by_mesa.items():
        if mesa != 'SEM MESA':
            states.append(TableState(Table(name=mesa, id=None), order, []))
    return states


def counter_orders():
    """Pedidos ativos fora do mapa: delivery e balcão (sem mesa)."""
    return (
        Order.objects.filter(status__in=Order.ACTIVE_STATUSES)
        .filter(Q(order_type='delivery') | Q(mesa='SEM MESA'))
        .order_by('created_at')
    )


def pending_online_orders():
    return Order.objects.filter(status='pendente').prefetch_related('items').order_by('created_at')


def pending_calls():
    return TableCall.objects.filter(resolved_at__isnull=True).select_related('table').order_by('created_at')


def create_call(table, kind):
    """Registra o chamado. Ignora repetições em menos de 2 minutos."""
    if kind not in dict(TableCall.KIND_CHOICES):
        raise ValueError('Tipo de chamado inválido.')
    recent = TableCall.objects.filter(
        table=table, kind=kind, resolved_at__isnull=True, created_at__gte=timezone.now() - CALL_COOLDOWN,
    ).first()
    if recent:
        return recent, False
    call = TableCall.objects.create(table=table, kind=kind)
    publish_event('table.call', {'table': table.name, 'kind': kind, 'label': call.get_kind_display()})
    return call, True


def resolve_calls(table_name, user):
    updated = TableCall.objects.filter(table__name=normalize_mesa(table_name), resolved_at__isnull=True).update(
        resolved_at=timezone.now(), resolved_by=user,
    )
    if updated:
        publish_event('table.call_resolved', {'table': table_name})
    return updated


def create_tables(count, start=1):
    """Cadastro rápido: cria as mesas start..start+count-1 que ainda não existem."""
    created = 0
    for number in range(start, start + count):
        _, was_created = Table.objects.get_or_create(name=str(number), defaults={'order': number})
        created += was_created
    return created
