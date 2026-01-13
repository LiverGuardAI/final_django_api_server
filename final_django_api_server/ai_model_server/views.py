from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from .tasks import (
    process_segmentation,
    process_feature_extraction,
    process_stage_prediction,
    process_relapse_prediction,
    process_survival_prediction,
    process_all_predictions
)

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


class FeatureExtractionTaskStatusView(APIView):
    """
    Feature extraction Celery Task의 상태를 조회하는 API
    """
    permission_classes = [AllowAny]

    def get(self, request, task_id):
        """
        Task ID로 작업 상태 조회
        """
        try:
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


class CreateFeatureExtractionView(APIView):
    """
    AI 모델을 사용하여 DICOM Series 특징 추출을 수행하는 API
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        """
        SeriesInstanceUID를 받아서 Celery Task를 생성하고 AI 처리를 시작

        Request Body:
        {
            "seriesinstanceuid": "dicom-series-instance-uid"
        }

        Response:
        {
            "task_id": "celery-task-id",
            "status": "pending",
            "message": "Feature extraction task started"
        }
        """
        series_instance_uid = (
            request.data.get('seriesinstanceuid')
            or request.data.get('SeriesInstanceUID')
            or request.data.get('series_instance_uid')
        )

        if not series_instance_uid:
            return Response({
                'error': 'seriesinstanceuid is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            task = process_feature_extraction.delay(series_instance_uid)

            return Response({
                'task_id': task.id,
                'status': 'pending',
                'message': 'Feature extraction task started',
                'seriesinstanceuid': series_instance_uid
            }, status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            return Response({
                'error': 'Failed to create task',
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
    Task 1: 병기 예측 (Celery Task 사용)

    POST /api/ai/bentoml/predict/stage/
    Body: {"clinical": [11 features], "series_uid": "..."}

    Returns: {"task_id": "...", "status": "pending"}
    """
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            clinical = request.data.get('clinical', [])
            series_uid = request.data.get('series_uid') or request.data.get('seriesinstanceuid')

            if len(clinical) != 11:
                return Response(
                    {"error": f"clinical must have 11 features, got {len(clinical)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not series_uid:
                return Response(
                    {"error": "series_uid or seriesinstanceuid is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Celery task 시작
            task = process_stage_prediction.delay(clinical, series_uid)

            return Response({
                'task_id': task.id,
                'status': 'pending',
                'message': 'Stage prediction task started',
                'series_uid': series_uid
            }, status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PredictRelapseView(APIView):
    """
    Task 2: 조기 재발 예측 (Celery Task 사용)

    POST /api/ai/bentoml/predict/relapse/
    Body: {"clinical": [11 features], "mrna": [20 features], "series_uid": "..."}

    Returns: {"task_id": "...", "status": "pending"}
    """
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            clinical = request.data.get('clinical', [])
            mrna = request.data.get('mrna', [])
            series_uid = request.data.get('series_uid') or request.data.get('seriesinstanceuid')

            if len(clinical) != 11:
                return Response({"error": "clinical must have 11 features"}, status=400)
            if len(mrna) != 20:
                return Response({"error": "mrna must have 20 features"}, status=400)

            if not series_uid:
                return Response(
                    {"error": "series_uid or seriesinstanceuid is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Celery task 시작
            task = process_relapse_prediction.delay(clinical, mrna, series_uid)

            return Response({
                'task_id': task.id,
                'status': 'pending',
                'message': 'Relapse prediction task started',
                'series_uid': series_uid
            }, status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PredictSurvivalView(APIView):
    """
    Task 3: 생존 분석 (Celery Task 사용)

    POST /api/ai/bentoml/predict/survival/
    Body: {"clinical": [11 features], "mrna": [20 features], "series_uid": "..."}

    Returns: {"task_id": "...", "status": "pending"}
    """
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            clinical = request.data.get('clinical', [])
            mrna = request.data.get('mrna', [])
            series_uid = request.data.get('series_uid') or request.data.get('seriesinstanceuid')

            if len(clinical) != 11:
                return Response({"error": f"clinical must have 11 features, got {len(clinical)}"}, status=400)
            if len(mrna) != 20:
                return Response({"error": f"mrna must have 20 features, got {len(mrna)}"}, status=400)

            if not series_uid:
                return Response(
                    {"error": "series_uid or seriesinstanceuid is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Celery task 시작
            task = process_survival_prediction.delay(clinical, mrna, series_uid)

            return Response({
                'task_id': task.id,
                'status': 'pending',
                'message': 'Survival prediction task started',
                'series_uid': series_uid
            }, status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PredictAllView(APIView):
    """
    전체 예측 (Task 1, 2, 3) - Celery Task 사용

    POST /api/ai/bentoml/predict/all/
    Body: {"clinical": [11 features], "mrna": [20 features], "series_uid": "..."}

    Returns: {"task_id": "...", "status": "pending"}
    """
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            clinical = request.data.get('clinical', [])
            mrna = request.data.get('mrna', [])
            series_uid = request.data.get('series_uid') or request.data.get('seriesinstanceuid')

            if not series_uid:
                return Response(
                    {"error": "series_uid or seriesinstanceuid is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Celery task 시작
            task = process_all_predictions.delay(clinical, mrna, series_uid)

            return Response({
                'task_id': task.id,
                'status': 'pending',
                'message': 'All predictions task started',
                'series_uid': series_uid
            }, status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PredictionTaskStatusView(APIView):
    """
    BentoML 예측 Task의 상태를 조회하는 API

    GET /api/ai/bentoml/prediction/status/<task_id>/

    Response:
    {
        "task_id": "...",
        "status": "PENDING|PROGRESS|SUCCESS|FAILURE",
        "result": {...} or "error": "..."
    }
    """
    permission_classes = [AllowAny]

    def get(self, request, task_id):
        try:
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
