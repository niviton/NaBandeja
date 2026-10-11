from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Order, OrderItem
from .realtime import publish_order_event


@receiver(post_save, sender=Order)
def order_saved(sender, instance, created, update_fields=None, **kwargs):
    if created:
        event = 'order.created'
    elif update_fields and 'status' in update_fields:
        event = 'order.status_changed'
    else:
        event = 'order.updated'
    publish_order_event(instance, event)


@receiver(post_save, sender=OrderItem)
@receiver(post_delete, sender=OrderItem)
def order_item_changed(sender, instance, **kwargs):
    try:
        order = instance.order
    except Order.DoesNotExist:  # pedido apagado junto
        return
    publish_order_event(order, 'order.items_changed')
