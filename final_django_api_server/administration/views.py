from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from accounts.permissions import IsClerk
from doctor.models import Patient, Appointment, Encounter
from .serializers import (
    PatientSerializer,
    AppointmentSerializer,
    AppointmentCreateSerializer,
    EncounterSerializer,
    EncounterCreateSerializer,
)
from django.db.models import Q, Count
from datetime import date, datetime
from .cache_manager import cache_manager
from django.db import transaction
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


def send_queue_update_websocket(message="대기열이 업데이트되었습니다.", extra_data=None):
    """
    WebSocket을 통해 대기열 변경 알림을 전송하는 헬퍼 함수

    Args:
        message: 전송할 메시지
        extra_data: 추가 데이터 (dict)
    """
    try:
        waiting_count = cache_manager.get_waiting_count('clinic')
        in_progress_count = cache_manager.get_in_progress_count('clinic')

        channel_layer = get_channel_layer()
        data = {
            "waiting_count": waiting_count,
            "in_progress_count": in_progress_count,
        }

        if extra_data:
            data.update(extra_data)

        async_to_sync(channel_layer.group_send)(
            "clinic_dashboard",
            {
                "type": "update_queue",
                "message": message,
                "data": data
            }
        )
    except Exception as e:
        print(f"!!! WebSocket 전송 실패: {e}")


class AdministrationDashboardView(APIView):
    """원무과 전용 대시보드 API"""
    permission_classes = [IsClerk]

    def get(self, request):
        user = request.user
        today = date.today()

        # 오늘 등록된 환자 수
        today_registrations = Patient.objects.filter(created_at__date=today).count()

        # 대기 중인 예약 수
        pending_appointments = Appointment.objects.filter(
            status='대기',
            appointment_date__gte=today
        ).count()

        # 오늘 진료 수
        today_encounters = Encounter.objects.filter(start_time__date=today).count()

        return Response({
            'message': f'안녕하세요, {user.first_name} 원무과',
            'user': {
                'id': user.id,
                'username': user.username,
                'role': user.role,
                'first_name': user.first_name,
                'last_name': user.last_name,
            },
            'stats': {
                'today_registrations': today_registrations,
                'pending_appointments': pending_appointments,
                'today_encounters': today_encounters,
            }
        }, status=status.HTTP_200_OK)


