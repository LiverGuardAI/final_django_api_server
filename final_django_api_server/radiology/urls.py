from django.urls import path
from .views import RadiologyDashboardView, DICOMStudyListView, WaitlistView, StartFilmingView

urlpatterns = [
    path('dashboard/', RadiologyDashboardView.as_view(), name='radiology_dashboard'),
    path('studies/', DICOMStudyListView.as_view(), name='dicom_studies'),
    path('waitlist/', WaitlistView.as_view(), name='radiology_waitlist'),
    path('waitlist/start-filming/', StartFilmingView.as_view(), name='start_filming'),
]
