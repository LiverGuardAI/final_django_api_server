# patients/views.py
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth.hashers import check_password
from django.utils import timezone
from django.db import IntegrityError
from datetime import date

from .models import UserProfile, AppSyncRequest
from .serializers import SignupSerializer, LoginSerializer, AppSyncRequestSerializer


@api_view(['POST'])
@permission_classes([AllowAny])
def signup_view(request):
    """
    회원가입 API

    POST /api/patients/signup/
    {
        "nickname": "홍길동",
        "phone_number": "01012345678",
        "gender": "M",
        "birth_date": "1950-01-01",
        "user_id": "hong123",
        "password": "secure_password",
        "password_confirm": "secure_password"
    }
    """
    serializer = SignupSerializer(data=request.data)

    if serializer.is_valid():
        user_profile = serializer.save()

        # 토큰 생성 (간단한 문자열로 profile_id 사용)
        token = f"token_{user_profile.profile_id}_{user_profile.user_id}"

        return Response({
            "success": True,
            "message": "회원가입이 완료되었습니다.",
            "token": token,
            "user": {
                "profile_id": user_profile.profile_id,
                "nickname": user_profile.nickname,
                "user_id": user_profile.user_id,
                "birth_date": user_profile.birth_date.isoformat() if user_profile.birth_date else None,
            }
        }, status=status.HTTP_201_CREATED)

    return Response({
        "success": False,
        "errors": serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """
    로그인 API

    POST /api/patients/login/
    {
        "user_id": "hong123",
        "password": "secure_password"
    }
    """
    serializer = LoginSerializer(data=request.data)

    if not serializer.is_valid():
        return Response({
            "success": False,
            "message": "아이디와 비밀번호를 모두 입력해주세요."
        }, status=status.HTTP_400_BAD_REQUEST)

    user_id = serializer.validated_data['user_id']
    password = serializer.validated_data['password']

    try:
        user_profile = UserProfile.objects.get(user_id=user_id)

        # 비밀번호 확인
        if check_password(password, user_profile.password):
            # 토큰 생성
            token = f"token_{user_profile.profile_id}_{user_profile.user_id}"

            return Response({
                "success": True,
                "message": "로그인 성공",
                "token": token,
                "user": {
                    "profile_id": user_profile.profile_id,
                    "nickname": user_profile.nickname,
                    "user_id": user_profile.user_id,
                    "birth_date": user_profile.birth_date.isoformat() if user_profile.birth_date else None,
                }
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                "success": False,
                "message": "비밀번호가 일치하지 않습니다."
            }, status=status.HTTP_401_UNAUTHORIZED)

    except UserProfile.DoesNotExist:
        return Response({
            "success": False,
            "message": "존재하지 않는 아이디입니다."
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([AllowAny])
def app_sync_request_create(request):
    """
    앱 연동 신청 생성 (Flutter 앱에서 호출)

    POST /api/patients/app-sync-requests/
    {
        "profile": <profile_id>
    }
    """
    profile_id = request.data.get('profile')

    if not profile_id:
        return Response({
            "success": False,
            "message": "profile_id가 필요합니다."
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        profile = UserProfile.objects.get(profile_id=profile_id)

        # 이미 연동된 사용자인지 확인
        if profile.is_verified and profile.linked_patient_id:
            return Response({
                "success": False,
                "message": "이미 연동된 계정입니다."
            }, status=status.HTTP_400_BAD_REQUEST)

        # 이미 대기 중인 신청이 있는지 확인
        existing_request = AppSyncRequest.objects.filter(
            profile=profile,
            status=AppSyncRequest.Status.PENDING
        ).first()

        if existing_request:
            return Response({
                "success": False,
                "message": "이미 승인 대기 중인 신청이 있습니다."
            }, status=status.HTTP_400_BAD_REQUEST)

        # 새 신청 생성
        sync_request = AppSyncRequest.objects.create(
            profile=profile,
            status=AppSyncRequest.Status.PENDING
        )

        serializer = AppSyncRequestSerializer(sync_request)

        return Response({
            "success": True,
            "message": "연동 신청이 완료되었습니다. 원무과의 승인을 기다려주세요.",
            "request": serializer.data
        }, status=status.HTTP_201_CREATED)

    except UserProfile.DoesNotExist:
        return Response({
            "success": False,
            "message": "존재하지 않는 사용자입니다."
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([AllowAny])
def app_sync_request_list(request):
    """
    앱 연동 신청 목록 조회 (React 원무과 화면에서 호출)

    GET /api/patients/app-sync-requests/?status=PENDING
    """
    status_filter = request.query_params.get('status', None)

    sync_requests = AppSyncRequest.objects.select_related('profile', 'processed_by').all()

    if status_filter:
        sync_requests = sync_requests.filter(status=status_filter)

    sync_requests = sync_requests.order_by('-requested_at')

    serializer = AppSyncRequestSerializer(sync_requests, many=True)

    return Response({
        "success": True,
        "count": sync_requests.count(),
        "results": serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def app_sync_request_approve(request, request_id):
    """
    앱 연동 신청 승인 (React 원무과 화면에서 호출)

    POST /api/patients/app-sync-requests/<request_id>/approve/
    {
        "patient_id": "P20240101001",
        "admin_id": <administration_id>
    }
    """
    patient_id = request.data.get('patient_id')
    admin_id = request.data.get('admin_id')

    try:
        sync_request = AppSyncRequest.objects.select_related('profile').get(request_id=request_id)

        # 이미 처리된 신청인지 확인
        if sync_request.status != AppSyncRequest.Status.PENDING:
            return Response({
                "success": False,
                "message": f"이미 처리된 신청입니다. (현재 상태: {sync_request.get_status_display()})"
            }, status=status.HTTP_400_BAD_REQUEST)

        # 환자번호 확인 또는 신규 생성
        from doctor.models import Patient
        profile = sync_request.profile

        if patient_id:
            try:
                patient = Patient.objects.get(patient_id=patient_id)
            except Patient.DoesNotExist:
                return Response({
                    "success": False,
                    "message": "존재하지 않는 환자번호입니다."
                }, status=status.HTTP_404_NOT_FOUND)
        else:
            # 이미 프로필에 연결된 환자가 있으면 사용
            if profile.linked_patient_id:
                existing = Patient.objects.filter(patient_id=profile.linked_patient_id).first()
                if existing:
                    patient = existing
                    patient_id = existing.patient_id
                else:
                    patient = None
            else:
                patient = Patient.objects.filter(profile=profile).first()

        if not patient_id:
            # 신규 환자 자동 생성 (P + YYMMDD + 001-999)
            today = date.today()
            date_str = today.strftime('%y%m%d')
            prefix = f'P{date_str}'

            existing_patients = Patient.objects.filter(
                patient_id__startswith=prefix
            ).order_by('-patient_id')

            if existing_patients.exists():
                last_patient_id = existing_patients.first().patient_id
                last_sequence = int(last_patient_id[-3:])
                if last_sequence >= 999:
                    return Response({
                        "success": False,
                        "message": "오늘 등록 가능한 환자 수를 초과했습니다. (최대 999명)"
                    }, status=status.HTTP_400_BAD_REQUEST)
                next_sequence = last_sequence + 1
            else:
                next_sequence = 1

            new_patient_id = f'{prefix}{next_sequence:03d}'

            age_value = None
            if profile.birth_date:
                age_value = today.year - profile.birth_date.year
                if (today.month, today.day) < (profile.birth_date.month, profile.birth_date.day):
                    age_value -= 1

            def format_phone_number(value):
                if not value:
                    return None
                digits = ''.join(ch for ch in value if ch.isdigit())
                if len(digits) == 11:
                    return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
                return value

            try:
                patient = Patient.objects.create(
                    patient_id=new_patient_id,
                    name=profile.nickname,
                    date_of_birth=profile.birth_date,
                    age=age_value,
                    gender=profile.gender,
                    phone=format_phone_number(profile.phone_number),
                    profile=profile
                )
                patient_id = patient.patient_id
            except IntegrityError:
                existing = Patient.objects.filter(profile=profile).first()
                if existing:
                    patient = existing
                    patient_id = existing.patient_id
                else:
                    return Response({
                        "success": False,
                        "message": "환자 등록 중 오류가 발생했습니다."
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 신청 승인 처리
        sync_request.status = AppSyncRequest.Status.APPROVED
        sync_request.assigned_patient_id = patient_id
        sync_request.processed_at = timezone.now()

        # admin_id가 제공된 경우 처리자 정보 저장
        if admin_id:
            from administration.models import Administration
            try:
                admin = Administration.objects.get(staff_id=admin_id)
                sync_request.processed_by = admin
            except Administration.DoesNotExist:
                pass

        sync_request.save()

        # UserProfile 업데이트
        profile.linked_patient_id = patient_id
        profile.is_verified = True
        profile.save()

        serializer = AppSyncRequestSerializer(sync_request)

        return Response({
            "success": True,
            "message": f"연동 신청이 승인되었습니다. ({profile.nickname} → {patient_id})",
            "request": serializer.data
        }, status=status.HTTP_200_OK)

    except AppSyncRequest.DoesNotExist:
        return Response({
            "success": False,
            "message": "존재하지 않는 신청입니다."
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([AllowAny])
def app_sync_request_verify(request):
    """
    환자 ID 기반 연동 승인 (Flutter 앱에서 호출)

    POST /api/patients/app-sync-requests/verify/
    {
        "profile": <profile_id>,
        "patient_id": "P20240101001"
    }
    """
    profile_id = request.data.get('profile')
    patient_id = request.data.get('patient_id')

    if not profile_id or not patient_id:
        return Response({
            "success": False,
            "message": "profile_id와 patient_id가 필요합니다."
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        profile = UserProfile.objects.get(profile_id=profile_id)

        from doctor.models import Patient
        try:
            patient = Patient.objects.get(patient_id=patient_id)
        except Patient.DoesNotExist:
            return Response({
                "success": False,
                "message": "존재하지 않는 환자번호입니다."
            }, status=status.HTTP_404_NOT_FOUND)

        if patient.profile and patient.profile_id != profile.profile_id:
            return Response({
                "success": False,
                "message": "이미 연동된 환자입니다."
            }, status=status.HTTP_400_BAD_REQUEST)

        def normalize_phone(value):
            if not value:
                return ''
            return ''.join(ch for ch in value if ch.isdigit())

        def format_phone(value):
            digits = normalize_phone(value)
            if len(digits) == 11:
                return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
            return value

        profile_phone = normalize_phone(profile.phone_number)
        patient_phone = normalize_phone(patient.phone)

        is_match = (
            profile.nickname == patient.name and
            profile.birth_date == patient.date_of_birth and
            profile.gender == patient.gender and
            profile_phone and patient_phone and profile_phone == patient_phone
        )

        if not is_match:
            return Response({
                "success": False,
                "message": "환자 정보와 일치하지 않습니다."
            }, status=status.HTTP_400_BAD_REQUEST)

        if profile.phone_number:
            patient.phone = format_phone(profile.phone_number)
        patient.profile = profile
        patient.save()

        sync_request = AppSyncRequest.objects.filter(
            profile=profile
        ).order_by('-requested_at').first()

        if sync_request and sync_request.status != AppSyncRequest.Status.PENDING:
            return Response({
                "success": False,
                "message": "이미 처리된 신청입니다."
            }, status=status.HTTP_400_BAD_REQUEST)

        if not sync_request:
            sync_request = AppSyncRequest.objects.create(
                profile=profile,
                status=AppSyncRequest.Status.PENDING
            )

        sync_request.status = AppSyncRequest.Status.APPROVED
        sync_request.assigned_patient_id = patient.patient_id
        sync_request.processed_at = timezone.now()
        sync_request.save()

        profile.linked_patient_id = patient.patient_id
        profile.is_verified = True
        profile.save()

        serializer = AppSyncRequestSerializer(sync_request)

        return Response({
            "success": True,
            "message": "연동 신청이 승인되었습니다.",
            "request": serializer.data
        }, status=status.HTTP_200_OK)

    except UserProfile.DoesNotExist:
        return Response({
            "success": False,
            "message": "존재하지 않는 사용자입니다."
        }, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([AllowAny])
def app_sync_request_reject(request, request_id):
    """
    앱 연동 신청 거절 (React 원무과 화면에서 호출)

    POST /api/patients/app-sync-requests/<request_id>/reject/
    {
        "admin_id": <administration_id>  # 선택사항
    }
    """
    admin_id = request.data.get('admin_id')

    try:
        sync_request = AppSyncRequest.objects.get(request_id=request_id)

        # 이미 처리된 신청인지 확인
        if sync_request.status != AppSyncRequest.Status.PENDING:
            return Response({
                "success": False,
                "message": f"이미 처리된 신청입니다. (현재 상태: {sync_request.get_status_display()})"
            }, status=status.HTTP_400_BAD_REQUEST)

        # 신청 거절 처리
        sync_request.status = AppSyncRequest.Status.REJECTED
        sync_request.processed_at = timezone.now()

        # admin_id가 제공된 경우 처리자 정보 저장
        if admin_id:
            from administration.models import Administration
            try:
                admin = Administration.objects.get(staff_id=admin_id)
                sync_request.processed_by = admin
            except Administration.DoesNotExist:
                pass

        sync_request.save()

        serializer = AppSyncRequestSerializer(sync_request)

        return Response({
            "success": True,
            "message": "연동 신청이 거절되었습니다.",
            "request": serializer.data
        }, status=status.HTTP_200_OK)

    except AppSyncRequest.DoesNotExist:
        return Response({
            "success": False,
            "message": "존재하지 않는 신청입니다."
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([AllowAny])
def app_sync_request_status(request, profile_id):
    """
    특정 사용자의 연동 신청 상태 조회 (Flutter 앱에서 호출)

    GET /api/patients/app-sync-requests/status/<profile_id>/
    """
    try:
        # 가장 최근 신청 조회
        sync_request = AppSyncRequest.objects.filter(
            profile_id=profile_id
        ).order_by('-requested_at').first()

        if not sync_request:
            return Response({
                "success": True,
                "has_request": False,
                "message": "연동 신청 내역이 없습니다."
            }, status=status.HTTP_200_OK)

        serializer = AppSyncRequestSerializer(sync_request)

        return Response({
            "success": True,
            "has_request": True,
            "request": serializer.data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({
            "success": False,
            "message": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ========== 진료 예약 관련 API ==========

@api_view(['GET'])
@permission_classes([AllowAny])
def get_departments(request):
    """
    진료과 목록 조회 API
    
    GET /api/patients/departments/
    """
    from accounts.models import Department
    
    # DB에서 특정 진료과만 조회 (소화기내과, 영상의학과)
    departments = Department.objects.filter(dept_name__in=['소화기내과', '영상의학과']).order_by('dept_name')
    
    department_list = [{'department_name': dept.dept_name} for dept in departments]
    
    return Response({
        'success': True,
        'departments': department_list
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_doctors(request):
    """
    의사 목록 조회 API (진료과별)
    
    GET /api/patients/doctors/?department=소화기내과
    """
    from doctor.models import Doctor
    from .serializers import DoctorListSerializer
    
    department = request.query_params.get('department', None)
    
    if not department:
        return Response({
            'success': False,
            'message': '진료과를 선택해주세요.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # 해당 진료과의 의사 목록 조회
    doctors = Doctor.objects.filter(department__dept_name=department).select_related('department').order_by('name')
    
    if not doctors.exists():
        return Response({
            'success': False,
            'message': '해당 진료과에 의사가 없습니다.'
        }, status=status.HTTP_404_NOT_FOUND)
    
    serializer = DoctorListSerializer(doctors, many=True)
    
    return Response({
        'success': True,
        'doctors': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def create_appointment(request):
    """
    당일 예약 생성 API (앱 전용)
    
    POST /api/patients/appointments/
    {
        "profile_id": 1,
        "doctor_id": 3,
        "notes": "복통"
    }
    """
    from doctor.models import Doctor, Patient, Appointment
    from .serializers import AppointmentCreateSerializer
    
    serializer = AppointmentCreateSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'success': False,
            'message': '입력 데이터가 올바르지 않습니다.',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    profile_id = serializer.validated_data['profile_id']
    doctor_id = serializer.validated_data['doctor_id']
    notes = serializer.validated_data.get('notes', '')
    
    # 1. UserProfile 조회
    try:
        profile = UserProfile.objects.get(profile_id=profile_id)
    except UserProfile.DoesNotExist:
        return Response({
            'success': False,
            'message': '존재하지 않는 사용자입니다.'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # 2. 병원 연동 확인
    if not profile.is_verified or not profile.linked_patient_id:
        return Response({
            'success': False,
            'message': '병원 연동이 필요합니다. 마이페이지에서 연동을 진행해주세요.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # 3. Patient 조회
    try:
        patient = Patient.objects.get(patient_id=profile.linked_patient_id)
    except Patient.DoesNotExist:
        return Response({
            'success': False,
            'message': '연동된 환자 정보를 찾을 수 없습니다.'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # 4. Doctor 조회
    try:
        doctor = Doctor.objects.get(doctor_id=doctor_id)
    except Doctor.DoesNotExist:
        return Response({
            'success': False,
            'message': '존재하지 않는 의사입니다.'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # 5. 당일 예약 생성
    today = date.today()
    from datetime import time
    
    # 당일 예약 시간은 현재 시각 기준 + 10분으로 설정
    from datetime import datetime, timedelta
    now = datetime.now()
    appointment_time = (now + timedelta(minutes=10)).time()
    
    try:
        appointment = Appointment.objects.create(
            patient=patient,
            doctor=doctor,
            appointment_date=today,
            appointment_time=appointment_time,
            appointment_type='당일예약',
            status='대기',
            department=doctor.department.dept_name,
            notes=notes
        )
        
        return Response({
            'success': True,
            'message': '예약이 완료되었습니다.',
            'appointment': {
                'appointment_id': appointment.appointment_id,
                'appointment_date': appointment.appointment_date.isoformat(),
                'appointment_time': appointment.appointment_time.strftime('%H:%M'),
                'doctor_name': doctor.name,
                'department': doctor.department.dept_name,
                'status': appointment.status
            }
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': f'예약 생성 중 오류가 발생했습니다: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_appointments(request):
    """
    예약 목록 조회 API (원무과용)
    
    GET /api/patients/appointments/list/?status=대기
    """
    from doctor.models import Appointment
    
    status_filter = request.query_params.get('status', None)
    
    appointments = Appointment.objects.select_related('patient', 'doctor').order_by('-created_at')
    
    if status_filter:
        appointments = appointments.filter(status=status_filter)
    
    # 예약 목록 직렬화
    appointment_list = []
    for appt in appointments:
        appointment_list.append({
            'appointment_id': appt.appointment_id,
            'appointment_date': appt.appointment_date.isoformat(),
            'appointment_time': appt.appointment_time.strftime('%H:%M'),
            'appointment_type': appt.appointment_type,
            'status': appt.status,
            'department': appt.department,
            'notes': appt.notes,
            'patient': {
                'patient_id': appt.patient.patient_id,
                'name': appt.patient.name,
                'phone': appt.patient.phone,
            },
            'doctor': {
                'doctor_id': appt.doctor.doctor_id if appt.doctor else None,
                'doctor_name': appt.doctor.name if appt.doctor else None,
            } if appt.doctor else None,
            'created_at': appt.created_at.isoformat(),
        })
    
    return Response({
        'success': True,
        'appointments': appointment_list,
        'count': len(appointment_list),
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def approve_appointment(request, appointment_id):
    """
    예약 승인 API (원무과용)

    POST /api/patients/appointments/{appointment_id}/approve/

    워크플로우:
    1. Appointment 조회
    2. Encounter 생성 (진료 대기열에 추가)
    3. Appointment 상태를 '예약완료'로 변경
    """
    from doctor.models import Appointment, Encounter
    from datetime import datetime

    try:
        appointment = Appointment.objects.select_related('patient', 'doctor').get(appointment_id=appointment_id)
    except Appointment.DoesNotExist:
        return Response({
            'success': False,
            'message': '존재하지 않는 예약입니다.'
        }, status=status.HTTP_404_NOT_FOUND)

    # 이미 처리된 예약인지 확인
    if appointment.status != '대기':
        return Response({
            'success': False,
            'message': f'이미 처리된 예약입니다. (현재 상태: {appointment.status})'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Encounter 생성 (진료 대기열에 추가)
    try:
        encounter = Encounter.objects.create(
            patient=appointment.patient,
            doctor=appointment.doctor,
            status='IN_PROGRESS',  # FHIR 상태
            workflow_state='WAITING_CLINIC',  # 진료 대기
            encounter_date=appointment.appointment_date,
            scheduled_time=datetime.combine(appointment.appointment_date, appointment.appointment_time),
            visit_reason=appointment.notes or '당일 예약',
        )

        # 예약 상태를 '예약완료'로 변경
        appointment.status = '예약완료'
        appointment.save()

        return Response({
            'success': True,
            'message': '예약이 승인되었습니다. 환자가 진료 대기열에 추가되었습니다.',
            'encounter_id': encounter.encounter_id,
            'appointment': {
                'appointment_id': appointment.appointment_id,
                'status': appointment.status,
                'patient_name': appointment.patient.name,
                'doctor_name': appointment.doctor.name if appointment.doctor else None,
                'department': appointment.department,
                'appointment_date': appointment.appointment_date.isoformat(),
                'appointment_time': appointment.appointment_time.strftime('%H:%M'),
            },
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': f'예약 승인 중 오류가 발생했습니다: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def reject_appointment(request, appointment_id):
    """
    예약 거절 API (원무과용)

    POST /api/patients/appointments/{appointment_id}/reject/
    {
        "reason": "진료 불가"
    }

    워크플로우:
    1. Appointment 조회
    2. 거절 사유를 notes에 추가
    3. Appointment 상태를 '예약마감'으로 변경
    """
    from doctor.models import Appointment

    try:
        appointment = Appointment.objects.select_related('patient', 'doctor').get(appointment_id=appointment_id)
    except Appointment.DoesNotExist:
        return Response({
            'success': False,
            'message': '존재하지 않는 예약입니다.'
        }, status=status.HTTP_404_NOT_FOUND)

    # 이미 처리된 예약인지 확인
    if appointment.status != '대기':
        return Response({
            'success': False,
            'message': f'이미 처리된 예약입니다. (현재 상태: {appointment.status})'
        }, status=status.HTTP_400_BAD_REQUEST)

    reason = request.data.get('reason', '')

    # 거절 사유를 notes에 추가
    if reason:
        if appointment.notes:
            appointment.notes += f"\n[거절 사유] {reason}"
        else:
            appointment.notes = f"[거절 사유] {reason}"

    # 예약 상태를 '예약마감'으로 변경
    appointment.status = '예약마감'
    appointment.save()

    return Response({
        'success': True,
        'message': '예약이 거절되었습니다.',
        'appointment': {
            'appointment_id': appointment.appointment_id,
            'status': appointment.status,
            'patient_name': appointment.patient.name,
            'doctor_name': appointment.doctor.name if appointment.doctor else None,
            'department': appointment.department,
            'appointment_date': appointment.appointment_date.isoformat(),
            'appointment_time': appointment.appointment_time.strftime('%H:%M'),
            'notes': appointment.notes,
        },
    }, status=status.HTTP_200_OK)
