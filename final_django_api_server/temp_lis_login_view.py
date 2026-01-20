
# 진단검사의학과 로그인 API (사번 + 전화번호)
class LisLoginView(APIView):
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

            # LisStaff 모델에서 사번과 전화번호로 검색
            from lis.models import LisStaff
            staff = LisStaff.objects.select_related('user').filter(
                employee_no=employee_no
            ).first()
            if staff is None and normalized_employee_no != employee_no:
                staff = LisStaff.objects.select_related('user').filter(
                    employee_no=normalized_employee_no
                ).first()
            if staff is None:
                raise LisStaff.DoesNotExist

            stored_phone = normalize_phone(staff.phone)
            if stored_phone != normalized_phone:
                raise LisStaff.DoesNotExist

            # 연결된 User 정보 가져오기
            user = staff.user

            # 역할이 LIS인지 확인 (대소문자 구분 없이)
            if user.role.upper() != 'LIS':
                return Response(
                    {'error': '진단검사의학과 계정이 아닙니다.'},
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
                'lis': { # Frontend expects this key for storage
                    'staff_id': staff.staff_id,
                    'name': staff.name,
                    'employee_no': staff.employee_no,
                    'department': {
                        'dept_id': staff.department.department_id,
                        'dept_name': staff.department.dept_name,
                    } if staff.department else None,
                }
            }, status=status.HTTP_200_OK)

        except LisStaff.DoesNotExist:
            return Response(
                {'error': '사번 또는 전화번호가 올바르지 않습니다.'},
                status=status.HTTP_401_UNAUTHORIZED
            )
