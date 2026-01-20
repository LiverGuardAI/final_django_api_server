import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import Conversation, ConversationMember, Message
from .serializers import get_user_display_name


class ChatConsumer(AsyncWebsocketConsumer):
    """
    채팅 WebSocket Consumer
    - 연결 시 사용자의 모든 대화방 그룹에 조인
    - 메시지 전송/수신 처리
    - 읽음 처리
    """

    async def connect(self):
        self.user = self.scope.get('user')

        if not self.user or not self.user.is_authenticated:
            print(f"ChatConsumer: Unauthenticated user attempted to connect")
            # 1008: Policy Violation - 인증 필요
            await self.close(code=4001)  # Custom code for auth failure
            return

        # 사용자 개인 그룹 (새 대화방 알림용)
        self.user_chat_group = f"chat_user_{self.user.user_id}"
        await self.channel_layer.group_add(
            self.user_chat_group,
            self.channel_name
        )

        # 사용자가 참여중인 모든 대화방 그룹에 조인
        conversation_ids = await self.get_user_conversations()
        self.joined_conversations = set()

        for conv_id in conversation_ids:
            group_name = f"chat_conversation_{conv_id}"
            await self.channel_layer.group_add(group_name, self.channel_name)
            self.joined_conversations.add(conv_id)

        await self.accept()
        print(f"ChatConsumer: User {self.user.user_id} connected, joined {len(self.joined_conversations)} conversations")

    async def disconnect(self, close_code):
        print(f"ChatConsumer: User disconnecting, code: {close_code}")

        # Fire-and-forget: 그룹 정리를 백그라운드로 실행하고 즉시 반환
        # Redis expiry=10초가 백업으로 자동 정리함
        async def cleanup_groups():
            tasks = []
            for conv_id in getattr(self, 'joined_conversations', set()):
                group_name = f"chat_conversation_{conv_id}"
                tasks.append(self.channel_layer.group_discard(group_name, self.channel_name))

            if hasattr(self, 'user_chat_group'):
                tasks.append(self.channel_layer.group_discard(self.user_chat_group, self.channel_name))

            if tasks:
                try:
                    await asyncio.gather(*tasks, return_exceptions=True)
                except Exception as e:
                    print(f"ChatConsumer: Error in background cleanup: {e}")

        # 백그라운드 태스크로 실행 (disconnect는 즉시 반환)
        asyncio.create_task(cleanup_groups())

        print(f"ChatConsumer: Disconnect complete")

    async def receive(self, text_data):
        """클라이언트로부터 메시지 수신"""
        try:
            data = json.loads(text_data)
            action = data.get('action')
            print(f"[ChatConsumer] 📥 Received action: {action}, data: {data}")

            if action == 'send_message':
                await self.handle_send_message(data)
            elif action == 'mark_read':
                await self.handle_mark_read(data)
            elif action == 'join_conversation':
                await self.handle_join_conversation(data)
            elif action == 'typing':
                await self.handle_typing(data)
            elif action == 'edit_message':
                print(f"[ChatConsumer] ✏️ Processing edit_message: {data}")
                await self.handle_edit_message(data)
            elif action == 'delete_message':
                print(f"[ChatConsumer] 🗑️ Processing delete_message: {data}")
                await self.handle_delete_message(data)
            elif action == 'ping':
                # Heartbeat ping 응답
                await self.send(text_data=json.dumps({'type': 'pong'}))
            else:
                print(f"[ChatConsumer] ⚠️ Unknown action: {action}")
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON format")
        except Exception as e:
            print(f"ChatConsumer receive error: {e}")
            import traceback
            traceback.print_exc()
            await self.send_error(str(e))

    async def handle_send_message(self, data):
        """메시지 전송 처리"""
        conversation_id = data.get('conversation_id')
        body = data.get('body', '').strip()

        if not conversation_id or not body:
            await self.send_error("conversation_id and body are required")
            return

        # 권한 확인 및 메시지 저장
        message_data = await self.save_message(conversation_id, body)

        if message_data is None:
            await self.send_error("Failed to send message or no permission")
            return

        # 대화방 그룹에 브로드캐스트
        group_name = f"chat_conversation_{conversation_id}"
        await self.channel_layer.group_send(
            group_name,
            {
                'type': 'chat_message',
                'message': message_data
            }
        )

    async def handle_mark_read(self, data):
        """읽음 처리"""
        conversation_id = data.get('conversation_id')
        message_id = data.get('message_id')

        if not conversation_id or not message_id:
            await self.send_error("conversation_id and message_id are required")
            return

        success = await self.update_last_read(conversation_id, message_id)

        if success:
            # 대화방 그룹에 읽음 상태 브로드캐스트
            group_name = f"chat_conversation_{conversation_id}"
            await self.channel_layer.group_send(
                group_name,
                {
                    'type': 'read_receipt',
                    'user_id': self.user.user_id,
                    'conversation_id': conversation_id,
                    'message_id': message_id
                }
            )

    async def handle_join_conversation(self, data):
        """새 대화방 조인 (DM 생성 후)"""
        conversation_id = data.get('conversation_id')

        if conversation_id and conversation_id not in self.joined_conversations:
            # 권한 확인
            is_member = await self.check_membership(conversation_id)
            if is_member:
                group_name = f"chat_conversation_{conversation_id}"
                await self.channel_layer.group_add(group_name, self.channel_name)
                self.joined_conversations.add(conversation_id)

    async def handle_typing(self, data):
        """타이핑 표시"""
        conversation_id = data.get('conversation_id')
        is_typing = data.get('is_typing', False)

        if conversation_id:
            group_name = f"chat_conversation_{conversation_id}"
            await self.channel_layer.group_send(
                group_name,
                {
                    'type': 'typing_indicator',
                    'user_id': self.user.user_id,
                    'username': self.user.username,
                    'conversation_id': conversation_id,
                    'is_typing': is_typing
                }
            )

    async def handle_edit_message(self, data):
        """메시지 수정 처리"""
        message_id = data.get('message_id')
        new_body = data.get('body', '').strip()
        print(f"[handle_edit_message] ✏️ Start - message_id: {message_id}, new_body: {new_body[:50] if new_body else 'empty'}...")

        if not message_id or not new_body:
            print(f"[handle_edit_message] ❌ Missing required fields")
            await self.send_error("message_id and body are required")
            return

        result = await self.edit_message(message_id, new_body)
        print(f"[handle_edit_message] 📝 edit_message result: {result}")

        if result is None:
            print(f"[handle_edit_message] ❌ edit_message returned None")
            await self.send_error("Failed to edit message or no permission")
            return

        # 대화방 그룹에 브로드캐스트
        group_name = f"chat_conversation_{result['conversation_id']}"
        print(f"[handle_edit_message] 📤 Broadcasting to group: {group_name}")
        await self.channel_layer.group_send(
            group_name,
            {
                'type': 'message_edited',
                'message_id': result['message_id'],
                'conversation_id': result['conversation_id'],
                'body': result['body'],
                'edited_at': result['edited_at'],
                'is_last_message': result.get('is_last_message', False)
            }
        )
        print(f"[handle_edit_message] ✅ Broadcast complete")

    async def handle_delete_message(self, data):
        """메시지 삭제 처리"""
        message_id = data.get('message_id')
        print(f"[handle_delete_message] 🗑️ Start - message_id: {message_id}, type: {type(message_id)}")

        if not message_id:
            print(f"[handle_delete_message] ❌ message_id is missing")
            await self.send_error("message_id is required")
            return

        result = await self.delete_message(message_id)
        print(f"[handle_delete_message] 📝 delete_message result: {result}")

        if result is None:
            print(f"[handle_delete_message] ❌ delete_message returned None")
            await self.send_error("Failed to delete message or no permission")
            return

        # 대화방 그룹에 브로드캐스트
        group_name = f"chat_conversation_{result['conversation_id']}"
        print(f"[handle_delete_message] 📤 Broadcasting to group: {group_name}")
        await self.channel_layer.group_send(
            group_name,
            {
                'type': 'message_deleted',
                'message_id': result['message_id'],
                'conversation_id': result['conversation_id'],
                'new_last_message': result.get('new_last_message')
            }
        )
        print(f"[handle_delete_message] ✅ Broadcast complete")

    # ===== Channel Layer Event Handlers =====

    async def chat_message(self, event):
        """대화방 메시지 브로드캐스트 수신"""
        print(f"ChatConsumer: 📨 chat_message received for user {self.user.user_id}, message_id: {event['message'].get('message_id')}")
        await self.send(text_data=json.dumps({
            'type': 'new_message',
            'message': event['message']
        }))
        print(f"ChatConsumer: ✅ new_message sent to user {self.user.user_id}")

    async def read_receipt(self, event):
        """읽음 상태 브로드캐스트 수신"""
        await self.send(text_data=json.dumps({
            'type': 'read_receipt',
            'user_id': event['user_id'],
            'conversation_id': event['conversation_id'],
            'message_id': event['message_id']
        }))

    async def typing_indicator(self, event):
        """타이핑 표시 브로드캐스트 수신"""
        # 자신의 타이핑은 보내지 않음
        if event['user_id'] != self.user.user_id:
            await self.send(text_data=json.dumps({
                'type': 'typing',
                'user_id': event['user_id'],
                'username': event['username'],
                'conversation_id': event['conversation_id'],
                'is_typing': event['is_typing']
            }))

    async def message_edited(self, event):
        """메시지 수정 브로드캐스트 수신"""
        await self.send(text_data=json.dumps({
            'type': 'message_edited',
            'message_id': event['message_id'],
            'conversation_id': event['conversation_id'],
            'body': event['body'],
            'edited_at': event['edited_at'],
            'is_last_message': event.get('is_last_message', False)
        }))

    async def message_deleted(self, event):
        """메시지 삭제 브로드캐스트 수신"""
        await self.send(text_data=json.dumps({
            'type': 'message_deleted',
            'message_id': event['message_id'],
            'conversation_id': event['conversation_id'],
            'new_last_message': event.get('new_last_message')
        }))

    async def new_conversation(self, event):
        """새 대화방 생성 알림 (개인 그룹으로 수신)"""
        conversation_id = event.get('conversation_id')
        if conversation_id:
            # 새 대화방 그룹에 조인
            group_name = f"chat_conversation_{conversation_id}"
            await self.channel_layer.group_add(group_name, self.channel_name)
            self.joined_conversations.add(conversation_id)

        await self.send(text_data=json.dumps({
            'type': 'new_conversation',
            'conversation': event.get('conversation')
        }))

    # ===== Database Operations =====

    @database_sync_to_async
    def get_user_conversations(self):
        """사용자가 참여중인 대화방 ID 목록"""
        return list(
            ConversationMember.objects.filter(user=self.user)
            .values_list('conversation_id', flat=True)
        )

    @database_sync_to_async
    def check_membership(self, conversation_id):
        """대화방 멤버십 확인"""
        return ConversationMember.objects.filter(
            conversation_id=conversation_id,
            user=self.user
        ).exists()

    @database_sync_to_async
    def save_message(self, conversation_id, body):
        """메시지 저장"""
        try:
            # 멤버십 확인
            if not ConversationMember.objects.filter(
                conversation_id=conversation_id,
                user=self.user
            ).exists():
                return None

            # 메시지 생성
            message = Message.objects.create(
                conversation_id=conversation_id,
                sender=self.user,
                body=body,
                message_type='TEXT'
            )

            # 대화방 updated_at 갱신
            Conversation.objects.filter(conversation_id=conversation_id).update(
                updated_at=timezone.now()
            )

            return {
                'message_id': message.message_id,
                'conversation_id': conversation_id,
                'sender_id': self.user.user_id,
                'sender_name': get_user_display_name(self.user),
                'body': message.body,
                'message_type': message.message_type,
                'created_at': message.created_at.isoformat()
            }
        except Exception as e:
            print(f"save_message error: {e}")
            return None

    @database_sync_to_async
    def update_last_read(self, conversation_id, message_id):
        """읽음 처리 업데이트"""
        try:
            ConversationMember.objects.filter(
                conversation_id=conversation_id,
                user=self.user
            ).update(last_read_message_id=message_id)
            return True
        except Exception as e:
            print(f"update_last_read error: {e}")
            return False

    @database_sync_to_async
    def edit_message(self, message_id, new_body):
        """메시지 수정 (본인 메시지만)"""
        try:
            message = Message.objects.get(
                message_id=message_id,
                sender=self.user,
                deleted_at__isnull=True
            )
            message.body = new_body
            message.edited_at = timezone.now()
            message.save(update_fields=['body', 'edited_at'])

            # 이 메시지가 대화방의 마지막 메시지인지 확인
            last_message = Message.objects.filter(
                conversation_id=message.conversation_id,
                deleted_at__isnull=True
            ).order_by('-created_at').first()

            is_last_message = last_message and last_message.message_id == message.message_id

            return {
                'message_id': message.message_id,
                'conversation_id': message.conversation_id,
                'body': message.body,
                'edited_at': message.edited_at.isoformat(),
                'is_last_message': is_last_message
            }
        except Message.DoesNotExist:
            return None
        except Exception as e:
            print(f"edit_message error: {e}")
            return None

    @database_sync_to_async
    def delete_message(self, message_id):
        """메시지 삭제 (soft delete, 본인 메시지만)"""
        try:
            print(f"[delete_message] Attempting to delete message_id={message_id}, user_id={self.user.user_id}")
            message = Message.objects.get(
                message_id=message_id,
                sender=self.user,
                deleted_at__isnull=True
            )
            conversation_id = message.conversation_id
            message.deleted_at = timezone.now()
            message.save(update_fields=['deleted_at'])
            print(f"[delete_message] ✅ Success: message_id={message.message_id}, conversation_id={conversation_id}")

            # 삭제 후 새로운 last_message 조회
            new_last_message = Message.objects.filter(
                conversation_id=conversation_id,
                deleted_at__isnull=True
            ).order_by('-created_at').first()

            last_message_data = None
            if new_last_message:
                last_message_data = {
                    'message_id': new_last_message.message_id,
                    'body': new_last_message.body[:50] if new_last_message.body else '[파일]',
                    'sender_id': new_last_message.sender_id,
                    'created_at': new_last_message.created_at.isoformat()
                }

            return {
                'message_id': message.message_id,
                'conversation_id': conversation_id,
                'new_last_message': last_message_data
            }
        except Message.DoesNotExist:
            print(f"[delete_message] ❌ Message not found: message_id={message_id}, user_id={self.user.user_id}")
            return None
        except Exception as e:
            print(f"[delete_message] ❌ Error: {e}")
            return None

    async def send_error(self, message):
        """에러 메시지 전송"""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message
        }))
