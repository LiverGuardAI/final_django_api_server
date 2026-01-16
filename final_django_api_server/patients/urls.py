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
    
    # 진료 예약 관련 API
    path('departments/', views.get_departments, name='get-departments'),
    path('doctors/', views.get_doctors, name='get-doctors'),
    path('doctors/available-dates/', views.get_doctor_available_dates, name='get-doctor-available-dates'),
    path('appointments/available-slots/', views.get_available_time_slots, name='get-available-time-slots'),
    path('appointments/', views.create_appointment, name='create-appointment'),
    path('appointments/status/', views.check_appointment_status, name='check-appointment-status'),
    path('appointments/list/', views.get_appointments, name='get-appointments'),
    path('appointments/<int:appointment_id>/approve/', views.approve_appointment, name='approve-appointment'),
    path('appointments/<int:appointment_id>/reject/', views.reject_appointment, name='reject-appointment'),

    # 문진표 관련 API
    path('questionnaire/', views.create_questionnaire, name='create-questionnaire'),
    path('questionnaire/get/', views.get_questionnaire, name='get-questionnaire'),

    # 대기열 상태 조회 API
    path('queue/status/', views.get_queue_status, name='get-queue-status'),
]
