from django.urls import path
from .views import (
    RadiologyDashboardView,
    DICOMStudyListView,
    DICOMStudySeriesView,
    PostProcessingActiveView,
    WaitlistView,
    StartFilmingView,
    EndFilmingView,
    ImagingStatsView,
    TumorAnalysisView,
    CTReportCreateView,
    get_radiologist_list,
)

urlpatterns = [
    path('dashboard/', RadiologyDashboardView.as_view(), name='radiology_dashboard'),
    path('studies/', DICOMStudyListView.as_view(), name='dicom_studies'),
    path('studies/<str:study_uid>/series/', DICOMStudySeriesView.as_view(), name='dicom_study_series'),
    path('post-processing/active/', PostProcessingActiveView.as_view(), name='post_processing_active'),
    path('waitlist/', WaitlistView.as_view(), name='radiology_waitlist'),
    path('waitlist/start-filming/', StartFilmingView.as_view(), name='start_filming'),
    path('waitlist/end-filming/', EndFilmingView.as_view(), name='end_filming'),
    path('stats/', ImagingStatsView.as_view(), name='imaging_stats'),
    path('tumor-analysis/', TumorAnalysisView.as_view(), name='tumor_analysis'),
    path('ct-reports/', CTReportCreateView.as_view(), name='ct_report_create'),
    path('list/', get_radiologist_list, name='radiologist_list'),
]
