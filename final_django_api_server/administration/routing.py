from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # ws://localhost:8000/ws/clinic/ 주소로 들어오면 연결!
    re_path(r'ws/clinic/$', consumers.ClinicConsumer.as_asgi()),
]