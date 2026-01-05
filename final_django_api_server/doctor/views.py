from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from accounts.permissions import IsDoctor
from .models import Encounter, Patient, Doctor
from .serializers import EncounterSerializer, UpdateEncounterStatusSerializer, DoctorListSerializer
from datetime import date, datetime
from django.utils import timezone


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


class QueueListView(APIView):
    """의사의 환자 대기열 조회 API (Encounter 기반)"""
    permission_classes = [IsDoctor]

    def get(self, request):
        try:
            # 현재 로그인한 의사 정보 가져오기
            doctor = Doctor.objects.get(user=request.user)

            # 오늘 날짜
            today = date.today()

            # 쿼리 파라미터로 상태 필터링 (기본값: WAITING)
            encounter_status = request.query_params.get('status', 'WAITING')

            # 해당 의사의 오늘 Encounter 조회
            encounters = Encounter.objects.filter(
                doctor=doctor,
                encounter_date=today
            )

            # 상태별 필터링
            if encounter_status == 'ALL':
                # 모든 상태
                pass
            else:
                encounters = encounters.filter(encounter_status=encounter_status)

            # 시간순 정렬
            encounters = encounters.order_by('encounter_time')

            # Serialize
            serializer = EncounterSerializer(encounters, many=True)

            # 통계 정보
            waiting_count = Encounter.objects.filter(
                doctor=doctor,
                encounter_date=today,
                encounter_status=Encounter.EncounterStatus.WAITING
            ).count()

            in_progress_count = Encounter.objects.filter(
                doctor=doctor,
                encounter_date=today,
                encounter_status=Encounter.EncounterStatus.IN_PROGRESS
            ).count()

            completed_count = Encounter.objects.filter(
                doctor=doctor,
                encounter_date=today,
                encounter_status=Encounter.EncounterStatus.COMPLETED
            ).count()

            return Response({
                'encounters': serializer.data,
                'stats': {
                    'waiting': waiting_count,
                    'in_progress': in_progress_count,
                    'completed': completed_count,
                    'total': waiting_count + in_progress_count + completed_count
                }
            }, status=status.HTTP_200_OK)

        except Doctor.DoesNotExist:
            return Response({
                'error': '의사 정보를 찾을 수 없습니다.'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UpdateEncounterStatusView(APIView):
    """Encounter 상태 변경 API (진료 시작/완료 등)"""
    permission_classes = [IsDoctor]

    def patch(self, request, encounter_id):
        try:
            # 현재 로그인한 의사 정보
            doctor = Doctor.objects.get(user=request.user)

            # 해당 Encounter 조회 (자신의 환자만)
            encounter = Encounter.objects.get(
                encounter_id=encounter_id,
                doctor=doctor
            )

            # 요청 데이터 검증
            serializer = UpdateEncounterStatusSerializer(data=request.data)
            if serializer.is_valid():
                new_status = serializer.validated_data['encounter_status']

                # 상태 변경
                encounter.encounter_status = new_status

                # 진료 시작 시간 자동 설정
                if new_status == Encounter.EncounterStatus.IN_PROGRESS and not encounter.encounter_start:
                    encounter.encounter_start = timezone.now().time()

                # 진료 완료 시간 자동 설정
                if new_status == Encounter.EncounterStatus.COMPLETED and not encounter.encounter_end:
                    encounter.encounter_end = timezone.now().time()

                # encounter_start/end가 요청에 포함되어 있으면 사용
                if 'encounter_start' in serializer.validated_data:
                    encounter.encounter_start = serializer.validated_data['encounter_start']
                if 'encounter_end' in serializer.validated_data:
                    encounter.encounter_end = serializer.validated_data['encounter_end']

                encounter.save()

                # 업데이트된 데이터 반환
                response_serializer = EncounterSerializer(encounter)
                return Response({
                    'message': '상태가 변경되었습니다.',
                    'encounter': response_serializer.data
                }, status=status.HTTP_200_OK)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Doctor.DoesNotExist:
            return Response({
                'error': '의사 정보를 찾을 수 없습니다.'
            }, status=status.HTTP_404_NOT_FOUND)
        except Encounter.DoesNotExist:
            return Response({
                'error': '해당 진료 기록을 찾을 수 없습니다.'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DoctorListView(APIView):
    """의사 목록 조회 API (원무과 환자 접수용)"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        모든 의사 목록 조회

        Query params:
        - department: 부서 ID로 필터링 (선택)
        """
        try:
            doctors = Doctor.objects.select_related('department').all()

            # 부서별 필터링
            department_id = request.query_params.get('department', None)
            if department_id:
                doctors = doctors.filter(department_id=department_id)

            serializer = DoctorListSerializer(doctors, many=True)

            return Response({
                'count': doctors.count(),
                'results': serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
