"""
Emissão de licenças do NaBandeja (uso exclusivo do dono do produto).

A chave privada fica FORA do repositório, em %USERPROFILE%\\.nabandeja\\licenca_privada.pem.
Faça backup dela: sem ela não dá para emitir licenças novas.

Uso:
    python scripts/licenca.py gerar-chaves          (só uma vez; imprime a chave pública)
    python scripts/licenca.py emitir --cliente "Billá Burger" --slug billa-burguer --dias 365
    python scripts/licenca.py emitir --cliente "Bar do Zé" --slug bar-do-ze --ate 2027-12-31
    python scripts/licenca.py ver <licença>
"""

import argparse
import sys
from datetime import date
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from restaurante.services.license import decode, encode, expiry_from_days  # noqa: E402

PRIVATE_KEY_PATH = Path.home() / '.nabandeja' / 'licenca_privada.pem'


def load_private_key():
    if not PRIVATE_KEY_PATH.exists():
        sys.exit(f'Chave privada não encontrada em {PRIVATE_KEY_PATH}. Rode "gerar-chaves" primeiro.')
    return serialization.load_pem_private_key(PRIVATE_KEY_PATH.read_bytes(), password=None)


def generate_keys(_args):
    if PRIVATE_KEY_PATH.exists():
        sys.exit(f'Já existe uma chave em {PRIVATE_KEY_PATH}. Gerar outra invalida as licenças emitidas.')
    private_key = Ed25519PrivateKey.generate()
    PRIVATE_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    PRIVATE_KEY_PATH.write_bytes(private_key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption(),
    ))
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    print(f'Chave privada salva em {PRIVATE_KEY_PATH} (FAÇA BACKUP E NÃO COMPARTILHE).')
    print('Coloque esta chave pública em restaurante/services/license.py (PUBLIC_KEY_PEM):\n')
    print(public_pem)


def issue(args):
    expires = date.fromisoformat(args.ate) if args.ate else expiry_from_days(args.dias)
    payload = {
        'cliente': args.cliente,
        'slug': args.slug,
        'expira': expires.isoformat(),
        'emitida': date.today().isoformat(),
    }
    key = encode(payload, load_private_key())
    decode(key)  # confere com a chave pública do código
    print(f'Licença de {args.cliente} válida até {expires:%d/%m/%Y}:\n')
    print(key)
    print('\nCole em Configurações > Licença no sistema do cliente.')


def show(args):
    payload = decode(args.licenca)
    print(f"Cliente: {payload['cliente']} ({payload.get('slug', '')})")
    print(f"Vence em: {payload['expira']:%d/%m/%Y}   Emitida em: {payload.get('emitida', '-')}")


def main():
    parser = argparse.ArgumentParser(description='Licenças do NaBandeja')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('gerar-chaves').set_defaults(func=generate_keys)
    emit = sub.add_parser('emitir')
    emit.add_argument('--cliente', required=True)
    emit.add_argument('--slug', required=True)
    group = emit.add_mutually_exclusive_group(required=True)
    group.add_argument('--dias', type=int)
    group.add_argument('--ate', help='AAAA-MM-DD')
    emit.set_defaults(func=issue)
    view = sub.add_parser('ver')
    view.add_argument('licenca')
    view.set_defaults(func=show)
    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
