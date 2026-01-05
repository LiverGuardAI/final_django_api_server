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
    OrthancPatientStudiesView,
    OrthancStudySeriesView,
    OrthancSeriesNiftiView,
)

urlpatterns = [
    # DICOM 파일 업로드
    path('upload/', UploadDicomView.as_view(), name='upload_dicom'),

    # Orthanc 시스템 정보
    path('system/', OrthancSystemInfoView.as_view(), name='orthanc_system'),

    # 환자의 Studies 목록 조회 (새 API)
    path('patients/<str:patient_id>/studies/', OrthancPatientStudiesView.as_view(), name='orthanc_patient_studies'),

    # Study 관련
    path('studies/<str:study_id>/series/', OrthancStudySeriesView.as_view(), name='orthanc_study_series'),
    path('studies/<str:study_id>/', OrthancStudyView.as_view(), name='orthanc_study'),

    # Series 관련 - 더 구체적인 패턴을 먼저 배치
    path('series/<str:series_id>/instances/', OrthancSeriesInstancesView.as_view(), name='orthanc_series_instances'),
    path('series/<str:series_id>/nifti/', OrthancSeriesNiftiView.as_view(), name='orthanc_series_nifti'),
    path('series/<str:series_id>/', OrthancSeriesView.as_view(), name='orthanc_series'),
    path('series/', OrthancSeriesListView.as_view(), name='orthanc_series_list'),

    # Instance 정보 조회
    path('instances/<str:instance_id>/', OrthancInstanceView.as_view(), name='orthanc_instance'),
    path('instances/<str:instance_id>/file/', OrthancInstanceFileView.as_view(), name='orthanc_instance_file'),
]