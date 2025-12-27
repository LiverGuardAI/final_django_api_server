from django.urls import path
from .views import CreateSegmentationMaskView, SegmentationTaskStatusView

urlpatterns = [
    # AI Segmentation via Mosec
    path('mosec/segmentation/create/', CreateSegmentationMaskView.as_view(), name='create_segmentation'),
    path('mosec/segmentation/status/<str:task_id>/', SegmentationTaskStatusView.as_view(), name='segmentation_status'),
]
