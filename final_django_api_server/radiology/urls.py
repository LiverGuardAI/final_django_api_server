from django.urls import path
<<<<<<< Updated upstream
from .views import RadiologyDashboardView, DICOMStudyListView, WaitlistView, StartFilmingView, EndFilmingView, ImagingStatsView
=======
from .views import RadiologyDashboardView, DICOMStudyListView, WaitlistView, StartFilmingView, EndFilmingView, get_radiologist_list
>>>>>>> Stashed changes

urlpatterns = [
    path('dashboard/', RadiologyDashboardView.as_view(), name='radiology_dashboard'),
    path('studies/', DICOMStudyListView.as_view(), name='dicom_studies'),
    path('waitlist/', WaitlistView.as_view(), name='radiology_waitlist'),
    path('waitlist/start-filming/', StartFilmingView.as_view(), name='start_filming'),
    path('waitlist/end-filming/', EndFilmingView.as_view(), name='end_filming'),
<<<<<<< Updated upstream
    path('stats/', ImagingStatsView.as_view(), name='imaging_stats'),
=======
    path('list/', get_radiologist_list, name='radiologist_list'),
>>>>>>> Stashed changes
]
