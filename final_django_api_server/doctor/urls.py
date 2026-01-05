from django.urls import path
from .views import DoctorDashboardView, PatientListView, QueueListView, UpdateEncounterStatusView, DoctorListView

urlpatterns = [
    path('dashboard/', DoctorDashboardView.as_view(), name='doctor_dashboard'),
    path('patients/', PatientListView.as_view(), name='doctor_patients'),
    path('queue/', QueueListView.as_view(), name='doctor_queue'),
    path('encounter/<int:encounter_id>/status/', UpdateEncounterStatusView.as_view(), name='update_encounter_status'),
    path('list/', DoctorListView.as_view(), name='doctor_list'),
]
