import os
import django
from django.core.asgi import get_asgi_application

# 환경변수 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'liverguard_api_server.settings')
django.setup()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import administration.routing  # 라우팅 파일 import

application = ProtocolTypeRouter({
    # 1. 일반 http 요청은 Django가 처리
    "http": get_asgi_application(),

    # 2. websocket 요청은 Channels가 처리
    "websocket": AuthMiddlewareStack(
        URLRouter(
            administration.routing.websocket_urlpatterns
        )
    ),
})