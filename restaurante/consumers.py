from channels.generic.websocket import AsyncJsonWebsocketConsumer


class OrdersConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        self.groups_to_join = ['orders_global']

        if user.role in ['cozinha', 'gerente']:
            self.groups_to_join.append('orders_kitchen')

        if user.role == 'gerente':
            self.groups_to_join.append('orders_admin')

        self.groups_to_join.append(f'orders_waiter_{user.id}')

        for group_name in self.groups_to_join:
            await self.channel_layer.group_add(group_name, self.channel_name)

        await self.accept()
        await self.send_json({'type': 'connection.ready'})

    async def disconnect(self, close_code):
        for group_name in getattr(self, 'groups_to_join', []):
            await self.channel_layer.group_discard(group_name, self.channel_name)

    async def order_event(self, event):
        await self.send_json(event['payload'])
