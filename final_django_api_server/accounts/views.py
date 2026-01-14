from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
import re
from django.contrib.auth import authenticate
from datetime import datetime, timedelta
from rest_framework.authentication import SessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

# 로그인 API
class LoginView(APIView):
    permission_classes = [AllowAny]  # 인증 없이 접근 가능
    
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        
        # 사용자 인증
        user = authenticate(username=username, password=password)
        
        if user is None:
            return Response(
                {'error': '아이디 또는 비밀번호가 올바르지 않습니다.'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # JWT 토큰 발급
        refresh = RefreshToken.for_user(user)
        
        # 사용자 역할 확인 (CustomUser 모델의 role 필드)
        user_role = user.role  # 'doctor', 'radiologist', 'clerk', 'patient'
        
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'id': user.user_id,
                'username': user.username,
                'role': user_role,
                'first_name': user.first_name,
                'last_name': user.last_name,
            }
        }, status=status.HTTP_200_OK)

# 의사 로그인 API (사번 + 전화번호)
class DoctorLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        employee_no = request.data.get('employee_no')
        phone = request.data.get('phone')

        if not employee_no or not phone:
            return Response(
                {'error': '사번과 전화번호를 입력해주세요.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            def normalize_employee_no(value):
                return re.sub(r"\s+", "", value or "")

            def normalize_phone(value):
                return re.sub(r"\D", "", value or "")

            normalized_employee_no = normalize_employee_no(employee_no)
            normalized_phone = normalize_phone(phone)

            # Doctor 모델에서 사번과 전화번호로 검색
            from doctor.models import Doctor
            doctor = Doctor.objects.select_related('user').filter(
                employee_no=employee_no
            ).first()
            if doctor is None and normalized_employee_no != employee_no:
                doctor = Doctor.objects.select_related('user').filter(
                    employee_no=normalized_employee_no
                ).first()
            if doctor is None:
                raise Doctor.DoesNotExist

            stored_phone = normalize_phone(doctor.phone)
            if stored_phone != normalized_phone:
                raise Doctor.DoesNotExist

            # Doctor의 연결된 User 정보 가져오기
            user = doctor.user

            # 역할이 doctor인지 확인 (대소문자 구분 없이)
            if user.role.upper() != 'DOCTOR':
                return Response(
                    {'error': '의사 계정이 아닙니다.'},
                    status=status.HTTP_403_FORBIDDEN
                )

            # JWT 토큰 발급
            refresh = RefreshToken.for_user(user)

            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {
                    'id': user.user_id,
                    'username': user.username,
                    'role': user.role,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                },
                'doctor': {
                    'doctor_id': doctor.doctor_id,
                    'name': doctor.name,
                    'employee_no': doctor.employee_no,
                    'department': {
                        'dept_id': doctor.department.department_id,
                        'dept_name': doctor.department.dept_name,
                    } if doctor.department else None,
                    'room_number': doctor.room_number,
                }
            }, status=status.HTTP_200_OK)

        except Doctor.DoesNotExist:
            return Response(
                {'error': '사번 또는 전화번호가 올바르지 않습니다.'},
                status=status.HTTP_401_UNAUTHORIZED
            )


# 원무과 로그인 API (사번 + 전화번호)
class AdministrationLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        employee_no = request.data.get('employee_no')
        phone = request.data.get('phone')

        if not employee_no or not phone:
            return Response(
                {'error': '사번과 전화번호를 입력해주세요.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            def normalize_employee_no(value):
                return re.sub(r"\s+", "", value or "")

            def normalize_phone(value):
                return re.sub(r"\D", "", value or "")

            normalized_employee_no = normalize_employee_no(employee_no)
            normalized_phone = normalize_phone(phone)

            from administration.models import Administration
            admin_staff = Administration.objects.select_related('user').filter(
                employee_no=employee_no
            ).first()
            if admin_staff is None and normalized_employee_no != employee_no:
                admin_staff = Administration.objects.select_related('user').filter(
                    employee_no=normalized_employee_no
                ).first()
            if admin_staff is None:
                raise Administration.DoesNotExist

            stored_phone = normalize_phone(admin_staff.phone)
            if stored_phone != normalized_phone:
                raise Administration.DoesNotExist

            user = admin_staff.user
            if user.role != 'CLERK':
                return Response(
                    {'error': '원무과 계정이 아닙니다.'},
                    status=status.HTTP_403_FORBIDDEN
                )

            refresh = RefreshToken.for_user(user)

            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {
                    'id': user.user_id,
                    'username': user.username,
                    'role': user.role,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                },
                'administration': {
                    'staff_id': admin_staff.staff_id,
                    'name': admin_staff.name,
                    'employee_no': admin_staff.employee_no,
                    'department': admin_staff.department.dept_name if admin_staff.department else None,
                }
            }, status=status.HTTP_200_OK)

        except Administration.DoesNotExist:
            return Response(
                {'error': '사번 또는 전화번호가 올바르지 않습니다.'},
                status=status.HTTP_401_UNAUTHORIZED
            )


