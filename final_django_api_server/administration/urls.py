from django.urls import path
from .views import AdministrationDashboardView, PatientRegistrationView

urlpatterns = [
    path('dashboard/', AdministrationDashboardView.as_view(), name='administration_dashboard'),
    path('patients/register/', PatientRegistrationView.as_view(), name='patient_registration'),
]
