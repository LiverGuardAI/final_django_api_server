from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from django.db.models import Q
from django.utils import timezone
from accounts.permissions import IsRadiologist, IsDoctorOrRadiologist
from doctor.models import Patient, Encounter
from .serializers import (
    PatientWaitlistSerializer,
    RadiologyQueueSerializer,
    EncounterWaitlistSerializer,
    CTReportSerializer,
)
import io
import math
import os
import zipfile
from collections import deque

import numpy as np
import pydicom
import requests


ORTHANC_BASE_URL = os.getenv(
    'ORTHANC_BASE_URL',
    'http://34.67.62.238/orthanc'
)

TUMOR_LABEL_VALUES = {2, 2000}
LIVER_LABEL_VALUES = {1, 1000}


def _convert_numpy_types(obj):
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {key: _convert_numpy_types(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [_convert_numpy_types(item) for item in obj]
    return obj


def _download_series_archive(series_id: str) -> bytes:
    response = requests.get(
        f'{ORTHANC_BASE_URL}/series/{series_id}/archive',
        timeout=120
    )
    if response.status_code != 200:
        raise ValueError(f'Archive for series {series_id} not found')
    return response.content


def _load_mask_volume_from_zip(zip_bytes: bytes) -> tuple[np.ndarray, dict, dict, list]:
    warnings: list[str] = []
    slices = []

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zip_ref:
        entries = [
            entry for entry in zip_ref.infolist()
            if entry.filename.lower().endswith(('.dcm', '.dicom'))
        ]

        if not entries:
            raise ValueError('No DICOM files found in archive')

        for entry in entries:
            with zip_ref.open(entry) as dicom_file:
                file_content = dicom_file.read()
            dataset = pydicom.dcmread(io.BytesIO(file_content), force=True)
            if not hasattr(dataset, 'PixelData'):
                continue

            try:
                pixel_array = dataset.pixel_array
            except Exception:
                continue

            if pixel_array.ndim == 2:
                frame_arrays = [pixel_array]
            elif pixel_array.ndim == 3:
                frame_arrays = list(pixel_array)
                warnings.append('Multi-frame DICOM detected; frame ordering may be approximate.')
            else:
                continue

            instance_number = getattr(dataset, 'InstanceNumber', None)
            image_position = getattr(dataset, 'ImagePositionPatient', None)
            pixel_spacing = getattr(dataset, 'PixelSpacing', None)
            slice_thickness = getattr(dataset, 'SliceThickness', None)
            spacing_between = getattr(dataset, 'SpacingBetweenSlices', None)

            for frame_index, frame in enumerate(frame_arrays):
                slices.append({
                    'array': frame,
                    'instance_number': instance_number if instance_number is not None else frame_index,
                    'image_position': image_position,
                    'pixel_spacing': pixel_spacing,
                    'slice_thickness': slice_thickness,
                    'spacing_between_slices': spacing_between,
                })

    if not slices:
        raise ValueError('No pixel data found in DICOM archive')

    positions = [s['image_position'] for s in slices if s['image_position'] is not None]
    if len(positions) == len(slices):
        slices.sort(key=lambda s: float(s['image_position'][2]))
    elif all(s['instance_number'] is not None for s in slices):
        slices.sort(key=lambda s: int(s['instance_number']))

    row_spacing = col_spacing = 1.0
    for s in slices:
        if s['pixel_spacing']:
            try:
                row_spacing = float(s['pixel_spacing'][0])
                col_spacing = float(s['pixel_spacing'][1])
            except Exception:
                warnings.append('Invalid PixelSpacing; defaulting to 1.0mm')
            break
    else:
        warnings.append('PixelSpacing missing; defaulting to 1.0mm')

    spacing_z = None
    for s in slices:
        if s['spacing_between_slices']:
            try:
                spacing_z = float(s['spacing_between_slices'])
                break
            except Exception:
                pass

    if spacing_z is None:
        for s in slices:
            if s['slice_thickness']:
                try:
                    spacing_z = float(s['slice_thickness'])
                    break
                except Exception:
                    pass

    if spacing_z is None and len(positions) >= 2:
        numeric_positions = []
        for pos in positions:
            try:
                numeric_positions.append(np.array(pos, dtype=float))
            except Exception:
                continue
        if len(numeric_positions) >= 2:
            diffs = [
                float(np.linalg.norm(numeric_positions[i + 1] - numeric_positions[i]))
                for i in range(len(numeric_positions) - 1)
                if np.linalg.norm(numeric_positions[i + 1] - numeric_positions[i]) > 0
            ]
            if diffs:
                spacing_z = float(np.median(diffs))

    if spacing_z is None:
        spacing_z = 1.0
        warnings.append('Slice spacing missing; defaulting to 1.0mm')

    volume = np.stack([s['array'] for s in slices], axis=0)
    volume = volume.astype(np.int32, copy=False)

    metadata = {
        'slice_count': len(slices),
        'rows': int(volume.shape[1]),
        'cols': int(volume.shape[2]),
    }

    spacing = {
        'x': float(col_spacing),
        'y': float(row_spacing),
        'z': float(spacing_z),
    }

    return volume, spacing, metadata, warnings


NEIGHBOR_OFFSETS_6 = [
    (-1, 0, 0),
    (1, 0, 0),
    (0, -1, 0),
    (0, 1, 0),
    (0, 0, -1),
    (0, 0, 1),
]

NEIGHBOR_OFFSETS_26 = [
    (dz, dy, dx)
    for dz in (-1, 0, 1)
    for dy in (-1, 0, 1)
    for dx in (-1, 0, 1)
    if not (dz == 0 and dy == 0 and dx == 0)
]


def _label_components(mask: np.ndarray, connectivity: int = 26) -> list[dict]:
    labels = np.zeros(mask.shape, dtype=np.int32)
    offsets = NEIGHBOR_OFFSETS_26 if connectivity == 26 else NEIGHBOR_OFFSETS_6
    components: list[dict] = []
    label_id = 0
    indices = np.argwhere(mask)

    for seed in indices:
        z, y, x = int(seed[0]), int(seed[1]), int(seed[2])
        if labels[z, y, x] != 0:
            continue
        label_id += 1
        queue = deque([(z, y, x)])
        labels[z, y, x] = label_id

        coords = []
        sum_z = sum_y = sum_x = 0
        min_z = max_z = z
        min_y = max_y = y
        min_x = max_x = x

        while queue:
            cz, cy, cx = queue.popleft()
            coords.append((cz, cy, cx))
            sum_z += cz
            sum_y += cy
            sum_x += cx
            min_z = min(min_z, cz)
            max_z = max(max_z, cz)
            min_y = min(min_y, cy)
            max_y = max(max_y, cy)
            min_x = min(min_x, cx)
            max_x = max(max_x, cx)

            for dz, dy, dx in offsets:
                nz, ny, nx = cz + dz, cy + dy, cx + dx
                if (
                    0 <= nz < mask.shape[0]
                    and 0 <= ny < mask.shape[1]
                    and 0 <= nx < mask.shape[2]
                    and mask[nz, ny, nx]
                    and labels[nz, ny, nx] == 0
                ):
                    labels[nz, ny, nx] = label_id
                    queue.append((nz, ny, nx))

        components.append({
            'label': label_id,
            'coords': coords,
            'voxel_count': len(coords),
            'sum': (sum_z, sum_y, sum_x),
            'bbox': (min_z, max_z, min_y, max_y, min_x, max_x),
        })

    return components


def _component_mask_from_coords(coords: list[tuple[int, int, int]], bbox: tuple[int, int, int, int, int, int]) -> np.ndarray:
    min_z, max_z, min_y, max_y, min_x, max_x = bbox
    depth = max_z - min_z + 1
    height = max_y - min_y + 1
    width = max_x - min_x + 1
    mask = np.zeros((depth, height, width), dtype=bool)
    coord_array = np.array(coords, dtype=np.int32)
    mask[
        coord_array[:, 0] - min_z,
        coord_array[:, 1] - min_y,
        coord_array[:, 2] - min_x,
    ] = True
    return mask


def _compute_surface_area(mask: np.ndarray, spacing: dict) -> float:
    if mask.size == 0:
        return 0.0

    area = 0.0
    dz_area = spacing['x'] * spacing['y']
    dy_area = spacing['x'] * spacing['z']
    dx_area = spacing['y'] * spacing['z']

    neighbor = np.zeros_like(mask)
    neighbor[:-1, :, :] = mask[1:, :, :]
    area += float(np.sum(mask & ~neighbor)) * dz_area

    neighbor = np.zeros_like(mask)
    neighbor[1:, :, :] = mask[:-1, :, :]
    area += float(np.sum(mask & ~neighbor)) * dz_area

    neighbor = np.zeros_like(mask)
    neighbor[:, :-1, :] = mask[:, 1:, :]
    area += float(np.sum(mask & ~neighbor)) * dy_area

    neighbor = np.zeros_like(mask)
    neighbor[:, 1:, :] = mask[:, :-1, :]
    area += float(np.sum(mask & ~neighbor)) * dy_area

    neighbor = np.zeros_like(mask)
    neighbor[:, :, :-1] = mask[:, :, 1:]
    area += float(np.sum(mask & ~neighbor)) * dx_area

    neighbor = np.zeros_like(mask)
    neighbor[:, :, 1:] = mask[:, :, :-1]
    area += float(np.sum(mask & ~neighbor)) * dx_area

    return area


def _compute_surface_points(mask: np.ndarray, bbox: tuple[int, int, int, int, int, int]) -> np.ndarray:
    if mask.size == 0:
        return np.empty((0, 3), dtype=np.int32)

    neighbor = np.zeros_like(mask)
    neighbor[:-1, :, :] = mask[1:, :, :]
    surface = mask & ~neighbor

    neighbor = np.zeros_like(mask)
    neighbor[1:, :, :] = mask[:-1, :, :]
    surface |= mask & ~neighbor

    neighbor = np.zeros_like(mask)
    neighbor[:, :-1, :] = mask[:, 1:, :]
    surface |= mask & ~neighbor

    neighbor = np.zeros_like(mask)
    neighbor[:, 1:, :] = mask[:, :-1, :]
    surface |= mask & ~neighbor

    neighbor = np.zeros_like(mask)
    neighbor[:, :, :-1] = mask[:, :, 1:]
    surface |= mask & ~neighbor

    neighbor = np.zeros_like(mask)
    neighbor[:, :, 1:] = mask[:, :, :-1]
    surface |= mask & ~neighbor

    surface_points = np.argwhere(surface)
    min_z, _, min_y, _, min_x, _ = bbox
    surface_points[:, 0] += min_z
    surface_points[:, 1] += min_y
    surface_points[:, 2] += min_x
    return surface_points


def _min_surface_distance_mm(
    tumor_points: np.ndarray,
    liver_points: np.ndarray,
    spacing: dict,
    warnings: list[str],
    max_points: int = 5000,
    batch_size: int = 200,
) -> float | None:
    if tumor_points.size == 0 or liver_points.size == 0:
        return None

    if tumor_points.shape[0] > max_points:
        step = math.ceil(tumor_points.shape[0] / max_points)
        tumor_points = tumor_points[::step]
        warnings.append('Tumor surface downsampled for distance calculation.')

    if liver_points.shape[0] > max_points:
        step = math.ceil(liver_points.shape[0] / max_points)
        liver_points = liver_points[::step]
        warnings.append('Liver surface downsampled for distance calculation.')

    spacing_vec = np.array([spacing['z'], spacing['y'], spacing['x']], dtype=float)
    tumor_mm = tumor_points.astype(float) * spacing_vec
    liver_mm = liver_points.astype(float) * spacing_vec

    min_dist = float('inf')
    for start in range(0, tumor_mm.shape[0], batch_size):
        chunk = tumor_mm[start:start + batch_size]
        diff = chunk[:, None, :] - liver_mm[None, :, :]
        dist = np.sqrt(np.sum(diff * diff, axis=2))
        chunk_min = float(np.min(dist))
        if chunk_min < min_dist:
            min_dist = chunk_min

    return None if math.isinf(min_dist) else float(min_dist)


def _mask_bbox(mask: np.ndarray) -> tuple[int, int, int, int, int, int] | None:
    coords = np.argwhere(mask)
    if coords.size == 0:
        return None
    min_z, min_y, min_x = coords.min(axis=0)
    max_z, max_y, max_x = coords.max(axis=0)
    return int(min_z), int(max_z), int(min_y), int(max_y), int(min_x), int(max_x)


def _dedupe_warnings(warnings: list[str]) -> list[str]:
    seen = set()
    deduped: list[str] = []
    for warning in warnings:
        if warning not in seen:
            seen.add(warning)
            deduped.append(warning)
    return deduped


def _normalize_mask_value(value: int) -> int:
    if value == 1000:
        return 1
    if value == 2000:
        return 2
    return int(value)


def _normalize_label_values(values: set[int]) -> list[int]:
    normalized = {_normalize_mask_value(int(value)) for value in values}
    return sorted(normalized)


class RadiologyDashboardView(APIView):
    """영상의학과 전용 대시보드 API"""
    permission_classes = [IsRadiologist]

    def get(self, request):
        user = request.user

        return Response({
            'message': f'안녕하세요, {user.first_name} 영상의학과',
            'user': {
                'id': user.user_id,
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
    """촬영 대기 환자 목록 조회 API (영상의학과 전용)"""
    permission_classes = [AllowAny]  # TODO: 나중에 IsRadiologist로 변경 필요

    def get(self, request):
        """
        Encounter.workflow_state가 'WAITING_IMAGING' 또는 'IN_IMAGING'인 환자 목록 조회
        - Redis 캐싱 적용 (5초 TTL)
        - DoctorToRadiologyOrder 처방 정보 포함
        - 대기 시간 계산
        """
        from administration.cache_manager import cache_manager
        from django.utils import timezone
        import json

        # Redis 캐시 키 (administration과 동일한 키 사용)
        cache_key = 'waiting_queue_list:imaging'

        # 1. 캐시 확인
        cached_data = cache_manager.redis_client.get(cache_key)
        if cached_data:
            return Response(json.loads(cached_data), status=status.HTTP_200_OK)

        # 2. 캐시 미스: DB 조회
        encounters = Encounter.objects.filter(
            workflow_state__in=[
                Encounter.WorkflowState.WAITING_IMAGING,
                Encounter.WorkflowState.IN_IMAGING,
            ]
        ).select_related('patient', 'assigned_doctor')\
         .prefetch_related('doctortoradiologyorder_set')\
         .order_by('state_entered_at')  # FIFO (오래된 순)

        # 3. 영상의학과 전용 상세 정보 구성
        queue_data = []
        now = timezone.now()

        for enc in encounters:
            # 처방 정보 수집
            imaging_orders = enc.doctortoradiologyorder_set.filter(
                status__in=['WAITING', 'IN_PROGRESS']
            )

            orders_info = [
                {
                    'order_id': order.order_id,
                    'modality': order.modality,
                    'body_part': order.body_part or 'N/A',
                    'priority': order.priority,
                    'status': order.status,
                    'ordered_at': order.ordered_at.isoformat() if order.ordered_at else None,
                }
                for order in imaging_orders
            ]

            # 대기 시간 계산 (분 단위)
            waiting_minutes = int((now - enc.state_entered_at).total_seconds() / 60) if enc.state_entered_at else 0

            queue_data.append({
                'encounter_id': enc.encounter_id,
                'patient_id': enc.patient.patient_id,
                'patient_name': enc.patient.name,
                'age': enc.patient.age,
                'gender': enc.patient.gender,
                'workflow_state': enc.workflow_state,
                'workflow_state_display': enc.get_workflow_state_display(),
                'state_entered_at': enc.state_entered_at.isoformat() if enc.state_entered_at else None,
                'waiting_minutes': waiting_minutes,
                'doctor_name': enc.assigned_doctor.name if enc.assigned_doctor else 'N/A',
                'imaging_orders': orders_info,
            })

        # 통계 정보
        stats = {
            'waiting': cache_manager.get_waiting_count('imaging'),
            'in_progress': cache_manager.get_in_progress_count('imaging'),
        }

        response_data = {
            'success': True,
            'message': '촬영 대기 환자 목록',
            'count': len(queue_data),
            'stats': stats,
            'patients': queue_data
        }

        # 4. Redis 캐싱 (5초)
        try:
            cache_manager.redis_client.setex(cache_key, 5, json.dumps(response_data))
        except Exception as e:
            print(f"Cache write failed: {e}")

        return Response(response_data, status=status.HTTP_200_OK)


class StartFilmingView(APIView):
    """환자 촬영 시작 API - 환자 상태를 '촬영중'으로 변경"""
    permission_classes = [AllowAny]  # TODO: 나중에 IsRadiologist로 변경 필요

    def post(self, request):
        """
        Encounter.workflow_state를 'IN_IMAGING'으로 업데이트

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
            encounter = Encounter.objects.filter(
                patient__patient_id=patient_id,
                workflow_state__in=[
                    Encounter.WorkflowState.WAITING_IMAGING,
                    Encounter.WorkflowState.IN_IMAGING,
                ],
            ).order_by('-state_entered_at').first()

            if not encounter:
                return Response({
                    'error': f'Encounter for patient {patient_id} not found'
                }, status=status.HTTP_404_NOT_FOUND)

            # 상태 업데이트 (통합 메서드 사용 - Redis 자동 업데이트)
            encounter.transition_to(Encounter.WorkflowState.IN_IMAGING)

            # 오더 상태 변경
            from doctor.models import DoctorToRadiologyOrder
            imaging_orders = DoctorToRadiologyOrder.objects.filter(
                encounter=encounter,
                status__in=['WAITING', 'REQUESTED']
            )
            imaging_orders.update(status='IN_PROGRESS')

            # 캐시 무효화
            from administration.cache_manager import cache_manager
            cache_manager.redis_client.delete('waiting_queue_list:imaging')

            # WebSocket 알림
            from administration.views import send_queue_update_websocket
            send_queue_update_websocket(
                message=f"촬영 시작: {encounter.patient.name}",
                extra_data={
                    "queue_type": "imaging",
                    "imaging_waiting": cache_manager.get_waiting_count('imaging'),
                    "imaging_in_progress": cache_manager.get_in_progress_count('imaging'),
                }
            )

            # 업데이트된 환자 정보 직렬화
            serializer = EncounterWaitlistSerializer(encounter)

            return Response({
                'message': '촬영이 시작되었습니다',
                'patient': serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EndFilmingView(APIView):
    """환자 촬영 종료 API - 환자 상태를 '촬영완료'로 변경"""
    permission_classes = [AllowAny]  # TODO: 나중에 IsRadiologist로 변경 필요

    def post(self, request):
        """
        Encounter.workflow_state를 'COMPLETED'로 업데이트

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
            encounter = Encounter.objects.filter(
                patient__patient_id=patient_id,
                workflow_state__in=[
                    Encounter.WorkflowState.WAITING_IMAGING,
                    Encounter.WorkflowState.IN_IMAGING,
                ],
            ).order_by('-state_entered_at').first()

            if not encounter:
                return Response({
                    'error': f'Encounter for patient {patient_id} not found'
                }, status=status.HTTP_404_NOT_FOUND)

            # 오더 완료 처리
            from doctor.models import DoctorToRadiologyOrder, LabOrder
            imaging_orders = DoctorToRadiologyOrder.objects.filter(
                encounter=encounter,
                status='IN_PROGRESS'
            )
            imaging_orders.update(status='COMPLETED')

            # **FIX**: 촬영 완료 후 다음 단계 결정
            # 1. 다른 IMAGING 오더(WAITING 상태)가 남아있는지 확인
            has_waiting_imaging = DoctorToRadiologyOrder.objects.filter(
                encounter=encounter,
                status='WAITING'
            ).exists()

            # 2. REQUESTED 상태 오더가 있는지 확인 (아직 접수 안 된 오더)
            has_requested_orders = (
                LabOrder.objects.filter(encounter=encounter, status='REQUESTED').exists() or
                DoctorToRadiologyOrder.objects.filter(encounter=encounter, status='REQUESTED').exists()
            )

            if has_waiting_imaging:
                # 다른 촬영 오더(접수 완료)가 남아있으면 촬영 대기로 유지
                encounter.transition_to(Encounter.WorkflowState.WAITING_IMAGING)
                print(f"INFO: 촬영 완료했지만 다른 IMAGING 오더 대기 중: {encounter.encounter_id}")
            elif has_requested_orders:
                # 아직 접수 안 된 오더가 있으면 원무과로 복귀
                encounter.transition_to(Encounter.WorkflowState.REGISTERED)
                print(f"INFO: 촬영 완료 후 미접수 오더 있음 → 원무과 복귀: {encounter.encounter_id}")
            else:
                # 모든 오더 완료 → 결과 대기 (환자 귀가)
                encounter.transition_to(Encounter.WorkflowState.WAITING_RESULTS)
                print(f"INFO: 모든 촬영 완료 → 결과 대기: {encounter.encounter_id}")

            # 캐시 무효화 (상태에 따라 적절한 캐시 삭제)
            from administration.cache_manager import cache_manager
            cache_manager.redis_client.delete('waiting_queue_list:imaging')

            if encounter.workflow_state == Encounter.WorkflowState.WAITING_RESULTS:
                # 결과대기는 clinic queue에도 포함
                cache_manager.redis_client.delete('waiting_queue_list:clinic')
            elif encounter.workflow_state == Encounter.WorkflowState.REGISTERED:
                # 원무과로 복귀한 경우 admin queue 무효화
                cache_manager.redis_client.delete('waiting_queue_list:admin')

            # WebSocket 알림 (상태에 맞는 메시지 전송)
            from administration.views import send_queue_update_websocket

            if encounter.workflow_state == Encounter.WorkflowState.WAITING_IMAGING:
                ws_message = f"촬영 완료: {encounter.patient.name} (다른 촬영 대기)"
                response_message = '촬영이 종료되었습니다. 다른 촬영 오더가 대기 중입니다.'
            elif encounter.workflow_state == Encounter.WorkflowState.REGISTERED:
                ws_message = f"촬영 완료: {encounter.patient.name} (원무과 복귀 - 미접수 오더 있음)"
                response_message = '촬영이 종료되었습니다. 접수되지 않은 오더가 있어 원무과로 복귀합니다.'
            else:  # WAITING_RESULTS
                ws_message = f"촬영 완료: {encounter.patient.name} (결과 대기 - 귀가 가능)"
                response_message = '촬영이 종료되었습니다. 모든 검사가 완료되어 결과 대기 중입니다. 환자 귀가 가능합니다.'

            send_queue_update_websocket(
                message=ws_message,
                extra_data={
                    "queue_type": "imaging",
                    "imaging_waiting": cache_manager.get_waiting_count('imaging'),
                    "imaging_in_progress": cache_manager.get_in_progress_count('imaging'),
                }
            )

            # 업데이트된 환자 정보 직렬화
            serializer = EncounterWaitlistSerializer(encounter)

            return Response({
                'success': True,
                'message': response_message,
                'patient': serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== 영상의학과 의사 목록 API ====================
@api_view(['GET'])
@permission_classes([AllowAny])
def get_radiologist_list(request):
    """
    영상의학과 의사 목록 조회 API

    GET /api/radiology/list/
    """
    from .models import Radiology

    radiologists = Radiology.objects.select_related('department').all().order_by('name')
    
    radiologist_list = []
    for radiologist in radiologists:
        radiologist_list.append({
            'radiologic_id': radiologist.radiologic_id,
            'name': radiologist.name,
            'department': {
                'dept_name': radiologist.department.dept_name if radiologist.department else '영상의학과'
            },
            'phone': radiologist.phone,
        })
    
    return Response({
        'success': True,
        'results': radiologist_list
    }, status=status.HTTP_200_OK)


class ImagingStatsView(APIView):
    """영상의학과 통계 API"""
    permission_classes = [AllowAny]  # TODO: 나중에 IsRadiologist로 변경 필요

    def get(self, request):
        """
        영상의학과 대기열 및 검사 통계 조회
        - 실시간 대기/진행 인원
        - 오늘 촬영 건수
        - 평균 대기 시간
        """
        from administration.cache_manager import cache_manager
        from django.utils import timezone
        from django.db.models import Count, Avg
        from datetime import timedelta

        today = timezone.localdate()
        now = timezone.now()

        # Redis 실시간 카운터
        waiting_count = cache_manager.get_waiting_count('imaging')
        in_progress_count = cache_manager.get_in_progress_count('imaging')

        # 오늘 촬영 완료 건수
        from doctor.models import DoctorToRadiologyOrder
        today_completed = DoctorToRadiologyOrder.objects.filter(
            status='COMPLETED',
            ordered_at__date=today
        ).count()

        # 현재 대기 중인 환자들의 평균 대기 시간
        waiting_encounters = Encounter.objects.filter(
            workflow_state=Encounter.WorkflowState.WAITING_IMAGING
        )

        if waiting_encounters.exists():
            total_waiting_seconds = sum([
                (now - enc.state_entered_at).total_seconds()
                for enc in waiting_encounters
                if enc.state_entered_at
            ])
            avg_waiting_minutes = int(total_waiting_seconds / 60 / waiting_encounters.count())
        else:
            avg_waiting_minutes = 0

        # 오늘 촬영 중인 환자들의 평균 촬영 시간
        today_imaging = Encounter.objects.filter(
            workflow_state=Encounter.WorkflowState.IN_IMAGING,
            state_entered_at__date=today
        )

        if today_imaging.exists():
            total_imaging_seconds = sum([
                (now - enc.state_entered_at).total_seconds()
                for enc in today_imaging
                if enc.state_entered_at
            ])
            avg_imaging_minutes = int(total_imaging_seconds / 60 / today_imaging.count())
        else:
            avg_imaging_minutes = 0

        return Response({
            'success': True,
            'stats': {
                'current': {
                    'waiting': waiting_count,
                    'in_progress': in_progress_count,
                    'avg_waiting_minutes': avg_waiting_minutes,
                },
                'today': {
                    'completed_count': today_completed,
                    'avg_imaging_minutes': avg_imaging_minutes,
                },
            }
        }, status=status.HTTP_200_OK)


class TumorAnalysisView(APIView):
    """종양 분석 API (마스크 시리즈 기반)"""
    permission_classes = [IsDoctorOrRadiologist]

    def post(self, request):
        mask_series_id = (
            request.data.get('mask_series_id')
            or request.data.get('maskSeriesId')
            or request.data.get('series_id')
        )

        if not mask_series_id:
            return Response(
                {'error': 'mask_series_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            archive_bytes = _download_series_archive(mask_series_id)
            volume, spacing, metadata, warnings = _load_mask_volume_from_zip(archive_bytes)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            return Response(
                {'error': 'Failed to load mask series', 'details': str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        unique_values = np.unique(volume)
        normalized_unique_values = _normalize_label_values(set(unique_values.tolist()))
        tumor_mask = np.isin(volume, list(TUMOR_LABEL_VALUES))
        liver_mask = np.isin(volume, list(LIVER_LABEL_VALUES))

        if not tumor_mask.any() and np.any(volume > 0):
            tumor_mask = volume > 0
            warnings.append('Tumor label values not found; using all non-zero voxels as tumor.')

        if not liver_mask.any():
            warnings.append('Liver label values not found; liver-based metrics omitted.')

        components = _label_components(tumor_mask, connectivity=26)

        spacing_vec = np.array([spacing['z'], spacing['y'], spacing['x']], dtype=float)
        voxel_volume_mm3 = spacing['x'] * spacing['y'] * spacing['z']

        liver_volume_mm3 = float(np.sum(liver_mask)) * voxel_volume_mm3 if liver_mask.any() else None
        liver_bbox = _mask_bbox(liver_mask) if liver_mask.any() else None
        liver_surface_points = None
        if liver_bbox:
            min_z, max_z, min_y, max_y, min_x, max_x = liver_bbox
            liver_submask = liver_mask[min_z:max_z + 1, min_y:max_y + 1, min_x:max_x + 1]
            liver_surface_points = _compute_surface_points(liver_submask, liver_bbox)

        tumor_components = []
        total_tumor_volume_mm3 = 0.0

        for component in components:
            voxel_count = component['voxel_count']
            if voxel_count == 0:
                continue

            min_z, max_z, min_y, max_y, min_x, max_x = component['bbox']
            extent_voxel = {
                'z': max_z - min_z + 1,
                'y': max_y - min_y + 1,
                'x': max_x - min_x + 1,
            }
            extent_mm = {
                'z': extent_voxel['z'] * spacing['z'],
                'y': extent_voxel['y'] * spacing['y'],
                'x': extent_voxel['x'] * spacing['x'],
            }

            volume_mm3 = voxel_count * voxel_volume_mm3
            total_tumor_volume_mm3 += volume_mm3

            centroid_voxel = {
                'z': component['sum'][0] / voxel_count,
                'y': component['sum'][1] / voxel_count,
                'x': component['sum'][2] / voxel_count,
            }
            centroid_mm = {
                'z': centroid_voxel['z'] * spacing['z'],
                'y': centroid_voxel['y'] * spacing['y'],
                'x': centroid_voxel['x'] * spacing['x'],
            }

            component_mask = _component_mask_from_coords(component['coords'], component['bbox'])
            surface_area_mm2 = _compute_surface_area(component_mask, spacing)
            surface_area_to_volume_ratio = (
                surface_area_mm2 / volume_mm3 if volume_mm3 > 0 else None
            )
            bbox_volume_mm3 = extent_mm['x'] * extent_mm['y'] * extent_mm['z']
            compactness = volume_mm3 / bbox_volume_mm3 if bbox_volume_mm3 > 0 else None

            sphericity = None
            if surface_area_mm2 > 0 and volume_mm3 > 0:
                sphericity = (math.pi ** (1 / 3) * (6 * volume_mm3) ** (2 / 3)) / surface_area_mm2

            coords_arr = np.array(component['coords'], dtype=float)
            if coords_arr.shape[0] >= 3:
                coords_mm = coords_arr * spacing_vec
                coords_mm -= coords_mm.mean(axis=0)
                cov = np.cov(coords_mm.T)
                eigvals = np.linalg.eigvalsh(cov)
                if eigvals[0] > 0:
                    elongation = math.sqrt(float(eigvals[-1] / eigvals[0]))
                else:
                    elongation = None
            else:
                elongation = None

            max_diameter_mm = max(extent_mm.values())
            bbox_diagonal_mm = math.sqrt(
                extent_mm['x'] ** 2 + extent_mm['y'] ** 2 + extent_mm['z'] ** 2
            )

            distance_to_capsule_mm = None
            if liver_surface_points is not None and liver_surface_points.size > 0:
                tumor_surface_points = _compute_surface_points(component_mask, component['bbox'])
                distance_to_capsule_mm = _min_surface_distance_mm(
                    tumor_surface_points,
                    liver_surface_points,
                    spacing,
                    warnings
                )

            relative_location = None
            if liver_bbox:
                liver_min_z, liver_max_z, liver_min_y, liver_max_y, liver_min_x, liver_max_x = liver_bbox
                liver_extent = {
                    'z': max(liver_max_z - liver_min_z + 1, 1),
                    'y': max(liver_max_y - liver_min_y + 1, 1),
                    'x': max(liver_max_x - liver_min_x + 1, 1),
                }
                relative_location = {
                    'z': (centroid_voxel['z'] - liver_min_z) / liver_extent['z'],
                    'y': (centroid_voxel['y'] - liver_min_y) / liver_extent['y'],
                    'x': (centroid_voxel['x'] - liver_min_x) / liver_extent['x'],
                }

            tumor_components.append({
                'label': component['label'],
                'voxel_count': voxel_count,
                'volume_mm3': volume_mm3,
                'volume_ml': volume_mm3 / 1000.0,
                'centroid_voxel': centroid_voxel,
                'centroid_mm': centroid_mm,
                'bbox_voxel': {
                    'min_z': min_z,
                    'max_z': max_z,
                    'min_y': min_y,
                    'max_y': max_y,
                    'min_x': min_x,
                    'max_x': max_x,
                },
                'extent_mm': extent_mm,
                'max_diameter_mm': max_diameter_mm,
                'bbox_diagonal_mm': bbox_diagonal_mm,
                'shape_metrics': {
                    'sphericity': sphericity,
                    'compactness': compactness,
                    'elongation': elongation,
                },
                'boundary_features': {
                    'surface_area_mm2': surface_area_mm2,
                    'surface_area_to_volume_ratio': surface_area_to_volume_ratio,
                },
                'location': {
                    'relative_to_liver_bbox': relative_location,
                },
                'distance_to_liver_capsule_mm': distance_to_capsule_mm,
            })

        tumor_to_liver_ratio = None
        tumor_burden_percent = None
        if liver_volume_mm3 and liver_volume_mm3 > 0:
            tumor_to_liver_ratio = total_tumor_volume_mm3 / liver_volume_mm3
            tumor_burden_percent = tumor_to_liver_ratio * 100.0

        response_data = {
            'success': True,
            'mask_series_id': mask_series_id,
            'spacing_mm': spacing,
            'labels': {
                'tumor_values': _normalize_label_values(TUMOR_LABEL_VALUES),
                'liver_values': _normalize_label_values(LIVER_LABEL_VALUES),
                'unique_values': normalized_unique_values,
            },
            'metadata': metadata,
            'analysis': {
                'tumor_count': len(tumor_components),
                'total_tumor_volume_mm3': total_tumor_volume_mm3,
                'total_tumor_volume_ml': total_tumor_volume_mm3 / 1000.0,
                'liver_volume_mm3': liver_volume_mm3,
                'liver_volume_ml': liver_volume_mm3 / 1000.0 if liver_volume_mm3 else None,
                'tumor_to_liver_ratio': tumor_to_liver_ratio,
                'tumor_burden_percent': tumor_burden_percent,
                'components': tumor_components,
            },
            'warnings': _dedupe_warnings(warnings),
        }

        return Response(_convert_numpy_types(response_data), status=status.HTTP_200_OK)


class CTReportCreateView(APIView):
    """CT 보고서 저장 API"""
    permission_classes = [IsDoctorOrRadiologist]

    def post(self, request):
        series_instance_uid = (
            request.data.get('series_instance_uid')
            or request.data.get('seriesInstanceUID')
            or request.data.get('seriesinstanceuid')
        )
        report_text = request.data.get('report_text') or request.data.get('report')

        if not series_instance_uid:
            return Response(
                {'error': 'series_instance_uid is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not report_text:
            return Response(
                {'error': 'report_text is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = CTReportSerializer(data={
            'series_instance_uid': series_instance_uid,
            'report_text': report_text,
        })
        if serializer.is_valid():
            report = serializer.save()
            return Response(CTReportSerializer(report).data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
