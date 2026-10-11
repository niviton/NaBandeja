"""Cálculos dos relatórios de vendas (por data de pagamento do pedido)."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db.models import Avg, Count, DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import TruncDay
from django.utils import timezone

from ..models import Order, OrderItem, Payment

FILTER_TYPES = ('day', 'month', 'year', 'range')


@dataclass
class Period:
    filter_type: str
    start: datetime
    end: datetime
    label: str
    day: str
    month: str
    year: str
    start_date: str
    end_date: str


def _aware(day):
    return timezone.make_aware(datetime.combine(day, time.min))


def _parse_day(raw, default):
    try:
        return date.fromisoformat((raw or '').strip())
    except ValueError:
        return default


def resolve_period(params, today=None):
    """Interpreta os filtros da tela (?filter=day&day=2026-10-11 ...)."""
    today = today or timezone.localdate()
    filter_type = params.get('filter', 'day')
    if filter_type not in FILTER_TYPES:
        filter_type = 'day'

    day = _parse_day(params.get('day'), today)
    try:
        year_num, month_num = (int(part) for part in (params.get('month') or '').split('-'))
        month_start = date(year_num, month_num, 1)
    except ValueError:
        month_start = date(today.year, today.month, 1)
    try:
        year_value = int(params.get('year') or today.year)
        date(year_value, 1, 1)
    except ValueError:
        year_value = today.year
    range_start = _parse_day(params.get('start_date'), today - timedelta(days=6))
    range_end = _parse_day(params.get('end_date'), today)
    if range_start > range_end:
        range_start, range_end = range_end, range_start

    if filter_type == 'day':
        start, end = _aware(day), _aware(day + timedelta(days=1))
        label = day.strftime('%d/%m/%Y')
    elif filter_type == 'month':
        next_month = date(month_start.year + month_start.month // 12, month_start.month % 12 + 1, 1)
        start, end = _aware(month_start), _aware(next_month)
        label = month_start.strftime('%m/%Y')
    elif filter_type == 'year':
        start, end = _aware(date(year_value, 1, 1)), _aware(date(year_value + 1, 1, 1))
        label = str(year_value)
    else:
        start, end = _aware(range_start), _aware(range_end + timedelta(days=1))
        label = f"{range_start:%d/%m/%Y} até {range_end:%d/%m/%Y}"

    return Period(
        filter_type=filter_type,
        start=start,
        end=end,
        label=label,
        day=day.isoformat(),
        month=month_start.strftime('%Y-%m'),
        year=str(year_value),
        start_date=range_start.isoformat(),
        end_date=range_end.isoformat(),
    )


def paid_orders(period):
    return Order.objects.filter(status='finalizado', closed_at__gte=period.start, closed_at__lt=period.end)


def history_orders(period, search=''):
    qs = (
        Order.objects.filter(status__in=['finalizado', 'cancelado'], closed_at__gte=period.start, closed_at__lt=period.end)
        .select_related('waiter')
        .prefetch_related('items__product')
        .order_by('-closed_at')
    )
    if search:
        qs = qs.filter(cliente__icontains=search)
    return qs


MONEY = DecimalField(max_digits=12, decimal_places=2)
LINE_TOTAL = ExpressionWrapper(F('quantity') * F('unit_price'), output_field=MONEY)
LINE_COST = ExpressionWrapper(F('quantity') * F('unit_cost'), output_field=MONEY)


def sales_summary(orders):
    """
    Faturamento = soma dos pagamentos (já desconta descontos e inclui taxas de
    entrega). Produtos e lucro vêm dos itens vendidos.
    """
    payments = Payment.objects.filter(order__in=orders)
    revenue = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    count = orders.count()
    items = OrderItem.objects.filter(order__in=orders)
    labels = dict(Order.PAYMENT_CHOICES)

    by_product = list(
        items.values('product_name', 'product__icon')
        .annotate(
            total_qty=Sum('quantity'),
            total_revenue=Sum(LINE_TOTAL),
            total_cost=Sum(LINE_COST),
            orders_count=Count('order', distinct=True),
        )
        .order_by('-total_qty', 'product_name')
    )
    items_revenue = Decimal('0')
    items_cost = Decimal('0')
    for row in by_product:
        row['total_revenue'] = row['total_revenue'] or Decimal('0')
        row['has_cost'] = row['total_cost'] is not None and row['total_cost'] > 0
        row['total_cost'] = row['total_cost'] or Decimal('0')
        row['profit'] = row['total_revenue'] - row['total_cost']
        row['margin'] = (row['profit'] / row['total_revenue'] * 100) if row['total_revenue'] and row['has_cost'] else None
        items_revenue += row['total_revenue']
        items_cost += row['total_cost']

    discounts = orders.aggregate(total=Sum('discount'))['total'] or Decimal('0')
    delivery_fees = orders.aggregate(total=Sum('delivery_fee'))['total'] or Decimal('0')
    return {
        'revenue': revenue,
        'orders': count,
        'avg_ticket': (revenue / count) if count else Decimal('0'),
        'items_sold': items.aggregate(total=Sum('quantity'))['total'] or 0,
        'discounts': discounts,
        'delivery_fees': delivery_fees,
        'items_cost': items_cost,
        'gross_profit': items_revenue - discounts - items_cost,
        'products_without_cost': sum(1 for row in by_product if not row['has_cost']),
        'by_waiter': list(
            orders.values('waiter__username')
            .annotate(total_sales=Sum('total'), orders_count=Count('id'), avg_ticket=Avg('total'))
            .order_by('-total_sales')
        ),
        'by_day': list(
            payments.annotate(day=TruncDay('order__closed_at')).values('day')
            .annotate(total=Sum('amount'), count=Count('order', distinct=True)).order_by('day')
        ),
        'by_product': by_product,
        'by_payment': [
            {'method': labels.get(row['method'], row['method']), 'total': row['total'], 'count': row['count']}
            for row in payments.values('method').annotate(total=Sum('amount'), count=Count('id')).order_by('-total')
        ],
    }
