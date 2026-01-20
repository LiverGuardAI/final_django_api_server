from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from accounts.permissions import IsClerk
from doctor.models import Patient, Appointment, Encounter, LabOrder, VitalData, AnthropometricData, MedicalRecord, Doctor
from .serializers import (
    PatientSerializer,
    AppointmentSerializer,
    AppointmentCreateSerializer,
    EncounterSerializer,
    EncounterCreateSerializer,
)
from django.db.models import Q, Count, Subquery, OuterRef
from datetime import date, datetime
from .cache_manager import cache_manager
from django.db import transaction
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils import timezone
from accounts.models import DutySchedule




def is_within_duty_schedule(doctor_id, appointment_date, appointment_time):
    if not doctor_id:
        return False
    doctor = Doctor.objects.filter(doctor_id=doctor_id).select_related('user').first()
    if not doctor:
        return False
    dt = datetime.combine(appointment_date, appointment_time)
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return DutySchedule.objects.filter(
        user_id=doctor.user_id,
        schedule_status='CONFIRMED',
        start_time__lt=dt,
        end_time__gt=dt
    ).exists()

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
                'id': user.user_id,
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

        # 방문 횟수 및 최근 방문일 Annotate (N+1 방지)
        # 1. 최근 방문일 (COMPLETED 상태인 최신 Encounter의 start_time)
        last_visit_subquery = Encounter.objects.filter(
            patient=OuterRef('pk'),
            status=Encounter.Status.COMPLETED
        ).order_by('-start_time').values('start_time')[:1]

        patients = patients.annotate(
            total_visits=Count('encounter', filter=Q(encounter__status=Encounter.Status.COMPLETED)),
            last_visit=Subquery(last_visit_subquery)
        )

        if search:
            # 커스텀 매니저 사용
            patients = patients.search_patient(search).order_by('-similarity', '-created_at')
        else:
            patients = patients.order_by('-created_at')

        # 총 개수 계산
        total_count = patients.count()

        # 페이지네이션 처리
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
                doctor = serializer.validated_data.get('doctor', appointment.doctor)
                appointment_date = serializer.validated_data.get('appointment_date', appointment.appointment_date)
                appointment_time = serializer.validated_data.get('appointment_time', appointment.appointment_time)
                if not doctor or not is_within_duty_schedule(doctor.doctor_id, appointment_date, appointment_time):
                    return Response({
                        'error': '\uD574\uB2F9 \uC2DC\uAC04\uC740 \uADFC\uBB34 \uC77C\uC815\uC774 \uC544\uB2D9\uB2C8\uB2E4.'
                    }, status=status.HTTP_400_BAD_REQUEST)
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
        # 환자번호 자동 생성 (P + YYMMDD + 001-999)
        today = date.today()
        date_str = today.strftime('%y%m%d')  # 예: 260112
        prefix = f'P{date_str}'  # 예: P260112

        # 오늘 등록된 환자 중 가장 높은 순번 찾기
        existing_patients = Patient.objects.filter(
            patient_id__startswith=prefix
        ).order_by('-patient_id')

        if existing_patients.exists():
            # 마지막 환자번호에서 순번 추출 (P260112001 -> 1)
            last_patient_id = existing_patients.first().patient_id
            last_sequence = int(last_patient_id[-3:])

            # 999를 초과하면 에러 반환
            if last_sequence >= 999:
                return Response({
                    'message': '오늘 등록 가능한 환자 수를 초과했습니다. (최대 999명)',
                }, status=status.HTTP_400_BAD_REQUEST)

            next_sequence = last_sequence + 1
        else:
            # 오늘 첫 환자
            next_sequence = 1

        # 환자번호 생성: P260112001
        new_patient_id = f'{prefix}{next_sequence:03d}'

        # request.data를 복사하고 patient_id 추가
        data = request.data.copy()
        data['patient_id'] = new_patient_id

        serializer = PatientSerializer(data=data)

        if serializer.is_valid():
            patient = serializer.save()
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

        doctor_id = request.query_params.get('doctor_id', None)
        if doctor_id:
            if str(doctor_id).lower() not in ['null', 'undefined', 'none']:
                try:
                    appointments = appointments.filter(doctor_id=int(doctor_id))
                except (TypeError, ValueError):
                    pass

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
            doctor = serializer.validated_data.get('doctor')
            appointment_date = serializer.validated_data.get('appointment_date')
            appointment_time = serializer.validated_data.get('appointment_time')
            if not doctor or not is_within_duty_schedule(doctor.doctor_id, appointment_date, appointment_time):
                return Response({
                    'error': '\uD574\uB2F9 \uC2DC\uAC04\uC740 \uADFC\uBB34 \uC77C\uC815\uC774 \uC544\uB2D9\uB2C8\uB2E4.'
                }, status=status.HTTP_400_BAD_REQUEST)
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
        
        date_param = request.query_params.get('date', None)
        if date_param:
            encounters = encounters.filter(start_time__date=date_param)

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
                # 통합 상태 변경 메서드 사용 (Redis 캐시 업데이트 포함)
                current_location = request.data.get('current_location')
                encounter.transition_to(new_workflow_state, current_location)
                updated = True

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
        from django.db.models import Q
        from django.utils import timezone
        
        # 기본 대기열 상태: 대기중, 진료중, 결과대기(추가진료), 수납대기
        filter_condition = Q(workflow_state__in=[
            Encounter.WorkflowState.WAITING_CLINIC,
            Encounter.WorkflowState.IN_CLINIC,
            Encounter.WorkflowState.WAITING_RESULTS,
            Encounter.WorkflowState.WAITING_PAYMENT
        ])

        # 오늘 완료된 진료는 항상 포함 (의사 사이드바 및 원무과 대기현황용)
        today = timezone.localdate()
        filter_condition = filter_condition | Q(
             workflow_state=Encounter.WorkflowState.COMPLETED,
             updated_at__date=today
        )

        # prefetch_related 추가 (Serializer N+1 방지)
        queryset = Encounter.objects.filter(filter_condition)\
            .select_related('patient', 'assigned_doctor')\
            .prefetch_related(
                'medical_records',          # MedicalRecord (related_name defined)
                'laborder_set',             # LabOrder (Default: laborder_set)
                'doctortoradiologyorder_set', # DoctorToRadiologyOrder (Default: doctortoradiologyorder_set)
                'questionnaire'             # Questionnaire (1:1 related_name='questionnaire')
            )\
            .order_by('state_entered_at')
        
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
        from django.core.serializers.json import DjangoJSONEncoder
        cache_manager.redis_client.setex(cache_key, 5, json.dumps(queue_data, cls=DjangoJSONEncoder))

        return Response({
            'success': True,
            'stats': {
                'waiting': cache_manager.get_waiting_count('clinic'),
            },
            'queue': queue_data
        }, status=status.HTTP_200_OK)


