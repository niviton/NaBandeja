from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, FileResponse, Http404
from django.views.decorators.http import require_POST
from django.conf import settings
from django.views.decorators.cache import never_cache
from django.db.models import Sum, Count, Avg, F
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth
from django.core.paginator import Paginator
from django.db import transaction
from django.core.exceptions import PermissionDenied
from django.core.validators import validate_slug
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from datetime import timedelta, date, datetime, time
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode
import io
import csv
import json
import socket
import unicodedata

from .models import (
    User,
    Category,
    Product,
    Order,
    OrderItem,
    AppSettings,
    Ingredient,
    ProductIngredient,
    AuditLog,
    IngredientStockMovement,
    CashSession,
    Additional,
    ProductAdditional,
    OrderItemAdditional,
)
from .services.pix import pix_for_order, pix_preview
from .forms import (
    LoginForm, UserForm, CategoryForm, ProductForm, 
    OrderForm, DeliveryOrderForm, PaymentForm, AppSettingsForm, IngredientForm
)


def enrich_delivery_order_display(order):
    """Extrai plataforma de delivery das observações para exibição em badge."""
    order.platform_name = ''
    order.display_observacoes = order.observacoes

    if order.order_type != 'delivery' or not order.observacoes:
        return

    prefix = 'Plataforma:'
    raw_observacoes = order.observacoes.strip()
    if not raw_observacoes.startswith(prefix):
        return

    after_prefix = raw_observacoes[len(prefix):].strip()
    if '|' in after_prefix:
        platform, remaining_obs = after_prefix.split('|', 1)
        order.platform_name = platform.strip()
        order.display_observacoes = remaining_obs.strip()
    else:
        order.platform_name = after_prefix.strip()
        order.display_observacoes = ''


def get_client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def audit_event(request, action, description='', model_name='', object_id='', metadata=None):
    AuditLog.objects.create(
        user=request.user if request.user.is_authenticated else None,
        action=action,
        model_name=model_name or '',
        object_id=str(object_id or ''),
        description=description or '',
        metadata=metadata or {},
        ip_address=get_client_ip(request),
    )


def log_ingredient_movement(ingredient, movement_type, quantity, quantity_before, quantity_after, user=None, reason=''):
    IngredientStockMovement.objects.create(
        ingredient=ingredient,
        movement_type=movement_type,
        quantity=Decimal(str(quantity)),
        quantity_before=Decimal(str(quantity_before)),
        quantity_after=Decimal(str(quantity_after)),
        reason=reason or '',
        created_by=user if user and user.is_authenticated else None,
    )


def _sanitize_pdf_text(value):
    text = str(value or '')
    normalized = []
    for char in text:
        try:
            char.encode('cp1252')
            normalized.append(char)
            continue
        except UnicodeEncodeError:
            pass

        fallback = unicodedata.normalize('NFKD', char).encode('ascii', 'ignore').decode('ascii')
        if fallback:
            normalized.append(fallback)

    return ''.join(normalized)


def _escape_pdf_text(value):
    text = _sanitize_pdf_text(value)
    return text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def _render_simple_pdf(lines, title='Relatorio de Vendas'):
    """Gera um PDF simples sem dependencias externas para listagens em texto."""
    page_width = 595
    page_height = 842
    margin_left = 36
    margin_top = 36
    line_height = 14
    max_lines_per_page = 52

    prepared_lines = [title, ''] + [str(line) for line in lines]
    pages_lines = [
        prepared_lines[i:i + max_lines_per_page]
        for i in range(0, len(prepared_lines), max_lines_per_page)
    ] or [[title]]

    objects = []

    # 1: Catalog
    objects.append('<< /Type /Catalog /Pages 2 0 R >>')

    # 2: Pages (children preenchido depois)
    objects.append('')

    page_object_ids = []
    content_object_ids = []
    next_object_id = 3

    for _ in pages_lines:
        page_object_ids.append(next_object_id)
        next_object_id += 1
        content_object_ids.append(next_object_id)
        next_object_id += 1

    font_object_id = next_object_id

    for page_idx, page_lines in enumerate(pages_lines):
        page_obj = page_object_ids[page_idx]
        content_obj = content_object_ids[page_idx]

        objects.extend(['', ''])

        y_start = page_height - margin_top
        stream_commands = ['BT', f'/F1 10 Tf', f'{margin_left} {y_start} Td']

        for line in page_lines:
            escaped = _escape_pdf_text(line)
            stream_commands.append(f'({escaped}) Tj')
            stream_commands.append(f'0 -{line_height} Td')

        page_no = page_idx + 1
        stream_commands.append(f'(Pagina {page_no}/{len(pages_lines)}) Tj')
        stream_commands.append('ET')

        stream_data = '\n'.join(stream_commands)
        stream_bytes = stream_data.encode('latin-1', 'replace')

        objects[page_obj - 1] = (
            f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width} {page_height}] '
            f'/Resources << /Font << /F1 {font_object_id} 0 R >> >> /Contents {content_obj} 0 R >>'
        )
        objects[content_obj - 1] = (
            f'<< /Length {len(stream_bytes)} >>\nstream\n{stream_data}\nendstream'
        )

    kids = ' '.join(f'{obj_id} 0 R' for obj_id in page_object_ids)
    objects[1] = f'<< /Type /Pages /Kids [{kids}] /Count {len(page_object_ids)} >>'

    # Fonte Helvetica
    objects.append('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>')

    pdf_bytes = bytearray(b'%PDF-1.4\n')
    offsets = [0]

    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(pdf_bytes))
        obj_bytes = obj.encode('latin-1', 'replace')
        pdf_bytes.extend(f'{idx} 0 obj\n'.encode('ascii'))
        pdf_bytes.extend(obj_bytes)
        pdf_bytes.extend(b'\nendobj\n')

    xref_pos = len(pdf_bytes)
    pdf_bytes.extend(f'xref\n0 {len(objects) + 1}\n'.encode('ascii'))
    pdf_bytes.extend(b'0000000000 65535 f \n')
    for offset in offsets[1:]:
        pdf_bytes.extend(f'{offset:010d} 00000 n \n'.encode('ascii'))

    pdf_bytes.extend(
        (
            f'trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n'
            f'startxref\n{xref_pos}\n%%EOF'
        ).encode('ascii')
    )
    return bytes(pdf_bytes)


def _hex_to_pdf_rgb(color_hex, fallback=(0.15, 0.15, 0.15)):
    raw = str(color_hex or '').strip().lstrip('#')
    if len(raw) != 6:
        return fallback
    try:
        r = int(raw[0:2], 16) / 255
        g = int(raw[2:4], 16) / 255
        b = int(raw[4:6], 16) / 255
    except ValueError:
        return fallback
    return (r, g, b)


def _truncate_pdf(value, max_len):
    text = _sanitize_pdf_text(value)
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + '...'


def _prepare_logo_jpeg(store_settings):
    logo_field = getattr(store_settings, 'logo', None)
    if not logo_field:
        return None

    try:
        logo_path = logo_field.path
    except Exception:
        return None

    try:
        from PIL import Image
    except Exception:
        return None

    try:
        with Image.open(logo_path) as image:
            image = image.convert('RGBA')
            background = Image.new('RGBA', image.size, (255, 255, 255, 255))
            image = Image.alpha_composite(background, image).convert('RGB')
            image.thumbnail((220, 120), Image.Resampling.LANCZOS)

            output = io.BytesIO()
            image.save(output, format='JPEG', quality=90)
            jpeg_bytes = output.getvalue()
            width, height = image.size
            return {
                'bytes': jpeg_bytes,
                'width': width,
                'height': height,
            }
    except Exception:
        return None


