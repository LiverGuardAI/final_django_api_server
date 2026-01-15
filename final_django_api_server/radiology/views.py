from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from django.db.models import Q
from django.utils import timezone
from accounts.permissions import IsRadiologist, IsDoctorOrRadiologist
from doctor.models import Patient, Encounter
from .serializers import PatientWaitlistSerializer, RadiologyQueueSerializer, EncounterWaitlistSerializer


class RadiologyDashboardView(APIView):
    """영상의학과 전용 대시보드 API"""
    permission_classes = [IsRadiologist]

    def get(self, request):
        user = request.user

        return Response({
            'message': f'안녕하세요, {user.first_name} 영상의학과',
            'user': {
                'id': user.user_id,
                'username': user.username,
                'role': user.role,
                'first_name': user.first_name,
                'last_name': user.last_name,
            },
            'stats': {
                'total_studies': 0,  # 실제 데이터로 대체 필요
                'pending_ai_analysis': 0,
                'today_scans': 0,
            }
        }, status=status.HTTP_200_OK)


class DICOMStudyListView(APIView):
    """DICOM 스터디 목록 조회 API (의사와 영상의학과 모두 접근 가능)"""
    permission_classes = [IsDoctorOrRadiologist]

    def get(self, request):
        # 실제로는 DB에서 DICOM 스터디 목록을 가져와야 함
        return Response({
            'message': 'DICOM 스터디 목록',
            'studies': []  # 실제 스터디 데이터로 대체 필요
        }, status=status.HTTP_200_OK)


class WaitlistView(APIView):
    """촬영 대기 환자 목록 조회 API (영상의학과 전용)"""
    permission_classes = [AllowAny]  # TODO: 나중에 IsRadiologist로 변경 필요

    def get(self, request):
        """
        Encounter.workflow_state가 'WAITING_IMAGING' 또는 'IN_IMAGING'인 환자 목록 조회
        - Redis 캐싱 적용 (5초 TTL)
        - DoctorToRadiologyOrder 처방 정보 포함
        - 대기 시간 계산
        """
        from administration.cache_manager import cache_manager
        from django.utils import timezone
        import json

        # Redis 캐시 키 (administration과 동일한 키 사용)
        cache_key = 'waiting_queue_list:imaging'

        # 1. 캐시 확인
        cached_data = cache_manager.redis_client.get(cache_key)
        if cached_data:
            return Response(json.loads(cached_data), status=status.HTTP_200_OK)

        # 2. 캐시 미스: DB 조회
        encounters = Encounter.objects.filter(
            workflow_state__in=[
                Encounter.WorkflowState.WAITING_IMAGING,
                Encounter.WorkflowState.IN_IMAGING,
            ]
        ).select_related('patient', 'assigned_doctor')\
         .prefetch_related('doctortoradiologyorder_set')\
         .order_by('state_entered_at')  # FIFO (오래된 순)

        # 3. 영상의학과 전용 상세 정보 구성
        queue_data = []
        now = timezone.now()

        for enc in encounters:
            # 처방 정보 수집
            imaging_orders = enc.doctortoradiologyorder_set.filter(
                status__in=['WAITING', 'IN_PROGRESS']
            )

            orders_info = [
                {
                    'order_id': order.order_id,
                    'modality': order.modality,
                    'body_part': order.body_part or 'N/A',
                    'priority': order.priority,
                    'status': order.status,
                    'ordered_at': order.ordered_at.isoformat() if order.ordered_at else None,
                }
                for order in imaging_orders
            ]

            # 대기 시간 계산 (분 단위)
            waiting_minutes = int((now - enc.state_entered_at).total_seconds() / 60) if enc.state_entered_at else 0

            queue_data.append({
                'encounter_id': enc.encounter_id,
                'patient_id': enc.patient.patient_id,
                'patient_name': enc.patient.name,
                'age': enc.patient.age,
                'gender': enc.patient.gender,
                'workflow_state': enc.workflow_state,
                'workflow_state_display': enc.get_workflow_state_display(),
                'state_entered_at': enc.state_entered_at.isoformat() if enc.state_entered_at else None,
                'waiting_minutes': waiting_minutes,
                'doctor_name': enc.assigned_doctor.name if enc.assigned_doctor else 'N/A',
                'imaging_orders': orders_info,
            })

        # 통계 정보
        stats = {
            'waiting': cache_manager.get_waiting_count('imaging'),
            'in_progress': cache_manager.get_in_progress_count('imaging'),
        }

        response_data = {
            'success': True,
            'message': '촬영 대기 환자 목록',
            'count': len(queue_data),
            'stats': stats,
            'patients': queue_data
        }

        # 4. Redis 캐싱 (5초)
        try:
            cache_manager.redis_client.setex(cache_key, 5, json.dumps(response_data))
        except Exception as e:
            print(f"Cache write failed: {e}")

        return Response(response_data, status=status.HTTP_200_OK)


