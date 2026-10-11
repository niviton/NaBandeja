from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.test import TestCase

from restaurante.realtime import ORDERS_GROUP
from restaurante.services import orders

from . import factories as f


class RealtimeTests(TestCase):
    def setUp(self):
        self.layer = get_channel_layer()
        self.channel = async_to_sync(self.layer.new_channel)()
        async_to_sync(self.layer.group_add)(ORDERS_GROUP, self.channel)

    def received(self):
        """Tipos dos eventos que chegaram ao grupo desde a última leitura."""
        events = []
        while self.layer.channels.get(self.channel):
            events.append(async_to_sync(self.layer.receive)(self.channel)['payload']['type'])
        return events

    def test_eventos_saem_apos_gravar(self):
        manager = f.user()
        with self.captureOnCommitCallbacks(execute=True):
            order, _ = orders.place_order(manager, f.FakeCart((f.product(), 1)), mesa='4', store_settings=f.open_store())
        events = self.received()
        self.assertEqual(events.count('order.created'), 1)

        with self.captureOnCommitCallbacks(execute=True):
            orders.mark_ready(order)
        self.assertIn('order.status_changed', self.received())
