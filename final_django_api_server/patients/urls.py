# patients/urls.py
from django.urls import path
from . import views

app_name = 'patients'

urlpatterns = [
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),

    # 앱 연동 신청 관련 API
    path('app-sync-requests/', views.app_sync_request_create, name='app-sync-request-create'),
    path('app-sync-requests/verify/', views.app_sync_request_verify, name='app-sync-request-verify'),
    path('app-sync-requests/list/', views.app_sync_request_list, name='app-sync-request-list'),
    path('app-sync-requests/<int:request_id>/approve/', views.app_sync_request_approve, name='app-sync-request-approve'),
    path('app-sync-requests/<int:request_id>/reject/', views.app_sync_request_reject, name='app-sync-request-reject'),
    path('app-sync-requests/status/<int:profile_id>/', views.app_sync_request_status, name='app-sync-request-status'),
]
