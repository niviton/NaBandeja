"""
Avisos em tempo real (WebSocket /ws/orders/).

Toda tela logada entra no grupo ORDERS_GROUP e recebe um evento por mudança:
    {"type": "order.created" | "order.updated" | "order.status_changed" | "order.items_changed",
     "order": {...}}
As telas usam o evento para se atualizar; se o WebSocket cair, usam polling.
"""

import logging

from asgiref.sync import async_to_sync
from django.db import transaction

logger = logging.getLogger('nabandeja.realtime')

ORDERS_GROUP = 'orders'


def _send(payload):
    try:
        from channels.layers import get_channel_layer
    except ImportError:
        return
    layer = get_channel_layer()
    if layer is None:
        return
    try:
        async_to_sync(layer.group_send)(ORDERS_GROUP, {'type': 'order_event', 'payload': payload})
    except Exception:  # tempo real é melhoria; nunca derruba a gravação do pedido
        logger.exception('Falha ao publicar evento em tempo real')


def publish_order_event(order, event_name='order.updated'):
    payload = {
        'type': event_name,
        'order': {
            'id': order.id,
            'mesa': order.mesa,
            'cliente': order.cliente,
            'status': order.status,
            'order_type': order.order_type,
            'total': float(order.total),
            'waiter_id': order.waiter_id,
            'updated_at': order.updated_at.isoformat() if order.updated_at else None,
        },
    }
    # Só avisa depois que a transação foi gravada (evita tela buscar dado inexistente).
    transaction.on_commit(lambda: _send(payload))
