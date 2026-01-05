import json
from channels.generic.websocket import AsyncWebsocketConsumer

class ClinicConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # 1. 프론트엔드가 연결하면 'clinic_dashboard' 그룹에 초대
        self.group_name = 'clinic_dashboard'

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept() # 연결 수락

    async def disconnect(self, close_code):
        # 2. 연결 종료 시 그룹에서 제거
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    # 3. views.py에서 보낸 알림을 받아서 프론트엔드한테 전달하는 함수
    # 메서드명은 views.py의 "type": "update_queue"와 일치해야 함
    async def update_queue(self, event):
        # event 딕셔너리에 views.py가 보낸 데이터가 들어있음
        message = event.get('message', '')
        data = event.get('data', {})

        # 프론트엔드(React)에게 JSON으로 쏘기
        await self.send(text_data=json.dumps({
            'type': 'queue_update',
            'message': message,
            'data': data
        }))