from django.urls import path
from .views import (
    UploadDicomView,
    OrthancSystemInfoView,
    OrthancStudyView,
    OrthancInstanceView,
    OrthancSeriesListView,
    OrthancSeriesView,
    OrthancSeriesInstancesView,
    OrthancInstanceFileView,
)

urlpatterns = [
    # DICOM 파일 업로드
    path('upload/', UploadDicomView.as_view(), name='upload_dicom'),

    # Orthanc 시스템 정보
    path('system/', OrthancSystemInfoView.as_view(), name='orthanc_system'),

    # Study 정보 조회
    path('studies/<str:study_id>/', OrthancStudyView.as_view(), name='orthanc_study'),

    # Series 관련
    path('series/', OrthancSeriesListView.as_view(), name='orthanc_series_list'),
    path('series/<str:series_id>/', OrthancSeriesView.as_view(), name='orthanc_series'),
    path('series/<str:series_id>/instances/', OrthancSeriesInstancesView.as_view(), name='orthanc_series_instances'),

    # Instance 정보 조회
    path('instances/<str:instance_id>/', OrthancInstanceView.as_view(), name='orthanc_instance'),
    path('instances/<str:instance_id>/file/', OrthancInstanceFileView.as_view(), name='orthanc_instance_file'),
]