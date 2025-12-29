from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from accounts.permissions import IsClerk
from doctor.models import Patient, Appointment, Encounter
from .serializers import (
    PatientSerializer,
    PatientCreateSerializer,
    AppointmentSerializer,
    AppointmentCreateSerializer,
    EncounterSerializer,
    EncounterCreateSerializer,
)
from django.db.models import Q, Count
from datetime import date, datetime
from .queue_manager import queue_manager
from .cache_manager import cache_manager


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

        patients = Patient.objects.all()

        if search:
            patients = patients.filter(
                Q(patient_id__icontains=search) |
                Q(name__icontains=search) |
                Q(sample_id__icontains=search)
            )

        patients = patients.order_by('-created_at')
        serializer = PatientSerializer(patients, many=True)

        return Response({
            'count': patients.count(),
            'results': serializer.data
        }, status=status.HTTP_200_OK)


class PatientDetailView(APIView):
    """환자 상세 정보 조회 API"""
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


class PatientRegistrationView(APIView):
    """환자 등록 API (원무과 전용)"""
    permission_classes = [IsClerk]

    def post(self, request):
        serializer = PatientCreateSerializer(data=request.data)

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

        Request body:
        {
            "patient_id": "P2024001",
            "doctor_id": 1,
            "chief_complaint": "복통",
            "priority": 5  # 선택, 기본값 5
        }
        """
        serializer = EncounterCreateSerializer(data=request.data)

        if serializer.is_valid():
            # 1. DB에 Encounter 저장
            encounter = serializer.save(
                staff_id=request.user.user_id,
                encounter_status=Encounter.EncounterStatus.WAITING
            )

            # 2. 환자 상태 업데이트
            patient = encounter.patient
            patient.current_status = Patient.PatientStatus.WAITING_CLINIC
            patient.save()

            # 3. RabbitMQ 대기열에 추가
            priority = request.data.get('priority', 5)
            queue_success = queue_manager.add_to_queue(
                encounter_id=encounter.encounter_id,
                patient_id=patient.patient_id,
                patient_name=patient.name,
                priority=priority
            )

            # 4. Redis 대기 카운트 증가
            if queue_success:
                cache_manager.increment_waiting_count('clinic')
                cache_manager.set_patient_status(
                    patient.patient_id,
                    Patient.PatientStatus.WAITING_CLINIC
                )

            # 5. 현재 대기 인원 조회
            waiting_count = cache_manager.get_waiting_count('clinic')

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

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EncounterDetailView(APIView):
    """진료 기록 상세 조회 API"""
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


class WaitingQueueView(APIView):
    """대기열 관리 API"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        현재 대기열 조회

        Query params:
        - max_count: 조회할 최대 환자 수 (기본값: 10)
        """
        max_count = int(request.query_params.get('max_count', 10))

        # RabbitMQ에서 대기 목록 조회 (큐에서 제거하지 않음)
        waiting_list = queue_manager.peek_queue(max_count=max_count)

        # Redis에서 통계 조회
        waiting_count = cache_manager.get_waiting_count('clinic')
        in_progress_count = cache_manager.get_in_progress_count('clinic')

        return Response({
            'success': True,
            'stats': {
                'waiting': waiting_count,
                'in_progress': in_progress_count,
                'total': waiting_count + in_progress_count
            },
            'queue': waiting_list
        }, status=status.HTTP_200_OK)


class CallNextPatientView(APIView):
    """다음 환자 호출 API"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        다음 대기 환자 호출

        Returns:
        - 다음 환자 정보
        - Encounter를 IN_PROGRESS로 변경
        - Patient를 IN_CLINIC으로 변경
        - Redis 카운트 조정
        """
        # 1. RabbitMQ에서 다음 환자 가져오기
        next_patient = queue_manager.get_next_patient()

        if not next_patient:
            return Response({
                'success': False,
                'message': '대기 중인 환자가 없습니다.'
            }, status=status.HTTP_200_OK)

        # 2. Encounter 상태 업데이트
        try:
            encounter = Encounter.objects.get(pk=next_patient['encounter_id'])
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

            # 5. 현재 통계 조회
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

        except Encounter.DoesNotExist:
            return Response({
                'success': False,
                'message': f'Encounter ID {next_patient["encounter_id"]}를 찾을 수 없습니다.'
            }, status=status.HTTP_404_NOT_FOUND)


class DashboardStatsView(APIView):
    """실시간 대시보드 통계 API"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        실시간 대시보드 통계 조회 (Redis 캐시 사용)

        Returns:
        - 진료실, 촬영실, 검사실 대기/진행 인원
        """
        stats = cache_manager.get_dashboard_stats()

        # RabbitMQ 큐 길이도 함께 반환
        queue_length = queue_manager.get_queue_length()

        return Response({
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'stats': stats,
            'rabbitmq_queue_length': queue_length
        }, status=status.HTTP_200_OK)
