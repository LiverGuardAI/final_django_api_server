from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.db.models import Q
from accounts.permissions import IsRadiologist, IsDoctorOrRadiologist
from doctor.models import Patient
from .serializers import PatientWaitlistSerializer, RadiologyQueueSerializer
from .models import RadiologyPatientQueue


class RadiologyDashboardView(APIView):
    """영상의학과 전용 대시보드 API"""
    permission_classes = [IsRadiologist]

    def get(self, request):
        user = request.user

        return Response({
            'message': f'안녕하세요, {user.first_name} 영상의학과',
            'user': {
                'id': user.id,
                'username': user.username,
                'role': user.role,
                'first_name': user.first_name,
                'last_name': user.last_name,
            },
            'stats': {
                'total_studies': 0,  # 실제 데이터로 대체 필요
                'pending_ai_analysis': 0,
                'today_scans': 0,
            }
        }, status=status.HTTP_200_OK)


class DICOMStudyListView(APIView):
    """DICOM 스터디 목록 조회 API (의사와 영상의학과 모두 접근 가능)"""
    permission_classes = [IsDoctorOrRadiologist]

    def get(self, request):
        # 실제로는 DB에서 DICOM 스터디 목록을 가져와야 함
        return Response({
            'message': 'DICOM 스터디 목록',
            'studies': []  # 실제 스터디 데이터로 대체 필요
        }, status=status.HTTP_200_OK)


class WaitlistView(APIView):
    """촬영 대기 환자 목록 조회 API (테스트용 - AllowAny)"""
    permission_classes = [AllowAny]  # TODO: 나중에 IsRadiologist로 변경 필요

    def get(self, request):
        """
        current_status가 '촬영대기중' 또는 '촬영중'인 환자 목록 조회
        """
        # Patient 모델에서 촬영대기중 또는 촬영중인 환자 필터링
        patients = Patient.objects.filter(
            Q(current_status='촬영대기중') | Q(current_status='촬영중')
        ).order_by('-created_at')

        # 직렬화
        serializer = PatientWaitlistSerializer(patients, many=True)

        return Response({
            'message': '촬영 대기 환자 목록',
            'count': patients.count(),
            'patients': serializer.data
        }, status=status.HTTP_200_OK)


class StartFilmingView(APIView):
    """환자 촬영 시작 API - 환자 상태를 '촬영중'으로 변경"""
    permission_classes = [AllowAny]  # TODO: 나중에 IsRadiologist로 변경 필요

    def post(self, request):
        """
        환자의 current_status를 '촬영중'으로 업데이트

        Request Body:
        {
            "patient_id": "TCGA-BC-4073"
        }
        """
        patient_id = request.data.get('patient_id')

        if not patient_id:
            return Response({
                'error': 'patient_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 환자 조회
            patient = Patient.objects.get(patient_id=patient_id)

            # 상태 업데이트
            patient.current_status = '촬영중'
            patient.save()

            # 업데이트된 환자 정보 직렬화
            serializer = PatientWaitlistSerializer(patient)

            return Response({
                'message': '촬영이 시작되었습니다',
                'patient': serializer.data
            }, status=status.HTTP_200_OK)

        except Patient.DoesNotExist:
            return Response({
                'error': f'Patient with ID {patient_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
