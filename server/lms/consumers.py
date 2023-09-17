import json

from asgiref.sync import async_to_sync
from channels.generic.websocket import AsyncWebsocketConsumer


class SyncConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        print('connect method')
        self.lms_id = self.scope['url_route']['kwargs']['id']
        self.lsm_group_name = f'lsm_{self.lms_id}'

        await self.channel_layer.group_add(self.lsm_group_name, self.channel_name)

        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.lsm_group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']
        await self.send(text_data=json.dumps({'message': message}))