# 영상의학과 로그인 API (사번 + 전화번호)
class RadiologyLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        employee_no = request.data.get('employee_no')
        phone = request.data.get('phone')

        if not employee_no or not phone:
            return Response(
                {'error': '사번과 전화번호를 입력해주세요.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            def normalize_employee_no(value):
                return re.sub(r"\s+", "", value or "")

            def normalize_phone(value):
                return re.sub(r"\D", "", value or "")

            normalized_employee_no = normalize_employee_no(employee_no)
            normalized_phone = normalize_phone(phone)

            from radiology.models import Radiology
            radiology = Radiology.objects.select_related('user').filter(
                employee_no=employee_no
            ).first()
            if radiology is None and normalized_employee_no != employee_no:
                radiology = Radiology.objects.select_related('user').filter(
                    employee_no=normalized_employee_no
                ).first()
            if radiology is None:
                raise Radiology.DoesNotExist

            stored_phone = normalize_phone(radiology.phone)
            if stored_phone != normalized_phone:
                raise Radiology.DoesNotExist

            user = radiology.user
            if user.role.upper() != 'RADIOLOGIST':
                return Response(
                    {'error': '영상의학과 계정이 아닙니다.'},
                    status=status.HTTP_403_FORBIDDEN
                )

            refresh = RefreshToken.for_user(user)

            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {
                    'id': user.user_id,
                    'username': user.username,
                    'role': user.role,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                },
                'radiology': {
                    'radiologic_id': radiology.radiologic_id,
                    'employee_no': radiology.employee_no,
                    'department': radiology.department.dept_name if radiology.department else None,
                }
            }, status=status.HTTP_200_OK)

        except Radiology.DoesNotExist:
            return Response(
                {'error': '사번 또는 전화번호가 올바르지 않습니다.'},
                status=status.HTTP_401_UNAUTHORIZED
            )
# 로그아웃 API (블랙리스트 미사용 - 프론트엔드에서 토큰 삭제)
class LogoutView(APIView):
    permission_classes = [AllowAny]  # 인증 불필요

    def post(self, request):
        # 프론트엔드에서 토큰을 삭제하는 방식으로 로그아웃 처리
        return Response(
            {'message': '로그아웃 되었습니다.'},
            status=status.HTTP_200_OK
        )



