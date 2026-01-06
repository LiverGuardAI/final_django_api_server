from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
import requests
import pydicom
import nibabel as nib
import numpy as np
import os
import tempfile
from django.http import FileResponse


# Orthanc 서버 설정
ORTHANC_BASE_URL = os.getenv(
    'ORTHANC_BASE_URL',
    'http://34.67.62.238/orthanc'  # 기본값 (로컬 개발용)
)

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


class OrthancSeriesListView(APIView):
    """Orthanc Series 목록 조회 API"""
    permission_classes = [AllowAny]

    def get(self, request):
        """
        모든 Series 목록 조회
        GET /series
        """
        try:
            response = requests.get(
                f'{ORTHANC_BASE_URL}/series',
                timeout=10
            )

            if response.status_code == 200:
                series_ids = response.json()

                # 각 series의 상세 정보 가져오기
                series_list = []
                for series_id in series_ids[:50]:  # 최대 50개만 가져오기
                    try:
                        series_response = requests.get(
                            f'{ORTHANC_BASE_URL}/series/{series_id}',
                            timeout=5
                        )
                        if series_response.status_code == 200:
                            series_data = series_response.json()
                            series_list.append({
                                'id': series_id,
                                'data': series_data
                            })
                    except:
                        continue

                return Response(series_list, status=status.HTTP_200_OK)
            else:
                return Response({
                    'error': 'Failed to fetch series list'
                }, status=response.status_code)

        except requests.exceptions.RequestException as e:
            return Response({
                'error': 'Failed to connect to Orthanc server',
                'details': str(e)
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class OrthancSeriesView(APIView):
    """Orthanc Series 정보 조회 API"""
    permission_classes = [AllowAny]

    def get(self, request, series_id):
        """
        특정 Series 정보 조회
        GET /series/{series_id}
        """
        try:
            response = requests.get(
                f'{ORTHANC_BASE_URL}/series/{series_id}',
                timeout=10
            )

            if response.status_code == 200:
                return Response(
                    response.json(),
                    status=status.HTTP_200_OK
                )
            else:
                return Response({
                    'error': f'Series {series_id} not found'
                }, status=response.status_code)

        except requests.exceptions.RequestException as e:
            return Response({
                'error': 'Failed to connect to Orthanc server',
                'details': str(e)
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class OrthancSeriesInstancesView(APIView):
    """Orthanc Series의 Instances 목록 조회 API"""
    permission_classes = [AllowAny]

    def get(self, request, series_id):
        """
        특정 Series의 모든 Instances 조회
        GET /series/{series_id}/instances
        """
        try:
            response = requests.get(
                f'{ORTHANC_BASE_URL}/series/{series_id}/instances',
                timeout=10
            )

            if response.status_code == 200:
                return Response(
                    response.json(),
                    status=status.HTTP_200_OK
                )
            else:
                return Response({
                    'error': f'Instances for series {series_id} not found'
                }, status=response.status_code)

        except requests.exceptions.RequestException as e:
            return Response({
                'error': 'Failed to connect to Orthanc server',
                'details': str(e)
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class OrthancInstanceFileView(APIView):
    """Orthanc Instance 파일 다운로드 API"""
    permission_classes = [AllowAny]

    def get(self, request, instance_id):
        """
        특정 Instance의 DICOM 파일 다운로드
        GET /instances/{instance_id}/file
        """
        try:
            response = requests.get(
                f'{ORTHANC_BASE_URL}/instances/{instance_id}/file',
                timeout=30
            )

            if response.status_code == 200:
                from django.http import HttpResponse
                return HttpResponse(
                    response.content,
                    content_type='application/dicom',
                    headers={
                        'Content-Disposition': f'attachment; filename="{instance_id}.dcm"'
                    }
                )
            else:
                return Response({
                    'error': f'File for instance {instance_id} not found'
                }, status=response.status_code)

        except requests.exceptions.RequestException as e:
            return Response({
                'error': 'Failed to connect to Orthanc server',
                'details': str(e)
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class OrthancSeriesArchiveView(APIView):
    """Orthanc Series ZIP Archive 다운로드 API"""
    permission_classes = [AllowAny]

    def get(self, request, series_id):
        """
        특정 Series의 모든 DICOM 파일을 ZIP으로 다운로드
        GET /series/{series_id}/archive
        """
        try:
            response = requests.get(
                f'{ORTHANC_BASE_URL}/series/{series_id}/archive',
                timeout=60,
                stream=True
            )

            if response.status_code == 200:
                from django.http import HttpResponse
                return HttpResponse(
                    response.content,
                    content_type='application/zip',
                    headers={
                        'Content-Disposition': f'attachment; filename="series_{series_id}.zip"'
                    }
                )
            else:
                return Response({
                    'error': f'Archive for series {series_id} not found'
                }, status=response.status_code)

        except requests.exceptions.RequestException as e:
            return Response({
                'error': 'Failed to connect to Orthanc server',
                'details': str(e)
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class OrthancPatientStudiesView(APIView):
    """특정 환자의 Studies 목록 조회 API"""
    permission_classes = [AllowAny]

    def get(self, request, patient_id):
        """
        특정 환자의 모든 Studies 조회
        GET /orthanc/patients/{patient_id}/studies/
        """
        try:
            # PatientID로 환자 검색
            search_response = requests.post(
                f'{ORTHANC_BASE_URL}/tools/find',
                json={
                    "Level": "Patient",
                    "Query": {
                        "PatientID": patient_id
                    }
                },
                timeout=10
            )

            if search_response.status_code != 200:
                return Response({
                    'error': 'Failed to search for patient'
                }, status=search_response.status_code)

            patient_uuids = search_response.json()
            if not patient_uuids:
                return Response({
                    'error': f'Patient {patient_id} not found'
                }, status=status.HTTP_404_NOT_FOUND)

            # 첫 번째 매칭되는 환자의 정보 가져오기
            patient_uuid = patient_uuids[0]
            patient_response = requests.get(
                f'{ORTHANC_BASE_URL}/patients/{patient_uuid}',
                timeout=10
            )

            if patient_response.status_code != 200:
                return Response({
                    'error': f'Patient {patient_id} not found'
                }, status=patient_response.status_code)

            patient_data = patient_response.json()
            study_ids = patient_data.get('Studies', [])

            # 각 Study의 상세 정보 가져오기
            studies = []
            for study_id in study_ids:
                try:
                    study_response = requests.get(
                        f'{ORTHANC_BASE_URL}/studies/{study_id}',
                        timeout=5
                    )
                    if study_response.status_code == 200:
                        study_data = study_response.json()
                        studies.append({
                            'ID': study_id,
                            'PatientID': study_data.get('PatientMainDicomTags', {}).get('PatientID', ''),
                            'StudyDate': study_data.get('MainDicomTags', {}).get('StudyDate', ''),
                            'StudyDescription': study_data.get('MainDicomTags', {}).get('StudyDescription', ''),
                            'StudyInstanceUID': study_data.get('MainDicomTags', {}).get('StudyInstanceUID', ''),
                        })
                except:
                    continue

            return Response(studies, status=status.HTTP_200_OK)

        except requests.exceptions.RequestException as e:
            return Response({
                'error': 'Failed to connect to Orthanc server',
                'details': str(e)
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class OrthancStudySeriesView(APIView):
    """특정 Study의 Series 목록 조회 API"""
    permission_classes = [AllowAny]

    def get(self, request, study_id):
        """
        특정 Study의 모든 Series 조회
        GET /orthanc/studies/{study_id}/series/
        """
        try:
            # 먼저 Study 정보 조회
            study_response = requests.get(
                f'{ORTHANC_BASE_URL}/studies/{study_id}',
                timeout=10
            )

            if study_response.status_code != 200:
                return Response({
                    'error': f'Study {study_id} not found'
                }, status=study_response.status_code)

            study_data = study_response.json()
            series_ids = study_data.get('Series', [])

            # 각 Series의 상세 정보 가져오기
            series_list = []
            for series_id in series_ids:
                try:
                    series_response = requests.get(
                        f'{ORTHANC_BASE_URL}/series/{series_id}',
                        timeout=5
                    )
                    if series_response.status_code == 200:
                        series_data = series_response.json()
                        modality = series_data.get('MainDicomTags', {}).get('Modality', '')

                        series_info = {
                            'ID': series_id,
                            'SeriesNumber': series_data.get('MainDicomTags', {}).get('SeriesNumber', ''),
                            'Modality': modality,
                            'SeriesDescription': series_data.get('MainDicomTags', {}).get('SeriesDescription', ''),
                            'SeriesInstanceUID': series_data.get('MainDicomTags', {}).get('SeriesInstanceUID', ''),
                        }

                        # SEG인 경우 참조하는 시리즈 정보 추출
                        if modality == 'SEG':
                            try:
                                # 첫 번째 인스턴스의 태그 가져오기
                                instances = series_data.get('Instances', [])
                                if instances:
                                    instance_id = instances[0]
                                    tags_response = requests.get(
                                        f'{ORTHANC_BASE_URL}/instances/{instance_id}/tags?simplify',
                                        timeout=5
                                    )
                                    if tags_response.status_code == 200:
                                        tags = tags_response.json()
                                        # ReferencedSeriesSequence에서 참조하는 시리즈 찾기
                                        ref_series_seq = tags.get('ReferencedSeriesSequence', [])
                                        if ref_series_seq and len(ref_series_seq) > 0:
                                            series_info['ReferencedSeriesInstanceUID'] = ref_series_seq[0].get('SeriesInstanceUID', '')
                            except:
                                pass

                        series_list.append(series_info)
                except:
                    continue

            return Response(series_list, status=status.HTTP_200_OK)

        except requests.exceptions.RequestException as e:
            return Response({
                'error': 'Failed to connect to Orthanc server',
                'details': str(e)
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class OrthancSeriesNiftiView(APIView):
    """SEG DICOM Series를 NIfTI 형식으로 변환하는 API"""
    permission_classes = [AllowAny]

    def get(self, request, series_id):
        """
        SEG Series를 NIfTI로 변환하여 다운로드
        GET /orthanc/series/{series_id}/nifti/
        """
        try:
            # Step 1: Series의 모든 instances 가져오기
            instances_response = requests.get(
                f'{ORTHANC_BASE_URL}/series/{series_id}/instances',
                timeout=10
            )

            if instances_response.status_code != 200:
                return Response({
                    'error': f'Failed to fetch instances for series {series_id}'
                }, status=instances_response.status_code)

            instances = instances_response.json()

            if not instances:
                return Response({
                    'error': 'No instances found in series'
                }, status=status.HTTP_404_NOT_FOUND)

            # Step 2: 각 instance 다운로드 및 정렬
            dicom_slices = []
            for instance_data in instances:
                instance_id = instance_data.get('ID')

                # DICOM 파일 다운로드
                file_response = requests.get(
                    f'{ORTHANC_BASE_URL}/instances/{instance_id}/file',
                    timeout=30
                )

                if file_response.status_code == 200:
                    # pydicom으로 파일 읽기
                    dcm = pydicom.dcmread(pydicom.filebase.DicomBytesIO(file_response.content))
                    dicom_slices.append(dcm)

            if not dicom_slices:
                return Response({
                    'error': 'Failed to load DICOM instances'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Step 3: InstanceNumber로 정렬
            dicom_slices.sort(key=lambda x: int(x.InstanceNumber) if hasattr(x, 'InstanceNumber') else 0)

            # Step 4: 3D 볼륨 구성
            # 첫 번째 슬라이스에서 메타데이터 추출
            first_slice = dicom_slices[0]

            # 픽셀 데이터 추출
            pixel_arrays = []
            for dcm in dicom_slices:
                pixel_array = dcm.pixel_array
                pixel_arrays.append(pixel_array)

            # 3D 볼륨 생성 (depth, height, width)
            volume_3d = np.stack(pixel_arrays, axis=0)

            # Step 5: Spacing 정보 추출
            try:
                # Pixel Spacing (row, column)
                if hasattr(first_slice, 'PixelSpacing'):
                    pixel_spacing = first_slice.PixelSpacing
                    spacing_x = float(pixel_spacing[1])  # Column spacing
                    spacing_y = float(pixel_spacing[0])  # Row spacing
                else:
                    spacing_x = 1.0
                    spacing_y = 1.0

                # Slice Thickness
                if hasattr(first_slice, 'SliceThickness'):
                    spacing_z = float(first_slice.SliceThickness)
                else:
                    # 두 개 이상의 슬라이스가 있으면 ImagePositionPatient로 계산
                    if len(dicom_slices) > 1 and hasattr(first_slice, 'ImagePositionPatient'):
                        second_slice = dicom_slices[1]
                        if hasattr(second_slice, 'ImagePositionPatient'):
                            pos1 = np.array(first_slice.ImagePositionPatient)
                            pos2 = np.array(second_slice.ImagePositionPatient)
                            spacing_z = float(np.linalg.norm(pos2 - pos1))
                        else:
                            spacing_z = 1.0
                    else:
                        spacing_z = 1.0

            except Exception as e:
                print(f"Warning: Could not extract spacing info: {e}")
                spacing_x = 1.0
                spacing_y = 1.0
                spacing_z = 1.0

            # Step 6: NIfTI 이미지 생성
            # nibabel은 (x, y, z) 순서를 사용하므로 transpose 필요
            # DICOM은 (z, y, x) 순서
            volume_nifti = np.transpose(volume_3d, (2, 1, 0))

            # Affine 매트릭스 생성 (spacing 정보 포함)
            affine = np.eye(4)
            affine[0, 0] = spacing_x
            affine[1, 1] = spacing_y
            affine[2, 2] = spacing_z

            # NIfTI 이미지 생성
            nifti_img = nib.Nifti1Image(volume_nifti, affine)

            # Step 7: 임시 파일에 저장
            temp_dir = tempfile.mkdtemp()
            nifti_path = os.path.join(temp_dir, f'{series_id}.nii.gz')
            nib.save(nifti_img, nifti_path)

            # Step 8: 파일 응답 반환
            response = FileResponse(
                open(nifti_path, 'rb'),
                content_type='application/gzip',
                as_attachment=True,
                filename=f'{series_id}.nii.gz'
            )

            # 응답 후 임시 파일 정리를 위한 콜백 설정
            def cleanup():
                try:
                    if os.path.exists(nifti_path):
                        os.remove(nifti_path)
                    if os.path.exists(temp_dir):
                        os.rmdir(temp_dir)
                except:
                    pass

            response.close = cleanup

            return response

        except requests.exceptions.RequestException as e:
            return Response({
                'error': 'Failed to connect to Orthanc server',
                'details': str(e)
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            return Response({
                'error': 'Failed to convert to NIfTI',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)