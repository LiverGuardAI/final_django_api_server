from django.db import models
from django.conf import settings


class Conversation(models.Model):
    """대화방"""

    class ConversationType(models.TextChoices):
        DM = 'DM', '1:1 대화'
        GROUP = 'GROUP', '그룹 대화'

    conversation_id = models.AutoField(primary_key=True)
    type = models.CharField(
        max_length=10,
        choices=ConversationType.choices,
        default=ConversationType.DM
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_conversations',
        db_column='created_by'
    )
    title = models.CharField(max_length=100, blank=True, null=True)  # GROUP용

    # DM 중복 방지용 (DM일 때만 사용, GROUP은 NULL)
    # 항상 dm_user1_id < dm_user2_id 규칙 적용
    dm_user1 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='dm_conversations_as_user1',
        db_column='dm_user1_id'
    )
    dm_user2 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='dm_conversations_as_user2',
        db_column='dm_user2_id'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'conversations'
        verbose_name = '대화방'
        verbose_name_plural = '대화방'
        # DM 중복 방지
        constraints = [
            models.UniqueConstraint(
                fields=['dm_user1', 'dm_user2'],
                name='unique_dm_conversation',
                condition=models.Q(type='DM')
            )
        ]
        ordering = ['-updated_at']

    def __str__(self):
        if self.type == 'DM':
            return f"DM: {self.dm_user1} ↔ {self.dm_user2}"
        return f"GROUP: {self.title or self.conversation_id}"

    @classmethod
    def get_or_create_dm(cls, user1, user2):
        """DM 대화방 조회 또는 생성 (user1_id < user2_id 규칙 적용)"""
        # ID 정렬
        if user1.user_id > user2.user_id:
            user1, user2 = user2, user1

        conversation, created = cls.objects.get_or_create(
            type='DM',
            dm_user1=user1,
            dm_user2=user2,
            defaults={'created_by': user1}
        )

        # 멤버 추가 (생성 시에만)
        if created:
            ConversationMember.objects.create(conversation=conversation, user=user1)
            ConversationMember.objects.create(conversation=conversation, user=user2)

        return conversation, created


class ConversationMember(models.Model):
    """대화방 멤버"""

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='members',
        db_column='conversation_id'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='conversation_memberships',
        db_column='user_id'
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    # 읽음 처리
    last_read_message = models.ForeignKey(
        'Message',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        db_column='last_read_message_id'
    )

    class Meta:
        db_table = 'conversation_members'
        verbose_name = '대화방 멤버'
        verbose_name_plural = '대화방 멤버'
        constraints = [
            models.UniqueConstraint(
                fields=['conversation', 'user'],
                name='unique_conversation_member'
            )
        ]

    def __str__(self):
        return f"{self.user} in {self.conversation}"

    def get_unread_count(self):
        """안 읽은 메시지 수 (자신이 보낸 메시지 제외)"""
        queryset = Message.objects.filter(conversation=self.conversation).exclude(sender=self.user)
        if self.last_read_message:
            queryset = queryset.filter(message_id__gt=self.last_read_message.message_id)
        return queryset.count()


class Message(models.Model):
    """메시지"""

    class MessageType(models.TextChoices):
        TEXT = 'TEXT', '텍스트'
        FILE = 'FILE', '파일'
        MIXED = 'MIXED', '텍스트+파일'
        SYSTEM = 'SYSTEM', '시스템'

    message_id = models.AutoField(primary_key=True)
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
        db_column='conversation_id'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='sent_messages',
        db_column='sender_id'
    )
    body = models.TextField(blank=True, null=True)
    message_type = models.CharField(
        max_length=10,
        choices=MessageType.choices,
        default=MessageType.TEXT
    )

    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)  # soft delete

    class Meta:
        db_table = 'messages'
        verbose_name = '메시지'
        verbose_name_plural = '메시지'
        ordering = ['created_at']

    def __str__(self):
        sender_name = self.sender.username if self.sender else 'System'
        return f"{sender_name}: {self.body[:30] if self.body else '[파일]'}"

    @property
    def is_deleted(self):
        return self.deleted_at is not None


class File(models.Model):
    """파일 메타데이터"""

    class StorageType(models.TextChoices):
        LOCAL = 'LOCAL', '로컬'
        S3 = 'S3', 'AWS S3'

    file_id = models.AutoField(primary_key=True)
    uploader = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_files',
        db_column='uploader_id'
    )
    storage_type = models.CharField(
        max_length=10,
        choices=StorageType.choices,
        default=StorageType.LOCAL
    )
    storage_key = models.CharField(max_length=500)  # 파일 경로 또는 S3 key
    original_name = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100)
    size_bytes = models.BigIntegerField()

    # 이미지용 (optional)
    width = models.IntegerField(null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)

    checksum_sha256 = models.CharField(max_length=64, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'files'
        verbose_name = '파일'
        verbose_name_plural = '파일'

    def __str__(self):
        return self.original_name


class MessageFile(models.Model):
    """메시지-파일 연결 (N:M)"""

    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='attached_files',
        db_column='message_id'
    )
    file = models.ForeignKey(
        File,
        on_delete=models.CASCADE,
        related_name='message_attachments',
        db_column='file_id'
    )
    sort_order = models.IntegerField(default=0)

    class Meta:
        db_table = 'message_files'
        verbose_name = '메시지 첨부파일'
        verbose_name_plural = '메시지 첨부파일'
        constraints = [
            models.UniqueConstraint(
                fields=['message', 'file'],
                name='unique_message_file'
            )
        ]
        ordering = ['sort_order']

    def __str__(self):
        return f"{self.message} - {self.file}"
