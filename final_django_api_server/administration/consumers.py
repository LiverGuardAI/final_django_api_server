import json
from channels.generic.websocket import AsyncWebsocketConsumer
from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from django.conf import settings
import jwt
from django.contrib.auth import get_user_model

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
            await self.close()

    async def disconnect(self, close_code):
        # Leave general group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
        # Leave user group
        user = self.scope.get('user')
        if user and user.is_authenticated:
            await self.channel_layer.group_discard(
                f"user_{user.user_id}",
                self.channel_name
            )

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
