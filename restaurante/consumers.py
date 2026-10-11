from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .realtime import ORDERS_GROUP


class OrdersConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return
        await self.channel_layer.group_add(ORDERS_GROUP, self.channel_name)
        await self.accept()
        await self.send_json({'type': 'connection.ready'})

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(ORDERS_GROUP, self.channel_name)

    async def order_event(self, event):
        await self.send_json(event['payload'])
