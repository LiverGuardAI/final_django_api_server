from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # ws://localhost:8000/ws/chat/ 주소로 채팅 WebSocket 연결
    re_path(r'ws/chat/$', consumers.ChatConsumer.as_asgi()),
]
