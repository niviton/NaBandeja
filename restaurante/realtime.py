"""
Avisos em tempo real, iguais em qualquer servidor.

Cada mudança vira UM evento, gravado em RealtimeEvent depois do commit:
    {"id": 123,
     "type": "order.created" | "order.updated" | "order.status_changed" | "order.items_changed"
             | "table.call" | "table.call_resolved",
     "order": {...} | "data": {...}}

O registro é a fonte da verdade; o transporte é só a entrega:
- websocket: /ws/orders/ (ASGI com Channels) entrega na hora;
- polling:   GET /tempo-real/eventos/?desde=<id> funciona em qualquer servidor
             (WSGI no PythonAnywhere, vários processos no Railway, Termux).
O navegador usa o id para não repetir nem perder eventos (static/js/nabandeja.js).
"""

import logging
from datetime import timedelta

from asgiref.sync import async_to_sync
from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from .models import RealtimeEvent

logger = logging.getLogger('nabandeja.realtime')

ORDERS_GROUP = 'orders'
KEEP_MINUTES = 15       # o polling recupera quedas de até 15 min; depois disso a tela recarrega tudo
PRUNE_EVERY = 200       # limpa o registro a cada N eventos
MAX_BATCH = 200


def transport():
    """
    Como o navegador recebe os avisos: 'websocket', 'polling', 'auto' ou 'off'.

    O ponto de entrada diz se há WebSocket: wsgi.py marca NABANDEJA_SERVIDOR=wsgi
    (PythonAnywhere, runserver) e aí é sempre polling.
    """
    configured = settings.REALTIME_TRANSPORT
    if configured == 'off':
        return 'off'
    if not settings.ENABLE_REALTIME or settings.NABANDEJA_SERVIDOR == 'wsgi' or not settings.HAS_CHANNELS:
        return 'polling'
    return configured if configured in ('websocket', 'polling') else 'auto'


# ------------------------------------------------------------------ publicar

def _broadcast(message):
    try:
        from channels.layers import get_channel_layer
    except ImportError:
        return
    layer = get_channel_layer()
    if layer is None:
        return
    try:
        async_to_sync(layer.group_send)(ORDERS_GROUP, {'type': 'order_event', 'payload': message})
    except Exception:  # o polling entrega mesmo assim
        logger.exception('Falha ao enviar evento pelo WebSocket')


def _deliver(payload):
    try:
        event = RealtimeEvent.objects.create(kind=payload['type'], payload=payload)
    except Exception:  # tempo real é melhoria; nunca derruba a gravação do pedido
        logger.exception('Falha ao registrar evento em tempo real')
        return
    if event.id % PRUNE_EVERY == 0:
        prune()
    _broadcast({'id': event.id, **payload})


def publish_event(event_name, data):
    """Envia um evento genérico depois que a transação for gravada."""
    payload = {'type': event_name, 'data': data}
    transaction.on_commit(lambda: _deliver(payload))


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
    transaction.on_commit(lambda: _deliver(payload))


# ------------------------------------------------------------------ ler (polling)

def latest_cursor():
    return RealtimeEvent.objects.aggregate(last=Max('id'))['last'] or 0


def prune():
    """Apaga eventos antigos, mantendo sempre o último (o cursor nunca volta a zero)."""
    cutoff = timezone.now() - timedelta(minutes=KEEP_MINUTES)
    RealtimeEvent.objects.filter(created_at__lt=cutoff, id__lt=latest_cursor()).delete()


def events_since(cursor, limit=MAX_BATCH):
    """
    {'cursor': último id entregue, 'events': [...]}; ou {'reset': True, 'cursor': ...}
    quando o cursor é desconhecido (eventos já apagados ou banco trocado): a tela recarrega tudo.
    cursor None: só informa o cursor atual. Zero é válido (página aberta antes do 1º evento).
    """
    latest = latest_cursor()
    if cursor is None or cursor < 0:
        return {'cursor': latest, 'events': []}
    oldest = RealtimeEvent.objects.order_by('id').values_list('id', flat=True).first()
    if cursor > latest or (oldest is not None and cursor < oldest - 1):
        return {'reset': True, 'cursor': latest, 'events': []}
    events = [{'id': row.id, **row.payload} for row in RealtimeEvent.objects.filter(id__gt=cursor)[:limit]]
    return {'cursor': events[-1]['id'] if events else cursor, 'events': events}
