from django.urls import path
from .views import CreateLabResultView, CreateGenomicDataView

urlpatterns = [
    path('patient/<str:patient_id>/lab-results/', CreateLabResultView.as_view(), name='lis_create_lab_result'),
    path('patient/<str:patient_id>/genomic-data/', CreateGenomicDataView.as_view(), name='lis_create_genomic_data'),
]
