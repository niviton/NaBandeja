"""
Geração de PDF sem dependências externas (relatório de vendas).

Escreve o PDF "na mão" (objetos, xref, fontes Helvetica) para não precisar
de bibliotecas nativas no executável Windows.
"""

import io
import unicodedata

from django.utils import timezone


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


def render_sales_pdf(export_rows, store_settings, period_label, summary, product_quantities=None):
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

            row_product = _truncate_pdf(item.get('product_name') or '-', qty_cols[0][2])
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


def build_sales_export_rows(orders_qs):
    rows = []
    for order in orders_qs:
        if order.cliente:
            display_name = order.cliente
        elif order.order_type == 'delivery':
            display_name = 'Cliente delivery'
        else:
            display_name = f'Mesa {order.mesa}'

        order_items = [
            f"{item.quantity}x {item.name} (R$ {item.subtotal:.2f})"
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
