from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
import requests


# Orthanc 서버 설정
ORTHANC_BASE_URL = 'http://34.67.62.238/orthanc'


class UploadDicomView(APIView):
    """DICOM 파일을 Orthanc 서버에 업로드하는 프록시 API"""
    permission_classes = [AllowAny]
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        """
        DICOM 파일을 받아서 Orthanc 서버로 전달

        Request:
        - multipart/form-data로 DICOM 파일 전송
        - 파일 필드명: 'file'

        Response:
        {
            "ID": "instance-id",
            "Path": "/instances/instance-id",
            "Status": "Success"
        }
        """
        # 업로드된 파일 가져오기
        uploaded_file = request.FILES.get('file')

        if not uploaded_file:
            return Response({
                'error': 'No file provided'
            }, status=status.HTTP_400_BAD_REQUEST)

        # DICOM 파일 확장자 검증
        if not (uploaded_file.name.endswith('.dcm') or uploaded_file.name.endswith('.dicom')):
            return Response({
                'error': 'Only DICOM files (.dcm, .dicom) are allowed'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 파일 내용 읽기
            file_content = uploaded_file.read()

            # Orthanc 서버로 전송
            orthanc_response = requests.post(
                f'{ORTHANC_BASE_URL}/instances',
                data=file_content,
                headers={
                    'Content-Type': 'application/dicom'
                },
                timeout=30
            )

            # Orthanc 응답 확인
            if orthanc_response.status_code == 200:
                return Response(
                    orthanc_response.json(),
                    status=status.HTTP_200_OK
                )
            else:
                return Response({
                    'error': 'Orthanc upload failed',
                    'details': orthanc_response.text
                }, status=orthanc_response.status_code)

        except requests.exceptions.RequestException as e:
            return Response({
                'error': 'Failed to connect to Orthanc server',
                'details': str(e)
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            return Response({
                'error': 'Internal server error',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class OrthancSystemInfoView(APIView):
    """Orthanc 시스템 정보 조회 API"""
    permission_classes = [AllowAny]

    def get(self, request):
        """
        Orthanc 서버의 시스템 정보 조회
        GET /system
        """
        try:
            response = requests.get(
                f'{ORTHANC_BASE_URL}/system',
                timeout=10
            )

            if response.status_code == 200:
                return Response(
                    response.json(),
                    status=status.HTTP_200_OK
                )
            else:
                return Response({
                    'error': 'Failed to fetch Orthanc system info'
                }, status=response.status_code)

        except requests.exceptions.RequestException as e:
            return Response({
                'error': 'Failed to connect to Orthanc server',
                'details': str(e)
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class OrthancStudyView(APIView):
    """Orthanc Study 정보 조회 API"""
    permission_classes = [AllowAny]

    def get(self, request, study_id):
        """
        특정 Study 정보 조회
        GET /studies/{study_id}
        """
        try:
            response = requests.get(
                f'{ORTHANC_BASE_URL}/studies/{study_id}',
                timeout=10
            )

            if response.status_code == 200:
                return Response(
                    response.json(),
                    status=status.HTTP_200_OK
                )
            else:
                return Response({
                    'error': f'Study {study_id} not found'
                }, status=response.status_code)

        except requests.exceptions.RequestException as e:
            return Response({
                'error': 'Failed to connect to Orthanc server',
                'details': str(e)
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class OrthancInstanceView(APIView):
    """Orthanc Instance 정보 조회 API"""
    permission_classes = [AllowAny]

    def get(self, request, instance_id):
        """
        특정 Instance 정보 조회
        GET /instances/{instance_id}
        """
        try:
            response = requests.get(
                f'{ORTHANC_BASE_URL}/instances/{instance_id}',
                timeout=10
            )

            if response.status_code == 200:
                return Response(
                    response.json(),
                    status=status.HTTP_200_OK
                )
            else:
                return Response({
                    'error': f'Instance {instance_id} not found'
                }, status=response.status_code)

        except requests.exceptions.RequestException as e:
            return Response({
                'error': 'Failed to connect to Orthanc server',
                'details': str(e)
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)