class PublicDutyScheduleView(APIView):
    """
    원무과/프론트엔드용 근무 일정 조회 (Read-Only)
    """
    permission_classes = [AllowAny]  # 필요에 따라 IsAuthenticated로 변경
    
    def get(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        doctor_id = request.query_params.get('doctor_id')
        schedule_status = request.query_params.get('status')
        
        queryset = DutySchedule.objects.select_related(
            'user',
            'user__doctor',
            'user__radiology',
            'user__administration'
        ).all()
        
        if start_date:
            # 일정이 start_date 이후에 끝나야 함 (start_date와 겹치거나 그 이후)
            queryset = queryset.filter(end_time__date__gte=start_date)
        if end_date:
            # 일정이 end_date 이전에 시작해야 함 (end_date와 겹치거나 그 이전)
            queryset = queryset.filter(start_time__date__lte=end_date)
        if doctor_id:
            queryset = queryset.filter(user_id=doctor_id)
        if schedule_status:
            queryset = queryset.filter(schedule_status=schedule_status)
            
        serializer = DutyScheduleSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

# 직원 리스트 조회 API
from .models import CustomUser

class StaffListView(APIView):
    permission_classes = [AllowAny] # Or IsAuthenticated
    authentication_classes = [SessionAuthentication] # Admin 페이지 전용

    def get(self, request):
        staff_list = []
        
        # 1. Doctors
        from doctor.models import Doctor
        doctors = Doctor.objects.select_related('user', 'department').all()
        for doc in doctors:
            staff_list.append({
                'user_id': doc.user.user_id,
                'name': doc.name,
                'role': 'DOCTOR',
                'dept_name': doc.department.dept_name if doc.department else 'Unknown'
            })
            
        # 2. Radiologists
        from radiology.models import Radiology
        radios = Radiology.objects.select_related('user', 'department').all()
        for rad in radios:
            staff_list.append({
                'user_id': rad.user.user_id,
                'name': rad.name,
                'role': 'RADIOLOGIST',
                'dept_name': rad.department.dept_name if rad.department else 'Unknown'
            })

        # 3. Administration (Clerks)
        from administration.models import Administration
        admins = Administration.objects.select_related('user', 'department').all()
        for adm in admins:
            staff_list.append({
                'user_id': adm.user.user_id,
                'name': adm.name,
                'role': 'CLERK',
                'dept_name': adm.department.dept_name if adm.department else 'Unknown'
            })
        
        # Sort by Dept Name then Role
        staff_list.sort(key=lambda x: (x['dept_name'], x['role']))
        
        return Response(staff_list, status=status.HTTP_200_OK)




# admin 계정 내 근무 일정 관리 API
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import DutySchedule, Notification
from .serializers import DutyScheduleSerializer, NotificationSerializer
from django.utils import timezone

from rest_framework.authentication import SessionAuthentication

class NotificationViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    authentication_classes = [SessionAuthentication, JWTAuthentication]

    def get_queryset(self):
        # Filter by user if provides
        queryset = super().get_queryset().select_related(
            'user',
            'user__doctor',
            'user__radiology',
            'user__administration'
        )
        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        return queryset

    @action(detail=True, methods=['post'])
    def read(self, request, pk=None):
        noti = self.get_object()
        noti.is_read = True
        noti.save()
        return Response({'status': 'marked as read'})

class DutyScheduleViewSet(viewsets.ModelViewSet):
    queryset = DutySchedule.objects.all()
    serializer_class = DutyScheduleSerializer
    authentication_classes = [SessionAuthentication, JWTAuthentication] # Admin 페이지 전용
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'user',
            'user__doctor',
            'user__radiology',
            'user__administration'
        )
        user_id = self.request.query_params.get('user_id')
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        schedule_status = self.request.query_params.get('status')
        
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if start_date:
            queryset = queryset.filter(start_time__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(end_time__date__lte=end_date)
        if schedule_status:
            queryset = queryset.filter(schedule_status=schedule_status)
            
        return queryset

    def perform_create(self, serializer):
        instance = serializer.save()
        self.send_notification(instance.user.user_id, 'new_schedule', f"새로운 근무 일정이 배정되었습니다: {instance.start_time.strftime('%Y-%m-%d')}")

    def perform_update(self, serializer):
        instance = serializer.save()
        self.send_notification(instance.user.user_id, 'schedule_update', f"근무 일정이 수정되었습니다: {instance.start_time.strftime('%Y-%m-%d')}")

    def send_notification(self, user_id, message_type, message):
        # Persist Notification
        try:
            Notification.objects.create(user_id=user_id, message_type=message_type, message=message)
        except Exception as e:
            print(f"Failed to create notification: {e}")

        # Send WS
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{user_id}",
            {
                "type": "schedule_update", 
                "message": {
                    "type": message_type,
                    "content": message
                }
            }
        )

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        schedule = self.get_object()
        schedule.schedule_status = 'CONFIRMED'
        schedule.save()
        return Response({'status': 'schedule confirmed'})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        schedule = self.get_object()
        schedule.schedule_status = 'CANCELLED'
        reason = request.data.get('reason', '')
        if reason:
            schedule.rejection_reason = reason
        schedule.save()
        return Response({'status': 'schedule cancelled', 'reason': reason})

