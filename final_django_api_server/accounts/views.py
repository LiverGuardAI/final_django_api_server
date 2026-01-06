from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
import re
from django.contrib.auth import authenticate
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
                'id': user.id,
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
                    'id': user.id,
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
                    'id': user.id,
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
                    'id': user.id,
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
