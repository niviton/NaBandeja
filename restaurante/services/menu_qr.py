"""
QR Codes do cardápio digital (cartão do suporte de molhos / mesa).

O cardápio roda no computador da loja, então o celular do cliente precisa
estar no Wi-Fi da loja, ou o sistema precisa de um endereço na internet
(PUBLIC_BASE_URL, ex.: Cloudflare Tunnel). Por isso o cartão pode ter dois
QR Codes: um que conecta ao Wi-Fi e outro que abre o cardápio.
"""

from django.conf import settings


LOCAL_HOSTS = ('localhost', '127.0.0.1', '[::1]')


def public_url(request, path):
    """
    Endereço que vai no QR: PUBLIC_BASE_URL (se configurado) ou o endereço
    atual. Se o gerente abriu pelo próprio PC (localhost), troca pelo IP da
    rede, senão o QR só funcionaria neste computador.
    """
    if settings.PUBLIC_BASE_URL:
        return f'{settings.PUBLIC_BASE_URL}{path}'
    host = request.get_host()
    hostname, _, port = host.rpartition(':') if ':' in host and not host.endswith(']') else (host, '', '')
    if hostname in LOCAL_HOSTS and settings.LOCAL_IP:
        host = f'{settings.LOCAL_IP}:{port}' if port else settings.LOCAL_IP
    scheme = 'https' if request.is_secure() else 'http'
    return f'{scheme}://{host}{path}'


def _escape_wifi(value):
    for char in '\\;,:"':
        value = value.replace(char, f'\\{char}')
    return value


def wifi_payload(ssid, password=''):
    """Texto do QR que a câmera do celular entende como "conectar ao Wi-Fi"."""
    if not ssid:
        return ''
    if not password:
        return f'WIFI:T:nopass;S:{_escape_wifi(ssid)};;'
    return f'WIFI:T:WPA;S:{_escape_wifi(ssid)};P:{_escape_wifi(password)};;'
