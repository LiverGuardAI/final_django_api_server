from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from django.db.models import Q, Prefetch

from .models import Conversation, ConversationMember, Message
from .serializers import (
    ConversationListSerializer,
    ConversationDetailSerializer,
    MessageSerializer,
    CreateDMSerializer,
    SendMessageSerializer,
    UserListSerializer,
    get_user_display_name,
)
from .tasks import broadcast_chat_message, broadcast_read_receipt, broadcast_new_conversation

User = get_user_model()


class ConversationViewSet(viewsets.ModelViewSet):
    """대화방 ViewSet"""
    permission_classes = [IsAuthenticated]
    serializer_class = ConversationListSerializer

    def get_queryset(self):
        """현재 사용자가 참여중인 대화방 목록 (최적화된 쿼리)"""
        user = self.request.user

        # last_message용 Prefetch: deleted_at이 NULL인 메시지만, created_at 내림차순
        # Serializer의 get_last_message와 동일한 조건
        last_message_prefetch = Prefetch(
            'messages',
            queryset=Message.objects.filter(
                deleted_at__isnull=True
            ).order_by('-created_at'),
            to_attr='prefetched_messages'
        )

        # members용 Prefetch: 현재 유저의 멤버십 정보 + last_read_message 포함
        members_prefetch = Prefetch(
            'members',
            queryset=ConversationMember.objects.select_related(
                'user', 'user__doctor', 'user__radiology', 'user__administration',
                'last_read_message'
            ),
            to_attr='prefetched_members'
        )

        return Conversation.objects.filter(
            members__user=user
        ).select_related(
            'dm_user1', 'dm_user2', 'created_by',
            'dm_user1__doctor', 'dm_user1__radiology', 'dm_user1__administration',
            'dm_user2__doctor', 'dm_user2__radiology', 'dm_user2__administration',
        ).prefetch_related(
            last_message_prefetch,
            members_prefetch,
        ).distinct().order_by('-updated_at')

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ConversationDetailSerializer
        return ConversationListSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    @action(detail=False, methods=['post'])
    def create_dm(self, request):
        """DM 대화방 생성 또는 조회"""
        serializer = CreateDMSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target_user_id = serializer.validated_data['target_user_id']

        # 자기 자신에게 DM 불가
        if target_user_id == request.user.user_id:
            return Response(
                {'error': 'Cannot create DM with yourself'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            target_user = User.objects.get(user_id=target_user_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # DM 생성 또는 조회 (get_or_create_dm이 ID 정렬 처리)
        conversation, created = Conversation.get_or_create_dm(
            request.user, target_user
        )

        # 새로 생성된 경우 상대방에게 WebSocket 알림 (Celery로 비동기 처리)
        if created:
            target_group = f"chat_user_{target_user.user_id}"

            conversation_data = ConversationListSerializer(
                conversation, context={'request': request}
            ).data

            broadcast_new_conversation.delay(
                target_group,
                conversation.conversation_id,
                conversation_data
            )

        response_serializer = ConversationDetailSerializer(
            conversation, context={'request': request}
        )
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )

    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        """대화방 메시지 목록 (최적화된 쿼리)"""
        conversation = self.get_object()

        # 멤버십 확인 - prefetch된 members 사용
        if not any(m.user_id == request.user.user_id for m in conversation.members.all()):
            return Response(
                {'error': 'Not a member of this conversation'},
                status=status.HTTP_403_FORBIDDEN
            )

        # 페이지네이션
        limit = int(request.query_params.get('limit', 50))
        before_id = request.query_params.get('before')

        # sender 관계 프리로드로 N+1 쿼리 방지
        messages = conversation.messages.filter(
            deleted_at__isnull=True
        ).select_related(
            'sender', 'sender__doctor', 'sender__radiology', 'sender__administration'
        )

        if before_id:
            messages = messages.filter(message_id__lt=before_id)

        messages = messages.order_by('-created_at')[:limit]
        messages = list(messages)[::-1]  # 오래된 순으로 정렬

        serializer = MessageSerializer(
            messages, many=True, context={'request': request}
        )
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def send(self, request, pk=None):
        """메시지 전송"""
        conversation = self.get_object()

        # 멤버십 확인
        if not conversation.members.filter(user=request.user).exists():
            return Response(
                {'error': 'Not a member of this conversation'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # 메시지 생성
        message = Message.objects.create(
            conversation=conversation,
            sender=request.user,
            body=serializer.validated_data.get('body', ''),
            message_type=serializer.validated_data.get('message_type', 'TEXT')
        )

        # 대화방 updated_at 갱신
        conversation.save()

        # WebSocket으로 브로드캐스트 (Celery로 비동기 처리 - 블로킹 방지)
        group_name = f"chat_conversation_{conversation.conversation_id}"

        message_data = {
            'message_id': message.message_id,
            'conversation_id': conversation.conversation_id,
            'sender_id': request.user.user_id,
            'sender_name': get_user_display_name(request.user),
            'body': message.body,
            'message_type': message.message_type,
            'created_at': message.created_at.isoformat()
        }

        broadcast_chat_message.delay(group_name, message_data)

        response_serializer = MessageSerializer(
            message, context={'request': request}
        )
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """읽음 처리"""
        conversation = self.get_object()
        message_id = request.data.get('message_id')

        if not message_id:
            return Response(
                {'error': 'message_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            member = conversation.members.get(user=request.user)
            member.last_read_message_id = message_id
            member.save()

            # WebSocket으로 읽음 상태 브로드캐스트 (Celery로 비동기 처리)
            group_name = f"chat_conversation_{conversation.conversation_id}"

            broadcast_read_receipt.delay(
                group_name,
                request.user.user_id,
                conversation.conversation_id,
                message_id
            )

            return Response({'status': 'ok'})
        except ConversationMember.DoesNotExist:
            return Response(
                {'error': 'Not a member of this conversation'},
                status=status.HTTP_403_FORBIDDEN
            )


class UserListViewSet(viewsets.ReadOnlyModelViewSet):
    """채팅 가능한 사용자 목록"""
    permission_classes = [IsAuthenticated]
    serializer_class = UserListSerializer

    def get_queryset(self):
        """의료진만 조회 (PATIENT 제외), 본인 제외 - 관련 모델 프리페치로 최적화"""
        queryset = User.objects.exclude(
            user_id=self.request.user.user_id
        ).exclude(
            role='PATIENT'
        ).filter(
            is_active=True
        ).select_related(
            'doctor', 'radiology', 'administration'  # 이름 조회용 역할별 모델 프리로드
        )

        # 부서(역할) 필터링
        department = self.request.query_params.get('department')
        if department:
            role_mapping = {
                '소화기내과': 'DOCTOR',
                '영상의학과': 'RADIOLOGIST',
                '원무과': 'CLERK',
            }
            role = role_mapping.get(department)
            if role:
                queryset = queryset.filter(role=role)

        return queryset.order_by('username')
