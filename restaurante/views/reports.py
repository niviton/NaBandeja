import csv

from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from ..models import AppSettings
from ..permissions import manager_required
from ..services import reports
from ..services.excel import sales_workbook
from ..services.pdf import build_sales_export_rows, render_sales_pdf

PAGE_SIZES = [15, 30, 50]


def _export_csv(rows, summary, period):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="historico_vendas.csv"'
    response.write('﻿')  # Excel reconhece UTF-8
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Pedido', 'Data', 'Hora', 'Nome', 'Tipo', 'Garcom', 'Itens', 'Valor Total', 'Pagamento'])
    for row in rows:
        writer.writerow([row['id'], row['date'], row['time'], row['name'], row['order_type'],
                         row['waiter'], row['items'], row['total'].replace('.', ','), row['payment']])
    writer.writerow([])
    writer.writerow(['Resumo por produto', period.label])
    writer.writerow(['Total de itens vendidos', summary['items_sold']])
    writer.writerow(['Produto', 'Quantidade', 'Pedidos'])
    for item in summary['by_product']:
        writer.writerow([item['product_name'], item['total_qty'], item['orders_count']])
    return response


@manager_required
def admin_reports(request):
    period = reports.resolve_period(request.GET)
    summary = reports.sales_summary(reports.paid_orders(period))
    search = (request.GET.get('history_search') or '').strip()
    history = reports.history_orders(period, search)

    export = (request.GET.get('export') or '').lower()
    if export == 'xlsx':
        content = sales_workbook(AppSettings.get_settings().store_name, period.label, summary, history)
        response = HttpResponse(content, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="vendas_{period.filter_type}_{period.start:%Y%m%d}.xlsx"'
        return response
    if export in ('csv', 'pdf'):
        rows = build_sales_export_rows(history)
        if export == 'csv':
            return _export_csv(rows, summary, period)
        pdf = render_sales_pdf(
            rows,
            store_settings=AppSettings.get_settings(),
            period_label=period.label,
            summary={'orders': summary['orders'], 'revenue': summary['revenue'], 'avg_ticket': summary['avg_ticket']},
            product_quantities=summary['by_product'],
        )
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="historico_vendas.pdf"'
        return response

    try:
        page_size = int(request.GET.get('page_size', PAGE_SIZES[0]))
    except ValueError:
        page_size = PAGE_SIZES[0]
    if page_size not in PAGE_SIZES:
        page_size = PAGE_SIZES[0]

    query = request.GET.copy()
    query.pop('page', None)
    query.pop('export', None)
    today = timezone.localdate()

    return render(request, 'restaurante/admin/reports.html', {
        'filter_type': period.filter_type,
        'selected_day': period.day,
        'selected_month': period.month,
        'selected_year': period.year,
        'selected_start_date': period.start_date,
        'selected_end_date': period.end_date,
        'period_label': period.label,
        'year_options': range(today.year - 5, today.year + 1),
        'total_revenue': summary['revenue'],
        'total_orders': summary['orders'],
        'ticket_medio': summary['avg_ticket'],
        'total_items_sold': summary['items_sold'],
        'waiter_ranking': summary['by_waiter'],
        'daily_sales': summary['by_day'],
        'top_products': summary['by_product'][:10],
        'product_quantities': summary['by_product'],
        'payment_summary': summary['by_payment'],
        'summary': summary,
        'sales_history': Paginator(history, page_size).get_page(request.GET.get('page')),
        'history_search': search,
        'history_total': history.count(),
        'page_size': page_size,
        'page_size_options': PAGE_SIZES,
        'base_query_string': query.urlencode(),
        'active_menu': 'reports',
    })
