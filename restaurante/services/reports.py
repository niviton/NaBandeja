"""Cálculos dos relatórios de vendas (por data de pagamento do pedido)."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db.models import Avg, Count, DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import TruncDay
from django.utils import timezone

from ..models import Order, OrderItem

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


LINE_TOTAL = ExpressionWrapper(F('quantity') * F('unit_price'), output_field=DecimalField(max_digits=12, decimal_places=2))


def sales_summary(orders):
    totals = orders.aggregate(revenue=Sum('total'), count=Count('id'), avg=Avg('total'))
    items = OrderItem.objects.filter(order__in=orders)
    labels = dict(Order.PAYMENT_CHOICES)
    return {
        'revenue': totals['revenue'] or Decimal('0'),
        'orders': totals['count'],
        'avg_ticket': totals['avg'] or Decimal('0'),
        'items_sold': items.aggregate(total=Sum('quantity'))['total'] or 0,
        'by_waiter': list(
            orders.values('waiter__username')
            .annotate(total_sales=Sum('total'), orders_count=Count('id'), avg_ticket=Avg('total'))
            .order_by('-total_sales')
        ),
        'by_day': list(
            orders.annotate(day=TruncDay('closed_at')).values('day')
            .annotate(total=Sum('total'), count=Count('id')).order_by('day')
        ),
        'by_product': list(
            items.values('product_name', 'product__icon')
            .annotate(total_qty=Sum('quantity'), total_revenue=Sum(LINE_TOTAL), orders_count=Count('order', distinct=True))
            .order_by('-total_qty', 'product_name')
        ),
        'by_payment': [
            {'method': labels.get(row['payment_method'], 'Não definido'), 'total': row['total'], 'count': row['count']}
            for row in orders.values('payment_method').annotate(total=Sum('total'), count=Count('id')).order_by('-total')
        ],
    }
