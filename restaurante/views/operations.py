"""Gerente: mesas (e QR Codes), áreas de entrega e pedidos online/delivery."""

from django.conf import settings
from django.contrib import messages
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from ..modules import module_required
from ..models import AppSettings, DeliveryZone, Order, Table
from ..permissions import manager_required
from ..services import orders as order_service
from ..services import tables as table_service
from ..services.audit import audit
from ..services.orders import OrderError, normalize_mesa
from ..services.cash import CashError, parse_amount
from ..services.menu_qr import public_url, wifi_payload
from ..services.pix import qr_svg


def _checkbox(request, name):
    """Checkbox desmarcado não é enviado; formulários de edição mandam '<name>_sent'."""
    if f'{name}_sent' in request.POST:
        return name in request.POST
    return True


# ------------------------------------------------------------------ mesas

@manager_required
def admin_tables(request):
    return render(request, 'restaurante/admin/tables.html', {
        'tables': Table.objects.all(),
        'active_menu': 'tables',
    })


@manager_required
@require_POST
def tables_quick_create(request):
    try:
        count = max(1, min(200, int(request.POST.get('count', 0))))
        start = max(1, int(request.POST.get('start', 1)))
    except ValueError:
        messages.error(request, 'Informe números válidos.')
        return redirect('admin_tables')
    created = table_service.create_tables(count, start)
    messages.success(request, f'{created} mesa(s) criada(s).')
    return redirect('admin_tables')


@manager_required
@require_POST
def table_save(request, table_id=None):
    table = get_object_or_404(Table, pk=table_id) if table_id else Table()
    name = normalize_mesa(request.POST.get('name', table.name))
    if not name or name in ('SEM MESA', 'DELIVERY'):
        messages.error(request, 'Nome de mesa inválido.')
        return redirect('admin_tables')
    table.name = name
    table.area = request.POST.get('area', '').strip()[:40]
    try:
        table.seats = max(1, int(request.POST.get('seats') or 4))
        table.order = int(name) if name.isdigit() else int(request.POST.get('order') or 1000)
    except ValueError:
        table.seats = 4
    table.is_active = _checkbox(request, 'is_active')
    try:
        table.save()
    except IntegrityError:
        messages.error(request, f'Já existe a mesa {name}.')
        return redirect('admin_tables')
    messages.success(request, f'Mesa {name} salva.')
    return redirect('admin_tables')


@manager_required
@require_POST
@module_required('cardapio_digital')
def table_new_qr(request, table_id):
    """Gera um QR Code novo (o antigo deixa de funcionar)."""
    table = get_object_or_404(Table, pk=table_id)
    from ..models import _new_token
    table.public_token = _new_token()
    table.save(update_fields=['public_token'])
    messages.success(request, f'QR Code da mesa {table.name} renovado. Imprima de novo.')
    return redirect('admin_tables')


@manager_required
@module_required('cardapio_digital')
def tables_qr_sheet(request):
    """Folha com os QR Codes de todas as mesas, pronta para imprimir e recortar."""
    cards = [
        {'table': table, 'url': public_url(request, reverse('table_menu', args=[table.public_token]))}
        for table in Table.objects.filter(is_active=True)
    ]
    for card in cards:
        card['svg'] = qr_svg(card['url'], box_size=8, border=1)
    return render(request, 'restaurante/admin/tables_qr.html', {'cards': cards})


# ------------------------------------------------------------------ áreas de entrega

@manager_required
@module_required('delivery')
def delivery_zones(request):
    return render(request, 'restaurante/admin/delivery_zones.html', {
        'zones': DeliveryZone.objects.all(),
        'active_menu': 'online',
    })


@manager_required
@require_POST
@module_required('delivery')
def delivery_zone_save(request, zone_id=None):
    zone = get_object_or_404(DeliveryZone, pk=zone_id) if zone_id else DeliveryZone()
    zone.name = request.POST.get('name', '').strip()[:80]
    if not zone.name:
        messages.error(request, 'Informe o bairro.')
        return redirect('delivery_zones')
    try:
        zone.fee = parse_amount(request.POST.get('fee'))  # aceita 0 (entrega grátis)
    except CashError as exc:
        messages.error(request, str(exc))
        return redirect('delivery_zones')
    zone.is_active = _checkbox(request, 'is_active')
    try:
        zone.save()
    except IntegrityError:
        messages.error(request, f'O bairro {zone.name} já existe.')
        return redirect('delivery_zones')
    messages.success(request, f'{zone.name} salvo.')
    return redirect('delivery_zones')


@manager_required
@require_POST
@module_required('delivery')
def delivery_zone_delete(request, zone_id):
    zone = get_object_or_404(DeliveryZone, pk=zone_id)
    zone.delete()
    messages.success(request, f'{zone.name} removido.')
    return redirect('delivery_zones')


# ------------------------------------------------------------------ pedidos online e delivery

@manager_required
def admin_online_orders(request):
    return render(request, 'restaurante/admin/online.html', {
        'pending': table_service.pending_online_orders(),
        'deliveries': Order.objects.filter(order_type='delivery', status__in=Order.ACTIVE_STATUSES)
            .prefetch_related('items').order_by('created_at'),
        'online_url': request.build_absolute_uri(reverse('online_order')),
        'active_menu': 'online',
    })


@manager_required
@require_POST
@module_required('online')
def online_order_decide(request, order_id, decision):
    order = get_object_or_404(Order, pk=order_id)
    try:
        if decision == 'aceitar':
            order_service.accept_pending(order, request.user)
            messages.success(request, f'Pedido #{order.id} aceito e enviado para a cozinha.')
        else:
            order_service.reject_pending(order, request.user)
            messages.warning(request, f'Pedido #{order.id} recusado.')
    except OrderError as exc:
        messages.error(request, str(exc))
    else:
        audit(request, f'online.{decision}', f'Pedido online #{order.id}: {decision}.', order)
    return redirect('admin_online_orders')


@manager_required
@module_required('cardapio_digital')
def menu_qr_sheet(request):
    """Cartões com o QR do cardápio (e do Wi-Fi) para o suporte de molhos."""
    store = AppSettings.get_settings()
    try:
        copies = max(1, min(60, int(request.GET.get('copias', 6))))
    except ValueError:
        copies = 6
    menu_url = public_url(request, reverse('public_menu'))
    wifi = wifi_payload(store.wifi_ssid, store.wifi_password)
    return render(request, 'restaurante/admin/menu_qr.html', {
        'store': store,
        'menu_url': menu_url,
        'menu_svg': qr_svg(menu_url, box_size=8, border=1),
        'wifi_svg': qr_svg(wifi, box_size=8, border=1) if wifi else '',
        'copies': range(copies),
        'copies_count': copies,
        'using_public_base': bool(settings.PUBLIC_BASE_URL),
    })
