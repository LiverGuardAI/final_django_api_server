import requests
import pandas as pd
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from services.report_llm import generate_tumor_analysis_report, generate_clinical_note_suggestion
from services.report_lmstudio import generate_lmstudio_report

# 기존 팀원분이 만든 Celery Task 임포트
from .tasks import (
    process_segmentation,
    process_feature_extraction,
    process_stage_prediction,
    process_relapse_prediction,
    process_survival_prediction,
    process_all_predictions
)

# ============================================================
# [추가] 약물 검색 엔진 데이터 로드 (서버 시작 시 1회 실행)
# ============================================================
try:
    try:
        drug_db = pd.read_csv(settings.MEDICINE_MASTER_PATH, encoding='cp949')
    except:
        drug_db = pd.read_csv(settings.MEDICINE_MASTER_PATH, encoding='utf-8')
        
    drug_db = drug_db[['item_name', 'ingr_name_ko', 'ingr_name_en']].fillna('').drop_duplicates()
    print(f"✅ [AI Model Server] 약물 검색 엔진 로드 완료: {len(drug_db)}개 항목")
except Exception as e:
    print(f"❌ [AI Model Server] 약물 데이터 로드 실패: {e}")
    drug_db = pd.DataFrame(columns=['item_name', 'ingr_name_ko', 'ingr_name_en'])


# ============================================================
# AI Segmentation & Feature Extraction (Mosec)
# ============================================================

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


# ============================================================
# [추가] 약물 검색 및 DDI 분석 API (doctor/views.py에서 이동)
# ============================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def search_drugs(request):
    """약물 마스터 CSV 기반 통합 검색 API"""
    query = request.query_params.get('q', '').strip()
    if not query:
        return Response([])

    # 제품명(item_name) 또는 성분명(ko/en)에서 검색어 포함 여부 확인
    mask = (
        drug_db['item_name'].str.contains(query, case=False, na=False) |
        drug_db['ingr_name_ko'].str.contains(query, case=False, na=False) |
        drug_db['ingr_name_en'].str.contains(query, case=False, na=False)
    )
    
    # 상위 15개 결과 추출 및 전송
    results = drug_db[mask].head(15)
    data = [
        {
            "item_name": row['item_name'],
            "name_kr": row['ingr_name_ko'],
            "name_en": row['ingr_name_en']
        }
        for _, row in results.iterrows()
    ]
    return Response(data)


class DDIAnalysisView(APIView):
    """BentoML 엔진을 사용한 약물 상호작용 분석"""
    permission_classes = [AllowAny]

    def post(self, request):
        drugs = request.data.get('drugs', [])
        if len(drugs) < 2:
            return Response({"error": "최소 2개의 약물이 필요합니다."}, status=400)

        try:
            # 💡 [방어 코드] 리액트에서 객체가 오든 글자가 오든 안전하게 추출
            d1 = drugs[0]
            d2 = drugs[1]

            payload = {
                "drug_a": { 
                    "name_kr": d1.get('name_kr', d1) if isinstance(d1, dict) else d1, 
                    "name_en": d1.get('name_en', d1) if isinstance(d1, dict) else d1 
                },
                "drug_b": { 
                    "name_kr": d2.get('name_kr', d2) if isinstance(d2, dict) else d2, 
                    "name_en": d2.get('name_en', d2) if isinstance(d2, dict) else d2 
                }
            }

            # AI 서버 호출 (settings.BENTOML_SERVER_URL 사용 권장)
            # 여기서는 명확성을 위해 직접 주소를 쓰거나 settings를 활용
            target_url = f"{settings.BENTOML_SERVER_URL}/check_ddi"
            response = requests.post(target_url, json=payload, timeout=15)
            response.raise_for_status()
            
            return Response(response.json(), status=200)

        except requests.exceptions.RequestException as e:
            return Response({"error": "AI 분석 엔진이 응답하지 않습니다."}, status=503)
        except Exception as e:
            return Response({"error": f"서버 내부 오류: {str(e)}"}, status=500)
        
        
class ReportGenerateView(APIView):
    def post(self, request):
        findings = request.data  # 또는 DB에서 불러온 findings_json
        report_text = generate_tumor_analysis_report(findings)
        return Response({"report": report_text})


class LMStudioReportGenerateView(APIView):
    def post(self, request):
        payload = request.data if isinstance(request.data, dict) else {}
        content = payload.get("content") if isinstance(payload.get("content"), str) else None
        system_content = (
            payload.get("system_content") if isinstance(payload.get("system_content"), str) else None
        )
        model = payload.get("model") if isinstance(payload.get("model"), str) else None
        try:
            report_text = generate_lmstudio_report(
                payload,
                content=content,
                system_content=system_content,
                model=model,
            )
            return Response({"report": report_text})
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except requests.exceptions.RequestException as exc:
            return Response(
                {"error": "LLM 서버 요청에 실패했습니다.", "details": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as exc:
            return Response({"error": f"서버 내부 오류: {str(exc)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ClinicalNoteGenerateView(APIView):
    def post(self, request):
        payload = request.data if isinstance(request.data, dict) else {}
        if not payload:
            return Response({"error": "payload is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            suggestion = generate_clinical_note_suggestion(payload)
            return Response({"suggestion": suggestion})
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({"error": f"Server error: {str(exc)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

