from django.urls import path
from .views import (
    RadiologyDashboardView,
    DICOMStudyListView,
    WaitlistView,
    StartFilmingView,
    EndFilmingView,
    ImagingStatsView,
    TumorAnalysisView,
    CTReportCreateView,
)

urlpatterns = [
    path('dashboard/', RadiologyDashboardView.as_view(), name='radiology_dashboard'),
    path('studies/', DICOMStudyListView.as_view(), name='dicom_studies'),
    path('waitlist/', WaitlistView.as_view(), name='radiology_waitlist'),
    path('waitlist/start-filming/', StartFilmingView.as_view(), name='start_filming'),
    path('waitlist/end-filming/', EndFilmingView.as_view(), name='end_filming'),
    path('stats/', ImagingStatsView.as_view(), name='imaging_stats'),
    path('tumor-analysis/', TumorAnalysisView.as_view(), name='tumor_analysis'),
    path('ct-reports/', CTReportCreateView.as_view(), name='ct_report_create'),
]
