from django.urls import path
from .views import UploadDicomView, OrthancSystemInfoView, OrthancStudyView, OrthancInstanceView

urlpatterns = [
    # DICOM 파일 업로드
    path('upload/', UploadDicomView.as_view(), name='upload_dicom'),

    # Orthanc 시스템 정보
    path('system/', OrthancSystemInfoView.as_view(), name='orthanc_system'),

    # Study 정보 조회
    path('studies/<str:study_id>/', OrthancStudyView.as_view(), name='orthanc_study'),

    # Instance 정보 조회
    path('instances/<str:instance_id>/', OrthancInstanceView.as_view(), name='orthanc_instance'),
]