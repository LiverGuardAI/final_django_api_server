import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.conf import settings
import jwt
from django.contrib.auth import get_user_model


class FlutterAppConsumer(AsyncWebsocketConsumer):
    """Flutter 환자 앱 전용 WebSocket Consumer"""

    async def connect(self):
        # URL에서 profile_id 추출: /ws/app/<profile_id>/
        self.profile_id = self.scope['url_route']['kwargs'].get('profile_id')

        if not self.profile_id:
            print("FlutterAppConsumer: profile_id missing, closing connection")
            await self.close(code=4001)
            return

        # 사용자별 그룹에 참여
        self.group_name = f'app_user_{self.profile_id}'
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()
        print(f"FlutterAppConsumer: Connected to group {self.group_name}")

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
        print(f"FlutterAppConsumer: Disconnected, code: {close_code}")

    async def receive(self, text_data):
        """클라이언트로부터 메시지 수신 (ping/pong)"""
        try:
            data = json.loads(text_data)
            if data.get('type') == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))
        except json.JSONDecodeError:
            pass

    async def app_sync_result(self, event):
        """앱 연동 승인/거절 결과 알림"""
        await self.send(text_data=json.dumps({
            'type': 'app_sync_result',
            'message': event.get('message', ''),
            'data': event.get('data', {})
        }))


class ClinicConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        import traceback
        try:
            print(f"DEBUG: WebSocket Connect attempted. Init User: {self.scope.get('user')}")

            user = self.scope.get('user')
            
            if not user or not user.is_authenticated:
                print(f"DEBUG: Unknown user connecting: {user}")
            else:
                print(f"DEBUG: Authenticated user: {user}")

            # 1. Join 'clinic_dashboard' group
            self.group_name = 'clinic_dashboard'
            await self.channel_layer.group_add(
                self.group_name,
                self.channel_name
            )
            
            # 2. Join User-specific group for notifications
            if user and user.is_authenticated:
                self.user_group_name = f"user_{user.user_id}"
                await self.channel_layer.group_add(
                    self.user_group_name,
                    self.channel_name
                )
                print(f"DEBUG: Added to user group {self.user_group_name}")
            else:
                print("DEBUG: User not authenticated, skipping personal group")

            print("DEBUG: Redis group_add successful")
            
            await self.accept()
            print("DEBUG: WebSocket accepted")
        except Exception as e:
            print(f"ERROR in WebSocket connect: {e}")
            traceback.print_exc()
            await self.close(code=4000)  # Custom code for server error

    async def disconnect(self, close_code):
        print(f"ClinicConsumer: Disconnecting, code: {close_code}")

        # Fire-and-forget: 그룹 정리를 백그라운드로 실행하고 즉시 반환
        # Redis expiry=10초가 백업으로 자동 정리함
        group_name = getattr(self, 'group_name', None)
        user = self.scope.get('user')
        channel_name = self.channel_name
        channel_layer = self.channel_layer

        async def cleanup_groups():
            tasks = []
            if group_name:
                tasks.append(channel_layer.group_discard(group_name, channel_name))
            if user and user.is_authenticated:
                tasks.append(channel_layer.group_discard(f"user_{user.user_id}", channel_name))

            if tasks:
                try:
                    await asyncio.gather(*tasks, return_exceptions=True)
                except Exception as e:
                    print(f"ClinicConsumer: Error in background cleanup: {e}")

        # 백그라운드 태스크로 실행 (disconnect는 즉시 반환)
        asyncio.create_task(cleanup_groups())

        print(f"ClinicConsumer: Disconnect complete")

    async def receive(self, text_data):
        """클라이언트로부터 메시지 수신 (ping/pong 등)"""
        try:
            data = json.loads(text_data)
            msg_type = data.get('type')

            if msg_type == 'ping':
                # Heartbeat ping 응답
                await self.send(text_data=json.dumps({'type': 'pong'}))
        except json.JSONDecodeError:
            pass
        except Exception as e:
            print(f"ClinicConsumer receive error: {e}")

    async def update_queue(self, event):
        message = event.get('message', '')
        data = event.get('data', {})

        await self.send(text_data=json.dumps({
            'type': 'queue_update',
            'message': message,
            'data': data
        }))

    async def schedule_update(self, event):
        message_content = event.get('message', {})

        await self.send(text_data=json.dumps({
            'type': 'schedule_update',
            'data': message_content
        }))

    async def patient_update(self, event):
        """환자 정보 업데이트 알림"""
        message = event.get('message', '')
        data = event.get('data', {})

        await self.send(text_data=json.dumps({
            'type': 'patient_update',
            'message': message,
            'data': data
        }))

    async def stats_update(self, event):
        """대시보드 통계 업데이트 알림"""
        message = event.get('message', '')
        data = event.get('data', {})

        await self.send(text_data=json.dumps({
            'type': 'stats_update',
            'message': message,
            'data': data
        }))

    async def questionnaire_update(self, event):
        """문진표 업데이트 알림"""
        message = event.get('message', '')
        data = event.get('data', {})

        await self.send(text_data=json.dumps({
            'type': 'questionnaire_update',
            'message': message,
            'data': data
        }))

    async def new_order(self, event):
        """새 오더 생성 알림"""
        message = event.get('message', '')
        data = event.get('data', {})

        await self.send(text_data=json.dumps({
            'type': 'new_order',
            'message': message,
            'data': data
        }))

    async def app_sync_request(self, event):
        """앱 연동 신청 알림"""
        message = event.get('message', '')
        data = event.get('data', {})

        await self.send(text_data=json.dumps({
            'type': 'app_sync_request',
            'message': message,
            'data': data
        }))

    async def app_sync_result(self, event):
        """앱 연동 승인/거절 결과 알림 (Flutter 앱으로 전송)"""
        message = event.get('message', '')
        data = event.get('data', {})

        await self.send(text_data=json.dumps({
            'type': 'app_sync_result',
            'message': message,
            'data': data
        }))

    @database_sync_to_async
    def get_user_from_token(self, token):
        User = get_user_model()
        try:
            # Decode the token
            # Note: simplejwt uses SECRET_KEY by default. 
            # If your simplejwt setup uses a different signing key, adjust here.
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get('user_id')
            if user_id:
                return User.objects.get(id=user_id)
        except Exception as e:
            print(f"JWT Decode Error: {e}")
            return None
        return None
