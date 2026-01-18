from django.urls import path
from .views import CreateSegmentationMaskView, ReportGenerateView, LMStudioReportGenerateView, SegmentationTaskStatusView, CreateFeatureExtractionView, FeatureExtractionTaskStatusView, ClinicalNoteGenerateView

from .views import BentoMLHealthView, PredictStageView, PredictRelapseView, PredictSurvivalView, PredictAllView, PredictionTaskStatusView, search_drugs, DDIAnalysisView

urlpatterns = [
    # AI Segmentation via Mosec
    path('mosec/segmentation/create/', CreateSegmentationMaskView.as_view(), name='create_segmentation'),
    path('mosec/segmentation/status/<str:task_id>/', SegmentationTaskStatusView.as_view(), name='segmentation_status'),
    path('mosec/extract-feature/', CreateFeatureExtractionView.as_view(), name='extract_feature'),
    path('mosec/extract-feature/status/<str:task_id>/', FeatureExtractionTaskStatusView.as_view(), name='extract_feature_status'),
    
    # AI Predictive Analysis via BentoML
    # Health check
    path('health/', BentoMLHealthView.as_view(), name='bentoml_health'),
    
    path('bentoml/predict/stage/', PredictStageView.as_view(), name='predict_stage'),
    path('bentoml/predict/relapse/', PredictRelapseView.as_view(), name='predict_relapse'),
    path('bentoml/predict/survival/', PredictSurvivalView.as_view(), name='predict_survival'),
    path('bentoml/predict/all/', PredictAllView.as_view(), name='predict_all'),
    path('bentoml/prediction/status/<str:task_id>/', PredictionTaskStatusView.as_view(), name='prediction_status'),
    path('bentoml/drugs/search/', search_drugs, name='search_drugs'),
    path('bentoml/ddi/analyze/', DDIAnalysisView.as_view(), name='ddi_analyze'),
    
    # open api view
    path('openapi/ct-report/generate/', ReportGenerateView.as_view(), name='ct_report_generate'),
    path('openapi/clinical-note/generate/', ClinicalNoteGenerateView.as_view(), name='clinical_note_generate'),
    path('lmstudio/ct-report/generate/', LMStudioReportGenerateView.as_view(), name='lmstudio_ct_report_generate'),
]
