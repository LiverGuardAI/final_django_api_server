from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from accounts.permissions import IsDoctor
from .models import Encounter, MedicalRecord, Patient, Doctor, LabResult, DoctorToRadiologyOrder, HCCDiagnosis
from .serializers import (
    EncounterSerializer, MedicalRecordSerializer, UpdateEncounterStatusSerializer, DoctorListSerializer,
    MedicalRecordDetailSerializer, LabResultSerializer, DoctorToRadiologyOrderSerializer,
    HCCDiagnosisSerializer
)
from datetime import date, datetime
from django.utils import timezone


class DoctorDashboardView(APIView):
    """의사 전용 대시보드 API"""
    permission_classes = [IsDoctor]

    def get(self, request):
        user = request.user

        # 오늘 날짜
        today = date.today()

        # 대기 환자 (진료 대기)
        clinic_waiting = Encounter.objects.filter(
            created_at__date=today,
            workflow_state=Encounter.WorkflowState.WAITING_CLINIC
        ).count()

        # 진료 중 환자
        clinic_in_progress = Encounter.objects.filter(
            created_at__date=today,
            workflow_state=Encounter.WorkflowState.IN_CLINIC
        ).count()

        # 완료 환자
        completed_today = Encounter.objects.filter(
            created_at__date=today,
            workflow_state=Encounter.WorkflowState.COMPLETED
        ).count()

        return Response({
            'message': f'안녕하세요, {user.first_name} 의사님',
            'user': {
                'id': user.id,
                'username': user.username,
                'role': user.role,
                'first_name': user.first_name,
                'last_name': user.last_name,
            },
            'stats': {
                'total_patients': clinic_waiting + clinic_in_progress + completed_today,
                'clinic_waiting': clinic_waiting,
                'clinic_in_progress': clinic_in_progress,
                'completed_today': completed_today,
            }
        }, status=status.HTTP_200_OK)


class PatientListView(APIView):
    """의사의 환자 목록 조회 API"""
    permission_classes = [IsDoctor]

    def get(self, request):
        # 실제로는 DB에서 환자 목록을 가져와야 함
        return Response({
            'message': '환자 목록',
            'patients': []  # 실제 환자 데이터로 대체 필요
        }, status=status.HTTP_200_OK)


