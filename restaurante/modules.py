"""
Módulos que o superusuário NaBandeja liga ou desliga para cada cliente.

O núcleo (salão, pedidos, cozinha, cardápio, equipe, configurações) está
sempre ligado. Os módulos abaixo são opcionais; desligado, o módulo some do
menu e as telas dele respondem 404.
"""

from functools import wraps

from django.http import Http404

MODULES = [
    ('delivery', 'Delivery', 'Pedidos de entrega lançados pela equipe, bairros e taxas.'),
    ('online', 'Pedidos online', 'O cliente faz o pedido de entrega pelo site (/pedir/).'),
    ('cardapio_digital', 'Cardápio digital', 'QR Code na mesa e no suporte de molhos; chamar garçom e pedir a conta.'),
    ('ingredientes', 'Estoque por ingredientes', 'Cadastro de ingredientes, receitas e baixa automática.'),
    ('caixa', 'Caixa', 'Abertura e fechamento de caixa por turno.'),
    ('financeiro', 'Contas a pagar', 'Despesas, vencimentos e saldo do mês.'),
    ('pix', 'PIX no cupom', 'QR Code PIX com o valor exato no cupom e no fechamento.'),
    ('google', 'Login com Google', 'Botão "Entrar com Google" na tela de login.'),
]
MODULE_KEYS = [key for key, _, _ in MODULES]


def enabled_modules(store):
    """{chave: ligado?} — módulos novos começam ligados."""
    saved = store.modules or {}
    return {key: bool(saved.get(key, True)) for key in MODULE_KEYS}


def is_enabled(key, store=None):
    if store is None:
        from .models import AppSettings
        store = AppSettings.get_settings()
    return enabled_modules(store).get(key, True)


def module_required(key):
    """Responde 404 quando o módulo está desligado para este cliente."""
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not is_enabled(key):
                raise Http404('Módulo desativado para esta loja.')
            return view(request, *args, **kwargs)
        return wrapper
    return decorator
