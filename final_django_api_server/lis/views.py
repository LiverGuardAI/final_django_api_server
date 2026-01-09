from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from doctor.models import Patient
from doctor.serializers import LabResultSerializer, GenomicDataSerializer


class CreateLabResultView(APIView):
    """LIS 혈액 검사 결과 생성 API"""
    permission_classes = [AllowAny]

    def post(self, request, patient_id):
        try:
            patient = Patient.objects.get(patient_id=patient_id)
            payload = request.data.copy()
            payload['patient'] = patient.patient_id
            serializer = LabResultSerializer(data=payload)
            if serializer.is_valid():
                lab_result = serializer.save()
                return Response(LabResultSerializer(lab_result).data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Patient.DoesNotExist:
            return Response({'error': '환자를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CreateGenomicDataView(APIView):
    """LIS 유전체 검사 결과 생성 API"""
    permission_classes = [AllowAny]

    def post(self, request, patient_id):
        try:
            patient = Patient.objects.get(patient_id=patient_id)
            payload = request.data.copy()
            payload['patient'] = patient.patient_id
            serializer = GenomicDataSerializer(data=payload)
            if serializer.is_valid():
                genomic = serializer.save()
                return Response(GenomicDataSerializer(genomic).data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Patient.DoesNotExist:
            return Response({'error': '환자를 찾을 수 없습니다.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
