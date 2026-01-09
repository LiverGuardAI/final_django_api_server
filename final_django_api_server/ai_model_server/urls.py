from django.urls import path
from .views import CreateSegmentationMaskView, SegmentationTaskStatusView, CreateFeatureExtractionView, FeatureExtractionTaskStatusView, AITaskStatusView

from .views import (BentoMLHealthView, GetFeatureInfoView, PredictStageView, PredictRelapseView, PredictSurvivalView, PredictAllView,
                    PatientRadioFeatureListView, PatientClinicalFeatureListView, PatientGenomicFeatureListView, BuildClinicalVectorView, PredictByIdsView, PredictFromPatientView,
                    SaveAnalysisResultView, PatientAnalysisHistoryView,)

urlpatterns = [
    # AI Segmentation via Mosec
    path('mosec/segmentation/create/', CreateSegmentationMaskView.as_view(), name='create_segmentation'),
    path('mosec/segmentation/status/<str:task_id>/', SegmentationTaskStatusView.as_view(), name='segmentation_status'),
    path('mosec/extract-feature/', CreateFeatureExtractionView.as_view(), name='extract_feature'),
    path('mosec/extract-feature/status/<str:task_id>/', FeatureExtractionTaskStatusView.as_view(), name='extract_feature_status'),
    
    # AI Predictive Analysis via BentoML
    path('health/', BentoMLHealthView.as_view(), name='bentoml_health'),
    path('feature-info/', GetFeatureInfoView.as_view(), name='feature_info'),
    
    path('bentoml/predict/stage/', PredictStageView.as_view(), name='predict_stage'),
    path('bentoml/predict/relapse/', PredictRelapseView.as_view(), name='predict_relapse'),
    path('bentoml/predict/survival/', PredictSurvivalView.as_view(), name='predict_survival'),
    path('bentoml/predict/all/', PredictAllView.as_view(), name='predict_all'),
    
    # Feature Vector APIs
    path('patients/<uuid:patient_id>/radio-features/', PatientRadioFeatureListView.as_view(), name='patient-radio-features'),
    path('patients/<uuid:patient_id>/clinical-features/', PatientClinicalFeatureListView.as_view(), name='patient-clinical-features'),
    path('patients/<uuid:patient_id>/genomic-features/', PatientGenomicFeatureListView.as_view(), name='patient-genomic-features'),
    # Clinical Vector Builder
    path('build-clinical-vector/', BuildClinicalVectorView.as_view(), name='build-clinical-vector'),
    # Advanced Prediction
    path('predict/by-ids/', PredictByIdsView.as_view(), name='predict-by-ids'),
    path('predict/from-patient/', PredictFromPatientView.as_view(), name='predict-from-patient'),

    # 결과 저장/조회
    path('analysis/save/', SaveAnalysisResultView.as_view(), name='analysis-save'),
    path('patients/<uuid:patient_id>/analysis-history/', PatientAnalysisHistoryView.as_view(), name='analysis-history'),
    path('task-status/<str:task_id>/', AITaskStatusView.as_view(), name='ai_task_status'),
]