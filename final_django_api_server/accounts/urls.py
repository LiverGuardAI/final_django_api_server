from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import LoginView, LogoutView, DoctorLoginView, AdministrationLoginView, RadiologyLoginView

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('doctor/login/', DoctorLoginView.as_view(), name='doctor_login'),
    path('administration/login/', AdministrationLoginView.as_view(), name='administration_login'),
    path('radiology/login/', RadiologyLoginView.as_view(), name='radiology_login'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),
]
