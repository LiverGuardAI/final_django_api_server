from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from .permissions import IsLisStaff
from doctor.models import Patient
from doctor.serializers import LabResultSerializer, GenomicDataSerializer


class CreateLabResultView(APIView):
    """LIS 혈액 검사 결과 생성 API"""
    permission_classes = [IsLisStaff]

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
    permission_classes = [IsLisStaff]

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


class PendingLabOrdersView(APIView):
    """대기 중인 검사 오더 목록 조회 API"""
    permission_classes = [IsLisStaff]

    def get(self, request):
        from doctor.models import LabOrder, Encounter
        from doctor.serializers import LabOrderSerializer

        # 1. 'REQUESTED' (무반응) 상태인 오더만 조회
        #    (동일 방문 내에서도 이미 완료된 오더는 제외하기 위함)
        #    AND 원무과 수납이 완료되어 '결과 대기' 상태인 경우만 조회
        orders = LabOrder.objects.filter(
            status=LabOrder.OrderStatus.REQUESTED,
            encounter__workflow_state=Encounter.WorkflowState.WAITING_RESULTS
        )
        
        # 2. 오더 타입 필터 (옵션)
        order_type = request.query_params.get('type')
        if order_type:
             orders = orders.filter(order_type=order_type)
        
        # 3. 정렬 (오래된 순)
        orders = orders.order_by('created_at')
        
        serializer = LabOrderSerializer(orders, many=True)
        return Response({
            'count': orders.count(),
            'results': serializer.data
        }, status=status.HTTP_200_OK)
