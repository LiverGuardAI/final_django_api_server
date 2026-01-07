from django.urls import path
from .views import (
    DoctorDashboardView, PatientListView, QueueListView, UpdateEncounterStatusView,
    DoctorListView, EncounterDetailView, PatientEncounterHistoryView,
    PatientLabResultsView, PatientImagingOrdersView, PatientHCCDiagnosisView,
    DoctorInfoView
)

urlpatterns = [
    path('me/', DoctorInfoView.as_view(), name='doctor_info'),
    path('dashboard/', DoctorDashboardView.as_view(), name='doctor_dashboard'),
    path('patients/', PatientListView.as_view(), name='doctor_patients'),
    path('queue/', QueueListView.as_view(), name='doctor_queue'),
    path('encounter/<int:encounter_id>/status/', UpdateEncounterStatusView.as_view(), name='update_encounter_status'),
    path('encounter/<int:encounter_id>/', EncounterDetailView.as_view(), name='encounter_detail'),
    path('patient/<str:patient_id>/encounters/', PatientEncounterHistoryView.as_view(), name='patient_encounter_history'),
    path('patient/<str:patient_id>/lab-results/', PatientLabResultsView.as_view(), name='patient_lab_results'),
    path('patient/<str:patient_id>/imaging-orders/', PatientImagingOrdersView.as_view(), name='patient_imaging_orders'),
    path('patient/<str:patient_id>/hcc-diagnosis/', PatientHCCDiagnosisView.as_view(), name='patient_hcc_diagnosis'),
    path('list/', DoctorListView.as_view(), name='doctor_list'),
]
