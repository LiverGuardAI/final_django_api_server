from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Conversation, ConversationMember, Message, File, MessageFile

User = get_user_model()


def get_user_display_name(user):
    """사용자의 실제 이름 반환 (역할별 모델에서 조회)"""
    if not user:
        return None

    try:
        if user.role == 'DOCTOR':
            return user.doctor.name
        elif user.role == 'RADIOLOGIST':
            return user.radiology.name
        elif user.role == 'CLERK':
            return user.administration.name
    except Exception:
        pass

    # 관련 모델이 없으면 username 반환
    return user.username


class UserSimpleSerializer(serializers.ModelSerializer):
    """사용자 간단 정보"""
    name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['user_id', 'username', 'role', 'name']

    def get_name(self, obj):
        return get_user_display_name(obj)


class MessageSerializer(serializers.ModelSerializer):
    """메시지 Serializer"""
    sender = UserSimpleSerializer(read_only=True)
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            'message_id', 'conversation', 'sender', 'body',
            'message_type', 'created_at', 'edited_at', 'is_deleted', 'is_mine'
        ]
        read_only_fields = ['message_id', 'sender', 'created_at', 'edited_at']

    def get_is_mine(self, obj):
        request = self.context.get('request')
        if request and request.user:
            return obj.sender_id == request.user.user_id
        return False


class ConversationMemberSerializer(serializers.ModelSerializer):
    """대화방 멤버 Serializer"""
    user = UserSimpleSerializer(read_only=True)
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = ConversationMember
        fields = ['user', 'joined_at', 'last_read_message', 'unread_count']

    def get_unread_count(self, obj):
        return obj.get_unread_count()


class ConversationListSerializer(serializers.ModelSerializer):
    """대화방 목록용 Serializer"""
    other_user = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            'conversation_id', 'type', 'title', 'other_user',
            'last_message', 'unread_count', 'created_at', 'updated_at'
        ]

    def get_other_user(self, obj):
        """DM에서 상대방 정보"""
        request = self.context.get('request')
        if obj.type == 'DM' and request:
            current_user_id = request.user.user_id
            if obj.dm_user1_id == current_user_id:
                other = obj.dm_user2
            else:
                other = obj.dm_user1
            if other:
                return UserSimpleSerializer(other).data
        return None

    def get_last_message(self, obj):
        """마지막 메시지 (prefetch된 데이터 활용, 없으면 기존 쿼리)"""
        # prefetched_messages가 있으면 사용 (N+1 방지)
        if hasattr(obj, 'prefetched_messages') and obj.prefetched_messages:
            last_msg = obj.prefetched_messages[0]  # 이미 -created_at 정렬됨
        else:
            # fallback: 기존 쿼리 (prefetch 안 된 경우)
            last_msg = obj.messages.filter(deleted_at__isnull=True).order_by('-created_at').first()

        if last_msg:
            return {
                'message_id': last_msg.message_id,
                'body': last_msg.body[:50] if last_msg.body else '[파일]',
                'sender_id': last_msg.sender_id,
                'created_at': last_msg.created_at.isoformat()
            }
        return None

    def get_unread_count(self, obj):
        """안 읽은 메시지 수 (prefetch된 데이터 활용, 없으면 기존 쿼리)"""
        request = self.context.get('request')
        if not request:
            return 0

        current_user = request.user
        member = None

        # prefetched_members가 있으면 사용 (N+1 방지)
        if hasattr(obj, 'prefetched_members'):
            for m in obj.prefetched_members:
                if m.user_id == current_user.user_id:
                    member = m
                    break
        else:
            # fallback: 기존 쿼리 (prefetch 안 된 경우)
            try:
                member = obj.members.get(user=current_user)
            except ConversationMember.DoesNotExist:
                return 0

        if not member:
            return 0

        # unread_count 계산: prefetched_messages 활용 (기존 로직과 동일)
        # 조건: sender != 현재유저, message_id > last_read_message_id
        if hasattr(obj, 'prefetched_messages'):
            last_read_id = member.last_read_message_id if member.last_read_message else None
            count = 0
            for msg in obj.prefetched_messages:
                # 기존 로직: exclude(sender=self.user)
                if msg.sender_id == current_user.user_id:
                    continue
                # 기존 로직: filter(message_id__gt=last_read_message.message_id)
                if last_read_id is None or msg.message_id > last_read_id:
                    count += 1
            return count
        else:
            # fallback: 기존 쿼리
            return member.get_unread_count()


class ConversationDetailSerializer(serializers.ModelSerializer):
    """대화방 상세 Serializer"""
    members = ConversationMemberSerializer(many=True, read_only=True)
    other_user = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            'conversation_id', 'type', 'title', 'created_by',
            'members', 'other_user', 'created_at', 'updated_at'
        ]

    def get_other_user(self, obj):
        request = self.context.get('request')
        if obj.type == 'DM' and request:
            current_user_id = request.user.user_id
            if obj.dm_user1_id == current_user_id:
                other = obj.dm_user2
            else:
                other = obj.dm_user1
            if other:
                return UserSimpleSerializer(other).data
        return None


class CreateDMSerializer(serializers.Serializer):
    """DM 생성용 Serializer"""
    target_user_id = serializers.IntegerField()

    def validate_target_user_id(self, value):
        try:
            User.objects.get(user_id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found")
        return value


class SendMessageSerializer(serializers.Serializer):
    """메시지 전송용 Serializer"""
    body = serializers.CharField(required=False, allow_blank=True)
    message_type = serializers.ChoiceField(
        choices=Message.MessageType.choices,
        default=Message.MessageType.TEXT
    )

    def validate(self, data):
        message_type = data.get('message_type', 'TEXT')
        body = data.get('body', '').strip()

        if message_type == 'TEXT' and not body:
            raise serializers.ValidationError("Text messages require body")

        return data


class UserListSerializer(serializers.ModelSerializer):
    """사용자 목록 (채팅 가능한 사용자)"""
    department = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['user_id', 'username', 'role', 'department', 'name']

    def get_name(self, obj):
        return get_user_display_name(obj)

    def get_department(self, obj):
        """역할에 따른 부서 반환"""
        role_to_department = {
            'DOCTOR': '소화기내과',
            'RADIOLOGIST': '영상의학과',
            'CLERK': '원무과',
        }
        return role_to_department.get(obj.role, '기타')