class PatientListView(APIView):
    """환자 목록 조회 API"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # 검색 쿼리
        search = request.query_params.get('search', '')

        # 페이지네이션 파라미터
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))

        # 환자 쿼리 (Patient 모델에는 doctor 필드가 없으므로 select_related 제거)
        patients = Patient.objects.all()

        if search:
            patients = patients.filter(
                Q(patient_id__icontains=search) |
                Q(name__icontains=search)
            )

        # 총 개수 먼저 계산
        total_count = patients.count()

        # 정렬 및 페이지네이션
        patients = patients.order_by('-created_at')
        start = (page - 1) * page_size
        end = start + page_size
        patients = patients[start:end]

        serializer = PatientSerializer(patients, many=True)

        return Response({
            'count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size,
            'results': serializer.data
        }, status=status.HTTP_200_OK)


class PatientDetailView(APIView):
    """환자 상세 정보 조회 및 수정 API"""
    permission_classes = [IsAuthenticated]

    def get(self, request, patient_id):
        try:
            patient = Patient.objects.get(patient_id=patient_id)
            serializer = PatientSerializer(patient)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Patient.DoesNotExist:
            return Response(
                {'error': '환자를 찾을 수 없습니다.'},
                status=status.HTTP_404_NOT_FOUND
            )

    def patch(self, request, patient_id):
        try:
            patient = Patient.objects.get(patient_id=patient_id)
            serializer = PatientSerializer(patient, data=request.data, partial=True)

            if serializer.is_valid():
                serializer.save()
                return Response({
                    'message': '환자 정보가 수정되었습니다.',
                    'patient': serializer.data
                }, status=status.HTTP_200_OK)

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Patient.DoesNotExist:
            return Response(
                {'error': '환자를 찾을 수 없습니다.'},
                status=status.HTTP_404_NOT_FOUND
            )


class PatientRegistrationView(APIView):
    """환자 등록 API (원무과 전용)"""
    permission_classes = [IsClerk]

    def post(self, request):
        serializer = PatientSerializer(data=request.data)

        if serializer.is_valid():
            patient = serializer.save(staff=request.user)
            return Response({
                'message': '환자 등록 완료',
                'patient': PatientSerializer(patient).data
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AppointmentListView(APIView):
    """예약 목록 조회 API"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # 필터 옵션
        status_filter = request.query_params.get('status', None)
        date_filter = request.query_params.get('date', None)
        patient_id = request.query_params.get('patient_id', None)

        appointments = Appointment.objects.select_related('patient', 'doctor')

        if status_filter:
            appointments = appointments.filter(status=status_filter)

        if date_filter:
            appointments = appointments.filter(appointment_date=date_filter)

        if patient_id:
            appointments = appointments.filter(patient_id=patient_id)

        appointments = appointments.order_by('-appointment_date', '-appointment_time')
        serializer = AppointmentSerializer(appointments, many=True)

        return Response({
            'count': appointments.count(),
            'results': serializer.data
        }, status=status.HTTP_200_OK)

    def post(self, request):
        """예약 생성"""
        serializer = AppointmentCreateSerializer(data=request.data)

        if serializer.is_valid():
            appointment = serializer.save()
            return Response({
                'message': '예약이 등록되었습니다.',
                'appointment': AppointmentSerializer(appointment).data
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AppointmentDetailView(APIView):
    """예약 상세 조회/수정/삭제 API"""
    permission_classes = [IsAuthenticated]

    def get(self, request, appointment_id):
        try:
            appointment = Appointment.objects.get(appointment_id=appointment_id)
            serializer = AppointmentSerializer(appointment)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Appointment.DoesNotExist:
            return Response(
                {'error': '예약을 찾을 수 없습니다.'},
                status=status.HTTP_404_NOT_FOUND
            )

    def put(self, request, appointment_id):
        try:
            appointment = Appointment.objects.get(appointment_id=appointment_id)
            serializer = AppointmentSerializer(appointment, data=request.data, partial=True)

            if serializer.is_valid():
                serializer.save()
                return Response({
                    'message': '예약이 수정되었습니다.',
                    'appointment': serializer.data
                }, status=status.HTTP_200_OK)

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Appointment.DoesNotExist:
            return Response(
                {'error': '예약을 찾을 수 없습니다.'},
                status=status.HTTP_404_NOT_FOUND
            )

    def delete(self, request, appointment_id):
        try:
            appointment = Appointment.objects.get(appointment_id=appointment_id)
            appointment.delete()
            return Response(
                {'message': '예약이 취소되었습니다.'},
                status=status.HTTP_200_OK
            )
        except Appointment.DoesNotExist:
            return Response(
                {'error': '예약을 찾을 수 없습니다.'},
                status=status.HTTP_404_NOT_FOUND
            )


class EncounterListView(APIView):
    """진료 기록 목록 조회 API"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        patient_id = request.query_params.get('patient_id', None)
        encounters = Encounter.objects.select_related('patient', 'assigned_doctor')

        if patient_id:
            encounters = encounters.filter(patient_id=patient_id)

        encounters = encounters.order_by('-start_time')
        serializer = EncounterSerializer(encounters, many=True)

        return Response({
            'count': encounters.count(),
            'results': serializer.data
        }, status=status.HTTP_200_OK)

    def post(self, request):
        """
        환자 접수 API (Encounter 생성)
        트랜잭션 적용
        """
        serializer = EncounterCreateSerializer(data=request.data)

        if serializer.is_valid():
            try:
                with transaction.atomic():
                    # 1. 중복 접수 체크: 이미 진행 중인 방문이 있는지 확인
                    patient_id = request.data.get('patient')
                    existing_encounter = Encounter.objects.filter(
                        patient_id=patient_id,
                        status__in=[
                            Encounter.EncounterStatus.REGISTERED,
                            Encounter.EncounterStatus.WAITING_CLINIC,
                            Encounter.EncounterStatus.IN_CLINIC,
                            Encounter.EncounterStatus.WAITING_IMAGING,
                            Encounter.EncounterStatus.IN_IMAGING
                        ]
                    ).first()

                    if existing_encounter:
                        return Response({
                            'success': False,
                            'message': f'해당 환자는 이미 진행 중인 방문이 있습니다. (상태: {existing_encounter.get_status_display()})'
                        }, status=status.HTTP_400_BAD_REQUEST)

                    # 2. Encounter 생성 (접수)
                    initial_workflow_state = serializer.validated_data.get('workflow_state', Encounter.WorkflowState.REGISTERED)
                    
                    # 의사 직접 배정 (assigned_doctor_id 저장)
                    save_kwargs = {
                        'status': Encounter.Status.PLANNED,
                        'workflow_state': initial_workflow_state,
                        'start_time': datetime.now(),
                        'assigned_doctor_id': request.data.get('doctor') # 직접 배정
                    }
                    
                    encounter = serializer.save(**save_kwargs)

                    # 3. Redis 대기 카운트 증가
                    # 바로 진료 대기 상태로 접수된 경우 카운트 증가
                    if initial_workflow_state == Encounter.WorkflowState.WAITING_CLINIC:
                         cache_manager.increment_waiting_count('clinic')

                # 4. Redis 캐시 무효화
                cache_manager.redis_client.delete('waiting_queue_list')

                # 5. WebSocket 알림
                send_queue_update_websocket(
                    message=f"새로운 환자 접수: {encounter.patient.name}",
                    extra_data={
                        "new_encounter": {
                            "patient_name": encounter.patient.name,
                            "patient_id": encounter.patient.patient_id
                        }
                    }
                )

                return Response({
                    'success': True,
                    'message': '접수가 완료되었습니다.',
                    'encounter': EncounterSerializer(encounter).data
                }, status=status.HTTP_201_CREATED)

            except Exception as e:
                print(f"!!! 접수 트랜잭션 롤백됨: {e}")
                return Response({
                    'success': False,
                    'message': '시스템 오류로 접수가 처리되지 않았습니다.',
                    'error': str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EncounterDetailView(APIView):
    """진료 기록 상세 조회 및 수정 API"""
    permission_classes = [IsAuthenticated]

    def get(self, request, encounter_id):
        try:
            encounter = Encounter.objects.get(encounter_id=encounter_id)
            serializer = EncounterSerializer(encounter)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Encounter.DoesNotExist:
            return Response(
                {'error': '진료 기록을 찾을 수 없습니다.'},
                status=status.HTTP_404_NOT_FOUND
            )

    def patch(self, request, encounter_id):
        """방문 세션 상태 변경 (Encounter)"""
        try:
            encounter = Encounter.objects.get(encounter_id=encounter_id)
            old_workflow_state = encounter.workflow_state
            updated = False

            # 워크플로우 상태 변경
            new_workflow_state = None

            # 1. Frontend API (encounter_status) - 우선 처리
            encounter_status = request.data.get('encounter_status')
            if encounter_status:
                if encounter_status == 'IN_PROGRESS':
                    new_workflow_state = Encounter.WorkflowState.IN_CLINIC
                elif encounter_status == 'IN_CLINIC':
                    new_workflow_state = Encounter.WorkflowState.IN_CLINIC
                elif encounter_status == 'WAITING':
                    new_workflow_state = Encounter.WorkflowState.WAITING_CLINIC
                elif encounter_status == 'COMPLETED':
                    new_workflow_state = Encounter.WorkflowState.COMPLETED
                elif encounter_status == 'CANCELLED':
                    new_workflow_state = Encounter.WorkflowState.CANCELLED
                elif encounter_status == 'WAITING_RESULTS':
                    new_workflow_state = Encounter.WorkflowState.WAITING_RESULTS

            # 2. Internal / Legacy (workflow_state, status) - Fallback
            if not new_workflow_state:
                new_workflow_state = request.data.get('workflow_state') or request.data.get('status')

            if new_workflow_state:
                encounter.workflow_state = new_workflow_state
                encounter.state_entered_at = datetime.now()  # 상태 진입 시간 갱신

                # FHIR 레벨 status 자동 설정
                if new_workflow_state in [Encounter.WorkflowState.REQUESTED, Encounter.WorkflowState.REGISTERED]:
                    encounter.status = Encounter.Status.PLANNED
                elif new_workflow_state in [Encounter.WorkflowState.WAITING_CLINIC, Encounter.WorkflowState.IN_CLINIC,
                                            Encounter.WorkflowState.WAITING_IMAGING, Encounter.WorkflowState.IN_IMAGING,
                                            Encounter.WorkflowState.WAITING_RESULTS]:
                    encounter.status = Encounter.Status.IN_PROGRESS
                elif new_workflow_state == Encounter.WorkflowState.COMPLETED:
                    encounter.status = Encounter.Status.COMPLETED
                elif new_workflow_state == Encounter.WorkflowState.CANCELLED:
                    encounter.status = Encounter.Status.CANCELLED

                updated = True

                # 완료/취소 시 종료 시간 기록
                if new_workflow_state in [Encounter.WorkflowState.COMPLETED, Encounter.WorkflowState.CANCELLED]:
                    encounter.end_time = datetime.now()

                # Redis 카운트 업데이트
                if old_workflow_state == Encounter.WorkflowState.WAITING_CLINIC and new_workflow_state == Encounter.WorkflowState.IN_CLINIC:
                    cache_manager.decrement_waiting_count('clinic')
                    cache_manager.increment_in_progress_count('clinic')
                elif old_workflow_state == Encounter.WorkflowState.IN_CLINIC and new_workflow_state == Encounter.WorkflowState.COMPLETED:
                    cache_manager.decrement_in_progress_count('clinic')

            # 위치 변경
            if 'current_location' in request.data:
                encounter.current_location = request.data['current_location']
                updated = True

            # 문진표 데이터 처리
            questionnaire_data = request.data.get('questionnaire_data')
            questionnaire_status = request.data.get('questionnaire_status')
            
            if questionnaire_data is not None or questionnaire_status is not None:
                from doctor.models import Questionnaire
                
                # 기존 문진표 가져오기 또는 생성
                questionnaire, created = Questionnaire.objects.get_or_create(
                    encounter=encounter,
                    defaults={
                        'patient': encounter.patient,
                        'status': Questionnaire.QStatus.NOT_STARTED,
                        'data': {}
                    }
                )
                
                if questionnaire_data is not None:
                    # null인 경우 (삭제 요청) 처리
                    if questionnaire_data is None: 
                         questionnaire.data = {}
                    else:
                         questionnaire.data = questionnaire_data
                    updated = True
                    
                if questionnaire_status:
                    questionnaire.status = questionnaire_status
                    updated = True
                    
                questionnaire.save()

            if updated:
                encounter.save()

                # 캐시 무효화
                cache_manager.redis_client.delete('waiting_queue_list')

                # WebSocket 알림
                send_queue_update_websocket(
                    message=f"환자 상태 변경: {encounter.patient.name} ({encounter.get_status_display()})",
                    extra_data={
                        "updated_encounter": {
                            "id": encounter.encounter_id,
                            "patient_name": encounter.patient.name,
                            "status": encounter.status
                        }
                    }
                )

                return Response(
                    {
                        'message': '방문 상태가 업데이트되었습니다.',
                        'encounter': EncounterSerializer(encounter).data
                    },
                    status=status.HTTP_200_OK
                )

            return Response(
                {'error': '수정할 데이터가 없습니다.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Encounter.DoesNotExist:
            return Response(
                {'error': '방문 기록을 찾을 수 없습니다.'},
                status=status.HTTP_404_NOT_FOUND
            )


class WaitingQueueView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        max_count = int(request.query_params.get('max_count', 50))
        limit = int(request.query_params.get('limit', 50))
        doctor_id = request.query_params.get('doctor_id')

        # Cache key depends on doctor_id to isolate queues
        if doctor_id:
            cache_key = f'waiting_queue_list:doctor_{doctor_id}'
        else:
            cache_key = 'waiting_queue_list:all'

        cached_queue = cache_manager.redis_client.get(cache_key)

        if cached_queue:
            # 캐시된 데이터 반환
            import json
            queue_data = json.loads(cached_queue)
            return Response({
                'success': True,
                'stats': {
                    'waiting': cache_manager.get_waiting_count('clinic'),
                },
                'queue': queue_data[:max_count]
            }, status=status.HTTP_200_OK)

        # 캐시 미스: DB에서 조회 후 Redis에 저장 (state_entered_at 기준 FIFO)
        # 캐시 미스: DB에서 조회 후 Redis에 저장 (state_entered_at 기준 FIFO)
        from django.db.models import Q
        from django.utils import timezone
        
        # 기본 대기열 상태: 대기중, 진료중
        filter_condition = Q(workflow_state__in=[
            Encounter.WorkflowState.WAITING_CLINIC,
            Encounter.WorkflowState.IN_CLINIC
        ])

        # 오늘 완료된 진료는 항상 포함 (의사 사이드바 및 원무과 대기현황용)
        today = timezone.localdate()
        filter_condition = filter_condition | Q(
             workflow_state=Encounter.WorkflowState.COMPLETED,
             updated_at__date=today
        )

        queryset = Encounter.objects.filter(filter_condition).select_related('patient', 'assigned_doctor').order_by('state_entered_at')
        
        if doctor_id:
             try:
                 # Encounter에 직접 배정된 의사 정보로 필터링
                 queryset = queryset.filter(assigned_doctor_id=int(doctor_id))
             except ValueError:
                 pass

        waiting_encounters = queryset[:max_count]

        serializer = EncounterSerializer(waiting_encounters, many=True)
        queue_data = serializer.data

        # Redis에 5초간 캐싱
        import json
        cache_manager.redis_client.setex(cache_key, 5, json.dumps(queue_data))

        return Response({
            'success': True,
            'stats': {
                'waiting': cache_manager.get_waiting_count('clinic'),
            },
            'queue': queue_data
        }, status=status.HTTP_200_OK)


class CallNextPatientView(APIView):
    """다음 환자 호출 API"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        다음 대기 환자 호출 (DB 기반)

        Returns:
        - 다음 환자 정보
        - Encounter를 IN_CLINIC으로 변경
        - Redis 카운트 조정
        """
        # 1. DB에서 가장 오래 대기 중인 환자 가져오기 (FIFO - state_entered_at 기준)
        encounter = Encounter.objects.filter(
            workflow_state=Encounter.WorkflowState.WAITING_CLINIC
        ).select_related('patient').order_by('state_entered_at').first()

        if not encounter:
            return Response({
                'success': False,
                'message': '대기 중인 환자가 없습니다.'
            }, status=status.HTTP_200_OK)

        # 2. Encounter 상태 업데이트
        encounter.status = Encounter.Status.IN_PROGRESS
        encounter.workflow_state = Encounter.WorkflowState.IN_CLINIC
        encounter.state_entered_at = datetime.now()
        encounter.save()

        # 3. Redis 카운트 업데이트
        cache_manager.decrement_waiting_count('clinic')
        cache_manager.increment_in_progress_count('clinic')

        # 4. Redis 캐시 무효화 (대기열 변경)
        cache_manager.redis_client.delete('waiting_queue_list')

        # 5. WebSocket으로 실시간 알림 전송
        send_queue_update_websocket(
            message=f"환자 호출: {encounter.patient.name}",
            extra_data={
                "called_patient": {
                    "name": encounter.patient.name,
                    "id": encounter.patient.patient_id
                }
            }
        )

        # 6. 현재 통계 조회
        waiting_count = cache_manager.get_waiting_count('clinic')
        in_progress_count = cache_manager.get_in_progress_count('clinic')

        return Response({
            'success': True,
            'message': f'다음 환자: {encounter.patient.name}',
            'patient': {
                'patient_id': encounter.patient.patient_id,
                'name': encounter.patient.name,
                'age': encounter.patient.age,
                'gender': encounter.patient.gender,
            },
            'encounter': EncounterSerializer(encounter).data,
            'stats': {
                'waiting': waiting_count,
                'in_progress': in_progress_count
            }
        }, status=status.HTTP_200_OK)


class DashboardStatsView(APIView):
    """실시간 대시보드 통계 API"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        실시간 대시보드 통계 조회 (Redis 캐시 사용)

        Returns:
        - 진료실, 촬영실, 검사실 대기/진행 인원
        """
        # 전체 통계
        stats = cache_manager.get_dashboard_stats()

        return Response({
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'stats': stats
        }, status=status.HTTP_200_OK)

class PendingOrdersView(APIView):
    """
    모든 미처리 오더(검사 대기) 목록 조회 API ("추가진료" 탭용)
    - LabOrder (REQUESTED)
    - DoctorToRadiologyOrder (REQUESTED)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            from doctor.models import LabOrder, DoctorToRadiologyOrder
            from django.utils import timezone

            today_start = timezone.localtime(timezone.now()).replace(hour=0, minute=0, second=0, microsecond=0)
            
            # 1. Lab Orders (REQUESTED) - 오늘 날짜 기준
            lab_orders = LabOrder.objects.filter(
                status='REQUESTED',
                created_at__gte=today_start
            ).select_related('patient', 'doctor', 'doctor__department').order_by('-created_at')

            # 2. Imaging Orders (REQUESTED) - 오늘 날짜 기준
            imaging_orders = DoctorToRadiologyOrder.objects.filter(
                status='REQUESTED',
                ordered_at__gte=today_start
            ).select_related('patient', 'doctor', 'doctor__department').order_by('-ordered_at')

            results = []

            # Lab Order 변환
            for order in lab_orders:
                results.append({
                    'id': f'lab_{order.order_id}',
                    'type': 'LAB',
                    'type_display': '진단검사',
                    'order_name': order.get_order_type_display(),
                    'patient_id': order.patient.patient_id,
                    'patient_name': order.patient.name,
                    'doctor_name': order.doctor.name,
                    'department_name': order.doctor.department.dept_name if order.doctor.department else 'N/A',
                    'created_at': order.created_at,
                    'status': order.status,
                    'status_display': '검사대기'
                })

            # Imaging Order 변환
            for order in imaging_orders:
                results.append({
                    'id': f'img_{order.order_id}',
                    'type': 'IMAGING',
                    'type_display': '영상의학',
                    'order_name': f"{order.modality} ({order.body_part or '전신'})",
                    'patient_id': order.patient.patient_id,
                    'patient_name': order.patient.name,
                    'doctor_name': order.doctor.name,
                    'department_name': order.doctor.department.dept_name if order.doctor.department else 'N/A',
                    'created_at': order.ordered_at,
                    'status': order.status,
                    'status_display': '촬영대기'
                })

            # 최신순 정렬 (created_at 기준)
            results.sort(key=lambda x: x['created_at'], reverse=True)

            return Response({
                'count': len(results),
                'results': results
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ConfirmOrderView(APIView):
    """
    오더 접수 및 처리 API (관리자용)
    - 오더 상태 변경 (REQUESTED -> WAITING/IN_PROGRESS)
    - 선택적 귀가 조치 (Encounter -> COMPLETED)
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, order_id):
        try:
            order_type = request.data.get('order_type') # 'LAB' or 'IMAGING'
            action = request.data.get('action') # 'CONFIRM' or 'CONFIRM_AND_DISCHARGE'
            
            from doctor.models import LabOrder, DoctorToRadiologyOrder, Encounter
            from django.utils import timezone

            encounter_to_close = None

            if order_type == 'LAB':
                order = LabOrder.objects.get(order_id=order_id)
                order.status = 'IN_PROGRESS' # 접수 완료 -> 검사 중
                order.save()
                encounter_to_close = order.encounter
            
            elif order_type == 'IMAGING':
                order = DoctorToRadiologyOrder.objects.get(order_id=order_id)
                order.status = 'WAITING' # 접수 완료 -> 촬영 대기
                order.save()
                encounter_to_close = order.encounter
            
            else:
                return Response({'error': 'Invalid order type'}, status=status.HTTP_400_BAD_REQUEST)

            # 귀가 조치 로직
            if action == 'CONFIRM_AND_DISCHARGE' and encounter_to_close:
                encounter_to_close.workflow_state = Encounter.WorkflowState.COMPLETED
                encounter_to_close.status = Encounter.Status.COMPLETED
                encounter_to_close.end_time = timezone.now()
                encounter_to_close.save()

            return Response({'message': '오더가 처리되었습니다.'}, status=status.HTTP_200_OK)

        except (LabOrder.DoesNotExist, DoctorToRadiologyOrder.DoesNotExist):
             return Response({'error': '오더를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

