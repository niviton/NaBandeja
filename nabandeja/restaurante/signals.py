from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Order, OrderItem
from .realtime import publish_order_event


@receiver(post_save, sender=Order)
def order_saved(sender, instance, created, **kwargs):
    event_name = 'order.created' if created else 'order.updated'
    publish_order_event(instance, event_name=event_name)


@receiver(post_save, sender=OrderItem)
def order_item_saved(sender, instance, created, **kwargs):
    order = instance.order
    publish_order_event(order, event_name='order.items_changed')


@receiver(post_delete, sender=OrderItem)
def order_item_deleted(sender, instance, **kwargs):
    order = instance.order
    publish_order_event(order, event_name='order.items_changed')
