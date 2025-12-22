from django.urls import path
from .views import DoctorDashboardView, PatientListView

urlpatterns = [
    path('dashboard/', DoctorDashboardView.as_view(), name='doctor_dashboard'),
    path('patients/', PatientListView.as_view(), name='doctor_patients'),
]