class StartFilmingView(APIView):
    """환자 촬영 시작 API - 환자 상태를 '촬영중'으로 변경"""
    permission_classes = [AllowAny]  # TODO: 나중에 IsRadiologist로 변경 필요

    def post(self, request):
        """
        Encounter.workflow_state를 'IN_IMAGING'으로 업데이트

        Request Body:
        {
            "patient_id": "TCGA-BC-4073"
        }
        """
        patient_id = request.data.get('patient_id')

        if not patient_id:
            return Response({
                'error': 'patient_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            encounter = Encounter.objects.filter(
                patient__patient_id=patient_id,
                workflow_state__in=[
                    Encounter.WorkflowState.WAITING_IMAGING,
                    Encounter.WorkflowState.IN_IMAGING,
                ],
            ).order_by('-state_entered_at').first()

            if not encounter:
                return Response({
                    'error': f'Encounter for patient {patient_id} not found'
                }, status=status.HTTP_404_NOT_FOUND)

            # 상태 업데이트 (통합 메서드 사용 - Redis 자동 업데이트)
            encounter.transition_to(Encounter.WorkflowState.IN_IMAGING)

            # 오더 상태 변경
            from doctor.models import DoctorToRadiologyOrder
            imaging_orders = DoctorToRadiologyOrder.objects.filter(
                encounter=encounter,
                status__in=['WAITING', 'REQUESTED']
            )
            imaging_orders.update(status='IN_PROGRESS')

            # 캐시 무효화
            from administration.cache_manager import cache_manager
            cache_manager.redis_client.delete('waiting_queue_list:imaging')

            # WebSocket 알림
            from administration.views import send_queue_update_websocket
            send_queue_update_websocket(
                message=f"촬영 시작: {encounter.patient.name}",
                extra_data={
                    "queue_type": "imaging",
                    "imaging_waiting": cache_manager.get_waiting_count('imaging'),
                    "imaging_in_progress": cache_manager.get_in_progress_count('imaging'),
                }
            )

            # 업데이트된 환자 정보 직렬화
            serializer = EncounterWaitlistSerializer(encounter)

            return Response({
                'message': '촬영이 시작되었습니다',
                'patient': serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EndFilmingView(APIView):
    """환자 촬영 종료 API - 환자 상태를 '촬영완료'로 변경"""
    permission_classes = [AllowAny]  # TODO: 나중에 IsRadiologist로 변경 필요

    def post(self, request):
        """
        Encounter.workflow_state를 'COMPLETED'로 업데이트

        Request Body:
        {
            "patient_id": "TCGA-BC-4073"
        }
        """
        patient_id = request.data.get('patient_id')

        if not patient_id:
            return Response({
                'error': 'patient_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            encounter = Encounter.objects.filter(
                patient__patient_id=patient_id,
                workflow_state__in=[
                    Encounter.WorkflowState.WAITING_IMAGING,
                    Encounter.WorkflowState.IN_IMAGING,
                ],
            ).order_by('-state_entered_at').first()

            if not encounter:
                return Response({
                    'error': f'Encounter for patient {patient_id} not found'
                }, status=status.HTTP_404_NOT_FOUND)

            # 오더 완료 처리
            from doctor.models import DoctorToRadiologyOrder, LabOrder
            imaging_orders = DoctorToRadiologyOrder.objects.filter(
                encounter=encounter,
                status='IN_PROGRESS'
            )
            imaging_orders.update(status='COMPLETED')

            # **FIX**: 촬영 완료 후 다음 단계 결정
            # 1. 다른 IMAGING 오더(WAITING 상태)가 남아있는지 확인
            has_waiting_imaging = DoctorToRadiologyOrder.objects.filter(
                encounter=encounter,
                status='WAITING'
            ).exists()

            # 2. REQUESTED 상태 오더가 있는지 확인 (아직 접수 안 된 오더)
            has_requested_orders = (
                LabOrder.objects.filter(encounter=encounter, status='REQUESTED').exists() or
                DoctorToRadiologyOrder.objects.filter(encounter=encounter, status='REQUESTED').exists()
            )

            if has_waiting_imaging:
                # 다른 촬영 오더(접수 완료)가 남아있으면 촬영 대기로 유지
                encounter.transition_to(Encounter.WorkflowState.WAITING_IMAGING)
                print(f"INFO: 촬영 완료했지만 다른 IMAGING 오더 대기 중: {encounter.encounter_id}")
            elif has_requested_orders:
                # 아직 접수 안 된 오더가 있으면 원무과로 복귀
                encounter.transition_to(Encounter.WorkflowState.REGISTERED)
                print(f"INFO: 촬영 완료 후 미접수 오더 있음 → 원무과 복귀: {encounter.encounter_id}")
            else:
                # 모든 오더 완료 → 결과 대기 (환자 귀가)
                encounter.transition_to(Encounter.WorkflowState.WAITING_RESULTS)
                print(f"INFO: 모든 촬영 완료 → 결과 대기: {encounter.encounter_id}")

            # 캐시 무효화 (상태에 따라 적절한 캐시 삭제)
            from administration.cache_manager import cache_manager
            cache_manager.redis_client.delete('waiting_queue_list:imaging')

            if encounter.workflow_state == Encounter.WorkflowState.WAITING_RESULTS:
                # 결과대기는 clinic queue에도 포함
                cache_manager.redis_client.delete('waiting_queue_list:clinic')
            elif encounter.workflow_state == Encounter.WorkflowState.REGISTERED:
                # 원무과로 복귀한 경우 admin queue 무효화
                cache_manager.redis_client.delete('waiting_queue_list:admin')

            # WebSocket 알림 (상태에 맞는 메시지 전송)
            from administration.views import send_queue_update_websocket

            if encounter.workflow_state == Encounter.WorkflowState.WAITING_IMAGING:
                ws_message = f"촬영 완료: {encounter.patient.name} (다른 촬영 대기)"
                response_message = '촬영이 종료되었습니다. 다른 촬영 오더가 대기 중입니다.'
            elif encounter.workflow_state == Encounter.WorkflowState.REGISTERED:
                ws_message = f"촬영 완료: {encounter.patient.name} (원무과 복귀 - 미접수 오더 있음)"
                response_message = '촬영이 종료되었습니다. 접수되지 않은 오더가 있어 원무과로 복귀합니다.'
            else:  # WAITING_RESULTS
                ws_message = f"촬영 완료: {encounter.patient.name} (결과 대기 - 귀가 가능)"
                response_message = '촬영이 종료되었습니다. 모든 검사가 완료되어 결과 대기 중입니다. 환자 귀가 가능합니다.'

            send_queue_update_websocket(
                message=ws_message,
                extra_data={
                    "queue_type": "imaging",
                    "imaging_waiting": cache_manager.get_waiting_count('imaging'),
                    "imaging_in_progress": cache_manager.get_in_progress_count('imaging'),
                }
            )

            # 업데이트된 환자 정보 직렬화
            serializer = EncounterWaitlistSerializer(encounter)

            return Response({
                'success': True,
                'message': response_message,
                'patient': serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== 영상의학과 의사 목록 API ====================
@api_view(['GET'])
@permission_classes([AllowAny])
def get_radiologist_list(request):
    """
    영상의학과 의사 목록 조회 API

    GET /api/radiology/list/
    """
    from .models import Radiology

    radiologists = Radiology.objects.select_related('department').all().order_by('name')
    
    radiologist_list = []
    for radiologist in radiologists:
        radiologist_list.append({
            'radiologic_id': radiologist.radiologic_id,
            'name': radiologist.name,
            'department': {
                'dept_name': radiologist.department.dept_name if radiologist.department else '영상의학과'
            },
            'phone': radiologist.phone,
        })
    
    return Response({
        'success': True,
        'results': radiologist_list
    }, status=status.HTTP_200_OK)
<<<<<<< Updated upstream


class ImagingStatsView(APIView):
    """영상의학과 통계 API"""
    permission_classes = [AllowAny]  # TODO: 나중에 IsRadiologist로 변경 필요

    def get(self, request):
        """
        영상의학과 대기열 및 검사 통계 조회
        - 실시간 대기/진행 인원
        - 오늘 촬영 건수
        - 평균 대기 시간
        """
        from administration.cache_manager import cache_manager
        from django.utils import timezone
        from django.db.models import Count, Avg
        from datetime import timedelta

        today = timezone.localdate()
        now = timezone.now()

        # Redis 실시간 카운터
        waiting_count = cache_manager.get_waiting_count('imaging')
        in_progress_count = cache_manager.get_in_progress_count('imaging')

        # 오늘 촬영 완료 건수
        from doctor.models import DoctorToRadiologyOrder
        today_completed = DoctorToRadiologyOrder.objects.filter(
            status='COMPLETED',
            ordered_at__date=today
        ).count()

        # 현재 대기 중인 환자들의 평균 대기 시간
        waiting_encounters = Encounter.objects.filter(
            workflow_state=Encounter.WorkflowState.WAITING_IMAGING
        )

        if waiting_encounters.exists():
            total_waiting_seconds = sum([
                (now - enc.state_entered_at).total_seconds()
                for enc in waiting_encounters
                if enc.state_entered_at
            ])
            avg_waiting_minutes = int(total_waiting_seconds / 60 / waiting_encounters.count())
        else:
            avg_waiting_minutes = 0

        # 오늘 촬영 중인 환자들의 평균 촬영 시간
        today_imaging = Encounter.objects.filter(
            workflow_state=Encounter.WorkflowState.IN_IMAGING,
            state_entered_at__date=today
        )

        if today_imaging.exists():
            total_imaging_seconds = sum([
                (now - enc.state_entered_at).total_seconds()
                for enc in today_imaging
                if enc.state_entered_at
            ])
            avg_imaging_minutes = int(total_imaging_seconds / 60 / today_imaging.count())
        else:
            avg_imaging_minutes = 0

        return Response({
            'success': True,
            'stats': {
                'current': {
                    'waiting': waiting_count,
                    'in_progress': in_progress_count,
                    'avg_waiting_minutes': avg_waiting_minutes,
                },
                'today': {
                    'completed_count': today_completed,
                    'avg_imaging_minutes': avg_imaging_minutes,
                },
            }
        }, status=status.HTTP_200_OK)
=======
>>>>>>> Stashed changes
