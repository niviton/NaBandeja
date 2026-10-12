from datetime import timedelta
from unittest import mock

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from nabandeja_project import servir
from nabandeja_project.dburl import parse_database_url
from restaurante import realtime
from restaurante.models import RealtimeEvent
from restaurante.realtime import ORDERS_GROUP
from restaurante.services import orders

from . import factories as f


class RealtimeTests(TestCase):
    def setUp(self):
        self.layer = get_channel_layer()
        self.channel = async_to_sync(self.layer.new_channel)()
        async_to_sync(self.layer.group_add)(ORDERS_GROUP, self.channel)

    def received(self):
        """Eventos que chegaram ao grupo (WebSocket) desde a última leitura."""
        events = []
        while self.layer.channels.get(self.channel):
            events.append(async_to_sync(self.layer.receive)(self.channel)['payload'])
        return events

    def test_eventos_saem_apos_gravar(self):
        manager = f.user()
        with self.captureOnCommitCallbacks(execute=True):
            order, _ = orders.place_order(manager, f.FakeCart((f.product(), 1)), mesa='4', store_settings=f.open_store())
        types = [event['type'] for event in self.received()]
        self.assertEqual(types.count('order.created'), 1)

        with self.captureOnCommitCallbacks(execute=True):
            orders.mark_ready(order)
        self.assertIn('order.status_changed', [event['type'] for event in self.received()])

    def test_websocket_e_registro_tem_o_mesmo_id(self):
        cursor = realtime.latest_cursor()  # 0 num banco novo: também precisa entregar
        with self.captureOnCommitCallbacks(execute=True):
            realtime.publish_event('table.call', {'table': '3', 'kind': 'garcom'})
        sent = self.received()[-1]
        stored = RealtimeEvent.objects.get(id=sent['id'])
        self.assertEqual(stored.kind, 'table.call')
        self.assertEqual(realtime.events_since(cursor)['events'], [sent])

    def test_nada_sai_se_a_transacao_falhar(self):
        with self.captureOnCommitCallbacks(execute=False):
            realtime.publish_event('table.call', {'table': '3'})
        self.assertFalse(RealtimeEvent.objects.exists())
        self.assertEqual(self.received(), [])


class PollingTests(TestCase):
    def publish(self, kind='order.updated'):
        with self.captureOnCommitCallbacks(execute=True):
            realtime.publish_event(kind, {})
        return realtime.latest_cursor()

    def test_endpoint_exige_login(self):
        self.assertEqual(self.client.get(reverse('realtime_events')).status_code, 401)

    def test_entrega_so_depois_do_cursor(self):
        self.client.force_login(f.user())
        first = self.publish('order.created')
        second = self.publish('table.call')
        data = self.client.get(reverse('realtime_events'), {'desde': first}).json()
        self.assertEqual([event['type'] for event in data['events']], ['table.call'])
        self.assertEqual(data['cursor'], second)
        empty = self.client.get(reverse('realtime_events'), {'desde': second}).json()
        self.assertEqual(empty, {'cursor': second, 'events': []})

    def test_sem_cursor_so_devolve_o_atual(self):
        self.client.force_login(f.user())
        latest = self.publish()
        self.assertEqual(self.client.get(reverse('realtime_events')).json(), {'cursor': latest, 'events': []})
        self.assertEqual(self.client.get(reverse('realtime_events'), {'desde': 'abc'}).json()['events'], [])

    def test_cursor_velho_ou_desconhecido_pede_recarga(self):
        self.client.force_login(f.user())
        for _ in range(3):
            self.publish()
        ids = list(RealtimeEvent.objects.order_by('id').values_list('id', flat=True))
        RealtimeEvent.objects.filter(id__in=ids[:2]).delete()  # apagados pela limpeza
        self.assertTrue(self.client.get(reverse('realtime_events'), {'desde': ids[0]}).json()['reset'])
        self.assertNotIn('reset', self.client.get(reverse('realtime_events'), {'desde': ids[1]}).json())
        self.assertTrue(self.client.get(reverse('realtime_events'), {'desde': 10 ** 9}).json()['reset'])

    def test_primeiro_evento_com_cursor_zero(self):
        """Página aberta antes de existir qualquer evento (instalação nova)."""
        self.client.force_login(f.user())
        self.publish('order.created')
        data = self.client.get(reverse('realtime_events'), {'desde': 0}).json()
        self.assertEqual([event['type'] for event in data['events']], ['order.created'])

    def test_limpeza_mantem_o_ultimo(self):
        for _ in range(3):
            self.publish()
        RealtimeEvent.objects.update(created_at=timezone.now() - timedelta(hours=1))
        realtime.prune()
        self.assertEqual(list(RealtimeEvent.objects.values_list('id', flat=True)), [realtime.latest_cursor()])

    def test_pagina_informa_transporte_e_cursor(self):
        f.open_store()
        self.client.force_login(f.user())
        latest = self.publish()
        response = self.client.get(reverse('kitchen_view'))
        self.assertContains(response, f'data-realtime-cursor="{latest}"')
        self.assertContains(response, 'data-realtime="')


class TransportTests(SimpleTestCase):
    def test_escolha_por_ambiente(self):
        cases = [
            (dict(NABANDEJA_SERVIDOR='wsgi'), 'polling'),                       # PythonAnywhere
            (dict(NABANDEJA_SERVIDOR='asgi'), 'auto'),                          # Daphne
            (dict(NABANDEJA_SERVIDOR='asgi', HAS_CHANNELS=False), 'polling'),   # ASGI sem channels
            (dict(NABANDEJA_SERVIDOR='asgi', ENABLE_REALTIME=False), 'polling'),
            (dict(NABANDEJA_SERVIDOR='asgi', REALTIME_TRANSPORT='websocket'), 'websocket'),
            (dict(NABANDEJA_SERVIDOR='asgi', REALTIME_TRANSPORT='polling'), 'polling'),
            (dict(NABANDEJA_SERVIDOR='wsgi', REALTIME_TRANSPORT='off'), 'off'),
        ]
        for extra, expected in cases:
            options = {'ENABLE_REALTIME': True, 'HAS_CHANNELS': True, 'REALTIME_TRANSPORT': 'auto', **extra}
            with self.subTest(**extra), override_settings(**options):
                self.assertEqual(realtime.transport(), expected)

    def test_servir_cai_para_wsgi_sem_daphne(self):
        with mock.patch.object(servir, 'has_asgi_server', return_value=False):
            self.assertEqual(servir.choose_server(), 'wsgi')
        with mock.patch.object(servir, 'has_asgi_server', return_value=True):
            self.assertEqual(servir.choose_server(), 'asgi')
            self.assertEqual(servir.choose_server(force_wsgi=True), 'wsgi')

    def test_servir_usa_porta_do_railway(self):
        with mock.patch.dict('os.environ', {'PORT': '7123', 'APP_PORT': '8000'}):
            self.assertEqual(servir.parse_args([]).port, 7123)

    def test_database_url(self):
        config = parse_database_url('postgres://user:s%40nha@db.railway.internal:5433/nabandeja?sslmode=require')
        self.assertEqual(config['ENGINE'], 'django.db.backends.postgresql')
        self.assertEqual((config['USER'], config['PASSWORD']), ('user', 's@nha'))
        self.assertEqual((config['HOST'], config['PORT'], config['NAME']), ('db.railway.internal', '5433', 'nabandeja'))
        self.assertEqual(config['OPTIONS'], {'sslmode': 'require'})
        with self.assertRaises(ValueError):
            parse_database_url('mysql://x@y/z')
