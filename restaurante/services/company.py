"""Código da empresa usado no login (uma instalação = uma empresa)."""

import re
import unicodedata


def normalize(code):
    """'Billá Burger' == 'billa-burger' == 'BILLA BURGER'."""
    text = unicodedata.normalize('NFKD', code or '').encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'[^a-z0-9]', '', text.lower())


def matches(code, store):
    expected = normalize(store.company_code or store.store_name)
    return bool(expected) and normalize(code) == expected
