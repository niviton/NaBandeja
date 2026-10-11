"""
Licença do NaBandeja por cliente (assinatura Ed25519, verificada offline).

Formato da chave:  <dados em base64url>.<assinatura em base64url>
Dados (JSON):      {"cliente": "...", "slug": "...", "expira": "AAAA-MM-DD", "emitida": "AAAA-MM-DD"}

Só quem tem a chave privada (fora do repositório) emite licenças:
    python scripts/licenca.py emitir --cliente "Billá Burger" --slug billa-burguer --dias 365

Regras:
- sem licença instalada: funciona normalmente (instalações antigas/testes);
- faltando 10 dias: aviso para o gerente;
- vencida: mais 7 dias de tolerância com aviso;
- depois disso: bloqueia NOVOS pedidos (contas abertas ainda podem ser fechadas).
"""

import base64
import json
from dataclasses import dataclass
from datetime import date, timedelta

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from django.utils import timezone

PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAnutfWTJfJAWOAyFziI71Kdkcq6ZXvwM5U8p11AT9QJY=
-----END PUBLIC KEY-----
"""

WARNING_DAYS = 10
GRACE_DAYS = 7


def _b64decode(text):
    return base64.urlsafe_b64decode(text + '=' * (-len(text) % 4))


@dataclass
class LicenseStatus:
    state: str              # sem_licenca | valida | vencendo | tolerancia | bloqueada | invalida
    client: str = ''
    expires: date | None = None
    days_left: int | None = None

    @property
    def blocks_new_orders(self):
        return self.state in ('bloqueada', 'invalida')

    @property
    def show_warning(self):
        return self.state in ('vencendo', 'tolerancia', 'bloqueada', 'invalida')

    @property
    def message(self):
        if self.state == 'vencendo':
            return f'A licença do NaBandeja vence em {self.days_left} dia(s) ({self.expires:%d/%m/%Y}). Fale com o suporte para renovar.'
        if self.state == 'tolerancia':
            return (f'A licença venceu em {self.expires:%d/%m/%Y}. Novos pedidos serão bloqueados em '
                    f'{GRACE_DAYS + self.days_left} dia(s). Fale com o suporte.')
        if self.state == 'bloqueada':
            return 'Licença vencida: novos pedidos estão bloqueados. Fale com o suporte para renovar.'
        if self.state == 'invalida':
            return 'A licença instalada é inválida. Fale com o suporte.'
        return ''


def decode(key):
    """Valida a assinatura e devolve os dados da licença (ou levanta ValueError)."""
    try:
        data_part, signature_part = key.strip().split('.')
        data = _b64decode(data_part)
        signature = _b64decode(signature_part)
        load_pem_public_key(PUBLIC_KEY_PEM).verify(signature, data)
        payload = json.loads(data)
        payload['expira'] = date.fromisoformat(payload['expira'])
        return payload
    except (ValueError, KeyError, InvalidSignature, TypeError) as exc:
        raise ValueError('Licença inválida.') from exc


def status(key, today=None):
    if not (key or '').strip():
        return LicenseStatus('sem_licenca')
    try:
        payload = decode(key)
    except ValueError:
        return LicenseStatus('invalida')

    today = today or timezone.localdate()
    expires = payload['expira']
    days_left = (expires - today).days
    info = dict(client=payload.get('cliente', ''), expires=expires, days_left=days_left)
    if days_left > WARNING_DAYS:
        return LicenseStatus('valida', **info)
    if days_left >= 0:
        return LicenseStatus('vencendo', **info)
    if days_left >= -GRACE_DAYS:
        return LicenseStatus('tolerancia', **info)
    return LicenseStatus('bloqueada', **info)


def current_status():
    from ..models import AppSettings
    return status(AppSettings.get_settings().license_key)


def install(store_settings, key):
    """Instala uma licença nova. Não aceita trocar por uma que vença antes da atual."""
    payload = decode(key)
    if store_settings.license_key:
        try:
            current = decode(store_settings.license_key)
        except ValueError:
            current = None
        if current and payload['expira'] < current['expira']:
            raise ValueError('Esta licença vence antes da licença já instalada.')
    store_settings.license_key = key.strip()
    store_settings.save(update_fields=['license_key'])
    return payload


def encode(payload, private_key):
    """Usado por scripts/licenca.py (precisa da chave privada)."""
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode('utf-8')
    signature = private_key.sign(data)

    def b64(raw):
        return base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')

    return f'{b64(data)}.{b64(signature)}'


def expiry_from_days(days, today=None):
    return (today or date.today()) + timedelta(days=int(days))
