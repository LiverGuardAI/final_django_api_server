from django.urls import path
from . import views

urlpatterns = [
    path('native-app-key/', views.get_native_app_key, name='kakao_native_app_key'),
    path('map/', views.get_map_html, name='kakao_map_html'),
]