class AdministrationWaitingQueueView(APIView):
    """원무과 전용 대기열 조회 API (진료 / 영상 별도 조회)"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        view_type = request.query_params.get('type', 'clinic') # clinic | imaging

        from django.db.models import Q
        from django.utils import timezone
        import json

        today = timezone.localdate()

        # Redis 캐시 키
        cache_key = f'waiting_queue_list:{view_type}'

        # 1. 캐시 확인 (5초 TTL)
        cached_data = cache_manager.redis_client.get(cache_key)
        if cached_data:
            return Response(json.loads(cached_data), status=status.HTTP_200_OK)

        # 2. 캐시 미스: DB 조회
        if view_type == 'clinic':
             # 진료 대기 현황: 진료대기, 진료중, 진료완료(오늘)
            filter_condition = Q(workflow_state__in=[
                Encounter.WorkflowState.WAITING_CLINIC,
                Encounter.WorkflowState.IN_CLINIC,
                Encounter.WorkflowState.WAITING_RESULTS, # 결과 대기도 진료의 연장선
            ]) | Q(
                workflow_state=Encounter.WorkflowState.COMPLETED,
                updated_at__date=today
            )
        elif view_type == 'imaging':
             # 영상 대기 현황: 촬영대기, 촬영중
            filter_condition = Q(workflow_state__in=[
                Encounter.WorkflowState.WAITING_IMAGING,
                Encounter.WorkflowState.IN_IMAGING,
            ])
        else:
            return Response({'error': 'Invalid view type'}, status=status.HTTP_400_BAD_REQUEST)

        queryset = Encounter.objects.filter(filter_condition)\
            .select_related('patient', 'assigned_doctor')\
            .prefetch_related(
                'medical_records',
                'laborder_set',
                'doctortoradiologyorder_set',
                'questionnaire'
            )\
            .order_by('state_entered_at')

        serializer = EncounterSerializer(queryset, many=True)

        # 통계 정보
        if view_type == 'clinic':
            stats = {
                'waiting': cache_manager.get_waiting_count('clinic'),
                'in_progress': cache_manager.get_in_progress_count('clinic'),
            }
        else:  # imaging
            stats = {
                'waiting': cache_manager.get_waiting_count('imaging'),
                'in_progress': cache_manager.get_in_progress_count('imaging'),
            }

        response_data = {
            'success': True,
            'stats': stats,
            'queue': serializer.data
        }

        # 3. Redis 캐싱 (5초)
        try:
            cache_manager.redis_client.setex(cache_key, 5, json.dumps(response_data))
        except Exception as e:
            print(f"Cache write failed: {e}")

        return Response(response_data, status=status.HTTP_200_OK)


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

            # 1. Lab Orders (REQUESTED) - 모든 미처리 오더
            lab_orders = LabOrder.objects.filter(
                status='REQUESTED'
            ).select_related('patient', 'doctor', 'doctor__department').order_by('-created_at')

            # 2. Imaging Orders (REQUESTED) - 모든 미처리 오더
            imaging_orders = DoctorToRadiologyOrder.objects.filter(
                status='REQUESTED'
            ).select_related('patient', 'doctor', 'doctor__department').order_by('-ordered_at')

            # 3. Radiology To Doctor Orders (REQUESTED) - 영상의학과 -> 의사 역오더 (원무과 확인 후 의사 배정)
            from radiology.models import RadiologyToDoctorOrder
            radiology_requests = RadiologyToDoctorOrder.objects.filter(
                status='REQUESTED'
            ).select_related('patient', 'doctor', 'radiologist').order_by('-created_at')

            results = []

            # Lab Order 변환
            for order in lab_orders:
                results.append({
                    'id': f'lab_{order.order_id}',
                    'type': 'LAB',
                    'type_display': '진단검사',
                    'order_name': order.get_order_type_display(),
                    'order_type': order.order_type,  # 추가: 세부 오더 타입
                    'patient_id': order.patient.patient_id,
                    'patient_name': order.patient.name,
                    'doctor_name': order.doctor.name,
                    'department_name': order.doctor.department.dept_name if order.doctor.department else 'N/A',
                    'created_at': order.created_at,
                    'status': order.status,
                    'status_display': '검사대기',
                    'encounter_id': order.encounter.encounter_id if order.encounter else None  # 추가: encounter_id
                })

            # Imaging Order 변환
            for order in imaging_orders:
                results.append({
                    'id': f'img_{order.order_id}',
                    'type': 'IMAGING',
                    'type_display': '영상의학',
                    'order_name': f"{order.modality} ({order.body_part or '전신'})",
                    'order_type': 'IMAGING',  
                    'patient_id': order.patient.patient_id,
                    'patient_name': order.patient.name,
                    'doctor_name': order.doctor.name,
                    'department_name': order.doctor.department.dept_name if order.doctor.department else 'N/A',
                    'created_at': order.ordered_at,
                    'status': order.status,
                    'status_display': '촬영대기',
                    'encounter_id': order.encounter.encounter_id if order.encounter else None
                })

            # Radiology Request 변환 (영상의학과 -> 의사)
            for order in radiology_requests:
                results.append({
                    'id': f'rd_{order.rd_order_id}',
                    'type': 'RADIOLOGY_REQUEST',
                    'type_display': '영상과 요청',
                    'order_name': order.message or '추가 처방 요청',
                    'order_type': 'RADIOLOGY',
                    'patient_id': order.patient.patient_id,
                    'patient_name': order.patient.name,
                    'doctor_name': order.doctor.name,
                    'department_name': '영상의학과', # 요청 부서
                    'created_at': order.created_at,
                    'status': order.status,
                    'status_display': '확인대기',
                    'encounter_id': order.encounter.encounter_id if order.encounter else None
                })

            # 최신순 정렬 (created_at 기준)
            results.sort(key=lambda x: x['created_at'], reverse=True)

            return Response({
                'count': len(results),
                'results': results
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class InProgressOrdersView(APIView):
    """
    진행 중인 검사 목록 조회 API ("검사 대기" 탭용)
    - LabOrder (IN_PROGRESS) - 혈액검사/유전체검사 등 며칠 걸리는 검사
    - DoctorToRadiologyOrder (WAITING, IN_PROGRESS) - 촬영 대기 중
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            from doctor.models import LabOrder, DoctorToRadiologyOrder

            # 1. Lab Orders (IN_PROGRESS) - 검사 진행 중
            lab_orders = LabOrder.objects.filter(
                status='IN_PROGRESS'
            ).select_related('patient', 'doctor', 'doctor__department').order_by('-created_at')

            # 2. Imaging Orders (WAITING, IN_PROGRESS) - 촬영 대기/진행 중
            imaging_orders = DoctorToRadiologyOrder.objects.filter(
                status__in=['WAITING', 'IN_PROGRESS']
            ).select_related('patient', 'doctor', 'doctor__department').order_by('-ordered_at')

            results = []

            # Lab Order 변환
            for order in lab_orders:
                results.append({
                    'id': f'lab_{order.order_id}',
                    'type': 'LAB',
                    'type_display': '진단검사',
                    'order_name': order.get_order_type_display(),
                    'order_type': order.order_type,
                    'patient_id': order.patient.patient_id,
                    'patient_name': order.patient.name,
                    'doctor_name': order.doctor.name,
                    'department_name': order.doctor.department.dept_name if order.doctor.department else 'N/A',
                    'created_at': order.created_at,
                    'status': order.status,
                    'status_display': '검사중',
                    'encounter_id': order.encounter.encounter_id if order.encounter else None
                })

            # Imaging Order 변환
            for order in imaging_orders:
                results.append({
                    'id': f'img_{order.order_id}',
                    'type': 'IMAGING',
                    'type_display': '영상의학',
                    'order_name': f"{order.modality} ({order.body_part or '전신'})",
                    'order_type': 'IMAGING',
                    'patient_id': order.patient.patient_id,
                    'patient_name': order.patient.name,
                    'doctor_name': order.doctor.name,
                    'department_name': order.doctor.department.dept_name if order.doctor.department else 'N/A',
                    'created_at': order.ordered_at,
                    'status': order.status,
                    'status_display': '촬영대기' if order.status == 'WAITING' else '촬영중',
                    'encounter_id': order.encounter.encounter_id if order.encounter else None
                })

            # 최신순 정렬
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
        """
        오더 접수 처리 - 새로운 로직:
        1. 오더 상태만 변경 (LAB: IN_PROGRESS, IMAGING: WAITING)
        2. 모든 오더가 접수 완료되었는지 확인
        3. 모든 오더 접수 완료 시:
           - CT 오더 있음 → WAITING_IMAGING (촬영 대기)
           - CT 오더 없음 → WAITING_RESULTS (결과 대기, 환자 귀가)
        """
        try:
            order_type = request.data.get('order_type')  # 'LAB' or 'IMAGING'

            from doctor.models import LabOrder, DoctorToRadiologyOrder, Encounter
            from django.utils import timezone

            encounter = None

            # 1. 오더 상태 변경
            if order_type == 'LAB':
                order = LabOrder.objects.get(order_id=order_id)
                order.status = 'IN_PROGRESS'  # 접수 완료 -> 검사 중 (외부검사는 며칠 소요)
                order.save()
                encounter = order.encounter

            elif order_type == 'IMAGING':
                order = DoctorToRadiologyOrder.objects.get(order_id=order_id)
                order.status = 'WAITING'  # 접수 완료 -> 촬영 대기
                order.save()
                encounter = order.encounter

            else:
                return Response({'error': 'Invalid order type'}, status=status.HTTP_400_BAD_REQUEST)

            if not encounter or encounter.workflow_state == Encounter.WorkflowState.COMPLETED:
                return Response({'message': '오더가 처리되었습니다.'}, status=status.HTTP_200_OK)

            # 2. 모든 오더 접수 완료 여부 확인
            has_pending_lab = LabOrder.objects.filter(
                encounter=encounter,
                status='REQUESTED'
            ).exists()

            has_pending_imaging = DoctorToRadiologyOrder.objects.filter(
                encounter=encounter,
                status='REQUESTED'
            ).exists()

            # 아직 접수 안 된 오더가 있으면 REGISTERED 상태 유지
            if has_pending_lab or has_pending_imaging:
                print(f"INFO: 오더 접수했지만 다른 오더 대기 중: {encounter.encounter_id}")
                return Response({'message': '오더가 처리되었습니다.'}, status=status.HTTP_200_OK)

            # 3. 모든 오더 접수 완료 → 다음 단계로 전환
            # 3-1. CT 오더가 있는지 확인
            has_imaging_orders = DoctorToRadiologyOrder.objects.filter(
                encounter=encounter,
                status__in=['WAITING', 'IN_PROGRESS']
            ).exists()

            if has_imaging_orders:
                # CT 오더 있음 → 촬영 대기로 전환
                encounter.transition_to(Encounter.WorkflowState.WAITING_IMAGING)

                # WebSocket 알림
                send_queue_update_websocket(
                    message=f"촬영 대기: {encounter.patient.name}",
                    extra_data={
                        "queue_type": "imaging",
                        "imaging_waiting": cache_manager.get_waiting_count('imaging'),
                        "imaging_in_progress": cache_manager.get_in_progress_count('imaging'),
                    }
                )
                cache_manager.redis_client.delete('waiting_queue_list:imaging')
                print(f"INFO: 모든 오더 접수 완료 → 촬영 대기: {encounter.encounter_id}")

            else:
                # CT 오더 없음 → 결과 대기 (환자 귀가)
                encounter.transition_to(Encounter.WorkflowState.WAITING_RESULTS)
                cache_manager.redis_client.delete('waiting_queue_list:clinic')
                print(f"INFO: 모든 오더 접수 완료 → 결과 대기 (귀가): {encounter.encounter_id}")

            return Response({'message': '오더가 처리되었습니다.'}, status=status.HTTP_200_OK)

        except (LabOrder.DoesNotExist, DoctorToRadiologyOrder.DoesNotExist):
            return Response({'error': '오더를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AssignImagingDoctorView(APIView):
    """
    Imaging order assignment API (admin).
    - validates radiologist id
    - moves order to WAITING
    - updates encounter workflow state when all orders are accepted
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, order_id):
        try:
            order_type = request.data.get('order_type')
            radiologist_id = request.data.get('doctor_id')

            if order_type != 'IMAGING':
                return Response({'error': 'Invalid order type'}, status=status.HTTP_400_BAD_REQUEST)
            if not radiologist_id:
                return Response({'error': 'doctor_id is required'}, status=status.HTTP_400_BAD_REQUEST)

            from doctor.models import LabOrder, DoctorToRadiologyOrder, Encounter
            from radiology.models import Radiology

            radiologist = Radiology.objects.filter(radiologic_id=radiologist_id).first()
            if not radiologist:
                return Response({'error': 'Radiologist not found'}, status=status.HTTP_404_NOT_FOUND)

            order = DoctorToRadiologyOrder.objects.get(order_id=order_id)
            order.status = 'WAITING'
            order.save()

            encounter = order.encounter
            if not encounter or encounter.workflow_state == Encounter.WorkflowState.COMPLETED:
                return Response({'message': 'Order assigned'}, status=status.HTTP_200_OK)

            has_pending_lab = LabOrder.objects.filter(
                encounter=encounter,
                status='REQUESTED'
            ).exists()
            has_pending_imaging = DoctorToRadiologyOrder.objects.filter(
                encounter=encounter,
                status='REQUESTED'
            ).exists()

            if has_pending_lab or has_pending_imaging:
                return Response({'message': 'Order assigned'}, status=status.HTTP_200_OK)

            has_imaging_orders = DoctorToRadiologyOrder.objects.filter(
                encounter=encounter,
                status__in=['WAITING', 'IN_PROGRESS']
            ).exists()

            if has_imaging_orders:
                encounter.transition_to(Encounter.WorkflowState.WAITING_IMAGING)
                send_queue_update_websocket(
                    message=f"Imaging waiting {encounter.patient.name}",
                    extra_data={
                        "queue_type": "imaging",
                        "imaging_waiting": cache_manager.get_waiting_count('imaging'),
                        "imaging_in_progress": cache_manager.get_in_progress_count('imaging'),
                    }
                )
                cache_manager.redis_client.delete('waiting_queue_list:imaging')
            else:
                encounter.transition_to(Encounter.WorkflowState.WAITING_RESULTS)
                cache_manager.redis_client.delete('waiting_queue_list:clinic')

            return Response({'message': 'Order assigned'}, status=status.HTTP_200_OK)

        except DoctorToRadiologyOrder.DoesNotExist:
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CompleteVitalOrPhysicalView(APIView):
    """
    바이탈/신체계측 데이터 입력 및 저장 API
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, order_id):
        try:
            order_type = request.data.get('order_type')  # 'VITAL' or 'PHYSICAL'
            lab_data = request.data.get('lab_data', {})

            # LabOrder 조회
            order = LabOrder.objects.get(order_id=order_id, order_type=order_type)
            
            # Encounter 및 Patient 가져오기
            encounter = order.encounter
            patient = order.patient

            # [FIX] 유효성 검사 (권한 및 의사 배정 확인)
            if not hasattr(request.user, 'administration'):
                return Response({'error': '원무과 직원 계정으로만 처리가 가능합니다.'}, status=status.HTTP_403_FORBIDDEN)
            
            if not encounter.assigned_doctor:
                return Response({'error': '담당 의사가 배정되지 않은 환자입니다. 의사를 배정해주세요.'}, status=status.HTTP_400_BAD_REQUEST)

            # MedicalRecord 생성 또는 가져오기
            # staff 필드는 NOT NULL이므로 반드시 request.user.administration을 할당해야 함
            medical_record, created = MedicalRecord.objects.get_or_create(
                encounter=encounter,
                patient=patient,
                defaults={
                    'record_date': timezone.now().date(),
                    'record_time': timezone.now().time(),
                    'doctor': encounter.assigned_doctor,
                    'staff': request.user.administration,
                    'record_status': MedicalRecord.RecordStatus.DRAFT,
                }
            )

            if order_type == 'VITAL':
                # 바이탈 데이터 저장
                VitalData.objects.create(
                    patient=patient,
                    medical_record=medical_record,
                    measured_at=timezone.now().date(),
                    sbp=lab_data.get('systolic_bp'),
                    dbp=lab_data.get('diastolic_bp'),
                    heart_rate=lab_data.get('heart_rate'),        # Added
                    temperature=lab_data.get('body_temperature'), # Added
                )
            
            elif order_type == 'PHYSICAL':
                #신체계측 데이터 저장
                AnthropometricData.objects.create(
                    patient=patient,
                    medical_record=medical_record,
                    measured_at=timezone.now().date(),
                    height=lab_data.get('height'),
                    weight=lab_data.get('weight'),
                    bmi=lab_data.get('bmi'),
                )

            order.status = LabOrder.OrderStatus.COMPLETED
            order.save()

            # **FIX**: LAB 오더 완료 후 encounter 상태 업데이트
            # 1. 다른 LAB 오더가 남아있는지 확인
            has_pending_lab = LabOrder.objects.filter(
                encounter=encounter,
                status__in=['REQUESTED', 'WAITING', 'IN_PROGRESS']
            ).exists()

            # 2. IMAGING 오더가 대기 중인지 확인
            has_pending_imaging = DoctorToRadiologyOrder.objects.filter(
                encounter=encounter,
                status__in=['REQUESTED', 'WAITING', 'IN_PROGRESS']
            ).exists()

            if has_pending_lab:
                # 다른 LAB 오더가 남아있으면 상태 유지
                print(f"INFO: LAB 오더 완료했지만 다른 LAB 오더 대기 중: {encounter.encounter_id}")
            elif has_pending_imaging:
                # IMAGING 오더가 남아있으면 촬영 대기로 전환
                if encounter.workflow_state not in [Encounter.WorkflowState.WAITING_IMAGING, Encounter.WorkflowState.IN_IMAGING]:
                    encounter.transition_to(Encounter.WorkflowState.WAITING_IMAGING)
                    print(f"INFO: LAB 완료 후 IMAGING 대기로 전환: {encounter.encounter_id}")

                    # 캐시 무효화 및 WebSocket 알림
                    cache_manager.redis_client.delete('waiting_queue_list:imaging')
                    send_queue_update_websocket(
                        message=f"LAB 완료 후 촬영 대기: {patient.name}",
                        extra_data={
                            "queue_type": "imaging",
                            "imaging_waiting": cache_manager.get_waiting_count('imaging'),
                            "imaging_in_progress": cache_manager.get_in_progress_count('imaging'),
                        }
                    )
            else:
                # 모든 오더 완료 → 결과 대기로 전환
                if encounter.workflow_state != Encounter.WorkflowState.COMPLETED:
                    encounter.transition_to(Encounter.WorkflowState.WAITING_RESULTS)
                    print(f"INFO: 모든 오더 완료 → 결과대기: {encounter.encounter_id}")

                    # 캐시 무효화
                    cache_manager.redis_client.delete('waiting_queue_list:clinic')

            return Response({
                'message': '검사 데이터가 저장되었습니다.',
                'encounter_id': encounter.encounter_id,
                'patient_id': patient.patient_id
            }, status=status.HTTP_200_OK)

        except LabOrder.DoesNotExist:
            return Response({'error': '오더를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CancelEncounterView(APIView):
    """Encounter 취소 API"""
    permission_classes = [IsAuthenticated]

    def post(self, request, encounter_id):
        try:
            encounter = Encounter.objects.get(encounter_id=encounter_id)
            
            # 이미 완료/취소된 경우 체크
            if encounter.workflow_state in [Encounter.WorkflowState.COMPLETED, Encounter.WorkflowState.CANCELLED]:
                 return Response({
                    'message': f'이미 {encounter.get_workflow_state_display()} 상태입니다.'
                }, status=status.HTTP_400_BAD_REQUEST)

            # 상태 변경
            encounter.transition_to(Encounter.WorkflowState.CANCELLED)
            
            # Redis 대기열 갱신은 transition_to 내부에서 처리됨 (decrement waiting/in_progress)
            # 안전을 위해 캐시 무효화
            cache_manager.redis_client.delete('waiting_queue_list')
            
            # WebSocket 알림
            send_queue_update_websocket(
                message=f"진료 취소: {encounter.patient.name}",
                extra_data={
                    "cancelled_encounter": {
                        "id": encounter.encounter_id,
                        "patient_name": encounter.patient.name
                    }
                }
            )

            return Response({
                'message': '진료가 취소되었습니다.',
                'encounter': EncounterSerializer(encounter).data
            }, status=status.HTTP_200_OK)

        except Encounter.DoesNotExist:
            return Response({'error': 'Encounter not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class DailyPatientStatusView(APIView):
    """오늘의 환자 현황판을 위한 최적화된 API"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.now().date()
        
        # 기본 쿼리셋 (오늘 데이터만, 시간순 정렬)
        queryset = Encounter.objects.filter(start_time__date=today).select_related(
            'patient', 'assigned_doctor'
        ).order_by('-state_entered_at')

        # 1. 통계 집계 (DB 레벨 계산)
        stats = queryset.aggregate(
            total=Count('encounter_id'),
            waiting=Count('encounter_id', filter=Q(workflow_state__in=[
                Encounter.WorkflowState.REGISTERED, 
                Encounter.WorkflowState.WAITING_CLINIC
            ])),
            in_progress=Count('encounter_id', filter=Q(workflow_state__in=[
                Encounter.WorkflowState.IN_CLINIC,
                Encounter.WorkflowState.WAITING_IMAGING,
                Encounter.WorkflowState.IN_IMAGING,
                Encounter.WorkflowState.WAITING_RESULTS,
                Encounter.WorkflowState.WAITING_PAYMENT
            ])),
            completed=Count('encounter_id', filter=Q(workflow_state=Encounter.WorkflowState.COMPLETED))
        )

        results = []
        for enc in queryset:
            doctor_name = enc.assigned_doctor.name if enc.assigned_doctor else None
            
            results.append({
                'encounter_id': enc.encounter_id,
                'patient_name': enc.patient.name,
                'patient_id': enc.patient.patient_id,
                'gender': enc.patient.gender,
                'age': enc.patient.age,
                'doctor_name': doctor_name,
                'workflow_state': enc.workflow_state,
                'state_entered_at': enc.state_entered_at,
                'start_time': enc.start_time,
                'end_time': enc.end_time or enc.updated_at,
                'updated_at': enc.updated_at,
            })

        return Response({
            'stats': stats,
            'encounters': results
        }, status=status.HTTP_200_OK)


class AdministrationInfoView(APIView):
    """현재 로그인한 원무과 직원 정보 조회/수정 API"""
    permission_classes = [IsClerk]

    def get(self, request):
        """
        현재 로그인한 원무과 직원의 상세 정보 조회
        """
        try:
            from .models import Administration
            from .serializers import AdministrationSerializer

            admin_staff = Administration.objects.select_related('department').get(user=request.user)
            serializer = AdministrationSerializer(admin_staff)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Administration.DoesNotExist:
            return Response({
                'error': '원무과 직원 정보를 찾을 수 없습니다.'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request):
        """
        현재 로그인한 원무과 직원의 정보 수정
        """
        try:
            from .models import Administration
            from .serializers import AdministrationSerializer

            admin_staff = Administration.objects.select_related('department').get(user=request.user)

            # 수정 가능한 필드들
            allowed_fields = ['name', 'phone']

            # date_of_birth는 별도 처리 (날짜 형식 검증)
            if 'date_of_birth' in request.data and request.data['date_of_birth']:
                admin_staff.date_of_birth = request.data['date_of_birth']

            for field in allowed_fields:
                if field in request.data:
                    setattr(admin_staff, field, request.data[field])

            admin_staff.save()

            serializer = AdministrationSerializer(admin_staff)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Administration.DoesNotExist:
            return Response({
                'error': '원무과 직원 정보를 찾을 수 없습니다.'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