class BulkScheduleView(APIView):
    """
    일괄 스케줄 생성 API (Django Admin용)
    - 기간, 휴무일, 근무타입(Day/Night 등)을 받아 일괄 생성
    """
    authentication_classes = [SessionAuthentication]
    permission_classes = [AllowAny] # Admin 페이지에서 Session Auth로 접근

    def post(self, request):
        try:
            user_id = request.data.get('user_id')
            start_date_str = request.data.get('start_date')
            end_date_str = request.data.get('end_date')
            off_days = request.data.get('off_days', []) # ['Sat', 'Sun'] etc.
            shift_type = request.data.get('shift_type') # 'DAY', 'EVENING', 'NIGHT'
            
            if not all([user_id, start_date_str, end_date_str, shift_type]):
                return Response({'error': 'Missing required fields'}, status=status.HTTP_400_BAD_REQUEST)

            # User 조회
            user = CustomUser.objects.get(user_id=user_id)
            
            # Work Role 매핑 (User Role -> Work Role)
            role_map = {
                'DOCTOR': 'DOCTOR',
                'RADIOLOGIST': 'RADIOLOGIST',
                'CLERK': 'CLERK'
            }
            user_role_upper = user.role.upper() if user.role else 'DOCTOR'
            work_role = role_map.get(user_role_upper, 'DOCTOR')

            # 날짜 파싱
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            
            # 요일 매핑
            weekday_map = {
                'Mon': 0, 'Tue': 1, 'Wed': 2, 'Thu': 3, 'Fri': 4, 'Sat': 5, 'Sun': 6
            }
            off_day_indices = [weekday_map[d] for d in off_days if d in weekday_map]

            # KST Timezone using django.utils.timezone
            kst = timezone.get_current_timezone()
            
            created_count = 0
            current_date = start_date
            
            while current_date <= end_date:
                # 1. 휴무일 체크
                if current_date.weekday() in off_day_indices:
                    current_date += timedelta(days=1)
                    continue
                
                # 2. 시간 설정
                if shift_type == 'DAY': # 09:00 ~ 18:00
                    start_dt_naive = datetime.combine(current_date, datetime.min.time().replace(hour=9))
                    end_dt_naive = datetime.combine(current_date, datetime.min.time().replace(hour=18))
                elif shift_type == 'EVENING': # 18:00 ~ 22:00
                    start_dt_naive = datetime.combine(current_date, datetime.min.time().replace(hour=18))
                    end_dt_naive = datetime.combine(current_date, datetime.min.time().replace(hour=22))
                elif shift_type == 'NIGHT': # 22:00 ~ 06:00 (+1 day)
                    start_dt_naive = datetime.combine(current_date, datetime.min.time().replace(hour=22))
                    next_day = current_date + timedelta(days=1)
                    end_dt_naive = datetime.combine(next_day, datetime.min.time().replace(hour=6))
                else: # Default DAY
                    start_dt_naive = datetime.combine(current_date, datetime.min.time().replace(hour=9))
                    end_dt_naive = datetime.combine(current_date, datetime.min.time().replace(hour=18))

                start_time = timezone.make_aware(start_dt_naive, kst)
                end_time = timezone.make_aware(end_dt_naive, kst)

                # 3. Create Schedule
                DutySchedule.objects.create(
                    user=user,
                    work_role=work_role,
                    start_time=start_time,
                    end_time=end_time,
                    shift_type=shift_type,
                    schedule_status='PENDING'
                )
                
                created_count += 1
                current_date += timedelta(days=1)

            # Send notification
            content = f"{created_count}개의 새로운 근무 일정이 일괄 배정되었습니다."
            try:
                Notification.objects.create(user=user, message_type='bulk_schedule_create', message=content)
            except Exception as e:
                print(f"Failed to create notification: {e}")

            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"user_{user.user_id}",
                {
                    "type": "schedule_update",
                    "message": {
                        "type": "bulk_schedule_create",
                        "content": content
                    }
                }
            )

            return Response({'message': f'{created_count} schedules created.'}, status=status.HTTP_201_CREATED)

        except CustomUser.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

