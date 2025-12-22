from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from accounts.permissions import IsClerk


class AdministrationDashboardView(APIView):
    """원무과 전용 대시보드 API"""
    permission_classes = [IsClerk]

    def get(self, request):
        user = request.user

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
                'today_registrations': 0,  # 실제 데이터로 대체 필요
                'pending_appointments': 0,
                'today_billing': 0,
            }
        }, status=status.HTTP_200_OK)


class PatientRegistrationView(APIView):
    """환자 등록 API (원무과 전용)"""
    permission_classes = [IsClerk]

    def post(self, request):
        # 실제로는 환자 등록 로직 구현 필요
        return Response({
            'message': '환자 등록 완료',
            'patient_id': None  # 실제 환자 ID로 대체 필요
        }, status=status.HTTP_201_CREATED)
