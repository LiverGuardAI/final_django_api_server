from django.urls import path
from .views import (
    DoctorDashboardView, PatientListView, QueueListView, UpdateEncounterStatusView,
    DoctorListView, EncounterDetailView, PatientEncounterHistoryView,
    PatientLabResultsView, PatientDoctorToRadiologyOrdersView, PatientHCCDiagnosisView,
    DoctorInfoView, DoctorMedicalRecordListView, CreateLabOrderView, CreateDoctorToRadiologyOrderView,
    PatientCTSeriesView, PatientGenomicDataView, PatientLabOrdersView
)

urlpatterns = [
    path('medical-records/', DoctorMedicalRecordListView.as_view(), name='doctor_medical_records'),
    path('me/', DoctorInfoView.as_view(), name='doctor_info'),
    path('dashboard/', DoctorDashboardView.as_view(), name='doctor_dashboard'),
    path('patients/', PatientListView.as_view(), name='doctor_patients'),
    path('queue/', QueueListView.as_view(), name='doctor_queue'),
    path('encounter/<int:encounter_id>/status/', UpdateEncounterStatusView.as_view(), name='update_encounter_status'),
    path('encounter/<int:encounter_id>/', EncounterDetailView.as_view(), name='encounter_detail'),
    path('patient/<str:patient_id>/encounters/', PatientEncounterHistoryView.as_view(), name='patient_encounter_history'),
    path('patient/<str:patient_id>/lab-results/', PatientLabResultsView.as_view(), name='patient_lab_results'),
    path('patient/<str:patient_id>/lab-orders/', PatientLabOrdersView.as_view(), name='patient_lab_orders'),
    path('patient/<str:patient_id>/doctor-to-radiology-orders/', PatientDoctorToRadiologyOrdersView.as_view(), name='patient_imaging_orders'),
    path('patient/<str:patient_id>/hcc-diagnosis/', PatientHCCDiagnosisView.as_view(), name='patient_hcc_diagnosis'),
    path('patient/<str:patient_id>/genomic-data/', PatientGenomicDataView.as_view(), name='patient_genomic_data'),
    path('patient/<str:patient_id>/ct-series/', PatientCTSeriesView.as_view(), name='patient_ct_series'),
    path('list/', DoctorListView.as_view(), name='doctor_list'),
    path('lab-orders/', CreateLabOrderView.as_view(), name='create_lab_order'),
    path('doctor-to-radiology-orders/', CreateDoctorToRadiologyOrderView.as_view(), name='create_imaging_order'),
]