def _render_professional_sales_pdf(export_rows, store_settings, period_label, summary, product_quantities=None):
    """Gera PDF profissional de vendas com identidade da loja e tabela paginada."""
    page_width = 595
    page_height = 842
    margin_left = 32
    margin_right = 32
    margin_bottom = 32
    content_width = page_width - margin_left - margin_right

    primary_r, primary_g, primary_b = _hex_to_pdf_rgb(
        getattr(store_settings, 'primary_color', '#a44a2f'),
        fallback=(0.64, 0.29, 0.18),
    )

    logo_info = _prepare_logo_jpeg(store_settings)

    def esc(value):
        return _escape_pdf_text(value)

    def text_cmd(commands, x, y, value, font='F1', size=9, color=(0.12, 0.12, 0.12)):
        r, g, b = color
        commands.append(
            f'{r:.3f} {g:.3f} {b:.3f} rg BT /{font} {size} Tf {x:.2f} {y:.2f} Td ({esc(value)}) Tj ET'
        )

    def rect_fill(commands, x, y, w, h, color):
        r, g, b = color
        commands.append(f'{r:.3f} {g:.3f} {b:.3f} rg')
        commands.append(f'{x:.2f} {y:.2f} {w:.2f} {h:.2f} re f')

    def line_stroke(commands, x1, y1, x2, y2, width=0.6, color=(0.8, 0.8, 0.8)):
        r, g, b = color
        commands.append(f'{r:.3f} {g:.3f} {b:.3f} RG')
        commands.append(f'{width:.2f} w')
        commands.append(f'{x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S')

    table_cols = [
        ('Data/Hora', 70, 16),
        ('Cliente', 100, 24),
        ('Tipo', 52, 14),
        ('Garcom', 60, 14),
        ('Pagto', 50, 12),
        ('Itens', 110, 30),
        ('Total', 53, 12),
    ]

    pages_commands = []
    current_commands = []
    y_cursor = page_height - 32

    def draw_table_header(commands, y_top):
        rect_fill(commands, margin_left, y_top - 18, content_width, 18, (0.95, 0.96, 0.97))
        x_cursor = margin_left + 6
        for header, col_width, _ in table_cols:
            text_cmd(commands, x_cursor, y_top - 13, header, font='F2', size=8)
            x_cursor += col_width
        line_stroke(commands, margin_left, y_top - 18, margin_left + content_width, y_top - 18, width=0.7, color=(0.85, 0.85, 0.85))

    def start_page(page_index):
        commands = []
        header_y = page_height - 86

        rect_fill(commands, margin_left, header_y, content_width, 54, (0.98, 0.97, 0.95))
        line_stroke(commands, margin_left, header_y, margin_left + content_width, header_y, width=1.1, color=(primary_r, primary_g, primary_b))

        text_start_x = margin_left + 10
        if logo_info:
            max_logo_w = 110
            max_logo_h = 44  # header has 54pt; leave 5pt padding top and bottom
            scale = min(max_logo_w / max(logo_info['width'], 1), max_logo_h / max(logo_info['height'], 1))
            logo_draw_w = logo_info['width'] * scale
            logo_draw_h = logo_info['height'] * scale
            logo_x = margin_left + 10
            logo_y = header_y + (54 - logo_draw_h) / 2
            commands.append(
                f'q {logo_draw_w:.2f} 0 0 {logo_draw_h:.2f} {logo_x:.2f} {logo_y:.2f} cm /Im1 Do Q'
            )
            text_start_x = logo_x + logo_draw_w + 12

        text_cmd(commands, text_start_x, header_y + 33, getattr(store_settings, 'store_name', 'Loja'), font='F2', size=13)
        text_cmd(commands, text_start_x, header_y + 18, getattr(store_settings, 'slogan', ''), font='F1', size=8)

        contact_parts = [
            part for part in [
                getattr(store_settings, 'phone', ''),
                getattr(store_settings, 'city', ''),
                getattr(store_settings, 'cnpj', ''),
            ] if part
        ]
        contact_text = ' | '.join(contact_parts) if contact_parts else 'Relatorio gerado pelo sistema'
        text_cmd(commands, margin_left + 10, header_y - 16, 'Relatorio de Vendas', font='F2', size=12)
        text_cmd(commands, margin_left + 10, header_y - 30, f'Periodo: {period_label}', font='F1', size=9)
        text_cmd(commands, margin_left + 10, header_y - 44, contact_text, font='F1', size=8)

        summary_text = (
            f"Pedidos: {summary['orders']}  |  Faturamento: R$ {summary['revenue']:.2f}"
            f"  |  Ticket Medio: R$ {summary['avg_ticket']:.2f}"
        )
        text_cmd(commands, margin_left + 10, header_y - 58, summary_text, font='F1', size=8)

        table_start_y = header_y - 82
        draw_table_header(commands, table_start_y)

        return commands, table_start_y - 24

    current_commands, y_cursor = start_page(1)

    for row in export_rows:
        if y_cursor < margin_bottom + 26:
            pages_commands.append(current_commands)
            current_commands, y_cursor = start_page(len(pages_commands) + 1)

        x_cursor = margin_left + 6
        row_values = [
            _truncate_pdf(f"{row['date']} {row['time']}", table_cols[0][2]),
            _truncate_pdf(row['name'], table_cols[1][2]),
            _truncate_pdf(row['order_type'], table_cols[2][2]),
            _truncate_pdf(row['waiter'], table_cols[3][2]),
            _truncate_pdf(row['payment'], table_cols[4][2]),
            _truncate_pdf(row['items'], table_cols[5][2]),
            _truncate_pdf(f"R$ {row['total']}", table_cols[6][2]),
        ]

        for idx, cell_value in enumerate(row_values):
            font_name = 'F2' if idx == 6 else 'F1'
            text_cmd(current_commands, x_cursor, y_cursor, cell_value, font=font_name, size=8)
            x_cursor += table_cols[idx][1]

        line_stroke(
            current_commands,
            margin_left,
            y_cursor - 6,
            margin_left + content_width,
            y_cursor - 6,
            width=0.45,
            color=(0.90, 0.90, 0.90),
        )
        y_cursor -= 16

    # Resumo de quantidade por produto no fim do relatório
    product_quantities = list(product_quantities or [])
    if product_quantities:
        if y_cursor < margin_bottom + 70:
            pages_commands.append(current_commands)
            current_commands, y_cursor = start_page(len(pages_commands) + 1)

        section_title_y = y_cursor - 6
        text_cmd(current_commands, margin_left + 2, section_title_y, 'Quantidade Vendida Por Produto', font='F2', size=10)
        y_cursor = section_title_y - 18

        qty_cols = [
            ('Produto', 300, 40),
            ('Qtd.', 80, 10),
            ('Pedidos', 80, 10),
        ]

        rect_fill(current_commands, margin_left, y_cursor - 12, 460, 14, (0.95, 0.96, 0.97))
        qty_x = margin_left + 6
        for header, col_width, _ in qty_cols:
            text_cmd(current_commands, qty_x, y_cursor - 8, header, font='F2', size=8)
            qty_x += col_width
        y_cursor -= 22

        for item in product_quantities:
            if y_cursor < margin_bottom + 20:
                pages_commands.append(current_commands)
                current_commands, y_cursor = start_page(len(pages_commands) + 1)
                text_cmd(current_commands, margin_left + 2, y_cursor - 4, 'Quantidade Vendida Por Produto (continuação)', font='F2', size=10)
                y_cursor -= 18
                rect_fill(current_commands, margin_left, y_cursor - 12, 460, 14, (0.95, 0.96, 0.97))
                qty_x = margin_left + 6
                for header, col_width, _ in qty_cols:
                    text_cmd(current_commands, qty_x, y_cursor - 8, header, font='F2', size=8)
                    qty_x += col_width
                y_cursor -= 22

            row_product = _truncate_pdf(item.get('product__name') or '-', qty_cols[0][2])
            row_qty = str(item.get('total_qty') or 0)
            row_orders = str(item.get('orders_count') or 0)

            qty_x = margin_left + 6
            text_cmd(current_commands, qty_x, y_cursor, row_product, font='F1', size=8)
            qty_x += qty_cols[0][1]
            text_cmd(current_commands, qty_x, y_cursor, row_qty, font='F2', size=8)
            qty_x += qty_cols[1][1]
            text_cmd(current_commands, qty_x, y_cursor, row_orders, font='F1', size=8)

            line_stroke(
                current_commands,
                margin_left,
                y_cursor - 5,
                margin_left + 460,
                y_cursor - 5,
                width=0.4,
                color=(0.90, 0.90, 0.90),
            )
            y_cursor -= 14

    pages_commands.append(current_commands)

    objects = []
    objects.append('<< /Type /Catalog /Pages 2 0 R >>')
    objects.append('')

    page_object_ids = []
    content_object_ids = []
    next_object_id = 3

    for _ in pages_commands:
        page_object_ids.append(next_object_id)
        next_object_id += 1
        content_object_ids.append(next_object_id)
        next_object_id += 1

    font_regular_id = next_object_id
    next_object_id += 1
    font_bold_id = next_object_id
    next_object_id += 1

    image_object_id = None
    if logo_info:
        image_object_id = next_object_id
        next_object_id += 1

    for page_idx, commands in enumerate(pages_commands):
        page_obj = page_object_ids[page_idx]
        content_obj = content_object_ids[page_idx]
        objects.extend(['', ''])

        footer_text = f'Pagina {page_idx + 1}/{len(pages_commands)} - Emitido em {timezone.localtime().strftime("%d/%m/%Y %H:%M")}'
        text_cmd(commands, margin_left + 4, 16, footer_text, font='F1', size=7)

        stream_data = '\n'.join(commands)
        stream_bytes = stream_data.encode('latin-1', 'replace')

        xobject_ref = ''
        if image_object_id:
            xobject_ref = f' /XObject << /Im1 {image_object_id} 0 R >>'

        objects[page_obj - 1] = (
            f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width} {page_height}] '
            f'/Resources << /Font << /F1 {font_regular_id} 0 R /F2 {font_bold_id} 0 R >>{xobject_ref} >> '
            f'/Contents {content_obj} 0 R >>'
        )
        objects[content_obj - 1] = f'<< /Length {len(stream_bytes)} >>\nstream\n{stream_data}\nendstream'

    kids = ' '.join(f'{obj_id} 0 R' for obj_id in page_object_ids)
    objects[1] = f'<< /Type /Pages /Kids [{kids}] /Count {len(page_object_ids)} >>'

    objects.append('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>')
    objects.append('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>')

    if logo_info and image_object_id:
        img_bytes = logo_info['bytes']
        img_stream = (
            f'<< /Type /XObject /Subtype /Image /Width {logo_info["width"]} /Height {logo_info["height"]} '
            f'/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length {len(img_bytes)} >>\nstream\n'
        ).encode('latin-1', 'replace') + img_bytes + b'\nendstream'
        objects.append(img_stream)

    pdf_bytes = bytearray(b'%PDF-1.4\n')
    offsets = [0]

    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(pdf_bytes))
        pdf_bytes.extend(f'{idx} 0 obj\n'.encode('ascii'))
        if isinstance(obj, bytes):
            pdf_bytes.extend(obj)
        else:
            pdf_bytes.extend(str(obj).encode('latin-1', 'replace'))
        pdf_bytes.extend(b'\nendobj\n')

    xref_pos = len(pdf_bytes)
    pdf_bytes.extend(f'xref\n0 {len(objects) + 1}\n'.encode('ascii'))
    pdf_bytes.extend(b'0000000000 65535 f \n')
    for offset in offsets[1:]:
        pdf_bytes.extend(f'{offset:010d} 00000 n \n'.encode('ascii'))

    pdf_bytes.extend(
        (
            f'trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n'
            f'startxref\n{xref_pos}\n%%EOF'
        ).encode('ascii')
    )
    return bytes(pdf_bytes)


def _build_sales_export_rows(orders_qs):
    rows = []
    for order in orders_qs:
        if order.cliente:
            display_name = order.cliente
        elif order.order_type == 'delivery':
            display_name = 'Cliente delivery'
        else:
            display_name = f'Mesa {order.mesa}'

        order_items = [
            f"{item.quantity}x {item.product.name} (R$ {item.subtotal:.2f})"
            for item in order.items.all()
        ]

        rows.append({
            'id': order.id,
            'date': timezone.localtime(order.created_at).strftime('%d/%m/%Y'),
            'time': timezone.localtime(order.created_at).strftime('%H:%M'),
            'name': display_name,
            'order_type': 'Delivery' if order.order_type == 'delivery' else f'Mesa {order.mesa}',
            'waiter': order.waiter.username if order.waiter else '-',
            'items': ' | '.join(order_items),
            'total': f"{order.total:.2f}",
            'payment': order.get_payment_method_display() if order.payment_method else '-',
        })

    return rows


def cart_qty_for_product(cart, product_id):
    for item in cart:
        if item['id'] == product_id:
            return item['qty']
    return 0


def validate_cart_ingredient_stock(cart):
    products = Product.objects.filter(id__in=[item['id'] for item in cart]).prefetch_related('recipe_items__ingredient')
    products_by_id = {product.id: product for product in products}

    for cart_item in cart:
        product = products_by_id.get(cart_item['id'])
        if not product:
            return f"Produto inválido no carrinho: ID {cart_item['id']}"
        if not product.can_make(cart_item['qty']):
            return f'Estoque insuficiente para {product.name}.'
    return None


