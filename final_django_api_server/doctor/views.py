from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from accounts.permissions import IsDoctor


class DoctorDashboardView(APIView):
    """의사 전용 대시보드 API"""
    permission_classes = [IsDoctor]

    def get(self, request):
        user = request.user

        return Response({
            'message': f'안녕하세요, {user.first_name} 의사님',
            'user': {
                'id': user.id,
                'username': user.username,
                'role': user.role,
                'first_name': user.first_name,
                'last_name': user.last_name,
            },
            'stats': {
                'total_patients': 0,  # 실제 데이터로 대체 필요
                'today_appointments': 0,
                'pending_prescriptions': 0,
            }
        }, status=status.HTTP_200_OK)


class PatientListView(APIView):
    """의사의 환자 목록 조회 API"""
    permission_classes = [IsDoctor]

    def get(self, request):
        # 실제로는 DB에서 환자 목록을 가져와야 함
        return Response({
            'message': '환자 목록',
            'patients': []  # 실제 환자 데이터로 대체 필요
        }, status=status.HTTP_200_OK)
