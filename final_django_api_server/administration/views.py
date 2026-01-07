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
        today_encounters = Encounter.objects.filter(encounter_date=today).count()

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
                Q(name__icontains=search) |
                Q(sample_id__icontains=search)
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
        encounters = Encounter.objects.select_related('patient', 'doctor')

        if patient_id:
            encounters = encounters.filter(patient_id=patient_id)

        encounters = encounters.order_by('-encounter_date', '-encounter_time')
        serializer = EncounterSerializer(encounters, many=True)

        return Response({
            'count': encounters.count(),
            'results': serializer.data
        }, status=status.HTTP_200_OK)

    def post(self, request):
        """
        환자 접수 API (Queue + Cache 연동)
        트랜잭션 적용: RabbitMQ 전송 실패 시 DB 저장도 취소됨 (중복 방지)
        """
        serializer = EncounterCreateSerializer(data=request.data)

        if serializer.is_valid():
            try:
                # [핵심] atomic 블록 시작: 이 안에서 에러가 나면 DB 저장이 싹 취소됩니다.
                with transaction.atomic():
                    
                    # 1. 원무과 직원 정보 가져오기
                    try:
                        staff_obj = request.user.administration
                        staff_id = staff_obj.staff_id
                    except Exception as e:
                        # 원무과 직원이 아니면 즉시 에러 리턴
                        return Response({
                            'success': False,
                            'message': f'원무과 프로필을 찾을 수 없습니다: {str(e)}'
                        }, status=status.HTTP_400_BAD_REQUEST)

                    # 1-1. 중복 접수 체크: 이미 대기 중이거나 진료 중인 환자인지 확인
                    patient_id = request.data.get('patient')
                    existing_encounter = Encounter.objects.filter(
                        patient_id=patient_id,
                        encounter_status__in=['WAITING', 'IN_PROGRESS']
                    ).first()

                    if existing_encounter:
                        status_display = '대기 중' if existing_encounter.encounter_status == 'WAITING' else '진료 중'
                        return Response({
                            'success': False,
                            'message': f'해당 환자는 이미 {status_display}입니다. (담당의사: {existing_encounter.doctor.name})'
                        }, status=status.HTTP_400_BAD_REQUEST)

                    # 2. DB에 Encounter 저장 (checkin_time 설정)
                    encounter = serializer.save(
                        staff_id=staff_id,
                        encounter_status=Encounter.EncounterStatus.WAITING,
                        checkin_time=datetime.now()  # 대기열 진입 시간 기록
                    )

                    # 3. 환자 상태 업데이트
                    patient = encounter.patient
                    patient.current_status = Patient.PatientStatus.WAITING_CLINIC
                    patient.save()

                    # 4. Redis 대기 카운트 증가
                    cache_manager.increment_waiting_count('clinic')
                    cache_manager.set_patient_status(
                        patient.patient_id,
                        Patient.PatientStatus.WAITING_CLINIC
                    )

                # 5. Redis 캐시 무효화 (대기열 변경)
                cache_manager.redis_client.delete('waiting_queue_list')

                # 6. WebSocket으로 실시간 알림 전송
                waiting_count = cache_manager.get_waiting_count('clinic')
                send_queue_update_websocket(
                    message="새로운 환자가 접수되었습니다.",
                    extra_data={
                        "new_patient": {
                            "name": patient.name,
                            "id": patient.patient_id
                        }
                    }
                )
                               
                return Response({
                    'success': True,
                    'message': f'접수가 완료되었습니다. 현재 대기 인원: {waiting_count}명',
                    'encounter': EncounterSerializer(encounter).data,
                    'queue_info': {
                        'position': waiting_count,
                        'waiting_count': waiting_count,
                        'patient_status': patient.current_status
                    }
                }, status=status.HTTP_201_CREATED)

            except Exception as e:
                # 로직에서 에러가 발생하면 여기로 옴 (트랜잭션 롤백)
                print(f"!!! 접수 트랜잭션 롤백됨: {e}")
                return Response({
                    'success': False,
                    'message': '시스템 오류로 접수가 처리되지 않았습니다. (DB 저장 취소됨)',
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
        """진료 기록 부분 수정 (상태 변경 등)"""
        try:
            encounter = Encounter.objects.get(encounter_id=encounter_id)
            updated = False

            # 상태 변경
            if 'encounter_status' in request.data:
                new_status = request.data['encounter_status']
                encounter.encounter_status = new_status
                updated = True

                # 대기 취소 시 문진표 데이터 삭제
                if new_status == 'CANCELLED':
                    encounter.questionnaire_data = None
                    encounter.questionnaire_status = 'NOT_STARTED'
                    encounter.chief_complaint = ''

            # 주 증상(문진표) 업데이트 - 레거시 지원
            if 'chief_complaint' in request.data:
                encounter.chief_complaint = request.data['chief_complaint']
                updated = True

            # 문진표 데이터 업데이트
            if 'questionnaire_data' in request.data:
                encounter.questionnaire_data = request.data['questionnaire_data']
                encounter.questionnaire_status = 'COMPLETED'
                # chief_complaint 추출 (의사용 요약)
                if isinstance(request.data['questionnaire_data'], dict):
                    encounter.chief_complaint = request.data['questionnaire_data'].get('chief_complaint', '')
                updated = True

            # 문진표 상태만 변경
            if 'questionnaire_status' in request.data:
                encounter.questionnaire_status = request.data['questionnaire_status']
                updated = True

            if updated:
                encounter.save()

                # 대기열 상태 변경 시 캐시 무효화 + WebSocket 알림
                if 'encounter_status' in request.data:
                    cache_manager.redis_client.delete('waiting_queue_list')

                    # WebSocket으로 실시간 알림 전송
                    status_display = {
                        'WAITING': '대기중',
                        'IN_PROGRESS': '진료중',
                        'COMPLETED': '완료',
                        'CANCELLED': '취소'
                    }.get(new_status, new_status)

                    send_queue_update_websocket(
                        message=f"환자 상태 변경: {encounter.patient.name} ({status_display})",
                        extra_data={
                            "updated_encounter": {
                                "id": encounter.encounter_id,
                                "patient_name": encounter.patient.name,
                                "status": new_status
                            }
                        }
                    )

                return Response(
                    {
                        'message': '진료 기록이 업데이트되었습니다.',
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
                {'error': '진료 기록을 찾을 수 없습니다.'},
                status=status.HTTP_404_NOT_FOUND
            )


class WaitingQueueView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        max_count = int(request.query_params.get('max_count', 50))
        limit = int(request.query_params.get('limit', 50))  # 추가: limit 파라미터
        doctor_id = request.query_params.get('doctor_id', None)  # 추가: 의사 필터링

        # doctor_id가 있으면 캐시를 사용하지 않고 직접 DB 조회
        if doctor_id:
            queryset = Encounter.objects.filter(
                encounter_status__in=['WAITING', 'IN_PROGRESS', 'COMPLETED']
            ).select_related('patient', 'doctor', 'doctor__department')

            # 의사 필터링
            queryset = queryset.filter(doctor_id=doctor_id)

            # 날짜 필터링 (오늘 날짜)
            from datetime import date
            today = date.today()
            queryset = queryset.filter(encounter_date=today)

            # 통계 계산 (슬라이싱 전에 수행)
            total_waiting = queryset.filter(encounter_status='WAITING').count()

            # 정렬 및 제한 (checkin_time 기준 FIFO)
            queryset = queryset.order_by('checkin_time')[:limit]

            serializer = EncounterSerializer(queryset, many=True)

            return Response({
                'queue': serializer.data,
                'total_waiting': total_waiting
            }, status=status.HTTP_200_OK)

        # 기존 로직: Redis 캐시 사용
        cache_key = 'waiting_queue_list'
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

        # 캐시 미스: DB에서 조회 후 Redis에 저장 (checkin_time 기준 FIFO)
        # WAITING과 IN_PROGRESS 모두 포함 (원무과 대기열 화면용)
        waiting_encounters = Encounter.objects.filter(
            encounter_status__in=['WAITING', 'IN_PROGRESS']
        ).select_related('patient', 'doctor', 'doctor__department').order_by('checkin_time')[:max_count]

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
        - Encounter를 IN_PROGRESS로 변경
        - Patient를 IN_CLINIC으로 변경
        - Redis 카운트 조정
        """
        # 1. DB에서 가장 오래 대기 중인 환자 가져오기 (FIFO - checkin_time 기준)
        encounter = Encounter.objects.filter(
            encounter_status=Encounter.EncounterStatus.WAITING
        ).select_related('patient').order_by('checkin_time').first()

        if not encounter:
            return Response({
                'success': False,
                'message': '대기 중인 환자가 없습니다.'
            }, status=status.HTTP_200_OK)

        # 2. Encounter 상태 업데이트
        encounter.encounter_status = Encounter.EncounterStatus.IN_PROGRESS
        encounter.encounter_start = datetime.now().time()
        encounter.save()

        # 3. Patient 상태 업데이트
        patient = encounter.patient
        patient.current_status = Patient.PatientStatus.IN_CLINIC
        patient.save()

        # 4. Redis 카운트 업데이트
        cache_manager.decrement_waiting_count('clinic')
        cache_manager.increment_in_progress_count('clinic')
        cache_manager.set_patient_status(patient.patient_id, Patient.PatientStatus.IN_CLINIC)

        # 5. Redis 캐시 무효화 (대기열 변경)
        cache_manager.redis_client.delete('waiting_queue_list')

        # 6. WebSocket으로 실시간 알림 전송
        send_queue_update_websocket(
            message=f"환자 호출: {patient.name}",
            extra_data={
                "called_patient": {
                    "name": patient.name,
                    "id": patient.patient_id
                }
            }
        )

        # 7. 현재 통계 조회
        waiting_count = cache_manager.get_waiting_count('clinic')
        in_progress_count = cache_manager.get_in_progress_count('clinic')

        return Response({
            'success': True,
            'message': f'다음 환자: {patient.name}',
            'patient': {
                'patient_id': patient.patient_id,
                'name': patient.name,
                'age': patient.age,
                'gender': patient.gender,
                'chief_complaint': encounter.chief_complaint
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
        doctor_id = request.query_params.get('doctor_id', None)

        # doctor_id가 있으면 해당 의사의 통계만 반환
        if doctor_id:
            from datetime import date
            today = date.today()

            # 해당 의사의 오늘 encounter 조회
            queryset = Encounter.objects.filter(
                doctor_id=doctor_id,
                encounter_date=today
            )

            clinic_waiting = queryset.filter(encounter_status='WAITING').count()
            clinic_in_progress = queryset.filter(encounter_status='IN_PROGRESS').count()
            completed_today = queryset.filter(encounter_status='COMPLETED').count()
            total_patients = queryset.count()

            return Response({
                'total_patients': total_patients,
                'clinic_waiting': clinic_waiting,
                'clinic_in_progress': clinic_in_progress,
                'completed_today': completed_today,
            }, status=status.HTTP_200_OK)

        # 기존 로직: 전체 통계
        stats = cache_manager.get_dashboard_stats()

        return Response({
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'stats': stats
        }, status=status.HTTP_200_OK)
