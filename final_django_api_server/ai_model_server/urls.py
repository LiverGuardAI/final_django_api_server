from django.urls import path
from .views import CreateSegmentationMaskView, SegmentationTaskStatusView

from .views import BentoMLHealthView, PredictStageView, PredictRelapseView, PredictSurvivalView, PredictAllView


urlpatterns = [
    # AI Segmentation via Mosec
    path('mosec/segmentation/create/', CreateSegmentationMaskView.as_view(), name='create_segmentation'),
    path('mosec/segmentation/status/<str:task_id>/', SegmentationTaskStatusView.as_view(), name='segmentation_status'),
    
    # AI Predictive Analysis via BentoML
    # Health check
    path('health/', BentoMLHealthView.as_view(), name='bentoml_health'),
    
    path('predict/stage/', PredictStageView.as_view(), name='predict_stage'),
    path('predict/relapse/', PredictRelapseView.as_view(), name='predict_relapse'),
    path('predict/survival/', PredictSurvivalView.as_view(), name='predict_survival'),
    path('predict/all/', PredictAllView.as_view(), name='predict_all'),
]
