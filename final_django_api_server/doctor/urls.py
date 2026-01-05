from django.urls import path
from .views import DoctorDashboardView, PatientListView, DoctorListView

urlpatterns = [
    path('dashboard/', DoctorDashboardView.as_view(), name='doctor_dashboard'),
    path('patients/', PatientListView.as_view(), name='doctor_patients'),
    path('list/', DoctorListView.as_view(), name='doctor_list'),
]
