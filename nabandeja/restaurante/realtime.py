from asgiref.sync import async_to_sync


def publish_order_event(order, event_name='order.updated'):
    try:
        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()
        if not channel_layer:
            return False

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

        targets = ['orders_global']
        if order.waiter_id:
            targets.append(f'orders_waiter_{order.waiter_id}')
        targets.append('orders_kitchen')
        targets.append('orders_admin')

        for target in targets:
            async_to_sync(channel_layer.group_send)(
                target,
                {
                    'type': 'order_event',
                    'payload': payload,
                },
            )

        return True
    except Exception:
        return False