def save_product_recipe_from_request(product, request):
    if not product.use_ingredient_stock:
        return 0

    ingredient_ids = request.POST.getlist('recipe_ingredient[]')
    quantities = request.POST.getlist('recipe_quantity[]')

    ProductIngredient.objects.filter(product=product).delete()

    recipe_rows = []
    for ingredient_id, quantity_raw in zip(ingredient_ids, quantities):
        ingredient_id = str(ingredient_id).strip()
        quantity_raw = str(quantity_raw).strip()
        if not ingredient_id or not quantity_raw:
            continue

        try:
            quantity = Decimal(quantity_raw)
        except InvalidOperation:
            continue

        if quantity <= 0:
            continue

        recipe_rows.append((int(ingredient_id), quantity))

    if not recipe_rows:
        return 0

    ingredients_map = {
        ingredient.id: ingredient
        for ingredient in Ingredient.objects.filter(id__in=[row[0] for row in recipe_rows], is_active=True)
    }

    created_ingredient_ids = set()
    for ingredient_id, quantity in recipe_rows:
        if ingredient_id in created_ingredient_ids:
            continue
        ingredient = ingredients_map.get(ingredient_id)
        if not ingredient:
            continue
        ProductIngredient.objects.create(
            product=product,
            ingredient=ingredient,
            quantity=quantity,
        )
        created_ingredient_ids.add(ingredient_id)

    return len(created_ingredient_ids)


