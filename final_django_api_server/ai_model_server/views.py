from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from .tasks import process_segmentation

import requests
from django.conf import settings


class CreateSegmentationMaskView(APIView):
    """
    AI 모델을 사용하여 DICOM Series에 대한 Segmentation Mask를 생성하는 API
    """
    authentication_classes = [] 
    permission_classes = [AllowAny]

    def post(self, request):
        """
        SeriesInstanceUID를 받아서 Celery Task를 생성하고 AI 처리를 시작

        Request Body:
        {
            "series_id": "orthanc-series-id"
        }

        Response:
        {
            "task_id": "celery-task-id",
            "status": "pending",
            "message": "Segmentation task started"
        }
        """
        series_id = request.data.get('series_id')

        if not series_id:
            return Response({
                'error': 'series_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Celery task 시작
            task = process_segmentation.delay(series_id)

            return Response({
                'task_id': task.id,
                'status': 'pending',
                'message': 'Segmentation task started',
                'series_id': series_id
            }, status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            return Response({
                'error': 'Failed to create task',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SegmentationTaskStatusView(APIView):
    """
    Celery Task의 상태를 조회하는 API
    """
    permission_classes = [AllowAny]

    def get(self, request, task_id):
        """
        Task ID로 작업 상태 조회

        Response:
        {
            "task_id": "task-id",
            "status": "PENDING|PROGRESS|SUCCESS|FAILURE",
            "result": {...} or "error": "..."
        }
        """
        try:
            # Import inside method to avoid circular import
            from celery.result import AsyncResult

            task_result = AsyncResult(task_id)

            response_data = {
                'task_id': task_id,
                'status': task_result.state,
            }

            if task_result.state == 'PENDING':
                response_data['message'] = 'Task is waiting to be processed'
            elif task_result.state == 'PROGRESS':
                response_data['progress'] = task_result.info
            elif task_result.state == 'SUCCESS':
                response_data['result'] = task_result.result
            elif task_result.state == 'FAILURE':
                response_data['error'] = str(task_result.info)
            else:
                response_data['message'] = f'Task state: {task_result.state}'

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': 'Failed to fetch task status',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ========================
# BentoML Proxy APIs
# ========================

class BentoMLHealthView(APIView):
    """BentoML 서비스 상태 확인"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        try:
            url = f"{settings.BENTOML_SERVER_URL}/health"
            resp = requests.post(url, json={}, timeout=10)
            return Response(resp.json(), status=resp.status_code)
        except Exception as e:
            return Response(
                {"status": "error", "message": str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
            
class PredictStageView(APIView):
    """
    Task 1: 병기 예측
    
    POST /api/predict/stage/
    Body: {"clinical": [...], "ct": [...]}
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        try:
            clinical = request.data.get('clinical', [])
            ct = request.data.get('ct', [])
            
            if len(clinical) != 11:
                return Response(
                    {"error": f"clinical must have 11 features, got {len(clinical)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if len(ct) != 512:
                return Response(
                    {"error": f"ct must have 512 features, got {len(ct)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            url = f"{settings.BENTOML_SERVER_URL}/predict_stage"
            resp = requests.post(url, json={"clinical": clinical, "ct": ct}, timeout=30)
            return Response(resp.json(), status=resp.status_code)
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PredictRelapseView(APIView):
    """
    Task 2: 조기 재발 예측
    
    POST /api/predict/relapse/
    Body: {"clinical": [...], "mrna": [...], "ct": [...]}
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        try:
            clinical = request.data.get('clinical', [])
            mrna = request.data.get('mrna', [])
            ct = request.data.get('ct', [])
            
            if len(clinical) != 11:
                return Response({"error": "clinical must have 11 features"}, status=400)
            if len(mrna) != 20:
                return Response({"error": "mrna must have 20 features"}, status=400)
            if len(ct) != 512:
                return Response({"error": "ct must have 512 features"}, status=400)
            
            url = f"{settings.BENTOML_SERVER_URL}/predict_relapse"
            resp = requests.post(url, json={"clinical": clinical, "mrna": mrna, "ct": ct}, timeout=30)
            return Response(resp.json(), status=resp.status_code)
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PredictSurvivalView(APIView):
    """
    Task 3: 생존 분석
    
    POST /api/predict/survival/
    Body: {"clinical": [...], "mrna": [...], "ct": [...]}
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        try:
            clinical = request.data.get('clinical', [])
            mrna = request.data.get('mrna', [])
            ct = request.data.get('ct', [])
            
            url = f"{settings.BENTOML_SERVER_URL}/predict_survival"
            resp = requests.post(url, json={"clinical": clinical, "mrna": mrna, "ct": ct}, timeout=30)
            return Response(resp.json(), status=resp.status_code)
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PredictAllView(APIView):
    """
    전체 예측 (Task 1, 2, 3)
    
    POST /api/predict/all/
    Body: {"clinical": [...], "mrna": [...], "ct": [...]}
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        try:
            clinical = request.data.get('clinical', [])
            mrna = request.data.get('mrna', [])
            ct = request.data.get('ct', [])
            
            url = f"{settings.BENTOML_SERVER_URL}/predict_all"
            resp = requests.post(url, json={"clinical": clinical, "mrna": mrna, "ct": ct}, timeout=60)
            return Response(resp.json(), status=resp.status_code)
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
