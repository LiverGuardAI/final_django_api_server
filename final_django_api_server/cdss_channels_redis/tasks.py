from celery import shared_task
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


@shared_task(name='cdss_channels_redis.broadcast_chat_message')
def broadcast_chat_message(group_name: str, message_data: dict):
    """
    Celery로 채팅 메시지 브로드캐스트 (비동기 처리)
    REST API 뷰에서 async_to_sync 블로킹 문제 해결
    """
    print(f"[ChatTask] 📤 Broadcasting to group: {group_name}, message_id: {message_data.get('message_id')}")
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'chat_message',
                'message': message_data
            }
        )
        print(f"[ChatTask] ✅ Broadcast sent to {group_name}")
    except Exception as e:
        print(f"[ChatTask] ❌ broadcast_chat_message error: {e}")


@shared_task(name='cdss_channels_redis.broadcast_read_receipt')
def broadcast_read_receipt(group_name: str, user_id: int, conversation_id: int, message_id: int):
    """
    Celery로 읽음 처리 브로드캐스트 (비동기 처리)
    """
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'read_receipt',
                'user_id': user_id,
                'conversation_id': conversation_id,
                'message_id': message_id
            }
        )
    except Exception as e:
        print(f"[ChatTask] broadcast_read_receipt error: {e}")


@shared_task(name='cdss_channels_redis.broadcast_new_conversation')
def broadcast_new_conversation(target_group: str, conversation_id: int, conversation_data: dict):
    """
    Celery로 새 대화방 알림 브로드캐스트 (비동기 처리)
    """
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            target_group,
            {
                'type': 'new_conversation',
                'conversation_id': conversation_id,
                'conversation': conversation_data
            }
        )
    except Exception as e:
        print(f"[ChatTask] broadcast_new_conversation error: {e}")
