"""
Geração de PIX "copia e cola" (BR Code) com valor, sem API de banco.

Segue o Manual de Padrões para Iniciação do Pix (Banco Central), formato
EMV-MPM: campos ID + tamanho (2 dígitos) + valor, terminando com CRC16.
O QR Code é gerado localmente com a biblioteca `qrcode` (SVG inline).
"""

import io
import re
import unicodedata
from decimal import Decimal, ROUND_HALF_UP

KEY_TYPES = [
    ('auto', 'Detectar automaticamente'),
    ('cpf', 'CPF'),
    ('cnpj', 'CNPJ'),
    ('telefone', 'Telefone'),
    ('email', 'E-mail'),
    ('aleatoria', 'Chave aleatória'),
]

_EVP_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)


class PixError(ValueError):
    pass


def _only_digits(value):
    return re.sub(r'\D', '', value or '')


def _ascii_upper(value, max_len):
    text = unicodedata.normalize('NFKD', value or '').encode('ascii', 'ignore').decode('ascii')
    text = re.sub(r'[^A-Za-z0-9 .\-]', '', text).strip().upper()
    return text[:max_len].strip()


def is_valid_cpf(value):
    digits = _only_digits(value)
    if len(digits) != 11 or digits == digits[0] * 11:
        return False
    for size in (9, 10):
        total = sum(int(d) * (size + 1 - i) for i, d in enumerate(digits[:size]))
        check = (total * 10) % 11 % 10
        if check != int(digits[size]):
            return False
    return True


def is_valid_cnpj(value):
    digits = _only_digits(value)
    if len(digits) != 14 or digits == digits[0] * 14:
        return False
    weights = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    for size in (12, 13):
        w = weights if size == 12 else [6] + weights
        total = sum(int(d) * w[i] for i, d in enumerate(digits[:size]))
        check = 11 - total % 11
        check = 0 if check >= 10 else check
        if check != int(digits[size]):
            return False
    return True


def detect_key_type(key):
    key = (key or '').strip()
    if not key:
        raise PixError('Chave PIX não configurada.')
    if '@' in key:
        return 'email'
    if _EVP_RE.match(key):
        return 'aleatoria'
    digits = _only_digits(key)
    if key.startswith('+') or (len(digits) in (12, 13) and digits.startswith('55')):
        return 'telefone'
    if len(digits) == 14 and is_valid_cnpj(digits):
        return 'cnpj'
    if len(digits) == 11 and is_valid_cpf(digits):
        return 'cpf'
    if len(digits) in (10, 11):
        return 'telefone'
    raise PixError('Não foi possível identificar o tipo da chave PIX. Escolha o tipo nas Configurações.')


def normalize_key(key, key_type='auto'):
    """Converte a chave para o formato exigido no BR Code."""
    key = (key or '').strip()
    if key_type in ('', None, 'auto'):
        key_type = detect_key_type(key)

    if key_type == 'cpf':
        digits = _only_digits(key)
        if not is_valid_cpf(digits):
            raise PixError('CPF da chave PIX é inválido.')
        return digits
    if key_type == 'cnpj':
        digits = _only_digits(key)
        if not is_valid_cnpj(digits):
            raise PixError('CNPJ da chave PIX é inválido.')
        return digits
    if key_type == 'telefone':
        digits = _only_digits(key)
        if not digits.startswith('55') or len(digits) < 12:
            digits = '55' + digits
        if len(digits) not in (12, 13):
            raise PixError('Telefone da chave PIX deve ter DDD + número.')
        return '+' + digits
    if key_type == 'email':
        if '@' not in key:
            raise PixError('E-mail da chave PIX é inválido.')
        return key.lower()
    if key_type == 'aleatoria':
        if not _EVP_RE.match(key):
            raise PixError('Chave aleatória PIX inválida (formato xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx).')
        return key.lower()
    raise PixError(f'Tipo de chave PIX desconhecido: {key_type}')


def _field(field_id, value):
    if len(value) > 99:
        raise PixError(f'Campo PIX {field_id} excede 99 caracteres.')
    return f'{field_id}{len(value):02d}{value}'


def crc16_ccitt(payload):
    crc = 0xFFFF
    for byte in payload.encode('utf-8'):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return f'{crc:04X}'


def build_payload(key, name, city, amount=None, txid='***', description='', key_type='auto'):
    """
    Monta o código PIX copia e cola.

    amount: Decimal/str/float com o valor exato (None = cliente digita o valor).
    txid: identificador que aparece no extrato (até 25 letras/números).
    """
    pix_key = normalize_key(key, key_type)
    merchant_name = _ascii_upper(name, 25)
    merchant_city = _ascii_upper(city, 15)
    if not merchant_name:
        raise PixError('Informe o nome do titular do PIX.')
    if not merchant_city:
        raise PixError('Informe a cidade do titular do PIX.')

    account = _field('00', 'br.gov.bcb.pix') + _field('01', pix_key)
    description = _ascii_upper(description, 40)
    if description and len(account) + 4 + len(description) <= 99:
        account += _field('02', description)

    txid = re.sub(r'[^A-Za-z0-9]', '', txid or '')[:25] or '***'

    payload = _field('00', '01')
    payload += _field('26', account)
    payload += _field('52', '0000')
    payload += _field('53', '986')
    if amount is not None:
        value = Decimal(str(amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if value <= 0:
            raise PixError('O valor do PIX deve ser maior que zero.')
        payload += _field('54', f'{value:.2f}')
    payload += _field('58', 'BR')
    payload += _field('59', merchant_name)
    payload += _field('60', merchant_city)
    payload += _field('62', _field('05', txid))
    payload += '6304'
    return payload + crc16_ccitt(payload)


def qr_svg(payload, box_size=10, border=2):
    """Retorna o QR Code como SVG (string) para embutir no HTML."""
    import qrcode
    import qrcode.image.svg

    image = qrcode.make(
        payload,
        image_factory=qrcode.image.svg.SvgPathImage,
        box_size=box_size,
        border=border,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
    )
    buffer = io.BytesIO()
    image.save(buffer)
    svg = buffer.getvalue().decode('utf-8')
    return svg[svg.find('<svg'):]


def _build_for_settings(store_settings, amount, txid):
    if not store_settings.pix_key:
        return None
    try:
        payload = build_payload(
            key=store_settings.pix_key,
            key_type=store_settings.pix_key_type,
            name=store_settings.pix_name or store_settings.store_name,
            city=store_settings.pix_city or store_settings.city,
            amount=amount,
            txid=txid,
        )
    except PixError as exc:
        return {'error': str(exc)}
    return {'payload': payload, 'svg': qr_svg(payload)}


def pix_preview(store_settings):
    """PIX de R$ 0,01 para o gerente conferir a configuração."""
    return _build_for_settings(store_settings, Decimal('0.01'), 'TESTE')


def pix_for_order(order, store_settings):
    """
    Gera {'payload', 'svg'} para o total do pedido, ou {'error'} se a
    configuração estiver incompleta. Nunca levanta exceção (usado em template).
    """
    return _build_for_settings(store_settings, order.amount_due, f'PEDIDO{order.id}')
