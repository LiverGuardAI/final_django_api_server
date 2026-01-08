from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.permissions import AllowAny
from .tasks import process_segmentation, process_feature_extraction

from datetime import datetime
from rest_framework import generics
from .models import RadioFeatureVector, ClinicalFeatureVector, AIAnalysisResult
from .serializers import RadioFeatureSerializer, ClinicalFeatureSerializer, GenomicFeatureSerializer, AIAnalysisResultSerializer
from .feature_mapping import create_clinical_feature_vector_from_dict, validate_clinical_vector, MODEL_CLINICAL_FEATURES
from doctor.models import GenomicData

import requests
from django.conf import settings
from typing import Dict, Any


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

# 입력 차원 상수 (Feature Selection 적용)
N_CLINICAL = 9
N_MRNA = 20
N_CT = 512

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


class GetFeatureInfoView(APIView):
    """Feature 정보 조회"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        try:
            url = f"{settings.BENTOML_SERVER_URL}/get_feature_info"
            resp = requests.post(url, json={}, timeout=10)
            return Response(resp.json(), status=resp.status_code)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PredictStageView(APIView):
    """
    Task 1: 병기 예측
    
    POST /api/predict/stage/
    Body: {"clinical": [9개], "ct": [512개]}
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        try:
            clinical = request.data.get('clinical', [])
            ct = request.data.get('ct', [])
            
            if len(clinical) != N_CLINICAL:
                return Response(
                    {"error": f"clinical must have {N_CLINICAL} features (selected), got {len(clinical)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if len(ct) != N_CT:
                return Response(
                    {"error": f"ct must have {N_CT} features, got {len(ct)}"},
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
    Body: {"clinical": [9개], "mrna": [20개], "ct": [512개]}
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        try:
            clinical = request.data.get('clinical', [])
            mrna = request.data.get('mrna', [])
            ct = request.data.get('ct', [])
            
            if len(clinical) != N_CLINICAL:
                return Response(
                    {"error": f"clinical must have {N_CLINICAL} features (selected)"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if len(mrna) != N_MRNA:
                return Response(
                    {"error": f"mrna must have {N_MRNA} features (selected)"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if len(ct) != N_CT:
                return Response(
                    {"error": f"ct must have {N_CT} features"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            url = f"{settings.BENTOML_SERVER_URL}/predict_relapse"
            resp = requests.post(url, json={"clinical": clinical, "mrna": mrna, "ct": ct}, timeout=30)
            return Response(resp.json(), status=resp.status_code)
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PredictSurvivalView(APIView):
    """
    Task 3: 생존 분석
    
    POST /api/predict/survival/
    Body: {"clinical": [9개], "mrna": [20개], "ct": [512개]}
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        try:
            clinical = request.data.get('clinical', [])
            mrna = request.data.get('mrna', [])
            ct = request.data.get('ct', [])
            
            if len(clinical) != N_CLINICAL:
                return Response({"error": f"clinical must have {N_CLINICAL} features"}, status=400)
            if len(mrna) != N_MRNA:
                return Response({"error": f"mrna must have {N_MRNA} features"}, status=400)
            if len(ct) != N_CT:
                return Response({"error": f"ct must have {N_CT} features"}, status=400)
            
            url = f"{settings.BENTOML_SERVER_URL}/predict_survival"
            resp = requests.post(url, json={"clinical": clinical, "mrna": mrna, "ct": ct}, timeout=30)
            return Response(resp.json(), status=resp.status_code)
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PredictAllView(APIView):
    """
    전체 예측 (Task 1, 2, 3)
    
    POST /api/predict/all/
    Body: {"clinical": [9개], "mrna": [20개], "ct": [512개]}
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        try:
            clinical = request.data.get('clinical', [])
            mrna = request.data.get('mrna', [])
            ct = request.data.get('ct', [])
            
            # 입력 검증
            if len(clinical) != N_CLINICAL:
                return Response({"error": f"clinical must have {N_CLINICAL} features"}, status=400)
            if len(mrna) != N_MRNA:
                return Response({"error": f"mrna must have {N_MRNA} features"}, status=400)
            if len(ct) != N_CT:
                return Response({"error": f"ct must have {N_CT} features"}, status=400)
            
            url = f"{settings.BENTOML_SERVER_URL}/predict_all"
            resp = requests.post(url, json={"clinical": clinical, "mrna": mrna, "ct": ct}, timeout=60)
            return Response(resp.json(), status=resp.status_code)
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================
# Validation Helpers
# ============================================================

def validate_prediction_input(clinical: list, ct: list, mrna: list = None,
                              require_mrna: bool = False) -> tuple:
    """통일된 입력 검증"""
    
    if not clinical or len(clinical) < 5:
        return False, "clinical_vector must have at least 5 features"
    
    if not ct or len(ct) != 512:
        return False, f"ct_vector must be 512-dimensional, got {len(ct) if ct else 0}"
    
    if require_mrna and (not mrna or len(mrna) != 20):
        return False, f"mrna_vector must have 20 pathways, got {len(mrna) if mrna else 0}"
    
    return True, None


def check_date_mismatch(date1, date2, threshold_days=30) -> dict:
    """날짜 불일치 검사"""
    try:
        from datetime import date as dt_date
        
        if isinstance(date1, str):
            date1 = dt_date.fromisoformat(str(date1)[:10])
        if isinstance(date2, str):
            date2 = dt_date.fromisoformat(str(date2)[:10])
        
        diff_days = abs((date1 - date2).days)
        
        if diff_days > threshold_days:
            return {
                "mismatch": True,
                "days": diff_days,
                "warning": f"Data dates differ by {diff_days} days (>{threshold_days}). Results may be less reliable."
            }
        return {"mismatch": False, "days": diff_days, "warning": None}
    except Exception:
        return {"mismatch": False, "days": 0, "warning": None}


# ============================================================
# DB에서 Clinical Feature Vector 생성
# ============================================================

def build_clinical_vector_from_db(patient_id: str, lab_id: str = None, hcc_id: str = None) -> Dict[str, Any]:
    """
    DB 테이블에서 Clinical Feature Vector 조합
    
    순서: [AGE, SEX, GRADE, VASCULAR_INVASION, ISHAK, AFP, ALBUMIN, BILIRUBIN, PLATELET]
    
    Returns:
        {
            "vector": [9개 값],
            "source": {테이블별 ID},
            "validation": {검증 결과},
            "dates": {날짜 정보}
        }
    """
    try:
        # 환자 정보
        patient = Patient.objects.get(patient_id=patient_id)
        patient_data = {
            'age': patient.age,
            'gender': patient.gender
        }
        
        # HCC 진단 정보 (최신)
        if hcc_id:
            hcc = HccDiagnosis.objects.get(hcc_id=hcc_id)
        else:
            hcc = HccDiagnosis.objects.filter(patient_id=patient_id).order_by('-hcc_diagnosis_date').first()
        
        hcc_data = {}
        hcc_date = None
        if hcc:
            hcc_data = {
                'grade': hcc.grade,
                'vascular_invasion': hcc.vascular_invasion,
                'ishak_score': hcc.ishak_score
            }
            hcc_date = hcc.hcc_diagnosis_date
        
        # Lab 결과 (최신)
        if lab_id:
            lab = LabResults.objects.get(lab_id=lab_id)
        else:
            lab = LabResults.objects.filter(patient_id=patient_id).order_by('-test_date').first()
        
        lab_data = {}
        lab_date = None
        if lab:
            lab_data = {
                'afp': lab.afp,
                'albumin': lab.albumin,
                'bilirubin_total': lab.bilirubin_total,
                'platelet': lab.platelet
            }
            lab_date = lab.test_date
        
        # Feature Vector 생성
        vector = create_clinical_feature_vector_from_dict(patient_data, hcc_data, lab_data)
        validation = validate_clinical_vector(vector)
        
        return {
            "vector": vector,
            "source": {
                "patient_id": str(patient_id),
                "hcc_id": str(hcc.hcc_id) if hcc else None,
                "lab_id": str(lab.lab_id) if lab else None
            },
            "validation": validation,
            "dates": {
                "hcc_date": str(hcc_date) if hcc_date else None,
                "lab_date": str(lab_date) if lab_date else None
            },
            "feature_names": MODEL_CLINICAL_FEATURES
        }
        
    except Patient.DoesNotExist:
        return {"error": f"Patient {patient_id} not found"}
    except Exception as e:
        return {"error": str(e)}
    
    
# ============================================================
# Feature Vector List Views
# ============================================================

class PatientRadioFeatureListView(generics.ListAPIView):
    """환자별 CT 특징 벡터 목록"""
    serializer_class = RadioFeatureSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        patient_id = self.kwargs['patient_id']
        # series → study → patient 관계를 통해 필터링
        return RadioFeatureVector.objects.filter(
            series__study__patient_id=patient_id
        ).select_related('series', 'series__study').order_by('-created_at')


class PatientClinicalFeatureListView(generics.ListAPIView):
    """환자별 임상 특징 벡터 목록"""
    serializer_class = ClinicalFeatureSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        patient_id = self.kwargs['patient_id']
        # encounter를 통해 patient 필터링
        return ClinicalFeatureVector.objects.filter(
            encounter__patient_id=patient_id
        ).select_related('encounter').order_by('-created_at')


class PatientGenomicFeatureListView(generics.ListAPIView):
    """환자별 유전체 특징 벡터 목록"""
    serializer_class = GenomicFeatureSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        patient_id = self.kwargs['patient_id']
        return GenomicData.objects.filter(patient_id=patient_id).order_by('-created_at')


# ============================================================
# Clinical Feature Builder View (DB에서 직접 조합)
# ============================================================

class BuildClinicalVectorView(APIView):
    """
    DB에서 Clinical Feature Vector 조합
    
    POST /api/ai/build-clinical-vector/
    
    Body:
    {
        "patient_id": "uuid",
        "lab_id": "uuid" (선택),
        "hcc_id": "uuid" (선택)
    }
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        patient_id = request.data.get('patient_id')
        lab_id = request.data.get('lab_id')
        hcc_id = request.data.get('hcc_id')
        
        if not patient_id:
            return Response(
                {"error": "patient_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        result = build_clinical_vector_from_db(patient_id, lab_id, hcc_id)
        
        if "error" in result:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(result, status=status.HTTP_200_OK)


# ============================================================
# Prediction Views
# ============================================================

class PredictByIdsView(APIView):
    """
    ID 기반 예측 (DB에서 Feature Vector 조회)
    
    POST /api/ai/predict/by-ids/
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        radio_id = request.data.get('radio_vector_id')
        clinical_id = request.data.get('clinical_vector_id')
        genomic_id = request.data.get('genomic_id')
        
        if not radio_id or not clinical_id:
            return Response(
                {"error": "radio_vector_id and clinical_vector_id are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # DB 조회
            radio = RadioFeatureVector.objects.select_related(
                'series', 'series__study'
            ).get(radio_vector_id=radio_id)
            
            clinical = ClinicalFeatureVector.objects.select_related(
                'encounter'
            ).get(clinical_vector_id=clinical_id)
            
            # 날짜 추출
            radio_date = radio.series.study.study_datetime.date() if radio.series and radio.series.study else None
            clinical_date = clinical.encounter.encounter_date if clinical.encounter else None
            date_check = check_date_mismatch(radio_date, clinical_date) if radio_date and clinical_date else {}
            
            # mRNA 처리
            mrna_vector = None
            use_mrna = False
            genomic_date = None
            
            if genomic_id:
                genomic_obj = GenomicData.objects.get(genomic_id=genomic_id)
                mrna_vector = genomic_obj.pathway_scores 
                use_mrna = True
        except GenomicData.DoesNotExist:
            pass
            
            # BentoML 요청
            bentoml_payload = {
                "clinical": clinical.feature_vector,
                "ct_features": radio.feature_vector,
                "mrna": mrna_vector,
                "use_mrna": use_mrna
            }
            if use_mrna and mrna_vector:
                bentoml_payload["mrna"] = mrna_vector
            
            response = requests.post(f"http://localhost:3001/predict", json=bentoml_payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            # 입력 요약
            result['input_summary'] = {
                'radio_vector_id': str(radio_id),
                'radio_study_date': str(radio_date) if radio_date else None,
                'clinical_vector_id': str(clinical_id),
                'clinical_date': str(clinical_date) if clinical_date else None,
                'genomic_id': str(genomic_id) if genomic_id else None,
                'genomic_sample_date': str(genomic_date) if genomic_date else None,
                'use_mrna': use_mrna
            }
            
            if date_check.get('warning'):
                result['warnings'] = result.get('warnings', {})
                result['warnings']['date_mismatch'] = date_check
            
            return Response(result, status=status.HTTP_200_OK)
            
        except RadioFeatureVector.DoesNotExist:
            return Response({"error": f"RadioFeatureVector {radio_id} not found"}, status=status.HTTP_404_NOT_FOUND)
        except ClinicalFeatureVector.DoesNotExist:
            return Response({"error": f"ClinicalFeatureVector {clinical_id} not found"}, status=status.HTTP_404_NOT_FOUND)
        except requests.exceptions.RequestException as e:
            return Response({"error": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class PredictFromPatientView(APIView):
    """
    환자 ID로 직접 예측 (DB에서 모든 데이터 자동 조합)
    
    POST /api/ai/predict/from-patient/
    
    Body:
    {
        "patient_id": "uuid",
        "radio_vector_id": "uuid" (필수),
        "lab_id": "uuid" (선택, 없으면 최신),
        "hcc_id": "uuid" (선택, 없으면 최신),
        "genomic_id": "uuid" (선택, mRNA 사용 시)
    }
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        patient_id = request.data.get('patient_id')
        radio_vector_id = request.data.get('radio_vector_id')
        lab_id = request.data.get('lab_id')
        hcc_id = request.data.get('hcc_id')
        genomic_id = request.data.get('genomic_id')
        
        if not patient_id or not radio_vector_id:
            return Response(
                {"error": "patient_id and radio_vector_id are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # CT Feature Vector 조회
            radio = RadioFeatureVector.objects.get(radio_vector_id=radio_vector_id)
            ct_vector = radio.feature_vector
            
            # Clinical Vector 조합 (DB에서)
            clinical_result = build_clinical_vector_from_db(patient_id, lab_id, hcc_id)
            if "error" in clinical_result:
                return Response(clinical_result, status=status.HTTP_400_BAD_REQUEST)
            
            clinical_vector = clinical_result['vector']
            
            # mRNA Vector (선택)
            mrna_vector = None
            use_mrna = False
            if genomic_id:
                try:
                    genomic = GenomicData.objects.get(genomic_id=genomic_id)
                    mrna_vector = genomic.pathway_scores
                    use_mrna = True
                except GenomicData.DoesNotExist:
                    pass
            
            # BentoML 요청
            bentoml_payload = {
                "clinical": clinical_vector,
                "ct_features": ct_vector,
                "use_mrna": use_mrna
            }
            if use_mrna and mrna_vector:
                bentoml_payload["mrna"] = mrna_vector
            
            response = requests.post("http://localhost:3001/predict", json=bentoml_payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            # 메타데이터 추가
            result['input_summary'] = {
                'patient_id': str(patient_id),
                'radio_vector_id': str(radio_vector_id),
                'clinical_source': clinical_result['source'],
                'clinical_validation': clinical_result['validation'],
                'use_mrna': use_mrna,
                'genomic_id': str(genomic_id) if genomic_id else None
            }
            
            return Response(result, status=status.HTTP_200_OK)
            
        except RadioFeatureVector.DoesNotExist:
            return Response({"error": f"RadioFeatureVector {radio_vector_id} not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Prediction error: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================
# Analysis Result Views
# ============================================================

class SaveAnalysisResultView(APIView):
    """AI 분석 결과 저장"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        try:
            result = AIAnalysisResult.objects.create(
                patient_id=request.data['patient_id'],
                imaging_vector_id=request.data.get('radio_vector_id'),
                clinical_vector_id=request.data.get('clinical_vector_id'),
                genomic_id=request.data.get('genomic_vector_id'),
                prediction_results={
                    'stage': request.data.get('stage_prediction', {}),
                    'relapse': request.data.get('relapse_prediction', {}),
                    'survival': request.data.get('survival_prediction', {})
                },
                risk_score=request.data.get('survival_prediction', {}).get('risk_score'),
                risk_group=request.data.get('survival_prediction', {}).get('risk_group'),
                model_version=request.data.get('model_version', 'v11.6'),
                status='completed',
                completed_at=datetime.now()
            )
            
            return Response(
                {"result_id": str(result.result_id), "message": "Saved successfully"},
                status=status.HTTP_201_CREATED
            )
        except KeyError as e:
            return Response({"error": f"Missing field: {e}"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class PatientAnalysisHistoryView(generics.ListAPIView):
    """환자별 AI 분석 이력"""
    serializer_class = AIAnalysisResultSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        patient_id = self.kwargs['patient_id']
        return AIAnalysisResult.objects.filter(patient_id=patient_id).order_by('-created_at')
