from django.urls import path
from .views import (
    AdministrationDashboardView,
    PatientListView,
    PatientDetailView,
    PatientRegistrationView,
    AppointmentListView,
    AppointmentDetailView,
    EncounterListView,
    EncounterDetailView,
    WaitingQueueView,
    CallNextPatientView,
    DashboardStatsView,
)

urlpatterns = [
    # 대시보드
    path('dashboard/', AdministrationDashboardView.as_view(), name='administration_dashboard'),
    path('dashboard/stats/', DashboardStatsView.as_view(), name='dashboard_stats'),

    # 환자 관리
    path('patients/', PatientListView.as_view(), name='patient_list'),
    path('patients/<str:patient_id>/', PatientDetailView.as_view(), name='patient_detail'),
    path('patients/register/', PatientRegistrationView.as_view(), name='patient_registration'),

    # 예약 관리
    path('appointments/', AppointmentListView.as_view(), name='appointment_list'),
    path('appointments/<int:appointment_id>/', AppointmentDetailView.as_view(), name='appointment_detail'),

    # 진료 기록 (접수)
    path('encounters/', EncounterListView.as_view(), name='encounter_list'),
    path('encounters/<int:encounter_id>/', EncounterDetailView.as_view(), name='encounter_detail'),

    # 대기열 관리 (Queue + Cache)
    path('queue/waiting/', WaitingQueueView.as_view(), name='waiting_queue'),
    path('queue/call-next/', CallNextPatientView.as_view(), name='call_next_patient'),
]