@never_cache
def login_view(request):
    """View de login"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Bem-vindo, {user.username}!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Usuário ou senha incorretos')
    else:
        form = LoginForm()
    
    return render(request, 'restaurante/login.html', {'form': form})


def logout_view(request):
    """View de logout"""
    logout(request)
    messages.info(request, 'Você saiu do sistema.')
    return redirect('login')


@login_required
def dashboard(request):
    """Dashboard principal - redireciona baseado no role do usuário"""
    user = request.user
    if user.role == 'gerente':
        return redirect('admin_dashboard')
    elif user.role == 'cozinha':
        return redirect('kitchen_view')
    else:
        return redirect('waiter_view')


def redirect_order_entry(request):
    """Redireciona para a tela de criação de pedidos conforme o perfil."""
    if request.user.role == 'gerente':
        return redirect('admin_online_orders')
    return redirect('waiter_view')


# ============== GARÇOM VIEWS ==============

@login_required
def waiter_view(request):
    """View principal do garçom"""
    if request.user.role == 'cozinha':
        messages.error(request, 'Acesso não autorizado')
        return redirect('kitchen_view')

    categories = Category.objects.prefetch_related('products__recipe_items__ingredient').all()

    # Garantir cart_key em itens legados na sessão
    cart = request.session.get('cart', [])
    needs_save = False
    for item in cart:
        if 'cart_key' not in item:
            item['cart_key'] = str(item['id'])
            item.setdefault('additionals', [])
            item.setdefault('additionals_price', 0)
            needs_save = True
    if needs_save:
        request.session['cart'] = cart

    cart_total = sum(item['price'] * item['qty'] for item in cart)

    context = {
        'categories': categories,
        'cart': cart,
        'cart_total': cart_total,
    }
    return render(request, 'restaurante/waiter.html', context)


@login_required
def add_to_cart(request, product_id):
    """Adicionar produto ao carrinho"""
    product = get_object_or_404(Product, id=product_id)
    
    available_stock = product.available_stock
    if available_stock <= 0:
        messages.error(request, 'Produto sem estoque')
        return redirect_order_entry(request)
    
    cart = request.session.get('cart', [])
    
    # Verificar se já existe no carrinho
    for item in cart:
        if item['id'] == product_id:
            if item['qty'] >= available_stock:
                messages.error(request, 'Limite de estoque atingido')
                return redirect_order_entry(request)
            item['qty'] += 1
            request.session['cart'] = cart
            return redirect_order_entry(request)
    
    # Adicionar novo item
    cart.append({
        'id': product_id,
        'name': product.name,
        'price': float(product.price),
        'qty': 1,
        'icon': product.icon,
        'image': product.image.url if product.image else None,
    })
    request.session['cart'] = cart
    return redirect_order_entry(request)


@login_required
def remove_from_cart(request, product_id):
    """Remover produto do carrinho"""
    cart = request.session.get('cart', [])
    
    for item in cart:
        if item['id'] == product_id:
            if item['qty'] > 1:
                item['qty'] -= 1
            else:
                cart.remove(item)
            break
    
    request.session['cart'] = cart
    return redirect_order_entry(request)


@login_required
def clear_cart(request):
    """Limpar carrinho"""
    request.session['cart'] = []
    messages.info(request, 'Carrinho limpo')
    return redirect_order_entry(request)


@login_required
def submit_order(request):
    """Enviar pedido"""
    if request.method == 'POST':
        settings = AppSettings.get_settings()
        if not settings.is_store_open:
            messages.error(request, 'Loja fechada no momento. Aguarde o gerente abrir novamente.')
            return redirect_order_entry(request)

        cart = request.session.get('cart', [])
        
        if not cart:
            messages.error(request, '❌ O carrinho está vazio')
            return redirect_order_entry(request)
        
        mesa = request.POST.get('mesa', '').strip().upper()
        cliente = request.POST.get('cliente', '').strip()
        observacoes = request.POST.get('observacoes', '').strip()
        order_type = request.POST.get('order_type', 'dine-in')
        address = request.POST.get('address', '').strip()
        platform_note = ''
        
        if order_type == 'dine-in' and not mesa and not cliente:
            messages.error(request, '❌ Informe o número da mesa ou o nome do cliente')
            return redirect_order_entry(request)

        if order_type == 'dine-in' and not mesa:
            mesa = 'SEM MESA'

        if not cliente:
            cliente = 'Cliente'
        
        if order_type == 'delivery':
            mesa = 'DELIVERY'
            platform = request.POST.get('platform', 'Whatsapp')
            platform_note = f"Plataforma: {platform}"
            if not address:
                messages.error(request, '❌ Informe o endereço de entrega')
                return redirect_order_entry(request)

        if platform_note:
            observacoes = f"{platform_note} | {observacoes}" if observacoes else platform_note
        
        try:
            # Verificar se já existe pedido ativo para a mesa
            active_order = None
            if order_type == 'dine-in' and mesa != 'SEM MESA':
                active_order = Order.objects.filter(
                    mesa=mesa,
                    status__in=['cozinha', 'pronto']
                ).order_by('-updated_at', '-id').first()

            stock_error = validate_cart_ingredient_stock(cart)
            if stock_error:
                messages.error(request, f'❌ {stock_error}')
                return redirect_order_entry(request)

            product_ids = [item['id'] for item in cart]
            products_by_id = Product.objects.in_bulk(product_ids)
        
            with transaction.atomic():
                if active_order:
                # Adicionar itens ao pedido existente
                    existing_items = {
                        item.product_id: item
                        for item in active_order.items.select_related('product').all()
                    }

                    for cart_item in cart:
                        product = products_by_id.get(cart_item['id'])
                        if not product:
                            raise ValueError(f"Produto inválido: {cart_item['id']}")
                        existing_item = existing_items.get(product.id)

                        if existing_item:
                            existing_item.quantity += cart_item['qty']
                            existing_item.pending_quantity += cart_item['qty']
                            existing_item.save()
                        else:
                            OrderItem.objects.create(
                                order=active_order,
                                product=product,
                                quantity=cart_item['qty'],
                                pending_quantity=cart_item['qty'],
                                unit_price=product.price
                            )

                        product.consume_ingredients(cart_item['qty'])

                    active_order.status = 'cozinha'
                    if observacoes:
                        active_order.observacoes = (active_order.observacoes + " | " + observacoes) if active_order.observacoes else observacoes
                    active_order.calculate_total()
                    sync_order_kitchen_status(active_order)
                    messages.success(request, f'✅ Itens adicionados ao pedido da mesa {mesa}.')
                else:
                # Criar novo pedido
                    total = sum(item['price'] * item['qty'] for item in cart)
                    order = Order.objects.create(
                        mesa=mesa,
                        cliente=cliente,
                        observacoes=observacoes,
                        total=total,
                        status='cozinha',
                        order_type=order_type,
                        address=address,
                        waiter=request.user
                    )

                    for cart_item in cart:
                        product = products_by_id.get(cart_item['id'])
                        if not product:
                            raise ValueError(f"Produto inválido: {cart_item['id']}")
                        order_item = OrderItem.objects.create(
                            order=order,
                            product=product,
                            quantity=cart_item['qty'],
                            pending_quantity=cart_item['qty'],
                            unit_price=product.price
                        )
                        product.consume_ingredients(cart_item['qty'])

                    messages.success(request, f'✅ Pedido #{order.id} enviado para a cozinha!')
            
            # Limpar carrinho
            request.session['cart'] = []
            return redirect_order_entry(request)
        
        except Exception as e:
            messages.error(request, f'❌ Erro ao enviar pedido: {str(e)}')
            return redirect_order_entry(request)
    
    return redirect_order_entry(request)


def redirect_by_role(request):
    """Redireciona para a tela principal conforme função do usuário."""
    if request.user.role == 'gerente':
        return redirect('admin_dashboard')
    if request.user.role == 'cozinha':
        return redirect('kitchen_view')
    return redirect('waiter_view')


def can_manage_order(user):
    return user.role != 'cozinha'


def can_access_order(user, order):
    if user.role == 'gerente':
        return True
    if user.role == 'garcom':
        return order.waiter_id == user.id
    return False


def get_order_for_user_or_403(user, order_id):
    order = get_object_or_404(Order, id=order_id)
    if not can_access_order(user, order):
        raise PermissionDenied('Você não tem permissão para acessar este pedido.')
    return order


def is_ajax_request(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def order_snapshot(order):
    order_items = order.items.select_related('product').all().order_by('id')
    return {
        'id': order.id,
        'mesa': order.mesa,
        'cliente': order.cliente,
        'observacoes': order.observacoes or '',
        'total': float(order.total),
        'items': [
            {
                'id': item.id,
                'product_name': item.product.name,
                'product_icon': item.product.icon or '🍔',
                'quantity': item.quantity,
                'pending_quantity': item.pending_quantity,
                'unit_price': float(item.unit_price),
                'subtotal': float(item.subtotal),
            }
            for item in order_items
        ]
    }


def sync_order_kitchen_status(order):
    """Mantém status baseado no que ainda falta preparar na cozinha."""
    if order.status in ['finalizado', 'cancelado']:
        return

    # Se o pedido ficou sem nenhum item, cancela automaticamente
    if not order.items.exists():
        order.status = 'cancelado'
        order.save(update_fields=['status', 'updated_at'])
        return

    has_pending_items = order.items.filter(pending_quantity__gt=0).exists()
    target_status = 'cozinha' if has_pending_items else 'pronto'

    if order.status != target_status:
        order.status = target_status
        order.save(update_fields=['status', 'updated_at'])


@login_required
def manage_order(request, order_id):
    """Tela para gerente/garçom alterar pedido ativo e adicionar itens."""
    if not can_manage_order(request.user):
        messages.error(request, 'Acesso não autorizado')
        return redirect_by_role(request)

    order = get_order_for_user_or_403(request.user, order_id)
    order = Order.objects.prefetch_related('items__product').get(id=order.id)

    if order.status in ['finalizado', 'cancelado']:
        messages.error(request, 'Não é possível alterar um pedido finalizado/cancelado.')
        return redirect_by_role(request)

    categories = Category.objects.prefetch_related('products__recipe_items__ingredient').all()
    context = {
        'order': order,
        'categories': categories,
    }
    return render(request, 'restaurante/manage_order.html', context)


@login_required
@require_POST
def update_order_info(request, order_id):
    """Atualiza dados principais do pedido ativo."""
    if not can_manage_order(request.user):
        messages.error(request, 'Acesso não autorizado')
        return redirect_by_role(request)

    order = get_order_for_user_or_403(request.user, order_id)
    if order.status in ['finalizado', 'cancelado']:
        messages.error(request, 'Pedido não pode mais ser alterado.')
        return redirect_by_role(request)

    mesa = request.POST.get('mesa', '').strip()
    cliente = request.POST.get('cliente', '').strip() or 'Cliente'
    observacoes = request.POST.get('observacoes', '').strip()

    if order.order_type == 'dine-in' and not mesa:
        if is_ajax_request(request):
            return JsonResponse({'success': False, 'message': 'Informe o número da mesa.'}, status=400)
        messages.error(request, 'Informe o número da mesa.')
        return redirect('manage_order', order_id=order.id)

    if order.order_type == 'delivery':
        mesa = 'DELIVERY'

    order.mesa = mesa
    order.cliente = cliente
    order.observacoes = observacoes
    order.save(update_fields=['mesa', 'cliente', 'observacoes', 'updated_at'])
    sync_order_kitchen_status(order)

    if is_ajax_request(request):
        return JsonResponse({
            'success': True,
            'message': 'Dados do pedido atualizados.',
            'order': order_snapshot(order)
        })

    messages.success(request, 'Dados do pedido atualizados.')
    return redirect('manage_order', order_id=order.id)


@login_required
@require_POST
def add_product_to_order(request, order_id, product_id):
    """Adiciona item ao pedido existente (mesa)."""
    if not can_manage_order(request.user):
        messages.error(request, 'Acesso não autorizado')
        return redirect_by_role(request)

    order = get_order_for_user_or_403(request.user, order_id)
    product = get_object_or_404(Product, id=product_id)

    if order.status in ['finalizado', 'cancelado']:
        if is_ajax_request(request):
            return JsonResponse({'success': False, 'message': 'Pedido não pode mais ser alterado.'}, status=400)
        messages.error(request, 'Pedido não pode mais ser alterado.')
        return redirect('manage_order', order_id=order.id)

    if product.available_stock <= 0:
        if is_ajax_request(request):
            return JsonResponse({'success': False, 'message': 'Produto sem estoque.'}, status=400)
        messages.error(request, 'Produto sem estoque.')
        return redirect('manage_order', order_id=order.id)

    order_item = order.items.filter(product=product).first()
    if order_item:
        order_item.quantity += 1
        order_item.pending_quantity += 1
        order_item.save()
    else:
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=1,
            pending_quantity=1,
            unit_price=product.price
        )

    product.consume_ingredients(1)
    order.calculate_total()
    sync_order_kitchen_status(order)

    if is_ajax_request(request):
        order.refresh_from_db()
        return JsonResponse({
            'success': True,
            'message': f'{product.name} adicionado ao pedido.',
            'order': order_snapshot(order)
        })

    messages.success(request, f'{product.name} adicionado ao pedido.')
    return redirect('manage_order', order_id=order.id)


@login_required
@require_POST
def change_order_item_qty(request, order_id, item_id):
    """Incrementa/decrementa/remove item de um pedido ativo."""
    if not can_manage_order(request.user):
        messages.error(request, 'Acesso não autorizado')
        return redirect_by_role(request)

    order = get_order_for_user_or_403(request.user, order_id)
    order_item = get_object_or_404(OrderItem, id=item_id, order=order)

    if order.status in ['finalizado', 'cancelado']:
        if is_ajax_request(request):
            return JsonResponse({'success': False, 'message': 'Pedido não pode mais ser alterado.'}, status=400)
        messages.error(request, 'Pedido não pode mais ser alterado.')
        return redirect('manage_order', order_id=order.id)

    action = request.POST.get('action')
    product = order_item.product

    if action == 'add':
        if product.available_stock <= 0:
            if is_ajax_request(request):
                return JsonResponse({'success': False, 'message': 'Produto sem estoque.'}, status=400)
            messages.error(request, 'Produto sem estoque.')
            return redirect('manage_order', order_id=order.id)
        order_item.quantity += 1
        order_item.pending_quantity += 1
        product.consume_ingredients(1)
        order_item.save(update_fields=['quantity', 'pending_quantity'])

    elif action == 'remove':
        order_item.quantity -= 1
        if order_item.pending_quantity > 0:
            order_item.pending_quantity -= 1
            # Reverte estoque apenas da parte que ainda nao foi produzida.
            product.restore_ingredients(1)
        if order_item.quantity <= 0:
            order_item.delete()
        else:
            order_item.save(update_fields=['quantity', 'pending_quantity'])

    elif action == 'delete':
        pending_to_cancel = order_item.pending_quantity
        if pending_to_cancel > 0:
            # Reverte apenas unidades que ainda estavam pendentes.
            product.restore_ingredients(pending_to_cancel)
        order_item.delete()

    else:
        if is_ajax_request(request):
            return JsonResponse({'success': False, 'message': 'Ação inválida.'}, status=400)
        messages.error(request, 'Ação inválida.')
        return redirect('manage_order', order_id=order.id)

    order.calculate_total()
    sync_order_kitchen_status(order)

    if is_ajax_request(request):
        order.refresh_from_db()
        return JsonResponse({
            'success': True,
            'message': 'Pedido atualizado.',
            'order': order_snapshot(order)
        })

    messages.success(request, 'Pedido atualizado.')
    return redirect('manage_order', order_id=order.id)


# ============== COZINHA VIEWS ==============

@login_required
def kitchen_view(request):
    """View da cozinha"""
    if request.user.role not in ['cozinha', 'gerente']:
        messages.error(request, 'Acesso não autorizado')
        return redirect('dashboard')

    now = timezone.now()
    threshold_time = now - timedelta(minutes=15)  # Pedidos com mais de 15 min
    
    orders_cozinha_raw = Order.objects.filter(status='cozinha').prefetch_related('items__product').order_by('created_at')
    orders_pronto = Order.objects.filter(status='pronto').prefetch_related('items__product').order_by('created_at')

    orders_cozinha = []
    
    # Adicionar flag de atrasado para cada pedido
    for order in orders_cozinha_raw:
        order.pending_items = [item for item in order.items.all() if item.pending_quantity > 0]
        if not order.pending_items:
            continue
        # Para pedidos alterados/reenviados, o tempo deve contar da última atualização enviada para cozinha.
        order.kitchen_reference_time = order.updated_at or order.created_at
        order.is_late = order.kitchen_reference_time < threshold_time
        order.wait_minutes = int((now - order.kitchen_reference_time).total_seconds() // 60)
        enrich_delivery_order_display(order)
        orders_cozinha.append(order)
    
    for order in orders_pronto:
        order.wait_minutes = int((now - order.created_at).total_seconds() // 60)
        enrich_delivery_order_display(order)
    
    context = {
        'orders_cozinha': orders_cozinha,
        'orders_pronto': orders_pronto,
        'now': now,
    }
    return render(request, 'restaurante/kitchen.html', context)


@login_required
@require_POST
def mark_order_ready(request, order_id):
    """Marcar pedido como pronto"""
    if request.user.role not in ['cozinha', 'gerente']:
        messages.error(request, 'Acesso não autorizado')
        return redirect('dashboard')

    order = get_object_or_404(Order, id=order_id)
    order.items.update(pending_quantity=0)
    order.status = 'pronto'
    order.save()
    messages.success(request, f'Pedido #{order.id} marcado como pronto!')
    return redirect('kitchen_view')


# ============== ADMIN VIEWS ==============

@login_required
def admin_dashboard(request):
    """Dashboard do gerente"""
    if request.user.role != 'gerente':
        messages.error(request, 'Acesso não autorizado')
        return redirect('dashboard')
    
    local_now = timezone.localtime()
    day_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    
    # Estatísticas do dia
    orders_today = Order.objects.filter(
        created_at__gte=day_start,
        created_at__lt=day_end,
        status='finalizado'
    )
    
    total_today = orders_today.aggregate(total=Sum('total'))['total'] or 0
    orders_count_today = orders_today.count()
    avg_ticket = orders_today.aggregate(avg=Avg('total'))['avg'] or 0
    
    # Pedidos ativos
    active_orders = Order.objects.filter(
        status__in=['cozinha', 'pronto']
    ).prefetch_related('items__product').order_by('-created_at')

    for order in active_orders:
        enrich_delivery_order_display(order)
    
    # Mesas ativas (pedidos não finalizados, excluindo delivery)
    mesas_ativas = Order.objects.filter(
        status__in=['cozinha', 'pronto'],
        order_type='dine-in'
    ).values('mesa').distinct().count()
    
    # Alertas de estoque baixo (ingredientes abaixo do limite configurado)
    low_stock_ingredients = Ingredient.objects.filter(
        low_stock_alert__gt=0,
        stock_quantity__lte=F('low_stock_alert'),
        is_active=True
    ).order_by('stock_quantity')[:5]
    
    # Top 5 produtos
    top_products = OrderItem.objects.filter(
        order__created_at__gte=day_start,
        order__created_at__lt=day_end,
        order__status='finalizado'
    ).values('product__name').annotate(
        total_qty=Sum('quantity')
    ).order_by('-total_qty')[:5]

    context = {
        'vendas_hoje': total_today,
        'pedidos_hoje': orders_count_today,
        'ticket_medio': avg_ticket,
        'pedidos_ativos': active_orders.count(),
        'active_orders': active_orders,
        'top_products': top_products,
        'mesas_ativas': mesas_ativas,
        'low_stock_ingredients': low_stock_ingredients,
        'active_menu': 'dashboard',
    }
    return render(request, 'restaurante/admin/dashboard.html', context)


@login_required
def admin_reports(request):
    """Relatórios"""
    if request.user.role != 'gerente':
        return redirect('dashboard')

    today = timezone.localdate()
    filter_type = request.GET.get('filter', 'day')

    selected_day = request.GET.get('day') or today.strftime('%Y-%m-%d')
    selected_month = request.GET.get('month') or today.strftime('%Y-%m')
    selected_year = request.GET.get('year') or str(today.year)
    selected_start_date = (request.GET.get('start_date') or '').strip()
    selected_end_date = (request.GET.get('end_date') or '').strip()
    history_search = (request.GET.get('history_search') or '').strip()
    export_type = (request.GET.get('export') or '').strip().lower()
    page_size_options = [15, 30, 50]
    try:
        page_size = int(request.GET.get('page_size', 15))
    except (TypeError, ValueError):
        page_size = 15
    if page_size not in page_size_options:
        page_size = 15

    # Estatisticas financeiras consideram apenas pedidos finalizados.
    orders = Order.objects.filter(status='finalizado')
    # Historico de pedidos mostra finalizados e cancelados no mesmo lugar.
    history_orders = Order.objects.filter(status__in=['finalizado', 'cancelado'])

    if filter_type == 'day':
        try:
            year, month, day = [int(part) for part in selected_day.split('-')]
            target_day = date(year, month, day)
        except (TypeError, ValueError):
            target_day = today
            selected_day = today.strftime('%Y-%m-%d')

        period_start = timezone.make_aware(datetime.combine(target_day, time.min))
        period_end = period_start + timedelta(days=1)
        orders = orders.filter(created_at__gte=period_start, created_at__lt=period_end)
        history_orders = history_orders.filter(created_at__gte=period_start, created_at__lt=period_end)

    elif filter_type == 'month':
        try:
            year, month = [int(part) for part in selected_month.split('-')]
            start_month = date(year, month, 1)
        except (TypeError, ValueError):
            start_month = date(today.year, today.month, 1)
            selected_month = today.strftime('%Y-%m')

        if start_month.month == 12:
            next_month = date(start_month.year + 1, 1, 1)
        else:
            next_month = date(start_month.year, start_month.month + 1, 1)

        period_start = timezone.make_aware(datetime.combine(start_month, time.min))
        period_end = timezone.make_aware(datetime.combine(next_month, time.min))
        orders = orders.filter(created_at__gte=period_start, created_at__lt=period_end)
        history_orders = history_orders.filter(created_at__gte=period_start, created_at__lt=period_end)

    elif filter_type == 'year':
        try:
            target_year = int(selected_year)
        except (TypeError, ValueError):
            target_year = today.year
            selected_year = str(today.year)
        start_year = date(target_year, 1, 1)
        next_year = date(target_year + 1, 1, 1)
        period_start = timezone.make_aware(datetime.combine(start_year, time.min))
        period_end = timezone.make_aware(datetime.combine(next_year, time.min))
        orders = orders.filter(created_at__gte=period_start, created_at__lt=period_end)
        history_orders = history_orders.filter(created_at__gte=period_start, created_at__lt=period_end)

    elif filter_type == 'range':
        default_start = today - timedelta(days=6)
        default_end = today

        try:
            start_date = date.fromisoformat(selected_start_date)
        except (TypeError, ValueError):
            start_date = default_start
            selected_start_date = default_start.strftime('%Y-%m-%d')

        try:
            end_date = date.fromisoformat(selected_end_date)
        except (TypeError, ValueError):
            end_date = default_end
            selected_end_date = default_end.strftime('%Y-%m-%d')

        if start_date > end_date:
            start_date, end_date = end_date, start_date
            selected_start_date = start_date.strftime('%Y-%m-%d')
            selected_end_date = end_date.strftime('%Y-%m-%d')

        period_start = timezone.make_aware(datetime.combine(start_date, time.min))
        period_end = timezone.make_aware(datetime.combine(end_date + timedelta(days=1), time.min))
        orders = orders.filter(created_at__gte=period_start, created_at__lt=period_end)
        history_orders = history_orders.filter(created_at__gte=period_start, created_at__lt=period_end)

    else:
        filter_type = 'day'
        period_start = timezone.make_aware(datetime.combine(today, time.min))
        period_end = period_start + timedelta(days=1)
        orders = orders.filter(created_at__gte=period_start, created_at__lt=period_end)
        history_orders = history_orders.filter(created_at__gte=period_start, created_at__lt=period_end)
        selected_day = today.strftime('%Y-%m-%d')
    
    # Estatísticas
    total_revenue = orders.aggregate(total=Sum('total'))['total'] or 0
    total_orders = orders.count()
    avg_ticket = orders.aggregate(avg=Avg('total'))['avg'] or 0
    
    # Vendas por garçom
    waiter_stats = orders.values('waiter__username').annotate(
        total_sales=Sum('total'),
        orders_count=Count('id'),
        avg_ticket=Avg('total')
    ).order_by('-total_sales')
    
    # Vendas por dia
    daily_sales = orders.annotate(
        day=TruncDay('created_at')
    ).values('day').annotate(
        total=Sum('total'),
        count=Count('id')
    ).order_by('day')
    
    # Produtos mais vendidos
    top_products = OrderItem.objects.filter(
        order__in=orders
    ).values('product__name', 'product__icon').annotate(
        total_qty=Sum('quantity'),
        total_revenue=Sum('quantity') * Avg('unit_price')
    ).order_by('-total_qty')[:10]

    product_quantities = OrderItem.objects.filter(
        order__in=orders
    ).values('product__name', 'product__icon').annotate(
        total_qty=Sum('quantity'),
        orders_count=Count('order', distinct=True)
    ).order_by('-total_qty', 'product__name')

    total_items_sold = OrderItem.objects.filter(
        order__in=orders
    ).aggregate(total=Sum('quantity'))['total'] or 0
    
    # Totais agrupados por tipo de pagamento (apenas finalizados)
    payment_summary = orders.values('payment_method').annotate(
        total=Sum('total'),
        count=Count('id')
    ).order_by('-total')
    
    # Formatar labels de pagamento
    payment_labels = {
        'dinheiro': 'Dinheiro',
        'pix': 'PIX',
        'credito': 'Cartão de Crédito',
        'debito': 'Cartão de Débito',
        '': 'Não definido',
    }
    
    payment_summary_formatted = []
    for payment in payment_summary:
        method = payment['payment_method'] or ''
        payment_summary_formatted.append({
            'method': payment_labels.get(method, method),
            'total': payment['total'],
            'count': payment['count'],
        })
    
    sales_history_qs = history_orders.select_related('waiter').prefetch_related('items__product').order_by('-created_at')

    if history_search:
        sales_history_qs = sales_history_qs.filter(cliente__icontains=history_search)

    if filter_type == 'day':
        try:
            period_label = date.fromisoformat(selected_day).strftime('%d/%m/%Y')
        except ValueError:
            period_label = selected_day
    elif filter_type == 'month':
        try:
            year_value, month_value = [int(part) for part in selected_month.split('-')]
            period_label = f'{month_value:02d}/{year_value}'
        except (TypeError, ValueError):
            period_label = selected_month
    elif filter_type == 'year':
        period_label = selected_year
    else:
        try:
            start_display = date.fromisoformat(selected_start_date).strftime('%d/%m/%Y')
        except ValueError:
            start_display = selected_start_date
        try:
            end_display = date.fromisoformat(selected_end_date).strftime('%d/%m/%Y')
        except ValueError:
            end_display = selected_end_date
        period_label = f'{start_display} ate {end_display}'

    if export_type in ['csv', 'pdf']:
        export_rows = _build_sales_export_rows(sales_history_qs)
        product_quantities_rows = list(product_quantities)

        if export_type == 'csv':
            response = HttpResponse(content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = 'attachment; filename="historico_vendas.csv"'
            response.write('\ufeff')

            writer = csv.writer(response)
            writer.writerow(['Pedido', 'Data', 'Hora', 'Nome', 'Tipo', 'Garcom', 'Itens', 'Valor Total', 'Pagamento'])
            for row in export_rows:
                writer.writerow([
                    row['id'],
                    row['date'],
                    row['time'],
                    row['name'],
                    row['order_type'],
                    row['waiter'],
                    row['items'],
                    row['total'],
                    row['payment'],
                ])

            writer.writerow([])
            writer.writerow(['Resumo de Quantidade por Produto'])
            writer.writerow(['Periodo', period_label])
            writer.writerow(['Total de itens vendidos', total_items_sold])
            writer.writerow(['Produto', 'Quantidade Vendida', 'Pedidos com esse item'])
            for item in product_quantities_rows:
                writer.writerow([
                    f"{item.get('product__icon') or '🍔'} {item.get('product__name') or '-'}",
                    item.get('total_qty') or 0,
                    item.get('orders_count') or 0,
                ])
            return response

        store_settings = AppSettings.get_settings()
        pdf_summary = {
            'orders': total_orders,
            'revenue': total_revenue,
            'avg_ticket': avg_ticket,
        }
        pdf_bytes = _render_professional_sales_pdf(
            export_rows,
            store_settings=store_settings,
            period_label=period_label,
            summary=pdf_summary,
            product_quantities=product_quantities_rows,
        )
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="historico_vendas.pdf"'
        return response

    paginator = Paginator(sales_history_qs, page_size)
    page_number = request.GET.get('page')
    sales_history_page = paginator.get_page(page_number)

    query_without_page = request.GET.copy()
    query_without_page.pop('page', None)
    query_without_page.pop('export', None)
    base_query_string = query_without_page.urlencode()

    context = {
        'filter_type': filter_type,
        'selected_day': selected_day,
        'selected_month': selected_month,
        'selected_year': selected_year,
        'selected_start_date': selected_start_date,
        'selected_end_date': selected_end_date,
        'year_options': range(today.year - 5, today.year + 1),
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'ticket_medio': avg_ticket,
        'waiter_ranking': waiter_stats,
        'daily_sales': list(daily_sales),
        'top_products': top_products,
        'product_quantities': product_quantities,
        'total_items_sold': total_items_sold,
        'payment_summary': payment_summary_formatted,
        'sales_history': sales_history_page,
        'history_search': history_search,
        'history_total': sales_history_qs.count(),
        'page_size': page_size,
        'page_size_options': page_size_options,
        'base_query_string': base_query_string,
        'active_menu': 'reports',
    }
    return render(request, 'restaurante/admin/reports.html', context)


@login_required
@require_POST
def open_cash_session(request):
    """Abre uma sessão de caixa (turno)."""
    if request.user.role != 'gerente':
        messages.error(request, 'Apenas gerentes podem abrir caixa.')
        return redirect('dashboard')

    if CashSession.get_open_session():
        messages.warning(request, 'Já existe um caixa aberto.')
        return redirect('admin_dashboard')

    opening_amount_raw = request.POST.get('opening_amount', '0').replace(',', '.').strip()
    notes = request.POST.get('notes', '').strip()

    try:
        opening_amount = Decimal(opening_amount_raw)
        if opening_amount < 0:
            raise ValueError()
    except Exception:
        messages.error(request, 'Valor de abertura inválido.')
        return redirect('admin_dashboard')

    cash_session = CashSession.objects.create(
        opened_by=request.user,
        opening_amount=opening_amount,
        notes=notes,
        status='open',
    )

    audit_event(
        request,
        action='cash.open',
        description=f'Caixa aberto com valor inicial de R$ {opening_amount:.2f}.',
        model_name='CashSession',
        object_id=cash_session.id,
        metadata={'opening_amount': str(opening_amount), 'notes': notes},
    )

    messages.success(request, 'Caixa aberto com sucesso!')
    return redirect('admin_dashboard')


@login_required
@require_POST
def close_cash_session(request):
    """Fecha a sessão de caixa ativa."""
    if request.user.role != 'gerente':
        messages.error(request, 'Apenas gerentes podem fechar caixa.')
        return redirect('dashboard')

    cash_session = CashSession.get_open_session()
    if not cash_session:
        messages.warning(request, 'Não há caixa aberto para fechar.')
        return redirect('admin_dashboard')

    closing_amount_raw = request.POST.get('closing_amount', '0').replace(',', '.').strip()
    notes = request.POST.get('close_notes', '').strip()

    try:
        closing_amount = Decimal(closing_amount_raw)
        if closing_amount < 0:
            raise ValueError()
    except Exception:
        messages.error(request, 'Valor de fechamento inválido.')
        return redirect('admin_dashboard')

    closed_at = timezone.now()
    period_sales = Order.objects.filter(
        status='finalizado',
        created_at__gte=cash_session.opened_at,
        created_at__lte=closed_at,
    ).aggregate(total=Sum('total'))['total'] or Decimal('0')

    expected_amount = cash_session.opening_amount + period_sales
    difference_amount = closing_amount - expected_amount

    cash_session.closing_amount = closing_amount
    cash_session.expected_amount = expected_amount
    cash_session.difference_amount = difference_amount
    cash_session.status = 'closed'
    cash_session.closed_by = request.user
    cash_session.closed_at = closed_at
    if notes:
        cash_session.notes = (cash_session.notes + '\n' + notes).strip() if cash_session.notes else notes
    cash_session.save(update_fields=['closing_amount', 'expected_amount', 'difference_amount', 'status', 'closed_by', 'closed_at', 'notes'])

    audit_event(
        request,
        action='cash.close',
        description=f'Caixa fechado com R$ {closing_amount:.2f}. Diferença: R$ {difference_amount:.2f}.',
        model_name='CashSession',
        object_id=cash_session.id,
        metadata={
            'closing_amount': str(closing_amount),
            'expected_amount': str(expected_amount),
            'difference_amount': str(difference_amount),
            'period_sales': str(period_sales),
            'notes': notes,
        },
    )

    if difference_amount == 0:
        messages.success(request, 'Caixa fechado sem diferenças.')
    else:
        messages.warning(request, f'Caixa fechado com diferença de R$ {difference_amount:.2f}.')
    return redirect('admin_dashboard')


@login_required
@require_POST
def toggle_store_status(request):
    """Alterna status da loja (aberta/fechada) no painel do gerente."""
    if request.user.role != 'gerente':
        messages.error(request, 'Apenas gerentes podem alterar o status da loja.')
        return redirect('dashboard')

    settings = AppSettings.get_settings()
    settings.is_store_open = not settings.is_store_open
    settings.save(update_fields=['is_store_open'])

    audit_event(
        request,
        action='settings.store_toggle',
        description='Status da loja alterado.',
        model_name='AppSettings',
        object_id=settings.pk,
        metadata={'is_store_open': settings.is_store_open},
    )

    if settings.is_store_open:
        messages.success(request, 'Loja aberta com sucesso.')
    else:
        messages.warning(request, 'Loja fechada para novos pedidos.')

    next_url = request.POST.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('admin_dashboard')


@login_required
def admin_menu(request):
    """Gestão do cardápio"""
    if request.user.role != 'gerente':
        return redirect('dashboard')
    
    categories = Category.objects.prefetch_related('products__recipe_items__ingredient').all()
    
    context = {
        'categories': categories,
        'active_menu': 'menu',
    }
    return render(request, 'restaurante/admin/menu.html', context)


@login_required
def product_create(request):
    """Criar produto"""
    if request.user.role != 'gerente':
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                with transaction.atomic():
                    product = form.save()
                    recipe_count = save_product_recipe_from_request(product, request)
                    if product.use_ingredient_stock and recipe_count == 0:
                        raise ValueError('Defina ao menos 1 ingrediente na receita para usar estoque por ingredientes.')
                messages.success(request, 'Produto criado com sucesso!')
                return redirect('admin_menu')
            except ValueError as exc:
                messages.error(request, str(exc))
    else:
        form = ProductForm()
    
    categories = Category.objects.all()
    ingredients = Ingredient.objects.filter(is_active=True).order_by('name')
    return render(request, 'restaurante/admin/product_form.html', {'form': form, 'title': 'Novo Produto', 'active_menu': 'menu', 'categories': categories, 'ingredients': ingredients, 'recipe_items': []})


@login_required
def product_edit(request, product_id):
    """Editar produto"""
    if request.user.role != 'gerente':
        return redirect('dashboard')
    
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            try:
                with transaction.atomic():
                    product = form.save()
                    recipe_count = save_product_recipe_from_request(product, request)
                    if product.use_ingredient_stock and recipe_count == 0:
                        raise ValueError('Defina ao menos 1 ingrediente na receita para usar estoque por ingredientes.')
                messages.success(request, 'Produto atualizado!')
                return redirect('admin_menu')
            except ValueError as exc:
                messages.error(request, str(exc))
    else:
        form = ProductForm(instance=product)
    
    categories = Category.objects.all()
    ingredients = Ingredient.objects.filter(is_active=True).order_by('name')
    recipe_items = product.recipe_items.select_related('ingredient').all().order_by('ingredient__name')
    return render(request, 'restaurante/admin/product_form.html', {'form': form, 'title': 'Editar Produto', 'product': product, 'active_menu': 'menu', 'categories': categories, 'ingredients': ingredients, 'recipe_items': recipe_items})


@login_required
@require_POST
def product_delete(request, product_id):
    """Deletar produto"""
    if request.user.role != 'gerente':
        return redirect('dashboard')
    
    try:
        product = Product.objects.get(id=product_id)
        product.delete()
        messages.success(request, 'Produto removido!')
    except Product.DoesNotExist:
        messages.warning(request, 'Produto não encontrado ou já foi removido.')
    
    return redirect('admin_menu')


@login_required
def category_create(request):
    """Criar categoria"""
    if request.user.role != 'gerente':
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Categoria criada!')
            return redirect('admin_menu')
        messages.error(request, 'Não foi possível criar a categoria. Verifique os dados.')
    else:
        form = CategoryForm()
    
    return render(request, 'restaurante/admin/category_form.html', {'form': form, 'title': 'Nova Categoria', 'active_menu': 'menu'})


@login_required
def category_edit(request, category_id):
    """Editar categoria"""
    if request.user.role != 'gerente':
        return redirect('dashboard')

    category = get_object_or_404(Category, id=category_id)

    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, 'Categoria atualizada!')
            return redirect('admin_menu')
        messages.error(request, 'Não foi possível atualizar a categoria. Verifique os dados.')
    else:
        form = CategoryForm(instance=category)

    return render(
        request,
        'restaurante/admin/category_form.html',
        {'form': form, 'title': 'Editar Categoria', 'category': category, 'active_menu': 'menu'}
    )


@login_required
@require_POST
def category_delete(request, category_id):
    """Deletar categoria"""
    if request.user.role != 'gerente':
        return redirect('dashboard')

    try:
        category = Category.objects.get(id=category_id)
        category.delete()
        messages.success(request, 'Categoria removida!')
    except Category.DoesNotExist:
        messages.warning(request, 'Categoria não encontrada ou já foi removida.')
    
    return redirect('admin_menu')


@login_required
def admin_ingredients(request):
    """Gestão de ingredientes"""
    if request.user.role != 'gerente':
        return redirect('dashboard')

    ingredients = Ingredient.objects.all().order_by('name')
    context = {
        'ingredients': ingredients,
        'active_menu': 'ingredients',
    }
    return render(request, 'restaurante/admin/ingredients.html', context)


@login_required
def ingredient_create(request):
    """Criar ingrediente"""
    if request.user.role != 'gerente':
        return redirect('dashboard')

    if request.method == 'POST':
        form = IngredientForm(request.POST)
        if form.is_valid():
            ingredient = form.save()
            if ingredient.stock_quantity > 0:
                log_ingredient_movement(
                    ingredient=ingredient,
                    movement_type='entrada',
                    quantity=ingredient.stock_quantity,
                    quantity_before=Decimal('0'),
                    quantity_after=ingredient.stock_quantity,
                    user=request.user,
                    reason='Estoque inicial no cadastro do ingrediente',
                )
            audit_event(
                request,
                action='ingredient.create',
                description=f'Ingrediente "{ingredient.name}" criado.',
                model_name='Ingredient',
                object_id=ingredient.id,
                metadata={'stock_quantity': str(ingredient.stock_quantity), 'unit': ingredient.unit},
            )
            messages.success(request, 'Ingrediente criado com sucesso!')
            return redirect('admin_ingredients')
    else:
        form = IngredientForm()

    return render(request, 'restaurante/admin/ingredient_form.html', {
        'form': form,
        'title': 'Novo Ingrediente',
        'active_menu': 'ingredients',
    })


@login_required
def ingredient_edit(request, ingredient_id):
    """Editar ingrediente"""
    if request.user.role != 'gerente':
        return redirect('dashboard')

    ingredient = get_object_or_404(Ingredient, id=ingredient_id)
    if request.method == 'POST':
        previous_stock = ingredient.stock_quantity
        form = IngredientForm(request.POST, instance=ingredient)
        if form.is_valid():
            ingredient = form.save()
            if previous_stock != ingredient.stock_quantity:
                diff = ingredient.stock_quantity - previous_stock
                log_ingredient_movement(
                    ingredient=ingredient,
                    movement_type='ajuste',
                    quantity=abs(diff),
                    quantity_before=previous_stock,
                    quantity_after=ingredient.stock_quantity,
                    user=request.user,
                    reason='Ajuste manual via edição de ingrediente',
                )
            audit_event(
                request,
                action='ingredient.edit',
                description=f'Ingrediente "{ingredient.name}" atualizado.',
                model_name='Ingredient',
                object_id=ingredient.id,
                metadata={'previous_stock': str(previous_stock), 'new_stock': str(ingredient.stock_quantity)},
            )
            messages.success(request, 'Ingrediente atualizado!')
            return redirect('admin_ingredients')
    else:
        form = IngredientForm(instance=ingredient)

    return render(request, 'restaurante/admin/ingredient_form.html', {
        'form': form,
        'title': 'Editar Ingrediente',
        'ingredient': ingredient,
        'active_menu': 'ingredients',
    })


@login_required
@require_POST
def ingredient_delete(request, ingredient_id):
    """Remover ingrediente"""
    if request.user.role != 'gerente':
        return redirect('dashboard')

    try:
        ingredient = Ingredient.objects.get(id=ingredient_id)
        audit_event(
            request,
            action='ingredient.delete',
            description=f'Ingrediente "{ingredient.name}" removido.',
            model_name='Ingredient',
            object_id=ingredient.id,
            metadata={'stock_quantity': str(ingredient.stock_quantity), 'unit': ingredient.unit},
        )
        ingredient.delete()
        messages.success(request, 'Ingrediente removido!')
    except Ingredient.DoesNotExist:
        messages.warning(request, 'Ingrediente não encontrado ou já foi removido.')
    
    return redirect('admin_ingredients')


# ============== ADICIONAIS ==============

@login_required
def admin_additionals(request):
    """Gestão de adicionais"""
    if request.user.role != 'gerente':
        return redirect('dashboard')

    additionals = Additional.objects.prefetch_related('product_links__product').all()
    products = Product.objects.filter(is_active=True).select_related('category').order_by('category__name', 'name')

    linked_map = {}
    for pa in ProductAdditional.objects.all():
        linked_map.setdefault(pa.additional_id, set()).add(pa.product_id)

    context = {
        'additionals': additionals,
        'products': products,
        'linked_map': {k: list(v) for k, v in linked_map.items()},
        'active_menu': 'additionals',
    }
    return render(request, 'restaurante/admin/additionals.html', context)


@login_required
@require_POST
def additional_create(request):
    """Criar adicional"""
    if request.user.role != 'gerente':
        return redirect('dashboard')

    name = request.POST.get('name', '').strip()
    sale_price_str = request.POST.get('sale_price', '0').strip()
    order_str = request.POST.get('order', '0').strip()

    if not name:
        messages.error(request, 'Nome é obrigatório.')
        return redirect('admin_additionals')

    try:
        sale_price = Decimal(sale_price_str.replace(',', '.'))
    except InvalidOperation:
        sale_price = Decimal('0')

    try:
        display_order = int(order_str)
    except (ValueError, TypeError):
        display_order = 0

    additional = Additional.objects.create(
        name=name,
        sale_price=sale_price,
        order=display_order,
    )
    messages.success(request, f'Adicional "{additional.name}" criado!')
    return redirect('admin_additionals')


@login_required
@require_POST
def additional_edit(request, additional_id):
    """Editar adicional"""
    if request.user.role != 'gerente':
        return redirect('dashboard')

    additional = get_object_or_404(Additional, id=additional_id)
    name = request.POST.get('name', '').strip()
    sale_price_str = request.POST.get('sale_price', '0').strip()
    order_str = request.POST.get('order', '0').strip()
    is_active = request.POST.get('is_active') == 'on'

    if not name:
        messages.error(request, 'Nome é obrigatório.')
        return redirect('admin_additionals')

    try:
        sale_price = Decimal(sale_price_str.replace(',', '.'))
    except InvalidOperation:
        sale_price = Decimal('0')

    try:
        display_order = int(order_str)
    except (ValueError, TypeError):
        display_order = 0

    additional.name = name
    additional.sale_price = sale_price
    additional.order = display_order
    additional.is_active = is_active
    additional.save()
    messages.success(request, f'Adicional "{additional.name}" atualizado!')
    return redirect('admin_additionals')


@login_required
@require_POST
def additional_delete(request, additional_id):
    """Remover adicional"""
    if request.user.role != 'gerente':
        return redirect('dashboard')

    try:
        additional = Additional.objects.get(id=additional_id)
        additional.delete()
        messages.success(request, 'Adicional removido!')
    except Additional.DoesNotExist:
        messages.warning(request, 'Adicional não encontrado.')

    return redirect('admin_additionals')


@login_required
@require_POST
def additional_toggle_product(request, additional_id, product_id):
    """Liga/desliga adicional para um produto (AJAX)"""
    if request.user.role != 'gerente':
        return JsonResponse({'success': False}, status=403)

    additional = get_object_or_404(Additional, id=additional_id)
    product = get_object_or_404(Product, id=product_id)

    link, created = ProductAdditional.objects.get_or_create(product=product, additional=additional)
    if not created:
        link.delete()
        linked = False
    else:
        linked = True

    return JsonResponse({'success': True, 'linked': linked})


@login_required
def api_product_additionals(request, product_id):
    """API: Retorna adicionais disponíveis para um produto"""
    product = get_object_or_404(Product, id=product_id)
    additionals = [
        {
            'id': pa.additional.id,
            'name': pa.additional.name,
            'price': float(pa.additional.sale_price),
        }
        for pa in product.available_additionals.select_related('additional')
                         .filter(additional__is_active=True)
                         .order_by('additional__order', 'additional__name')
    ]
    return JsonResponse({'additionals': additionals})


@login_required
def admin_users(request):
    """Gestão de usuários"""
    if request.user.role != 'gerente':
        return redirect('dashboard')
    
    users = User.objects.all().order_by('role', 'username')
    
    context = {
        'users': users,
        'active_menu': 'users',
    }
    return render(request, 'restaurante/admin/users.html', context)


@login_required
def user_create(request):
    """Criar usuário"""
    if request.user.role != 'gerente':
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        role = request.POST.get('role', 'garcom')
        if role not in ['garcom', 'cozinha', 'gerente']:
            messages.error(request, '❌ Função inválida.')
            return redirect('user_create')
        
        # Validações
        if not username:
            messages.error(request, '❌ Informe o nome de usuário')
            return redirect('user_create')

        try:
            validate_slug(username)
        except ValidationError:
            messages.error(request, '❌ Usuário inválido. Use apenas letras, números, hífen ou underline.')
            return redirect('user_create')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, '❌ Este usuário já existe')
            return redirect('user_create')
        
        if not password:
            messages.error(request, '❌ Informe a senha')
            return redirect('user_create')

        try:
            validate_password(password)
        except ValidationError as exc:
            messages.error(request, '❌ ' + ' '.join(exc.messages))
            return redirect('user_create')
        
        # Criar usuário
        try:
            user = User.objects.create_user(
                username=username,
                password=password,
                role=role
            )
            audit_event(
                request,
                action='user.create',
                description=f'Usuário "{username}" criado.',
                model_name='User',
                object_id=user.id,
                metadata={'role': role},
            )
            messages.success(request, f'✅ Usuário "{username}" criado com sucesso!')
            return redirect('admin_users')
        except Exception as e:
            messages.error(request, f'❌ Erro ao criar usuário: {str(e)}')
            return redirect('user_create')
    
    return render(request, 'restaurante/admin/user_form.html', {'title': 'Novo Usuário', 'active_menu': 'users'})


@login_required
@require_POST
def user_delete(request, user_id):
    """Deletar usuário"""
    if request.user.role != 'gerente':
        return redirect('dashboard')
    
    if request.user.id == user_id:
        messages.error(request, 'Você não pode excluir a si mesmo')
        return redirect('admin_users')
    
    try:
        user = User.objects.get(id=user_id)
        audit_event(
            request,
            action='user.delete',
            description=f'Usuário "{user.username}" removido.',
            model_name='User',
            object_id=user.id,
            metadata={'role': user.role},
        )
        user.delete()
        messages.success(request, 'Usuário removido!')
    except User.DoesNotExist:
        messages.warning(request, 'Usuário não encontrado ou já foi removido.')
    
    return redirect('admin_users')


@login_required
def admin_settings(request):
    """Configurações da loja"""
    if request.user.role != 'gerente':
        return redirect('dashboard')
    
    settings = AppSettings.get_settings()
    
    if request.method == 'POST':
        form = AppSettingsForm(request.POST, request.FILES, instance=settings)
        if form.is_valid():
            form.save()
            audit_event(
                request,
                action='settings.update',
                description='Configurações da loja atualizadas.',
                model_name='AppSettings',
                object_id=settings.pk,
            )
            messages.success(request, 'Configurações salvas!')
            return redirect('admin_settings')
        for error in form.non_field_errors():
            messages.error(request, error)
        for field_name, errors in form.errors.items():
            if field_name != '__all__':
                label = form.fields[field_name].label if field_name in form.fields else field_name
                messages.error(request, f'{label}: {" ".join(errors)}')
    else:
        form = AppSettingsForm(instance=settings)
    
    def get_local_ip_address():
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect(('8.8.8.8', 80))
            ip = sock.getsockname()[0]
            sock.close()
            return ip
        except Exception:
            return '127.0.0.1'

    local_ip = get_local_ip_address()
    local_port = request.get_port() or '8000'
    access_links = {
        'local': f'http://localhost:{local_port}',
        'network': f'http://{local_ip}:{local_port}',
    }

    return render(request, 'restaurante/admin/settings.html', {
        'form': form,
        'settings': settings,
        'active_menu': 'settings',
        'access_links': access_links,
        'local_ip': local_ip,
        'pix_preview': pix_preview(settings),
    })


@login_required
def admin_online_orders(request):
    """Pedidos online/delivery"""
    if request.user.role != 'gerente':
        return redirect('dashboard')
    
    if request.method == 'POST':
        # Submeter pedido online usando a mesma lógica
        cart = request.session.get('cart', [])
        
        if not cart:
            messages.error(request, 'O carrinho está vazio')
            return redirect('admin_online_orders')
        
        cliente = request.POST.get('cliente', 'Cliente')
        address = request.POST.get('address', '')
        platform = request.POST.get('platform', 'Whatsapp')
        observacoes = request.POST.get('observacoes', '')
        
        if not cliente:
            messages.error(request, 'Informe o nome do cliente')
            return redirect('admin_online_orders')
        
        observacoes = f"Plataforma: {platform} | {observacoes}" if observacoes else f"Plataforma: {platform}"

        stock_error = validate_cart_ingredient_stock(cart)
        if stock_error:
            messages.error(request, stock_error)
            return redirect('admin_online_orders')

        product_ids = [item['id'] for item in cart]
        products_by_id = Product.objects.in_bulk(product_ids)

        with transaction.atomic():
            total = sum(item['price'] * item['qty'] for item in cart)
            order = Order.objects.create(
                mesa='DELIVERY',
                cliente=cliente,
                observacoes=observacoes,
                total=total,
                status='cozinha',
                order_type='delivery',
                address=address,
                waiter=request.user
            )

            for cart_item in cart:
                product = products_by_id.get(cart_item['id'])
                if not product:
                    raise ValueError(f"Produto inválido: {cart_item['id']}")
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=cart_item['qty'],
                    pending_quantity=cart_item['qty'],
                    unit_price=product.price
                )
                product.consume_ingredients(cart_item['qty'])
        
        request.session['cart'] = []
        messages.success(request, 'Pedido online enviado!')
        return redirect('admin_online_orders')
    
    categories = Category.objects.prefetch_related('products__recipe_items__ingredient').all()
    cart = request.session.get('cart', [])
    cart_total = sum(item['price'] * item['qty'] for item in cart)
    
    delivery_orders = Order.objects.filter(
        order_type='delivery',
        status__in=['cozinha', 'pronto']
    ).order_by('-created_at')
    
    context = {
        'categories': categories,
        'cart': cart,
        'cart_total': cart_total,
        'delivery_orders': delivery_orders,
        'active_menu': 'online',
    }
    return render(request, 'restaurante/admin/online.html', context)


# ============== FECHAMENTO DE CONTA ==============

@login_required
def close_order(request, order_id):
    """Fechar conta / finalizar pedido"""
    order = get_order_for_user_or_403(request.user, order_id)
    
    if request.method == 'POST':
        payment_method = request.POST.get('payment_method', 'dinheiro')
        order.status = 'finalizado'
        order.payment_method = payment_method
        order.save()
        audit_event(
            request,
            action='order.close',
            description=f'Pedido #{order.id} finalizado.',
            model_name='Order',
            object_id=order.id,
            metadata={'payment_method': payment_method, 'total': str(order.total)},
        )
        messages.success(request, f'Conta fechada! Pagamento: {order.get_payment_method_display()}')
        
        if request.user.role == 'gerente':
            return redirect('admin_dashboard')
        return redirect('waiter_view')
    
    form = PaymentForm()
    return render(request, 'restaurante/close_order.html', {
        'order': order,
        'form': form,
        'pix': pix_for_order(order, AppSettings.get_settings()),
    })


@login_required
@require_POST
def cancel_order(request, order_id):
    """Cancelar pedido"""
    if request.user.role != 'gerente':
        messages.error(request, 'Apenas gerentes podem cancelar pedidos')
        return redirect('dashboard')
    
    order = get_object_or_404(Order, id=order_id)
    
    # Devolver estoque
    for item in order.items.all():
        item.product.restore_ingredients(item.quantity)
    
    order.status = 'cancelado'
    order.save()
    audit_event(
        request,
        action='order.cancel',
        description=f'Pedido #{order.id} cancelado.',
        model_name='Order',
        object_id=order.id,
        metadata={'total': str(order.total), 'mesa': order.mesa, 'cliente': order.cliente},
    )
    messages.warning(request, f'Pedido #{order.id} cancelado')
    return redirect('admin_dashboard')


@login_required
def print_order(request, order_id):
    """Imprimir cupom"""
    order = get_order_for_user_or_403(request.user, order_id)
    settings = AppSettings.get_settings()

    audit_event(
        request,
        action='order.print',
        description=f'Cupom do pedido #{order.id} reimpresso.',
        model_name='Order',
        object_id=order.id,
        metadata={'status': order.status, 'total': str(order.total)},
    )
    
    pix = pix_for_order(order, settings) if settings.show_pix_on_receipt and order.status != 'cancelado' else None
    return render(request, 'restaurante/print_order.html', {
        'order': order,
        'settings': settings,
        'pix': pix,
    })


# ============== API VIEWS (AJAX) ==============

@login_required
def api_add_to_cart(request, product_id):
    """API: Adicionar ao carrinho via AJAX (produtos sem adicionais)"""
    if request.method == 'POST':
        product = get_object_or_404(Product, id=product_id)

        available_stock = product.available_stock
        if available_stock <= 0:
            return JsonResponse({'success': False, 'message': 'Produto sem estoque'})

        cart = request.session.get('cart', [])
        cart_key = str(product_id)

        for item in cart:
            if item.get('cart_key', str(item['id'])) == cart_key and not item.get('additionals'):
                if item['qty'] >= available_stock:
                    return JsonResponse({'success': False, 'message': 'Limite de estoque'})
                item['qty'] += 1
                request.session['cart'] = cart
                request.session.modified = True
                total = sum(i['price'] * i['qty'] for i in cart)
                return JsonResponse({'success': True, 'cart': cart, 'total': total})

        cart.append({
            'cart_key': cart_key,
            'id': product_id,
            'name': product.name,
            'price': float(product.price),
            'additionals_price': 0,
            'qty': 1,
            'icon': product.icon,
            'image': product.image.url if product.image else None,
            'additionals': [],
        })
        request.session['cart'] = cart
        request.session.modified = True
        total = sum(i['price'] * i['qty'] for i in cart)
        return JsonResponse({'success': True, 'cart': cart, 'total': total})

    return JsonResponse({'success': False})


@login_required
@require_POST
def api_add_bundle_to_cart(request):
    """API: Adicionar produto com adicionais ao carrinho (via JSON)"""
    import json as _json
    try:
        body = _json.loads(request.body)
    except (ValueError, AttributeError):
        return JsonResponse({'success': False, 'message': 'JSON inválido'}, status=400)

    product_id = int(body.get('product_id', 0))
    additional_ids = sorted(set(int(a) for a in body.get('additionals', [])))
    qty = max(1, int(body.get('qty', 1)))

    product = get_object_or_404(Product, id=product_id)
    available_stock = product.available_stock

    if available_stock <= 0:
        return JsonResponse({'success': False, 'message': 'Produto sem estoque'})

    additionals_data = []
    if additional_ids:
        ad_qs = Additional.objects.filter(id__in=additional_ids, is_active=True)
        ad_map = {a.id: a for a in ad_qs}
        for aid in additional_ids:
            if aid in ad_map:
                a = ad_map[aid]
                additionals_data.append({'id': a.id, 'name': a.name, 'price': float(a.sale_price)})

    additionals_price = sum(a['price'] for a in additionals_data)

    if additional_ids:
        cart_key = f"{product_id}_{'_'.join(str(a) for a in additional_ids)}"
    else:
        cart_key = str(product_id)

    cart = request.session.get('cart', [])

    for item in cart:
        if item.get('cart_key') == cart_key:
            new_qty = item['qty'] + qty
            if new_qty > available_stock:
                return JsonResponse({'success': False, 'message': 'Limite de estoque atingido'})
            item['qty'] = new_qty
            request.session['cart'] = cart
            request.session.modified = True
            total = sum(i['price'] * i['qty'] for i in cart)
            return JsonResponse({'success': True, 'cart': cart, 'total': total})

    cart.append({
        'cart_key': cart_key,
        'id': product_id,
        'name': product.name,
        'price': float(product.price),
        'additionals_price': additionals_price,
        'qty': qty,
        'icon': product.icon,
        'image': product.image.url if product.image else None,
        'additionals': additionals_data,
    })
    request.session['cart'] = cart
    request.session.modified = True
    total = sum(i['price'] * i['qty'] for i in cart)
    return JsonResponse({'success': True, 'cart': cart, 'total': total})


@login_required
@require_POST
def api_change_cart_item(request):
    """API: Incrementa ou decrementa item do carrinho por cart_key"""
    import json as _json
    try:
        body = _json.loads(request.body)
    except (ValueError, AttributeError):
        return JsonResponse({'success': False, 'message': 'JSON inválido'}, status=400)

    cart_key = str(body.get('cart_key', ''))
    delta = int(body.get('delta', 1))

    cart = request.session.get('cart', [])

    for item in cart:
        if item.get('cart_key', str(item['id'])) == cart_key:
            new_qty = item['qty'] + delta
            if new_qty <= 0:
                cart.remove(item)
            else:
                item['qty'] = new_qty
            break

    request.session['cart'] = cart
    request.session.modified = True
    total = sum(i['price'] * i['qty'] for i in cart)
    return JsonResponse({'success': True, 'cart': cart, 'total': total})


@login_required
def api_remove_from_cart(request, product_id):
    """API: Remover do carrinho via AJAX"""
    if request.method == 'POST':
        import json as _json
        cart_key_override = None
        try:
            body = _json.loads(request.body)
            cart_key_override = body.get('cart_key')
        except (ValueError, AttributeError):
            pass

        target_key = cart_key_override if cart_key_override else str(product_id)
        cart = request.session.get('cart', [])

        for item in cart:
            if item.get('cart_key', str(item['id'])) == target_key:
                if item['qty'] > 1:
                    item['qty'] -= 1
                else:
                    cart.remove(item)
                break

        request.session['cart'] = cart
        request.session.modified = True
        total = sum((i['price'] + i.get('additionals_price', 0)) * i['qty'] for i in cart)
        return JsonResponse({'success': True, 'cart': cart, 'total': total})

    return JsonResponse({'success': False})


@login_required
def api_get_cart(request):
    """API: Obter carrinho"""
    cart = request.session.get('cart', [])
    total = sum(item['price'] * item['qty'] for item in cart)
    return JsonResponse({'cart': cart, 'total': total})


@login_required
def api_clear_cart(request):
    """API: Limpar carrinho"""
    if request.method == 'POST':
        request.session['cart'] = []
        request.session.modified = True
        return JsonResponse({'success': True, 'cart': [], 'total': 0})

    return JsonResponse({'success': False})


def pwa_manifest(request):
    return render(request, 'pwa/manifest.webmanifest', content_type='application/manifest+json')


def pwa_service_worker(request):
    return render(request, 'pwa/sw.js', content_type='application/javascript')


def download_ca_cert(request):
    cert_path = settings.BASE_DIR / 'certs' / 'rootCA.pem'
    if not cert_path.exists():
        raise Http404
    return FileResponse(
        open(cert_path, 'rb'),
        as_attachment=True,
        filename='nabandeja-rootCA.pem',
        content_type='application/x-pem-file',
    )
