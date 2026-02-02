import os
import uuid
import hashlib
import mimetypes

# PIL은 선택적 - 이미지 크기 추출용
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from django.db.models import Q, Prefetch
from django.conf import settings
from django.http import FileResponse, Http404

from .models import Conversation, ConversationMember, Message, File, MessageFile
from .serializers import (
    ConversationListSerializer,
    ConversationDetailSerializer,
    MessageSerializer,
    CreateDMSerializer,
    SendMessageSerializer,
    UserListSerializer,
    FileSerializer,
    get_user_display_name,
)
from .tasks import broadcast_chat_message, broadcast_read_receipt, broadcast_new_conversation

User = get_user_model()

# 최대 파일 크기 (50MB)
MAX_FILE_SIZE = 50 * 1024 * 1024


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
        """의료진만 조회 (PATIENT 제외), 본인 제외 - 역할별 모델이 있는 사용자만"""
        from doctor.models import Doctor
        from radiology.models import Radiology
        from administration.models import Administration

        # 역할별 모델이 존재하는 employee_no 목록 조회
        valid_doctor_usernames = set(Doctor.objects.values_list('employee_no', flat=True))
        valid_radiology_usernames = set(Radiology.objects.values_list('employee_no', flat=True))
        valid_admin_usernames = set(Administration.objects.values_list('employee_no', flat=True))

        queryset = User.objects.exclude(
            user_id=self.request.user.user_id
        ).exclude(
            role='PATIENT'
        ).filter(
            is_active=True
        ).select_related(
            'doctor', 'radiology', 'administration'
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

        # 역할별 모델이 존재하는 사용자만 필터링
        valid_users = []
        for user in queryset:
            if user.role == 'DOCTOR' and user.username in valid_doctor_usernames:
                valid_users.append(user.user_id)
            elif user.role == 'RADIOLOGIST' and user.username in valid_radiology_usernames:
                valid_users.append(user.user_id)
            elif user.role == 'CLERK' and user.username in valid_admin_usernames:
                valid_users.append(user.user_id)

        return User.objects.filter(user_id__in=valid_users).select_related(
            'doctor', 'radiology', 'administration'
        ).order_by('username')


class FileUploadView(APIView):
    """파일 업로드 API"""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        """파일 업로드 및 메시지 전송"""
        conversation_id = request.data.get('conversation_id')
        uploaded_file = request.FILES.get('file')
        body = request.data.get('body', '')

        if not conversation_id:
            return Response(
                {'error': 'conversation_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not uploaded_file:
            return Response(
                {'error': 'file is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 파일 크기 검증
        if uploaded_file.size > MAX_FILE_SIZE:
            return Response(
                {'error': f'파일 크기가 너무 큽니다. 최대 {MAX_FILE_SIZE // (1024*1024)}MB'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 대화방 확인
        try:
            conversation = Conversation.objects.get(conversation_id=conversation_id)
        except Conversation.DoesNotExist:
            return Response(
                {'error': 'Conversation not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # 멤버십 확인
        if not conversation.members.filter(user=request.user).exists():
            return Response(
                {'error': 'Not a member of this conversation'},
                status=status.HTTP_403_FORBIDDEN
            )

        # 파일 저장
        file_ext = os.path.splitext(uploaded_file.name)[1].lower()
        unique_name = f"{uuid.uuid4().hex}{file_ext}"

        # chat_files 폴더에 저장
        upload_dir = os.path.join(settings.MEDIA_ROOT, 'chat_files')
        os.makedirs(upload_dir, exist_ok=True)

        file_path = os.path.join(upload_dir, unique_name)
        storage_key = f"chat_files/{unique_name}"

        # 파일 저장 및 해시 계산
        sha256_hash = hashlib.sha256()
        with open(file_path, 'wb+') as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)
                sha256_hash.update(chunk)

        # MIME 타입 감지
        mime_type = uploaded_file.content_type or mimetypes.guess_type(uploaded_file.name)[0] or 'application/octet-stream'

        # 이미지 크기 확인 (PIL 설치된 경우만)
        width, height = None, None
        if HAS_PIL and mime_type.startswith('image/'):
            try:
                with Image.open(file_path) as img:
                    width, height = img.size
            except Exception:
                pass

        # File 모델 생성
        file_obj = File.objects.create(
            uploader=request.user,
            storage_type='LOCAL',
            storage_key=storage_key,
            original_name=uploaded_file.name,
            mime_type=mime_type,
            size_bytes=uploaded_file.size,
            width=width,
            height=height,
            checksum_sha256=sha256_hash.hexdigest()
        )

        # 메시지 타입 결정
        if body.strip():
            message_type = 'MIXED'
        else:
            message_type = 'FILE'

        # 메시지 생성
        message = Message.objects.create(
            conversation=conversation,
            sender=request.user,
            body=body,
            message_type=message_type
        )

        # MessageFile 연결
        MessageFile.objects.create(
            message=message,
            file=file_obj,
            sort_order=0
        )

        # 대화방 updated_at 갱신
        conversation.save()

        # WebSocket 브로드캐스트
        group_name = f"chat_conversation_{conversation.conversation_id}"
        file_data = FileSerializer(file_obj, context={'request': request}).data

        message_data = {
            'message_id': message.message_id,
            'conversation_id': conversation.conversation_id,
            'sender_id': request.user.user_id,
            'sender_name': get_user_display_name(request.user),
            'body': message.body,
            'message_type': message.message_type,
            'created_at': message.created_at.isoformat(),
            'files': [file_data]
        }

        broadcast_chat_message.delay(group_name, message_data)

        response_serializer = MessageSerializer(message, context={'request': request})
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class FileDownloadView(APIView):
    """파일 다운로드 API"""
    permission_classes = [IsAuthenticated]

    def get(self, request, file_id):
        """파일 다운로드"""
        try:
            file_obj = File.objects.get(file_id=file_id)
        except File.DoesNotExist:
            return Response(
                {'error': '파일을 찾을 수 없습니다.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # 사용자 권한 확인 (파일이 속한 대화방의 멤버인지)
        message_files = MessageFile.objects.filter(file=file_obj).select_related('message__conversation')
        has_access = False
        for mf in message_files:
            if mf.message.conversation.members.filter(user=request.user).exists():
                has_access = True
                break

        if not has_access:
            return Response(
                {'error': '접근 권한이 없습니다.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # 파일 존재 확인
        if file_obj.storage_type == 'LOCAL':
            file_path = os.path.join(settings.MEDIA_ROOT, file_obj.storage_key)
            if not os.path.exists(file_path):
                return Response(
                    {'error': '존재하지 않는 파일입니다.', 'file_missing': True},
                    status=status.HTTP_404_NOT_FOUND
                )

            response = FileResponse(
                open(file_path, 'rb'),
                content_type=file_obj.mime_type
            )
            # 한글 파일명 처리
            from urllib.parse import quote
            encoded_name = quote(file_obj.original_name)
            response['Content-Disposition'] = f"attachment; filename*=UTF-8''{encoded_name}"
            return response
        else:
            # S3 처리 (추후 구현)
            return Response(
                {'error': 'S3 storage not implemented'},
                status=status.HTTP_501_NOT_IMPLEMENTED
            )
