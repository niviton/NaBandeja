"""
Chaves e criptografia dos dados que saem do PC da loja.

Backups: a loja cifra com a chave PÚBLICA do dono do NaBandeja e só a chave
privada, guardada no PC master, abre o arquivo. Nem o GitHub, nem quem pegar
a chave de envio de uma loja, consegue ler os dados.

Formato do arquivo (.nbk):
    b'NBK1' | chave pública efêmera X25519 (32) | nonce (12) | AES-256-GCM

Também gera as chaves SSH de envio (uma por empresa, só escrevem no
repositório de dados daquela empresa).
"""

import base64
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

MAGIC = b'NBK1'
_INFO = b'nabandeja-backup-v1'


class CofreError(ValueError):
    pass


def _b64(raw):
    return base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')


def _unb64(text):
    return base64.urlsafe_b64decode(text + '=' * (-len(text) % 4))


def _raw_public(public_key):
    return public_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def _derive(shared, ephemeral_raw, recipient_raw):
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=ephemeral_raw + recipient_raw, info=_INFO).derive(shared)


# ------------------------------------------------------------------ chave mestra

def generate_master_key():
    """(PEM da chave privada, chave pública em texto) para cifrar os backups."""
    private_key = X25519PrivateKey.generate()
    pem = private_key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption(),
    )
    return pem, _b64(_raw_public(private_key.public_key()))


def load_private_key(pem):
    key = serialization.load_pem_private_key(pem, password=None)
    if not isinstance(key, X25519PrivateKey):
        raise CofreError('A chave mestra não é do tipo esperado (X25519).')
    return key


def public_text(private_key):
    return _b64(_raw_public(private_key.public_key()))


def load_public_key(text):
    try:
        raw = _unb64(text.strip())
        return X25519PublicKey.from_public_bytes(raw)
    except ValueError as exc:
        raise CofreError('Chave pública do backup inválida.') from exc


# ------------------------------------------------------------------ cifrar

def encrypt(data, public_key_text):
    recipient = load_public_key(public_key_text)
    ephemeral = X25519PrivateKey.generate()
    ephemeral_raw = _raw_public(ephemeral.public_key())
    key = _derive(ephemeral.exchange(recipient), ephemeral_raw, _raw_public(recipient))
    nonce = os.urandom(12)
    return MAGIC + ephemeral_raw + nonce + AESGCM(key).encrypt(nonce, data, MAGIC)


def decrypt(blob, private_key):
    if blob[:4] != MAGIC or len(blob) < 4 + 32 + 12 + 16:
        raise CofreError('Arquivo de backup inválido.')
    ephemeral_raw, nonce, ciphertext = blob[4:36], blob[36:48], blob[48:]
    ephemeral = X25519PublicKey.from_public_bytes(ephemeral_raw)
    key = _derive(private_key.exchange(ephemeral), ephemeral_raw, _raw_public(private_key.public_key()))
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, MAGIC)
    except InvalidTag as exc:
        raise CofreError('Não foi possível abrir o backup: chave mestra errada ou arquivo corrompido.') from exc


# ------------------------------------------------------------------ chave SSH de envio

def generate_ssh_key(comment):
    """(chave privada OpenSSH, linha da chave pública) para o deploy key da empresa."""
    private_key = Ed25519PrivateKey.generate()
    private_bytes = private_key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.OpenSSH, serialization.NoEncryption(),
    )
    public_line = private_key.public_key().public_bytes(
        serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH,
    ).decode('ascii')
    return private_bytes, f'{public_line} {comment}'
