import os
import django
from django.core.asgi import get_asgi_application

# 환경변수 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'liverguard_api_server.settings')
django.setup()

from urllib.parse import parse_qs
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from channels.db import database_sync_to_async

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import administration.routing  # 라우팅 파일 import

@database_sync_to_async
def get_user(user_id):
    try:
        return get_user_model().objects.get(id=user_id)
    except:
        return AnonymousUser()

class JwtAuthMiddleware:
    """
    WebSocket 연결 시 쿼리 스트링(?token=...)에서 JWT 토큰을 추출하여 인증하는 미들웨어
    """
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        try:
            # 1. 쿼리 스트링 파싱
            query_string = scope.get('query_string', b'').decode()
            params = parse_qs(query_string)
            token = params.get('token', [None])[0]

            if token:
                # 2. SimpleJWT AccessToken 객체 생성 (자동으로 서명/만료 검증 수행)
                # settings.py의 설정을 따르므로 안전함
                validated_token = AccessToken(token) 
                
                # 3. 유저 조회
                user_id = validated_token['user_id']
                if user_id:
                    scope['user'] = await get_user(user_id)
        except (InvalidToken, TokenError, Exception) as e:
            # 인증 실패 시 기존 AuthMiddlewareStack의 결과(AnonymousUser 등)를 따름
            # print(f"WebSocket JWT Auth Failed: {e}") 
            pass

        return await self.inner(scope, receive, send)

application = ProtocolTypeRouter({
    # 1. 일반 http 요청은 Django가 처리
    "http": get_asgi_application(),

    # 2. websocket 요청은 Channels가 처리
    "websocket": AuthMiddlewareStack(
        JwtAuthMiddleware(
            URLRouter(
                administration.routing.websocket_urlpatterns
            )
        )
    ),
})