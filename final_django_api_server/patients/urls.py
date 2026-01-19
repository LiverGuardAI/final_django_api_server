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

    # 알러지 관련 API
    path('allergies/', views.get_allergies, name='get-allergies'),
    path('allergies/create/', views.create_allergy, name='create-allergy'),
    path('allergies/<int:allergy_id>/', views.update_allergy, name='update-allergy'),
    path('allergies/<int:allergy_id>/delete/', views.delete_allergy, name='delete-allergy'),
    path('allergies/sync/', views.sync_allergies, name='sync-allergies'),

    # 기저질환 관련 API
    path('disease-histories/', views.get_disease_histories, name='get-disease-histories'),
    path('disease-histories/create/', views.create_disease_history, name='create-disease-history'),
    path('disease-histories/<int:history_id>/', views.update_disease_history, name='update-disease-history'),
    path('disease-histories/<int:history_id>/delete/', views.delete_disease_history, name='delete-disease-history'),
    path('disease-histories/sync/', views.sync_disease_histories, name='sync-disease-histories'),

    # 진료기록 관련 API
    path('medical-records/', views.get_medical_records, name='get-medical-records'),
    path('medical-records/dates/', views.get_medical_record_dates, name='get-medical-record-dates'),
    path('medical-records/<int:record_id>/', views.get_medical_record_detail, name='get-medical-record-detail'),

    # 처방전 OCR 관련 API
    path('prescriptions/', views.get_ocr_prescriptions, name='get-ocr-prescriptions'),
    path('prescriptions/ocr/', views.create_ocr_prescription, name='create-ocr-prescription'),
    path('prescriptions/<int:pres_id>/delete/', views.delete_prescription, name='delete-prescription'),
    path('medications/current/', views.get_current_medications, name='get-current-medications'),
    path('medications/<int:med_id>/status/', views.update_medication_status, name='update-medication-status'),
]
