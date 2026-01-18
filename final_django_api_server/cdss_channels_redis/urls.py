from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ConversationViewSet, UserListViewSet

router = DefaultRouter()
router.register(r'conversations', ConversationViewSet, basename='conversation')
router.register(r'chat-users', UserListViewSet, basename='chat-user')

urlpatterns = [
    path('', include(router.urls)),
]

# API Endpoints:
# GET    /api/chat/conversations/          - 대화방 목록
# GET    /api/chat/conversations/{id}/     - 대화방 상세
# POST   /api/chat/conversations/create_dm/ - DM 생성 (target_user_id)
# GET    /api/chat/conversations/{id}/messages/  - 메시지 목록
# POST   /api/chat/conversations/{id}/send/      - 메시지 전송
# POST   /api/chat/conversations/{id}/mark_read/ - 읽음 처리
# GET    /api/chat/chat-users/             - 채팅 가능 사용자 목록
# GET    /api/chat/chat-users/?department=소화기내과  - 부서별 필터링
