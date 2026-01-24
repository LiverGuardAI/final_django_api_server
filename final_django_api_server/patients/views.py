# patients/views.py
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth.hashers import check_password
from django.utils import timezone
from accounts.models import DutySchedule
from django.db import IntegrityError
from datetime import date, datetime, time, timedelta

from .models import UserProfile, AppSyncRequest, Allergy, DiseaseHistory
from .serializers import SignupSerializer, LoginSerializer, AppSyncRequestSerializer, AllergySerializer, DiseaseHistorySerializer
from doctor.models import Patient, MedicalRecord, Prescription, Encounter
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


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

        # WebSocket으로 원무과에 실시간 알림 전송
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                'clinic_dashboard',
                {
                    'type': 'app_sync_request',
                    'message': f'새로운 앱 연동 신청: {profile.nickname}',
                    'data': serializer.data
                }
            )
        except Exception as e:
            print(f"WebSocket 알림 전송 실패: {e}")

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

        # WebSocket으로 Flutter 앱에 실시간 알림 전송
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'app_user_{profile.profile_id}',
                {
                    'type': 'app_sync_result',
                    'message': '병원 연동이 승인되었습니다.',
                    'data': {
                        'status': 'APPROVED',
                        'patient_id': patient_id,
                        'profile_id': str(profile.profile_id),
                    }
                }
            )
        except Exception as e:
            print(f"WebSocket 알림 전송 실패: {e}")

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

        # WebSocket으로 Flutter 앱에 실시간 알림 전송
        try:
            profile = sync_request.profile
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'app_user_{profile.profile_id}',
                {
                    'type': 'app_sync_result',
                    'message': '병원 연동이 거절되었습니다.',
                    'data': {
                        'status': 'REJECTED',
                        'profile_id': str(profile.profile_id),
                    }
                }
            )
        except Exception as e:
            print(f"WebSocket 알림 전송 실패: {e}")

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

    department_list = [{'dept_name': dept.dept_name} for dept in departments]

    return Response({
        'success': True,
        'departments': department_list
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_doctor_available_dates(request):
    """
    의사의 근무 가능한 날짜 목록 조회 API

    GET /api/patients/doctors/{doctor_id}/available-dates/?days=7

    심야 근무(22:00~06:00)의 경우 시작일과 종료일 모두 포함
    """
    from doctor.models import Doctor
    from accounts.models import DutySchedule
    from datetime import datetime, timedelta, time as dt_time

    doctor_id = request.query_params.get('doctor_id')
    days = int(request.query_params.get('days', 7))

    if not doctor_id:
        return Response({
            'success': False,
            'message': '의사 ID를 입력해주세요.'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        doctor = Doctor.objects.get(doctor_id=doctor_id)
    except Doctor.DoesNotExist:
        return Response({
            'success': False,
            'message': '존재하지 않는 의사입니다.'
        }, status=status.HTTP_404_NOT_FOUND)

    # 오늘부터 days일 동안의 날짜 범위
    today = date.today()
    end_date = today + timedelta(days=days - 1)

    # UTC 기준으로 범위 계산 (KST -9시간)
    range_start = datetime.combine(today, dt_time.min) - timedelta(hours=9)
    range_end = datetime.combine(end_date, dt_time.max) - timedelta(hours=9)

    # 해당 기간의 근무 일정 조회
    duty_schedules = DutySchedule.objects.filter(
        user=doctor.user,
        work_role='DOCTOR',
        schedule_status='CONFIRMED',
        start_time__lte=range_end,
        end_time__gte=range_start
    ).order_by('start_time')

    # 근무 가능한 날짜 수집 (심야 근무는 양일 모두 포함)
    available_dates = set()

    for schedule in duty_schedules:
        # UTC -> KST 변환
        start_kst = schedule.start_time + timedelta(hours=9)
        end_kst = schedule.end_time + timedelta(hours=9)

        # 시작일 추가
        if today <= start_kst.date() <= end_date:
            available_dates.add(start_kst.date().isoformat())

        # 종료일이 다른 날이면 (심야 근무) 종료일도 추가
        if start_kst.date() != end_kst.date():
            if today <= end_kst.date() <= end_date:
                available_dates.add(end_kst.date().isoformat())

    # 정렬된 리스트로 변환
    sorted_dates = sorted(list(available_dates))

    return Response({
        'success': True,
        'doctor_id': doctor.doctor_id,
        'doctor_name': doctor.name,
        'available_dates': sorted_dates
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_doctors(request):
    """
    의사 목록 조회 API (진료과별) - duty_schedules 포함

    GET /api/patients/doctors/?department=소화기내과&date=2024-01-15
    """
    from doctor.models import Doctor
    from accounts.models import DutySchedule
    from .serializers import DoctorListSerializer
    from datetime import datetime, timedelta
    from django.db.models import Q

    department = request.query_params.get('department', None)
    selected_date_str = request.query_params.get('date', None)

    if not department:
        return Response({
            'success': False,
            'message': '진료과를 선택해주세요.'
        }, status=status.HTTP_400_BAD_REQUEST)

    # 날짜 파싱 (없으면 오늘)
    if selected_date_str:
        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        except ValueError:
            selected_date = date.today()
    else:
        selected_date = date.today()

    # 선택한 날짜의 시작과 끝 시간 계산 (UTC 기준, KST 00:00 = UTC 전날 15:00)
    from datetime import time as dt_time
    from collections import defaultdict

    # KST 00:00:00 = UTC 전날 15:00:00, KST 23:59:59 = UTC 14:59:59
    day_start = datetime.combine(selected_date, dt_time.min) - timedelta(hours=9)
    day_end = datetime.combine(selected_date, dt_time.max) - timedelta(hours=9)

    # 해당 진료과의 의사 목록 조회 (user도 함께 조회)
    doctors = Doctor.objects.filter(
        department__dept_name=department
    ).select_related('department', 'user').order_by('name')

    if not doctors.exists():
        return Response({
            'success': False,
            'message': '해당 진료과에 의사가 없습니다.'
        }, status=status.HTTP_404_NOT_FOUND)

    # 모든 의사의 user_id 목록
    doctor_user_ids = [doctor.user_id for doctor in doctors]

    # 한 번의 쿼리로 해당 날짜의 모든 의사 근무 일정 조회
    all_schedules = DutySchedule.objects.filter(
        user_id__in=doctor_user_ids,
        work_role='DOCTOR',
        schedule_status='CONFIRMED',
        start_time__lte=day_end,
        end_time__gte=day_start
    ).order_by('user_id', 'start_time')

    # user_id별로 근무 일정 그룹화 (UTC+9 시간 보정)
    schedule_map = defaultdict(list)
    for schedule in all_schedules:
        # UTC로 저장된 시간에 9시간 더하기 (KST)
        start_kst = schedule.start_time + timedelta(hours=9)
        end_kst = schedule.end_time + timedelta(hours=9)
        schedule_map[schedule.user_id].append({
            'start_time': start_kst.strftime('%H:%M'),
            'end_time': end_kst.strftime('%H:%M'),
            'shift_type': schedule.shift_type or '일반'
        })

    # 의사 목록 생성
    doctor_list = []
    for doctor in doctors:
        working_hours = schedule_map.get(doctor.user_id, [])
        doctor_list.append({
            'doctor_id': doctor.doctor_id,
            'name': doctor.name,
            'department': doctor.department.dept_name,
            'working_hours': working_hours,
            'is_on_duty': len(working_hours) > 0
        })

    return Response({
        'success': True,
        'doctors': doctor_list
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_available_time_slots(request):
    """
    예약 가능한 시간 슬롯 조회 API

    GET /api/patients/appointments/available-slots/?doctor_id=3&date=2025-01-14
    """
    from doctor.models import Doctor, Appointment
    from accounts.models import DutySchedule
    from django.db.models import Q
    from datetime import datetime, time, timedelta

    doctor_id = request.query_params.get('doctor_id')
    selected_date_str = request.query_params.get('date')

    if not doctor_id or not selected_date_str:
        return Response({
            'success': False,
            'message': '의사 ID와 날짜를 입력해주세요.'
        }, status=status.HTTP_400_BAD_REQUEST)

    # 날짜 파싱
    try:
        selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
    except ValueError:
        return Response({
            'success': False,
            'message': '날짜 형식이 올바르지 않습니다. (YYYY-MM-DD)'
        }, status=status.HTTP_400_BAD_REQUEST)

    # 의사 조회
    try:
        doctor = Doctor.objects.get(doctor_id=doctor_id)
    except Doctor.DoesNotExist:
        return Response({
            'success': False,
            'message': '존재하지 않는 의사입니다.'
        }, status=status.HTTP_404_NOT_FOUND)

    # 해당 날짜의 근무 일정 조회 (확정된 일정만)
    # 선택한 날짜의 시작과 끝 시간 계산 (UTC 기준, KST -9시간)
    from datetime import time as dt_time

    day_start = datetime.combine(selected_date, dt_time.min) - timedelta(hours=9)
    day_end = datetime.combine(selected_date, dt_time.max) - timedelta(hours=9)

    duty_schedules = DutySchedule.objects.filter(
        Q(user=doctor.user) &
        Q(work_role='DOCTOR') &
        Q(schedule_status='CONFIRMED') &
        Q(start_time__lte=day_end) &
        Q(end_time__gte=day_start)
    ).order_by('start_time')

    if not duty_schedules.exists():
        return Response({
            'success': False,
            'message': '해당 날짜에 근무하지 않습니다.'
        }, status=status.HTTP_400_BAD_REQUEST)

    # 근무 시간 정보 생성 (UTC+9 시간 보정)
    working_hours = []
    for schedule in duty_schedules:
        start_kst = schedule.start_time + timedelta(hours=9)
        end_kst = schedule.end_time + timedelta(hours=9)
        working_hours.append({
            'start_time': start_kst.strftime('%H:%M'),
            'end_time': end_kst.strftime('%H:%M'),
        })

    # 이미 예약된 시간 조회 (승인된 예약만 - 대기/마감은 캘린더에 표시 안함)
    existing_appointments = Appointment.objects.filter(
        doctor=doctor,
        appointment_date=selected_date,
        status='예약완료'
    ).values_list('appointment_time', flat=True)

    booked_times = set()
    for apt_time in existing_appointments:
        booked_times.add(apt_time.strftime('%H:%M'))

    # 30분 단위 타임 슬롯 생성 (근무 시간 내에서만, UTC+9 보정)
    available_slots = []
    for schedule in duty_schedules:
        # UTC로 저장된 시간에 9시간 더하기 (KST)
        start_dt = schedule.start_time + timedelta(hours=9)
        end_dt = schedule.end_time + timedelta(hours=9)

        current_dt = start_dt.replace(minute=(start_dt.minute // 30) * 30, second=0, microsecond=0)

        while current_dt < end_dt:
            time_str = current_dt.strftime('%H:%M')

            # 해당 날짜의 슬롯만 포함 (KST 기준)
            if current_dt.date() == selected_date:
                slot_info = {
                    'time': time_str,
                    'is_available': time_str not in booked_times
                }
                available_slots.append(slot_info)

            current_dt += timedelta(minutes=30)

    # 중복 제거 및 정렬
    seen = set()
    unique_slots = []
    for slot in available_slots:
        if slot['time'] not in seen:
            seen.add(slot['time'])
            unique_slots.append(slot)

    unique_slots.sort(key=lambda x: x['time'])

    return Response({
        'success': True,
        'available_slots': unique_slots,
        'working_hours': working_hours
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
    appointment_date_str = request.data.get('appointment_date')  # "YYYY-MM-DD" 형식
    appointment_time_str = request.data.get('appointment_time')  # "HH:MM" 형식
    notes = serializer.validated_data.get('notes', '')

    print(f"📅 [create_appointment] 받은 데이터: appointment_date={appointment_date_str}, appointment_time={appointment_time_str}")

    # 날짜 파싱
    if appointment_date_str:
        try:
            appointment_date = datetime.strptime(appointment_date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({
                'success': False,
                'message': '올바른 날짜 형식이 아닙니다. (YYYY-MM-DD)'
            }, status=status.HTTP_400_BAD_REQUEST)
    else:
        appointment_date = date.today()

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
    
    # 5. 시간 파싱
    try:
        # "HH:MM" 형식을 time 객체로 변환
        hour, minute = map(int, appointment_time_str.split(':'))
        appointment_time = time(hour, minute)
    except (ValueError, AttributeError):
        return Response({
            'success': False,
            'message': '올바른 시간 형식이 아닙니다. (HH:MM)'
        }, status=status.HTTP_400_BAD_REQUEST)

    # 6. 의사 근무 일정 확인 (duty_schedules) - 확정된 일정만
    from django.db.models import Q

    # 선택한 날짜의 시작과 끝 시간 계산 (UTC 기준, KST -9시간)
    day_start = datetime.combine(appointment_date, time.min) - timedelta(hours=9)
    day_end = datetime.combine(appointment_date, time.max) - timedelta(hours=9)

    duty_schedules = DutySchedule.objects.filter(
        Q(user=doctor.user) &
        Q(work_role='DOCTOR') &
        Q(schedule_status='CONFIRMED') &
        Q(start_time__lte=day_end) &
        Q(end_time__gte=day_start)
    ).order_by('start_time')

    # 근무 중이 아니면 예약 불가
    if not duty_schedules.exists():
        return Response({
            'success': False,
            'message': '선택한 의사가 해당 날짜에 근무하지 않습니다.',
            'is_not_on_duty': True
        }, status=status.HTTP_400_BAD_REQUEST)

    # 8. 선택한 시간이 근무 시간 내인지 확인 (UTC+9 보정)
    is_within_duty_hours = False
    for schedule in duty_schedules:
        # UTC로 저장된 시간에 9시간 더하기 (KST)
        schedule_start = (schedule.start_time + timedelta(hours=9)).time()
        schedule_end = (schedule.end_time + timedelta(hours=9)).time()

        if schedule_start <= appointment_time <= schedule_end:
            is_within_duty_hours = True
            break

    if not is_within_duty_hours:
        return Response({
            'success': False,
            'message': '선택한 시간은 의사의 근무 시간이 아닙니다.',
        }, status=status.HTTP_400_BAD_REQUEST)

    # 10. 해당 시간에 이미 승인된 예약이 있는지 확인
    existing_appointment_at_time = Appointment.objects.filter(
        doctor=doctor,
        appointment_date=appointment_date,
        appointment_time=appointment_time,
        status='예약완료'
    ).first()

    if existing_appointment_at_time:
        return Response({
            'success': False,
            'message': '선택한 시간에 이미 예약이 있습니다. 다른 시간을 선택해주세요.',
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        # 예약 타입 결정 (당일이면 당일예약, 아니면 사전예약)
        is_same_day = (appointment_date == date.today())
        apt_type = '당일예약' if is_same_day else '사전예약'

        appointment = Appointment.objects.create(
            patient=patient,
            doctor=doctor,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            appointment_type=apt_type,
            status='대기',
            department=doctor.department.dept_name,
            notes=notes
        )

        # WebSocket으로 실시간 알림 전송
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        channel_layer = get_channel_layer()
        if channel_layer:
            try:
                async_to_sync(channel_layer.group_send)(
                    'clinic_dashboard',
                    {
                        'type': 'update_queue',
                        'message': '새로운 예약이 접수되었습니다.',
                        'data': {
                            'event_type': 'new_appointment',
                            'appointment': {
                                'appointment_id': appointment.appointment_id,
                                'patient_name': patient.name,
                                'patient_id': patient.patient_id,
                                'doctor_id': doctor.doctor_id,
                                'doctor_name': doctor.name,
                                'department': doctor.department.dept_name,
                                'appointment_date': appointment.appointment_date.isoformat(),
                                'appointment_time': appointment.appointment_time.strftime('%H:%M'),
                                'status': appointment.status,
                                'notes': notes,
                                'appointment_type': '당일예약',
                            }
                        }
                    }
                )
                print(f"✅ WebSocket 알림 전송 성공: 새 예약 {appointment.appointment_id}")
            except Exception as ws_error:
                print(f"❌ WebSocket 알림 전송 실패: {ws_error}")

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
def check_appointment_status(request):
    """
    사용자의 당일 예약 상태 확인 API (앱 전용)

    GET /api/patients/appointments/status/?profile_id=1
    """
    from doctor.models import Appointment, Patient
    from datetime import date

    profile_id = request.query_params.get('profile_id')

    if not profile_id:
        return Response({
            'success': False,
            'message': 'profile_id가 필요합니다.'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        profile = UserProfile.objects.get(profile_id=profile_id)
    except UserProfile.DoesNotExist:
        return Response({
            'success': False,
            'message': '존재하지 않는 사용자입니다.'
        }, status=status.HTTP_404_NOT_FOUND)

    if not profile.is_verified or not profile.linked_patient_id:
        return Response({
            'success': True,
            'has_appointment': False,
            'message': '병원 연동이 필요합니다.'
        }, status=status.HTTP_200_OK)

    try:
        patient = Patient.objects.get(patient_id=profile.linked_patient_id)
    except Patient.DoesNotExist:
        return Response({
            'success': True,
            'has_appointment': False,
            'message': '연동된 환자 정보를 찾을 수 없습니다.'
        }, status=status.HTTP_200_OK)

    # 오늘 이후 예약 확인 (당일 + 사전예약 포함)
    # 진료완료 상태는 제외 - 새로운 예약 가능하도록
    today = date.today()
    appointment = Appointment.objects.filter(
        patient=patient,
        appointment_date__gte=today,
        status__in=['대기', '예약완료']  # 진료완료, 취소, 마감 제외
    ).exclude(
        # 과거 날짜의 예약완료는 제외 (진료완료로 처리 안된 것)
        appointment_date__lt=today,
        status='예약완료'
    ).order_by('appointment_date', 'appointment_time').first()

    if appointment:
        return Response({
            'success': True,
            'has_appointment': True,
            'appointment': {
                'appointment_id': appointment.appointment_id,
                'appointment_date': appointment.appointment_date.isoformat(),
                'appointment_time': appointment.appointment_time.strftime('%H:%M'),
                'doctor_name': appointment.doctor.name if appointment.doctor else None,
                'department': appointment.department,
                'status': appointment.status,
                'notes': appointment.notes
            }
        }, status=status.HTTP_200_OK)
    else:
        return Response({
            'success': True,
            'has_appointment': False,
            'message': '당일 예약이 없습니다.'
        }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_appointments(request):
    """
    예약 목록 조회 API (원무과용)

    GET /api/patients/appointments/list/?status=대기&date=2025-01-16
    """
    from doctor.models import Appointment
    from datetime import datetime

    status_filter = request.query_params.get('status', None)
    date_filter = request.query_params.get('date', None)

    appointments = Appointment.objects.select_related('patient', 'doctor').order_by('-created_at')

    if status_filter:
        appointments = appointments.filter(status=status_filter)

    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            appointments = appointments.filter(appointment_date=filter_date)
        except ValueError:
            pass  # 잘못된 날짜 형식이면 무시
    
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
            'patient_name': appt.patient.name if appt.patient else None,
            'patient_id': appt.patient.patient_id if appt.patient else None,
            'doctor_name': appt.doctor.name if appt.doctor else None,
            'doctor_id': appt.doctor.doctor_id if appt.doctor else None,
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
    2. 근무 일정 확인
    3. 중복 예약 확인
    4. Appointment 상태를 '예약완료'로 변경

    Note: Encounter(진료 대기열)는 원무과에서 수동으로 추가합니다.
    """
    from doctor.models import Appointment
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

    # duty schedule check
    dt = datetime.combine(appointment.appointment_date, appointment.appointment_time)
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    if not DutySchedule.objects.filter(
        user_id=appointment.doctor.user_id,
        schedule_status='CONFIRMED',
        start_time__lt=dt,
        end_time__gt=dt
    ).exists():
        return Response({
            'success': False,
            'message': '해당 시간은 근무 일정이 아닙니다.'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        today = appointment.appointment_date
        requested_time = appointment.appointment_time

        # 해당 시간에 이미 승인된 예약이 있는지 확인 (승인된 예약만 체크)
        existing_approved = Appointment.objects.filter(
            doctor=appointment.doctor,
            appointment_date=today,
            appointment_time=requested_time,
            status='예약완료'
        ).exists()

        if existing_approved:
            return Response({
                'success': False,
                'message': f'해당 시간({requested_time.strftime("%H:%M")})에 이미 승인된 예약이 있습니다. 이 예약을 거절해주세요.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # 예약 상태를 '예약완료'로 변경 (Encounter는 생성하지 않음)
        appointment.status = '예약완료'
        appointment.save()

        return Response({
            'success': True,
            'message': '예약이 승인되었습니다.',
            'appointment': {
                'appointment_id': appointment.appointment_id,
                'status': appointment.status,
                'patient_name': appointment.patient.name,
                'doctor_name': appointment.doctor.name if appointment.doctor else None,
                'department': appointment.department,
                'appointment_date': appointment.appointment_date.isoformat(),
                'appointment_time': requested_time.strftime('%H:%M'),
            },
        }, status=status.HTTP_200_OK)

    except Exception as e:
        import traceback
        traceback.print_exc()
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


# ==================== 문진표 관련 API ====================

@api_view(['POST'])
@permission_classes([AllowAny])
def create_questionnaire(request):
    """
    문진표 작성 API (환자 앱용)

    POST /api/patients/questionnaire/
    {
        "profile_id": 1,
        "data": {
            "chief_complaint": "복부 불편감",
            "symptom_duration": "2주",
            "pain_level": 5,
            "symptoms": {"abdominalPain": true, "nausea": true, ...},
            "medical_history": {...},
            ...
        }
    }
    """
    from doctor.models import Appointment, Encounter, Questionnaire, Patient
    from .models import UserProfile

    profile_id = request.data.get('profile_id')
    questionnaire_data = request.data.get('data', {})

    if not profile_id:
        return Response({
            'success': False,
            'message': 'profile_id가 필요합니다.'
        }, status=status.HTTP_400_BAD_REQUEST)

    # 1. UserProfile 조회
    try:
        user_profile = UserProfile.objects.get(profile_id=profile_id)
    except UserProfile.DoesNotExist:
        return Response({
            'success': False,
            'message': '사용자를 찾을 수 없습니다.'
        }, status=status.HTTP_404_NOT_FOUND)

    # 2. 연동된 Patient 확인
    if not user_profile.linked_patient_id:
        return Response({
            'success': False,
            'message': '병원 환자 정보와 연동되지 않았습니다.'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        patient = Patient.objects.get(patient_id=user_profile.linked_patient_id)
    except Patient.DoesNotExist:
        return Response({
            'success': False,
            'message': '연동된 환자 정보를 찾을 수 없습니다.'
        }, status=status.HTTP_404_NOT_FOUND)

    # 3. 오늘 이후 승인된 예약 확인 (예약완료 상태만, 당일 + 사전예약 포함)
    today = date.today()
    appointment = Appointment.objects.filter(
        patient=patient,
        appointment_date__gte=today,
        status='예약완료'
    ).order_by('appointment_date', 'appointment_time').first()

    if not appointment:
        return Response({
            'success': False,
            'message': '승인된 진료 예약이 없습니다.'
        }, status=status.HTTP_400_BAD_REQUEST)

    # 4. 해당 예약에 연결된 Encounter 찾기
    try:
        encounter = Encounter.objects.get(appointment=appointment)
    except Encounter.DoesNotExist:
        return Response({
            'success': False,
            'message': '진료 대기열에 등록되지 않았습니다. 원무과에 문의해주세요.'
        }, status=status.HTTP_400_BAD_REQUEST)

    # 4-1. 진료중 상태 체크 - 문진표 저장 불가 (진료대기 상태에서는 작성 가능)
    if encounter.workflow_state == 'IN_CLINIC':
        return Response({
            'success': False,
            'blocked': True,
            'message': '현재 진료중 상태입니다. 문진표를 저장할 수 없습니다.',
            'workflow_state': encounter.workflow_state,
        }, status=status.HTTP_400_BAD_REQUEST)

    # 5. 이미 문진표가 있는지 확인
    existing_questionnaire = Questionnaire.objects.filter(encounter=encounter).first()
    if existing_questionnaire:
        # 기존 문진표 업데이트
        existing_questionnaire.data = questionnaire_data
        existing_questionnaire.status = Questionnaire.QStatus.COMPLETED
        existing_questionnaire.save()

        # WebSocket으로 문진표 업데이트 알림
        _send_questionnaire_update(encounter, patient, 'updated')

        return Response({
            'success': True,
            'message': '문진표가 수정되었습니다.',
            'questionnaire_id': existing_questionnaire.questionnaire_id,
        }, status=status.HTTP_200_OK)

    # 6. 새 문진표 생성
    questionnaire = Questionnaire.objects.create(
        encounter=encounter,
        patient=patient,
        data=questionnaire_data,
        status=Questionnaire.QStatus.COMPLETED,
    )

    # WebSocket으로 문진표 생성 알림
    _send_questionnaire_update(encounter, patient, 'created')

    return Response({
        'success': True,
        'message': '문진표가 저장되었습니다.',
        'questionnaire_id': questionnaire.questionnaire_id,
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_questionnaire(request):
    """
    문진표 조회 API (환자 앱용)

    GET /api/patients/questionnaire/?profile_id=1
    """
    from doctor.models import Appointment, Encounter, Questionnaire, Patient
    from .models import UserProfile

    profile_id = request.query_params.get('profile_id')

    if not profile_id:
        return Response({
            'success': False,
            'message': 'profile_id가 필요합니다.'
        }, status=status.HTTP_400_BAD_REQUEST)

    # 1. UserProfile 조회
    try:
        user_profile = UserProfile.objects.get(profile_id=profile_id)
    except UserProfile.DoesNotExist:
        return Response({
            'success': False,
            'message': '사용자를 찾을 수 없습니다.'
        }, status=status.HTTP_404_NOT_FOUND)

    # 2. 연동된 Patient 확인
    if not user_profile.linked_patient_id:
        return Response({
            'success': False,
            'message': '병원 환자 정보와 연동되지 않았습니다.'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        patient = Patient.objects.get(patient_id=user_profile.linked_patient_id)
    except Patient.DoesNotExist:
        return Response({
            'success': False,
            'message': '연동된 환자 정보를 찾을 수 없습니다.'
        }, status=status.HTTP_404_NOT_FOUND)

    # 3. 오늘 이후 승인된 예약 확인 (당일 + 사전예약 포함)
    today = date.today()
    appointment = Appointment.objects.filter(
        patient=patient,
        appointment_date__gte=today,
        status='예약완료'
    ).order_by('appointment_date', 'appointment_time').first()

    if not appointment:
        return Response({
            'success': False,
            'has_questionnaire': False,
            'message': '승인된 진료 예약이 없습니다.'
        }, status=status.HTTP_200_OK)

    # 4. 해당 예약에 연결된 Encounter 찾기
    try:
        encounter = Encounter.objects.get(appointment=appointment)
    except Encounter.DoesNotExist:
        return Response({
            'success': False,
            'has_questionnaire': False,
            'message': '진료 대기열에 등록되지 않았습니다.'
        }, status=status.HTTP_200_OK)

    # 4-1. 진료중 상태 체크 - 문진표 수정 불가 (진료대기 상태에서는 수정 가능)
    if encounter.workflow_state == 'IN_CLINIC':
        questionnaire = Questionnaire.objects.filter(encounter=encounter).first()
        return Response({
            'success': False,
            'blocked': True,
            'has_questionnaire': questionnaire is not None,
            'message': '현재 진료중 상태입니다. 문진표를 수정할 수 없습니다.',
            'workflow_state': encounter.workflow_state,
        }, status=status.HTTP_200_OK)

    # 5. 문진표 조회
    questionnaire = Questionnaire.objects.filter(encounter=encounter).first()

    if not questionnaire:
        return Response({
            'success': True,
            'has_questionnaire': False,
            'message': '작성된 문진표가 없습니다.',
        }, status=status.HTTP_200_OK)

    return Response({
        'success': True,
        'has_questionnaire': True,
        'questionnaire': {
            'questionnaire_id': questionnaire.questionnaire_id,
            'status': questionnaire.status,
            'data': questionnaire.data,
            'created_at': questionnaire.created_at.isoformat(),
            'updated_at': questionnaire.updated_at.isoformat(),
        }
    }, status=status.HTTP_200_OK)


def _send_questionnaire_update(encounter, patient, action):
    """
    문진표 업데이트 시 WebSocket으로 알림 전송
    """
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync

    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                'clinic_dashboard',
                {
                    'type': 'questionnaire_update',
                    'data': {
                        'action': action,
                        'encounter_id': encounter.encounter_id,
                        'patient_id': patient.patient_id,
                        'patient_name': patient.name,
                        'has_questionnaire': True,
                    }
                }
            )
    except Exception as e:
        print(f"WebSocket 문진표 알림 전송 실패: {e}")


@api_view(['GET'])
@permission_classes([AllowAny])
def get_queue_status(request):
    """
    환자의 진료 대기열 상태 조회 API (환자 앱용)

    GET /api/patients/queue/status/?profile_id=1

    Returns:
        - in_queue: 대기열에 있는지 여부
        - queue_position: 나의 대기 순서 (진료중인 사람 + 앞의 대기 인원)
        - waiting_count: 내 앞 대기 인원 (자신 제외)
        - in_progress_count: 현재 진료중인 인원
        - doctor_name: 담당 의사 이름
        - room_number: 진료실 번호
        - estimated_wait_minutes: 예상 대기 시간 (분)
        - workflow_state: 현재 상태 (WAITING_CLINIC, IN_CLINIC 등)
    """
    from doctor.models import Appointment, Encounter, Patient, Doctor
    from .models import UserProfile

    profile_id = request.query_params.get('profile_id')

    if not profile_id:
        return Response({
            'success': False,
            'message': 'profile_id가 필요합니다.'
        }, status=status.HTTP_400_BAD_REQUEST)

    # 1. UserProfile 조회
    try:
        user_profile = UserProfile.objects.get(profile_id=profile_id)
    except UserProfile.DoesNotExist:
        return Response({
            'success': False,
            'message': '사용자를 찾을 수 없습니다.'
        }, status=status.HTTP_404_NOT_FOUND)

    # 2. 연동된 Patient 확인
    if not user_profile.linked_patient_id:
        return Response({
            'success': False,
            'in_queue': False,
            'message': '병원 환자 정보와 연동되지 않았습니다.'
        }, status=status.HTTP_200_OK)

    try:
        patient = Patient.objects.get(patient_id=user_profile.linked_patient_id)
    except Patient.DoesNotExist:
        return Response({
            'success': False,
            'in_queue': False,
            'message': '연동된 환자 정보를 찾을 수 없습니다.'
        }, status=status.HTTP_200_OK)

    # 3. 현재 활성 Encounter 조회 (진료대기 또는 진료중)
    active_states = ['WAITING_CLINIC', 'WAITING_ADDITIONAL_CLINIC', 'IN_CLINIC']
    my_encounter = Encounter.objects.filter(
        patient=patient,
        workflow_state__in=active_states
    ).order_by('-created_at').first()

    if not my_encounter:
        return Response({
            'success': True,
            'in_queue': False,
            'message': '현재 진료 대기 상태가 아닙니다.'
        }, status=status.HTTP_200_OK)

    # 4. 담당 의사 정보
    doctor = my_encounter.assigned_doctor
    doctor_name = doctor.name if doctor else '미배정'
    room_number = doctor.room_number if doctor else '미정'

    # 5. 같은 의사의 대기열 조회
    if doctor:
        # 진료중인 환자 수
        in_progress_count = Encounter.objects.filter(
            assigned_doctor=doctor,
            workflow_state='IN_CLINIC'
        ).count()

        # 대기중인 환자 수 (자신 포함)
        total_waiting_count = Encounter.objects.filter(
            assigned_doctor=doctor,
            workflow_state__in=['WAITING_CLINIC', 'WAITING_ADDITIONAL_CLINIC']
        ).count()

        # 내 앞에 대기중인 환자 수 (나보다 먼저 대기열에 들어온 환자)
        waiting_before_me = Encounter.objects.filter(
            assigned_doctor=doctor,
            workflow_state__in=['WAITING_CLINIC', 'WAITING_ADDITIONAL_CLINIC'],
            created_at__lt=my_encounter.created_at
        ).count()

        # 내가 진료중이면
        if my_encounter.workflow_state == 'IN_CLINIC':
            queue_position = 1  # 진료중이면 1번
        else:
            # 대기중이면: 진료중 + 내 앞 대기자 + 나 자신(1)
            queue_position = in_progress_count + waiting_before_me + 1
    else:
        in_progress_count = 0
        total_waiting_count = 1  # 자신만
        queue_position = 1  # 의사 미배정이어도 자신은 1번

    # 예상 대기 시간 (인당 5분, 자신 포함)
    estimated_wait_minutes = queue_position * 5

    return Response({
        'success': True,
        'in_queue': True,
        'queue_position': queue_position,
        'waiting_count': total_waiting_count,
        'in_progress_count': in_progress_count,
        'doctor_name': doctor_name,
        'room_number': room_number or '미정',
        'estimated_wait_minutes': estimated_wait_minutes,
        'workflow_state': my_encounter.workflow_state,
        'workflow_state_display': my_encounter.get_workflow_state_display(),
    }, status=status.HTTP_200_OK)


# ==================== 알러지 관련 API ====================

@api_view(['GET'])
@permission_classes([AllowAny])
def get_allergies(request):
    """
    알러지 목록 조회 API (Flutter 앱용)

    GET /api/patients/allergies/?profile_id=1
    """
    profile_id = request.query_params.get('profile_id')

    if not profile_id:
        return Response({
            'success': False,
            'message': 'profile_id가 필요합니다.'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        profile = UserProfile.objects.get(profile_id=profile_id)
    except UserProfile.DoesNotExist:
        return Response({
            'success': False,
            'message': '존재하지 않는 사용자입니다.'
        }, status=status.HTTP_404_NOT_FOUND)

    allergies = Allergy.objects.filter(profile=profile).order_by('-created_at')
    serializer = AllergySerializer(allergies, many=True)

    return Response({
        'success': True,
        'allergies': serializer.data,
        'count': allergies.count()
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def create_allergy(request):
    """
    알러지 생성 API (Flutter 앱용)

    POST /api/patients/allergies/
    {
        "profile_id": 1,
        "allergy_type": "항생제",
        "trigger_agent": "페니실린",
        "reaction_desc": "피부 발진"
    }
    """
    profile_id = request.data.get('profile_id')
    allergy_type = request.data.get('allergy_type')
    trigger_agent = request.data.get('trigger_agent')
    reaction_desc = request.data.get('reaction_desc')

    if not profile_id:
        return Response({
            'success': False,
            'message': 'profile_id가 필요합니다.'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        profile = UserProfile.objects.get(profile_id=profile_id)
    except UserProfile.DoesNotExist:
        return Response({
            'success': False,
            'message': '존재하지 않는 사용자입니다.'
        }, status=status.HTTP_404_NOT_FOUND)

    allergy = Allergy.objects.create(
        profile=profile,
        allergy_type=allergy_type,
        trigger_agent=trigger_agent,
        reaction_desc=reaction_desc
    )

    serializer = AllergySerializer(allergy)

    return Response({
        'success': True,
        'message': '알러지가 등록되었습니다.',
        'allergy': serializer.data
    }, status=status.HTTP_201_CREATED)


@api_view(['PUT'])
@permission_classes([AllowAny])
def update_allergy(request, allergy_id):
    """
    알러지 수정 API (Flutter 앱용)

    PUT /api/patients/allergies/<allergy_id>/
    {
        "allergy_type": "소염진통제",
        "trigger_agent": "이부프로펜",
        "reaction_desc": "위장 장애"
    }
    """
    try:
        allergy = Allergy.objects.get(allergy_id=allergy_id)
    except Allergy.DoesNotExist:
        return Response({
            'success': False,
            'message': '존재하지 않는 알러지입니다.'
        }, status=status.HTTP_404_NOT_FOUND)

    allergy.allergy_type = request.data.get('allergy_type', allergy.allergy_type)
    allergy.trigger_agent = request.data.get('trigger_agent', allergy.trigger_agent)
    allergy.reaction_desc = request.data.get('reaction_desc', allergy.reaction_desc)
    allergy.save()

    serializer = AllergySerializer(allergy)

    return Response({
        'success': True,
        'message': '알러지가 수정되었습니다.',
        'allergy': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([AllowAny])
def delete_allergy(request, allergy_id):
    """
    알러지 삭제 API (Flutter 앱용)

    DELETE /api/patients/allergies/<allergy_id>/
    """
    try:
        allergy = Allergy.objects.get(allergy_id=allergy_id)
    except Allergy.DoesNotExist:
        return Response({
            'success': False,
            'message': '존재하지 않는 알러지입니다.'
        }, status=status.HTTP_404_NOT_FOUND)

    allergy.delete()

    return Response({
        'success': True,
        'message': '알러지가 삭제되었습니다.'
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def sync_allergies(request):
    """
    알러지 동기화 API (Flutter 앱용 - 전체 동기화)

    POST /api/patients/allergies/sync/
    {
        "profile_id": 1,
        "allergies": [
            {"allergy_type": "항생제", "trigger_agent": "페니실린", "reaction_desc": "발진"},
            {"allergy_type": "소염진통제", "trigger_agent": "아스피린", "reaction_desc": "호흡곤란"}
        ]
    }
    """
    profile_id = request.data.get('profile_id')
    allergies_data = request.data.get('allergies', [])

    if not profile_id:
        return Response({
            'success': False,
            'message': 'profile_id가 필요합니다.'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        profile = UserProfile.objects.get(profile_id=profile_id)
    except UserProfile.DoesNotExist:
        return Response({
            'success': False,
            'message': '존재하지 않는 사용자입니다.'
        }, status=status.HTTP_404_NOT_FOUND)

    # 기존 알러지 삭제 후 새로 추가
    Allergy.objects.filter(profile=profile).delete()

    created_allergies = []
    for allergy_data in allergies_data:
        allergy = Allergy.objects.create(
            profile=profile,
            allergy_type=allergy_data.get('allergy_type'),
            trigger_agent=allergy_data.get('trigger_agent'),
            reaction_desc=allergy_data.get('reaction_desc')
        )
        created_allergies.append(allergy)

    serializer = AllergySerializer(created_allergies, many=True)

    return Response({
        'success': True,
        'message': f'{len(created_allergies)}개의 알러지가 동기화되었습니다.',
        'allergies': serializer.data,
        'count': len(created_allergies)
    }, status=status.HTTP_200_OK)


# ==================== 기저질환 관련 API ====================

@api_view(['GET'])
@permission_classes([AllowAny])
def get_disease_histories(request):
    """
    기저질환 목록 조회 API (Flutter 앱용)

    GET /api/patients/disease-histories/?profile_id=1
    """
    profile_id = request.query_params.get('profile_id')

    if not profile_id:
        return Response({
            'success': False,
            'message': 'profile_id가 필요합니다.'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        profile = UserProfile.objects.get(profile_id=profile_id)
    except UserProfile.DoesNotExist:
        return Response({
            'success': False,
            'message': '존재하지 않는 사용자입니다.'
        }, status=status.HTTP_404_NOT_FOUND)

    diseases = DiseaseHistory.objects.filter(profile=profile).order_by('-created_at')
    serializer = DiseaseHistorySerializer(diseases, many=True)

    return Response({
        'success': True,
        'disease_histories': serializer.data,
        'count': diseases.count()
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def create_disease_history(request):
    """
    기저질환 생성 API (Flutter 앱용)

    POST /api/patients/disease-histories/
    {
        "profile_id": 1,
        "disease_name": "지방간",
        "disease_code": "K76.0",
        "diagnosis_date": "2024-01-01",
        "severity_level": 1,
        "is_active": true
    }
    """
    profile_id = request.data.get('profile_id')
    disease_name = request.data.get('disease_name')
    disease_code = request.data.get('disease_code')
    diagnosis_date = request.data.get('diagnosis_date')
    severity_level = request.data.get('severity_level')
    is_active = request.data.get('is_active', True)

    if not profile_id:
        return Response({
            'success': False,
            'message': 'profile_id가 필요합니다.'
        }, status=status.HTTP_400_BAD_REQUEST)

    if not disease_name:
        return Response({
            'success': False,
            'message': 'disease_name이 필요합니다.'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        profile = UserProfile.objects.get(profile_id=profile_id)
    except UserProfile.DoesNotExist:
        return Response({
            'success': False,
            'message': '존재하지 않는 사용자입니다.'
        }, status=status.HTTP_404_NOT_FOUND)

    disease = DiseaseHistory.objects.create(
        profile=profile,
        disease_name=disease_name,
        disease_code=disease_code,
        diagnosis_date=diagnosis_date,
        severity_level=severity_level,
        is_active=is_active
    )

    serializer = DiseaseHistorySerializer(disease)

    return Response({
        'success': True,
        'message': '기저질환이 등록되었습니다.',
        'disease_history': serializer.data
    }, status=status.HTTP_201_CREATED)


@api_view(['PUT'])
@permission_classes([AllowAny])
def update_disease_history(request, history_id):
    """
    기저질환 수정 API (Flutter 앱용)

    PUT /api/patients/disease-histories/<history_id>/
    {
        "disease_name": "간경변",
        "disease_code": "K74.6",
        "severity_level": 3,
        "is_active": true
    }
    """
    try:
        disease = DiseaseHistory.objects.get(history_id=history_id)
    except DiseaseHistory.DoesNotExist:
        return Response({
            'success': False,
            'message': '존재하지 않는 기저질환입니다.'
        }, status=status.HTTP_404_NOT_FOUND)

    disease.disease_name = request.data.get('disease_name', disease.disease_name)
    disease.disease_code = request.data.get('disease_code', disease.disease_code)
    disease.diagnosis_date = request.data.get('diagnosis_date', disease.diagnosis_date)
    disease.severity_level = request.data.get('severity_level', disease.severity_level)
    disease.is_active = request.data.get('is_active', disease.is_active)
    disease.save()

    serializer = DiseaseHistorySerializer(disease)

    return Response({
        'success': True,
        'message': '기저질환이 수정되었습니다.',
        'disease_history': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([AllowAny])
def delete_disease_history(request, history_id):
    """
    기저질환 삭제 API (Flutter 앱용)

    DELETE /api/patients/disease-histories/<history_id>/
    """
    try:
        disease = DiseaseHistory.objects.get(history_id=history_id)
    except DiseaseHistory.DoesNotExist:
        return Response({
            'success': False,
            'message': '존재하지 않는 기저질환입니다.'
        }, status=status.HTTP_404_NOT_FOUND)

    disease.delete()

    return Response({
        'success': True,
        'message': '기저질환이 삭제되었습니다.'
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def sync_disease_histories(request):
    """
    기저질환 동기화 API (Flutter 앱용 - 전체 동기화)

    POST /api/patients/disease-histories/sync/
    {
        "profile_id": 1,
        "disease_histories": [
            {"disease_name": "지방간", "disease_code": "K76.0", "severity_level": 1, "is_active": true},
            {"disease_name": "고혈압", "disease_code": "I10", "severity_level": 1, "is_active": true}
        ]
    }
    """
    profile_id = request.data.get('profile_id')
    diseases_data = request.data.get('disease_histories', [])

    if not profile_id:
        return Response({
            'success': False,
            'message': 'profile_id가 필요합니다.'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        profile = UserProfile.objects.get(profile_id=profile_id)
    except UserProfile.DoesNotExist:
        return Response({
            'success': False,
            'message': '존재하지 않는 사용자입니다.'
        }, status=status.HTTP_404_NOT_FOUND)

    # 기존 기저질환 삭제 후 새로 추가
    DiseaseHistory.objects.filter(profile=profile).delete()

    created_diseases = []
    for disease_data in diseases_data:
        disease = DiseaseHistory.objects.create(
            profile=profile,
            disease_name=disease_data.get('disease_name'),
            disease_code=disease_data.get('disease_code'),
            diagnosis_date=disease_data.get('diagnosis_date'),
            severity_level=disease_data.get('severity_level'),
            is_active=disease_data.get('is_active', True)
        )
        created_diseases.append(disease)

    serializer = DiseaseHistorySerializer(created_diseases, many=True)

    return Response({
        'success': True,
        'message': f'{len(created_diseases)}개의 기저질환이 동기화되었습니다.',
        'disease_histories': serializer.data,
        'count': len(created_diseases)
    }, status=status.HTTP_200_OK)


# ==================== 진료기록 관련 API ====================

@api_view(['GET'])
@permission_classes([AllowAny])
def get_medical_records(request):
    """
    진료기록 목록 조회 API (Flutter 앱용)

    GET /api/patients/medical-records/?profile_id=1
    GET /api/patients/medical-records/?profile_id=1&date=2025-01-15

    Returns:
        - 날짜별로 그룹화된 진료기록 목록
        - 각 기록에는 날짜, 진료과, 담당의, 주호소, 처방 목록 포함
    """
    profile_id = request.query_params.get('profile_id')
    date_filter = request.query_params.get('date')  # 선택적 날짜 필터

    if not profile_id:
        return Response({
            'success': False,
            'message': 'profile_id가 필요합니다.'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        profile = UserProfile.objects.get(profile_id=profile_id)
    except UserProfile.DoesNotExist:
        return Response({
            'success': False,
            'message': '존재하지 않는 사용자입니다.'
        }, status=status.HTTP_404_NOT_FOUND)

    # profile과 연결된 Patient 찾기
    try:
        patient = Patient.objects.get(profile=profile)
    except Patient.DoesNotExist:
        return Response({
            'success': True,
            'message': '연결된 환자 정보가 없습니다.',
            'medical_records': [],
            'count': 0
        }, status=status.HTTP_200_OK)

    # 진료기록 조회 - COMPLETED 상태만
    records = MedicalRecord.objects.filter(
        patient=patient,
        record_status='COMPLETED'
    ).select_related('doctor', 'diagnosis_type', 'encounter').order_by('-record_date', '-record_time')

    # 날짜 필터가 있으면 적용
    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            records = records.filter(record_date=filter_date)
        except ValueError:
            pass

    # 결과 직렬화
    records_data = []
    for record in records:
        # 해당 encounter의 처방 조회
        prescriptions = []
        if record.encounter:
            presc_list = Prescription.objects.filter(
                encounter=record.encounter,
                patient=patient
            )
            for p in presc_list:
                prescriptions.append({
                    'prescription_id': p.prescription_id,
                    'medication_name': p.medication_name,
                    'dosage': p.dosage,
                    'frequency': p.frequency,
                    'duration_days': p.duration_days,
                })

        records_data.append({
            'record_id': record.record_id,
            'record_date': record.record_date.isoformat() if record.record_date else None,
            'record_time': record.record_time.strftime('%H:%M') if record.record_time else None,
            'department': record.department,
            'doctor_name': record.doctor.name if record.doctor else None,
            'chief_complaint': record.chief_complaint,
            'clinical_notes': record.clinical_notes,
            'diagnosis_name': record.diagnosis_type.name if record.diagnosis_type else None,
            'diagnosis_code': record.diagnosis_type.code if record.diagnosis_type else None,
            'is_first_visit': record.is_first_visit,
            'prescriptions': prescriptions,
        })

    return Response({
        'success': True,
        'medical_records': records_data,
        'count': len(records_data)
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_medical_record_detail(request, record_id):
    """
    진료기록 상세 조회 API (Flutter 앱용)

    GET /api/patients/medical-records/<record_id>/
    """
    profile_id = request.query_params.get('profile_id')

    if not profile_id:
        return Response({
            'success': False,
            'message': 'profile_id가 필요합니다.'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        profile = UserProfile.objects.get(profile_id=profile_id)
        patient = Patient.objects.get(profile=profile)
    except (UserProfile.DoesNotExist, Patient.DoesNotExist):
        return Response({
            'success': False,
            'message': '존재하지 않는 사용자입니다.'
        }, status=status.HTTP_404_NOT_FOUND)

    try:
        record = MedicalRecord.objects.select_related(
            'doctor', 'diagnosis_type', 'encounter'
        ).get(record_id=record_id, patient=patient)
    except MedicalRecord.DoesNotExist:
        return Response({
            'success': False,
            'message': '존재하지 않는 진료기록입니다.'
        }, status=status.HTTP_404_NOT_FOUND)

    # 처방 조회
    prescriptions = []
    if record.encounter:
        presc_list = Prescription.objects.filter(
            encounter=record.encounter,
            patient=patient
        )
        for p in presc_list:
            prescriptions.append({
                'prescription_id': p.prescription_id,
                'medication_name': p.medication_name,
                'dosage': p.dosage,
                'frequency': p.frequency,
                'duration_days': p.duration_days,
                'pharmacy_notes': p.pharmacy_notes,
            })

    record_data = {
        'record_id': record.record_id,
        'record_date': record.record_date.isoformat() if record.record_date else None,
        'record_time': record.record_time.strftime('%H:%M') if record.record_time else None,
        'department': record.department,
        'clinic_room': record.clinic_room,
        'doctor_name': record.doctor.name if record.doctor else None,
        'chief_complaint': record.chief_complaint,
        'clinical_notes': record.clinical_notes,
        'diagnosis_name': record.diagnosis_type.name if record.diagnosis_type else None,
        'diagnosis_code': record.diagnosis_type.code if record.diagnosis_type else None,
        'is_first_visit': record.is_first_visit,
        'visit_start': record.visit_start.strftime('%H:%M') if record.visit_start else None,
        'visit_end': record.visit_end.strftime('%H:%M') if record.visit_end else None,
        'lab_recorded': record.lab_recorded,
        'ct_recorded': record.ct_recorded,
        'prescriptions': prescriptions,
    }

    return Response({
        'success': True,
        'medical_record': record_data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_medical_record_dates(request):
    """
    진료기록이 있는 날짜 목록 조회 API (Flutter 앱용 - 캘린더 표시용)

    GET /api/patients/medical-records/dates/?profile_id=1
    GET /api/patients/medical-records/dates/?profile_id=1&year=2025&month=1

    Returns:
        - 진료기록이 있는 날짜 목록
    """
    profile_id = request.query_params.get('profile_id')
    year = request.query_params.get('year')
    month = request.query_params.get('month')

    if not profile_id:
        return Response({
            'success': False,
            'message': 'profile_id가 필요합니다.'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        profile = UserProfile.objects.get(profile_id=profile_id)
        patient = Patient.objects.get(profile=profile)
    except (UserProfile.DoesNotExist, Patient.DoesNotExist):
        return Response({
            'success': True,
            'dates': [],
            'count': 0
        }, status=status.HTTP_200_OK)

    # 진료기록 날짜 조회
    records = MedicalRecord.objects.filter(
        patient=patient,
        record_status='COMPLETED'
    )

    # 연월 필터
    if year and month:
        try:
            records = records.filter(
                record_date__year=int(year),
                record_date__month=int(month)
            )
        except ValueError:
            pass

    # 중복 제거된 날짜 목록
    dates = records.values_list('record_date', flat=True).distinct().order_by('-record_date')
    date_list = [d.isoformat() for d in dates if d]

    return Response({
        'success': True,
        'dates': date_list,
        'count': len(date_list)
    }, status=status.HTTP_200_OK)


# ==================== 처방전 OCR 관련 API ====================

from .models import Prescription as AppPrescription, MedicationDetail, PillInfo

@api_view(['POST'])
@permission_classes([AllowAny])
def create_ocr_prescription(request):
    """
    OCR 처방전 저장 API (Flutter 앱용)

    POST /api/patients/prescriptions/ocr/
    {
        "profile_id": 1,
        "hospital_name": "서울대학교병원",
        "dispense_date": "2025-01-19",
        "total_days": 7,
        "medications": [
            {
                "item_name": "타이레놀",
                "item_seq": 123456789,
                "one_dose": "1정",
                "daily_count": "3회",
                "total_days": "7일"
            }
        ]
    }
    """
    profile_id = request.data.get('profile_id')
    hospital_name = request.data.get('hospital_name', '')
    dispense_date = request.data.get('dispense_date')
    medications = request.data.get('medications', [])

    if not profile_id:
        return Response({
            'success': False,
            'message': 'profile_id가 필요합니다.'
        }, status=status.HTTP_400_BAD_REQUEST)

    if not medications:
        return Response({
            'success': False,
            'message': '약물 정보가 필요합니다.'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        profile = UserProfile.objects.get(profile_id=profile_id)
    except UserProfile.DoesNotExist:
        return Response({
            'success': False,
            'message': '존재하지 않는 사용자입니다.'
        }, status=status.HTTP_404_NOT_FOUND)

    try:
        # 1. Prescription 생성
        prescription = AppPrescription.objects.create(
            profile=profile,
            hospital_name=hospital_name,
            dispense_date=dispense_date if dispense_date else date.today()
        )

        # 2. MedicationDetail 생성
        created_meds = []
        for med in medications:
            item_name = med.get('item_name', '')
            item_seq = med.get('item_seq')
            one_dose = med.get('one_dose')
            daily_count = med.get('daily_count')
            total_days = med.get('total_days')

            # PillInfo 연결 (item_seq가 있으면)
            pill_info = None
            if item_seq:
                try:
                    pill_info = PillInfo.objects.get(item_seq=item_seq)
                except PillInfo.DoesNotExist:
                    pass  # pill_info 없이 저장

            med_detail = MedicationDetail.objects.create(
                pres=prescription,
                item_name=item_name,
                one_dose=one_dose,
                daily_count=daily_count,
                total_days=total_days,
                is_taking=True,
                pill_info=pill_info
            )
            created_meds.append({
                'med_id': med_detail.med_id,
                'item_name': med_detail.item_name,
                'one_dose': med_detail.one_dose,
                'daily_count': med_detail.daily_count,
                'total_days': med_detail.total_days
            })

        return Response({
            'success': True,
            'message': '처방전이 저장되었습니다.',
            'prescription': {
                'pres_id': prescription.pres_id,
                'hospital_name': prescription.hospital_name,
                'dispense_date': prescription.dispense_date.isoformat() if prescription.dispense_date else None,
                'medications': created_meds
            }
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response({
            'success': False,
            'message': f'처방전 저장 중 오류가 발생했습니다: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_ocr_prescriptions(request):
    """
    OCR 처방전 목록 조회 API (Flutter 앱용)

    GET /api/patients/prescriptions/?profile_id=1
    """
    profile_id = request.query_params.get('profile_id')

    if not profile_id:
        return Response({
            'success': False,
            'message': 'profile_id가 필요합니다.'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        profile = UserProfile.objects.get(profile_id=profile_id)
    except UserProfile.DoesNotExist:
        return Response({
            'success': False,
            'message': '존재하지 않는 사용자입니다.'
        }, status=status.HTTP_404_NOT_FOUND)

    prescriptions = AppPrescription.objects.filter(profile=profile).order_by('-dispense_date', '-created_at')

    prescriptions_data = []
    for pres in prescriptions:
        meds = MedicationDetail.objects.filter(pres=pres)
        meds_data = [{
            'med_id': m.med_id,
            'item_name': m.item_name,
            'one_dose': m.one_dose,
            'daily_count': m.daily_count,
            'total_days': m.total_days,
            'is_taking': m.is_taking
        } for m in meds]

        prescriptions_data.append({
            'pres_id': pres.pres_id,
            'hospital_name': pres.hospital_name,
            'dispense_date': pres.dispense_date.isoformat() if pres.dispense_date else None,
            'created_at': pres.created_at.isoformat(),
            'medications': meds_data
        })

    return Response({
        'success': True,
        'prescriptions': prescriptions_data,
        'count': len(prescriptions_data)
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_current_medications(request):
    """
    현재 복용중인 약물 목록 조회 API (Flutter 앱용)

    GET /api/patients/medications/current/?profile_id=1
    """
    profile_id = request.query_params.get('profile_id')

    if not profile_id:
        return Response({
            'success': False,
            'message': 'profile_id가 필요합니다.'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        profile = UserProfile.objects.get(profile_id=profile_id)
    except UserProfile.DoesNotExist:
        return Response({
            'success': False,
            'message': '존재하지 않는 사용자입니다.'
        }, status=status.HTTP_404_NOT_FOUND)

    # 복용중인 약물만 조회 (is_taking=True)
    medications = MedicationDetail.objects.filter(
        pres__profile=profile,
        is_taking=True
    ).select_related('pres', 'pill_info').order_by('-created_at')

    meds_data = []
    for med in medications:
        meds_data.append({
            'med_id': med.med_id,
            'item_name': med.item_name,
            'one_dose': med.one_dose,
            'daily_count': med.daily_count,
            'total_days': med.total_days,
            'is_taking': med.is_taking,
            'pres_id': med.pres.pres_id,
            'hospital_name': med.pres.hospital_name,
            'dispense_date': med.pres.dispense_date.isoformat() if med.pres.dispense_date else None,
            'pill_info': {
                'item_seq': med.pill_info.item_seq,
                'item_image': med.pill_info.item_image,
                'entp_name': med.pill_info.entp_name,
                'class_name': med.pill_info.class_name
            } if med.pill_info else None
        })

    return Response({
        'success': True,
        'medications': meds_data,
        'count': len(meds_data)
    }, status=status.HTTP_200_OK)


@api_view(['PUT'])
@permission_classes([AllowAny])
def update_medication_status(request, med_id):
    """
    약물 복용 상태 업데이트 API (Flutter 앱용)

    PUT /api/patients/medications/<med_id>/status/
    {
        "is_taking": false
    }
    """
    is_taking = request.data.get('is_taking')

    if is_taking is None:
        return Response({
            'success': False,
            'message': 'is_taking 값이 필요합니다.'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        medication = MedicationDetail.objects.get(med_id=med_id)
    except MedicationDetail.DoesNotExist:
        return Response({
            'success': False,
            'message': '존재하지 않는 약물입니다.'
        }, status=status.HTTP_404_NOT_FOUND)

    medication.is_taking = is_taking
    medication.save()

    return Response({
        'success': True,
        'message': '약물 상태가 업데이트되었습니다.',
        'medication': {
            'med_id': medication.med_id,
            'item_name': medication.item_name,
            'is_taking': medication.is_taking
        }
    }, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([AllowAny])
def delete_prescription(request, pres_id):
    """
    처방전 삭제 API (Flutter 앱용)

    DELETE /api/patients/prescriptions/<pres_id>/
    """
    try:
        prescription = AppPrescription.objects.get(pres_id=pres_id)
    except AppPrescription.DoesNotExist:
        return Response({
            'success': False,
            'message': '존재하지 않는 처방전입니다.'
        }, status=status.HTTP_404_NOT_FOUND)

    prescription.delete()

    return Response({
        'success': True,
        'message': '처방전이 삭제되었습니다.'
    }, status=status.HTTP_200_OK)