class QueueListView(APIView):
    """의사의 환자 대기열 조회 API (Encounter 기반)"""
    permission_classes = [IsDoctor]

    def get(self, request):
        try:
            # 오늘 날짜
            today = date.today()

            # 쿼리 파라미터로 상태 필터링 (기본값: WAITING_CLINIC)
            encounter_status = request.query_params.get('status', 'WAITING_CLINIC')
            doctor_id = request.query_params.get('doctor_id')

            # Encounter 조회
            encounters = Encounter.objects.filter(
                created_at__date=today
            )
            
            # 의사별 필터링
            if doctor_id:
                encounters = encounters.filter(assigned_doctor_id=doctor_id)

            # 상태별 필터링
            if encounter_status == 'ALL':
                # 모든 상태
                pass
            else:
                encounters = encounters.filter(workflow_state=encounter_status)

            # state_entered_at 순 정렬 (FIFO)
            encounters = encounters.order_by('state_entered_at')

            # Serialize
            serializer = EncounterSerializer(encounters, many=True)

            # 통계 정보
            # 통계 정보 (필터링 적용된 기준)
            base_qs = Encounter.objects.filter(created_at__date=today)
            if doctor_id:
                base_qs = base_qs.filter(assigned_doctor_id=doctor_id)

            waiting_count = base_qs.filter(
                workflow_state=Encounter.WorkflowState.WAITING_CLINIC
            ).count()

            in_progress_count = base_qs.filter(
                workflow_state=Encounter.WorkflowState.IN_CLINIC
            ).count()

            completed_count = base_qs.filter(
                workflow_state=Encounter.WorkflowState.COMPLETED
            ).count()

            return Response({
                'encounters': serializer.data,
                'stats': {
                    'waiting': waiting_count,
                    'in_progress': in_progress_count,
                    'completed': completed_count,
                    'total': waiting_count + in_progress_count + completed_count
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UpdateEncounterStatusView(APIView):
    """Encounter 상태 변경 API (진료 시작/완료 등)"""
    permission_classes = [IsDoctor]

    def patch(self, request, encounter_id):
        try:
            # 해당 Encounter 조회
            encounter = Encounter.objects.get(encounter_id=encounter_id)

            # 요청 데이터 검증
            serializer = UpdateEncounterStatusSerializer(data=request.data)
            if serializer.is_valid():
                # 워크플로우 상태 변경 (backward compatibility: 'status' 필드도 허용)
                new_workflow_state = serializer.validated_data.get('workflow_state') or serializer.validated_data.get('status')

                if new_workflow_state:
                    # 워크플로우 상태 설정
                    encounter.workflow_state = new_workflow_state
                    encounter.state_entered_at = timezone.now()

                    # FHIR 레벨 status 자동 설정
                    if new_workflow_state in [Encounter.WorkflowState.REQUESTED, Encounter.WorkflowState.REGISTERED]:
                        encounter.status = Encounter.Status.PLANNED
                    elif new_workflow_state in [Encounter.WorkflowState.WAITING_CLINIC, Encounter.WorkflowState.IN_CLINIC,
                                                Encounter.WorkflowState.WAITING_IMAGING, Encounter.WorkflowState.IN_IMAGING]:
                        encounter.status = Encounter.Status.IN_PROGRESS
                    elif new_workflow_state == Encounter.WorkflowState.COMPLETED:
                        encounter.status = Encounter.Status.COMPLETED
                    elif new_workflow_state == Encounter.WorkflowState.CANCELLED:
                        encounter.status = Encounter.Status.CANCELLED

                    # 완료 시간 자동 설정
                    if new_workflow_state == Encounter.WorkflowState.COMPLETED and not encounter.end_time:
                        encounter.end_time = timezone.now()

                # 위치 변경
                if 'current_location' in serializer.validated_data:
                    encounter.current_location = serializer.validated_data['current_location']

                encounter.save()

                # 업데이트된 데이터 반환
                response_serializer = EncounterSerializer(encounter)
                return Response({
                    'message': '상태가 변경되었습니다.',
                    'encounter': response_serializer.data
                }, status=status.HTTP_200_OK)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Encounter.DoesNotExist:
            return Response({
                'error': '해당 방문 기록을 찾을 수 없습니다.'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DoctorListView(APIView):
    """의사 목록 조회 API (원무과 환자 접수용)"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        모든 의사 목록 조회

        Query params:
        - department: 부서 ID로 필터링 (선택)
        """
        try:
            doctors = Doctor.objects.select_related('department').all()

            # 부서별 필터링
            department_id = request.query_params.get('department', None)
            if department_id:
                doctors = doctors.filter(department_id=department_id)

            serializer = DoctorListSerializer(doctors, many=True)

            return Response({
                'count': doctors.count(),
                'results': serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MedicalRecordDetailView(APIView):
    """MedicalRecord 상세 정보 조회 API"""
    permission_classes = [IsDoctor]

    def get(self, request, record_id):
        try:
            # 1. 현재 로그인한 의사 정보 가져오기
            current_doctor = Doctor.objects.get(user=request.user)

            # 2. MedicalRecord 조회
            medical_record = MedicalRecord.objects.select_related(
                'patient', 'doctor', 'staff', 'diagnosis_type', 'encounter'
            ).get(record_id=record_id)

            # 3. 권한 검사
            if medical_record.doctor and medical_record.doctor.doctor_id != current_doctor.doctor_id:
                return Response({
                    'error': '본인의 진료 기록이 아닙니다.'
                }, status=status.HTTP_403_FORBIDDEN)

            # 4. 데이터 반환
            serializer = MedicalRecordDetailSerializer(medical_record)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Doctor.DoesNotExist:
            return Response({'error': '의사 정보를 찾을 수 없습니다.'}, status=404)
        except MedicalRecord.DoesNotExist:
            return Response({'error': '해당 진료 기록을 찾을 수 없습니다.'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class EncounterDetailView(APIView):
    """Encounter 상세 정보 조회 API"""
    permission_classes = [IsDoctor]

    def get(self, request, encounter_id):
        try:
            encounter = Encounter.objects.get(encounter_id=encounter_id)
            serializer = EncounterSerializer(encounter)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Encounter.DoesNotExist:
            return Response({'error': '해당 방문 기록을 찾을 수 없습니다.'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class PatientMedicalRecordHistoryView(APIView):
    """특정 환자의 과거 진료 기록 목록 조회 API"""
    permission_classes = [IsDoctor]

    def get(self, request, patient_id):
        """
        특정 환자의 과거 진료 기록 목록 조회
        """
        try:
            medical_records = MedicalRecord.objects.filter(
                patient_id=patient_id
            ).select_related('doctor', 'staff', 'diagnosis_type', 'encounter').order_by('-record_date', '-record_time')

            # 최근 N개만 조회 (선택적)
            limit = request.query_params.get('limit', None)
            if limit:
                medical_records = medical_records[:int(limit)]

            serializer = MedicalRecordDetailSerializer(medical_records, many=True)
            return Response({
                'count': medical_records.count(),
                'results': serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Backward compatibility alias
PatientEncounterHistoryView = PatientMedicalRecordHistoryView


class PatientLabResultsView(APIView):
    """특정 환자의 혈액 검사 결과 목록 조회 API"""
    permission_classes = [IsDoctor]

    def get(self, request, patient_id):
        """
        특정 환자의 혈액 검사 결과 목록 조회
        """
        try:
            lab_results = LabResult.objects.filter(
                patient_id=patient_id
            ).order_by('-test_date')

            # 최근 N개만 조회 (선택적)
            limit = request.query_params.get('limit', None)
            if limit:
                lab_results = lab_results[:int(limit)]

            serializer = LabResultSerializer(lab_results, many=True)
            return Response({
                'count': lab_results.count(),
                'results': serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PatientDoctorToRadiologyOrdersView(APIView):
    """특정 환자의 영상 검사 오더 목록 조회 API (의사 -> 영상의학과)"""
    permission_classes = [IsDoctor]

    def get(self, request, patient_id):
        """
        특정 환자의 영상 검사 오더 목록 조회
        """
        try:
            imaging_orders = DoctorToRadiologyOrder.objects.filter(
                patient_id=patient_id
            ).select_related('doctor').order_by('-ordered_at')

            # 최근 N개만 조회 (선택적)
            limit = request.query_params.get('limit', None)
            if limit:
                imaging_orders = imaging_orders[:int(limit)]

            serializer = DoctorToRadiologyOrderSerializer(imaging_orders, many=True)
            return Response({
                'count': imaging_orders.count(),
                'results': serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PatientHCCDiagnosisView(APIView):
    """특정 환자의 HCC 진단 정보 조회 API"""
    permission_classes = [IsDoctor]

    def get(self, request, patient_id):
        """
        특정 환자의 HCC 진단 정보 조회
        """
        try:
            hcc_diagnoses = HCCDiagnosis.objects.filter(
                patient_id=patient_id
            ).order_by('-hcc_diagnosis_date')

            serializer = HCCDiagnosisSerializer(hcc_diagnoses, many=True)
            return Response({
                'count': hcc_diagnoses.count(),
                'results': serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DoctorInfoView(APIView):
    """현재 로그인한 의사 정보 조회 API"""
    permission_classes = [IsDoctor]

    def get(self, request):
        """
        현재 로그인한 의사의 상세 정보 조회
        """
        try:
            doctor = Doctor.objects.select_related('department').get(user=request.user)
            serializer = DoctorListSerializer(doctor)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Doctor.DoesNotExist:
            return Response({
                'error': '의사 정보를 찾을 수 없습니다.'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
