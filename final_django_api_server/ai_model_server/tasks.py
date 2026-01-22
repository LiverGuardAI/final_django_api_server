from celery import shared_task
import requests
import os
import msgpack
import numpy as np
from django.conf import settings

ORTHANC_USER_NAME = os.getenv('ORTHANC_USER_NAME', '')
ORTHANC_PASSWORD = os.getenv('ORTHANC_PASSWORD', '')
ORTHANC_AUTH = (
    (ORTHANC_USER_NAME, ORTHANC_PASSWORD)
    if ORTHANC_USER_NAME and ORTHANC_PASSWORD
    else None
)


def _convert_numpy_types(obj):
    """
    Recursively convert NumPy types to Python native types
    """
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: _convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [_convert_numpy_types(item) for item in obj]
    else:
        return obj


def _get_series_instance_uid(orthanc_base_url, orthanc_series_id):
    if not orthanc_series_id:
        return None
    try:
        response = requests.get(
            f"{orthanc_base_url}/series/{orthanc_series_id}",
            auth=ORTHANC_AUTH,
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get('MainDicomTags', {}).get('SeriesInstanceUID')
    except Exception as e:
        print(f"Failed to fetch SeriesInstanceUID for series_id={orthanc_series_id}: {str(e)}")
        return None


@shared_task(bind=True, name='ai_model_server.process_segmentation', max_retries=0)
def process_segmentation(self, series_id):
    """
    Process DICOM series segmentation using Mosec AI server

    Args:
        series_id: Orthanc series ID

    Returns:
        Segmentation result with mask series ID
    """
    # Mosec API endpoint
    mosec_url = os.getenv('MOSEC_BASE_URL', '')
    endpoint = f'{mosec_url}/ai/mosec/nnU-Net-Seg'
    USE_CLOUDFLARE_MOSEC = os.getenv("USE_CLOUDFLARE_MOSEC", "0") == "1"

    try:
        # Update task state to PROGRESS
        self.update_state(
            state='PROGRESS',
            meta={
                'step': 'Sending request to AI server',
                'series_id': series_id,
                'progress': 10
            }
        )

        headers = {
            "Content-Type": "application/json",
        }
        
        if USE_CLOUDFLARE_MOSEC:
            headers["CF-Access-Client-Id"] = os.environ["CF_ACCESS_CLIENT_ID"]
            headers["CF-Access-Client-Secret"] = os.environ["CF_ACCESS_CLIENT_SECRET"]
            
        # Send request to Mosec server
        response = requests.post(
            endpoint,
            json={'series_id': series_id},
            headers=headers,
            timeout=3600  # 1 hour timeout for AI processing
        )

        response.raise_for_status()
        result = response.json()

        # Update progress
        self.update_state(
            state='PROGRESS',
            meta={
                'step': 'AI processing completed',
                'series_id': series_id,
                'progress': 90
            }
        )

        try:
            from radiology.models import RadiologyAIRun

            orthanc_url = os.getenv('ORTHANC_BASE_URL', '')
            series_instance_uid = _get_series_instance_uid(orthanc_url, series_id)

            mask_series_uid = (
                result.get('mask_series_uid')
                or result.get('mask_seriesinstanceuid')
            )
            if not mask_series_uid:
                mask_series_id = result.get('mask_series_id')
                mask_series_uid = _get_series_instance_uid(orthanc_url, mask_series_id)

            run = (
                RadiologyAIRun.objects.filter(series__series_uid=series_instance_uid)
                .order_by('-created_at')
                .first()
            )
            if not run:
                print(f"RadiologyAIRun not found for series_instance_uid={series_instance_uid}")
            else:
                update_fields = ['status']
                run.status = RadiologyAIRun.RunStatus.COMPLETED
                if mask_series_uid:
                    run.mask_series_uid = mask_series_uid
                    update_fields.append('mask_series_uid')
                run.save(update_fields=update_fields)
        except Exception as e:
            print(f"Failed to update RadiologyAIRun after segmentation: {str(e)}")

        return {
            'status': 'success',
            'series_id': series_id,
            'result': result,
            'message': 'Segmentation completed successfully'
        }

    except Exception as e:
        # Log error but do NOT retry
        print(f"Error calling Mosec API: {str(e)}")

        return {
            'status': 'failed',
            'series_id': series_id,
            'error': str(e),
            'message': 'Segmentation failed'
        }


@shared_task(bind=True, name='ai_model_server.process_feature_extraction', max_retries=0)
def process_feature_extraction(self, series_instance_uid):
    """
    Process DICOM series feature extraction using Mosec AI server

    Args:
        series_instance_uid: DICOM SeriesInstanceUID

    Returns:
        Feature extraction result
    """
    mosec_url = os.getenv('MOSEC_FEATURE_BASE_URL', '')
    endpoint = f'{mosec_url}/inference'
    USE_CLOUDFLARE_MOSEC = os.getenv("USE_CLOUDFLARE_MOSEC", "0") == "1"

    try:
        self.update_state(
            state='PROGRESS',
            meta={
                'step': 'Sending request to AI server',
                'seriesinstanceuid': series_instance_uid,
                'progress': 10
            }
        )
        
        headers = {
            "Content-Type": "application/json",
        }
        
        if USE_CLOUDFLARE_MOSEC:
            headers["CF-Access-Client-Id"] = os.environ["CF_ACCESS_CLIENT_ID"]
            headers["CF-Access-Client-Secret"] = os.environ["CF_ACCESS_CLIENT_SECRET"]
            

        packed_data = msgpack.packb({'seriesinstanceuid': series_instance_uid}, use_bin_type=True)
        response = requests.post(
            endpoint,
            data=packed_data,
            headers=headers,
            timeout=7200
        )
        response.raise_for_status()
        result = msgpack.unpackb(response.content, raw=False)

        self.update_state(
            state='PROGRESS',
            meta={
                'step': 'AI processing completed',
                'seriesinstanceuid': series_instance_uid,
                'progress': 90
            }
        )

        try:
            from radiology.models import RadiologyAIRun
            from .models import RadioFeatureVector

            run = (
                RadiologyAIRun.objects.filter(series__series_uid=series_instance_uid)
                .select_related('series')
                .order_by('-created_at')
                .first()
            )
            if not run:
                print(f"RadiologyAIRun not found for seriesinstanceuid={series_instance_uid}")
            else:
                features = result.get('features') or result.get('feature_vector')
                if features is None:
                    print(f"Feature vector missing for seriesinstanceuid={series_instance_uid}")
                else:
                    if hasattr(features, 'tolist'):
                        features = features.tolist()
                    elif not isinstance(features, list):
                        try:
                            features = list(features)
                        except TypeError:
                            features = [features]

                    feature_dim = result.get('feature_dim')
                    if feature_dim is None:
                        feature_dim = len(features)
                    else:
                        try:
                            feature_dim = int(feature_dim)
                        except (TypeError, ValueError):
                            feature_dim = len(features)

                    RadioFeatureVector.objects.update_or_create(
                        series=run.series,
                        run=run,
                        defaults={
                            'extraction_model': result.get('model_name') or result.get('extraction_model'),
                            'model_version': result.get('model_version'),
                            'vector_dim': feature_dim,
                            'feature_vector': features,
                        },
                    )
        except Exception as e:
            print(f"Failed to save feature vector: {str(e)}")

        return {
            'status': 'success',
            'seriesinstanceuid': series_instance_uid,
            'result': result,
            'message': 'Feature extraction completed successfully'
        }

    except Exception as e:
        print(f"Error calling Mosec feature extraction API: {str(e)}")

        return {
            'status': 'failed',
            'seriesinstanceuid': series_instance_uid,
            'error': str(e),
            'message': 'Feature extraction failed'
        }


# ========================
# BentoML Prediction Tasks
# ========================

@shared_task(bind=True, name='ai_model_server.process_stage_prediction', max_retries=0)
def process_stage_prediction(self, clinical, series_uid):
    """
    Task 1: 병기 예측 (Stage Prediction)

    Args:
        clinical: Clinical features (11 dimensions)
        series_uid: DICOM SeriesInstanceUID for CT feature extraction

    Returns:
        Prediction result
    """
    from .models import RadioFeatureVector

    bentoml_url = os.getenv('BENTOML_BASE_URL', '')
    endpoint = f'{bentoml_url}/predict_stage'

    try:
        self.update_state(
            state='PROGRESS',
            meta={
                'step': 'Fetching CT feature vector',
                'series_uid': series_uid,
                'progress': 20
            }
        )

        # RadioFeatureVector에서 series_uid로 feature_vector 조회
        try:
            radio_vector = RadioFeatureVector.objects.filter(series_id=series_uid).latest('created_at')
            ct = list(radio_vector.feature_vector) if radio_vector.feature_vector is not None else []
            ct = _convert_numpy_types(ct)
        except RadioFeatureVector.DoesNotExist:
            return {
                'status': 'failed',
                'error': f'No feature vector found for series_uid: {series_uid}',
                'message': 'Feature vector not found'
            }

        if len(ct) != 512:
            return {
                'status': 'failed',
                'error': f'ct feature vector must have 512 dimensions, got {len(ct)}',
                'message': 'Invalid feature vector dimension'
            }

        self.update_state(
            state='PROGRESS',
            meta={
                'step': 'Sending request to BentoML',
                'progress': 50
            }
        )

        # BentoML API 호출
        response = requests.post(
            endpoint,
            json={
                'data': {
                    'clinical': _convert_numpy_types(clinical),
                    'ct_features': ct,
                }
            },
            timeout=30
        )
        if not response.ok:
            return {
                'status': 'failed',
                'error': f'{response.status_code} Client Error: {response.reason} for url: {endpoint}',
                'details': response.text,
                'message': 'Stage prediction failed'
            }
        result = response.json()

        # Convert NumPy types to Python native types
        result = _convert_numpy_types(result)

        self.update_state(
            state='PROGRESS',
            meta={
                'step': 'Prediction completed',
                'progress': 90
            }
        )

        return {
            'status': 'success',
            'result': result,
            'message': 'Stage prediction completed successfully'
        }

    except Exception as e:
        print(f"Error in stage prediction: {str(e)}")
        return {
            'status': 'failed',
            'error': str(e),
            'message': 'Stage prediction failed'
        }


@shared_task(bind=True, name='ai_model_server.process_relapse_prediction', max_retries=0)
def process_relapse_prediction(self, clinical, mrna, series_uid):
    """
    Task 2: 재발 예측 (Relapse Prediction)

    Args:
        clinical: Clinical features (11 dimensions)
        mrna: mRNA pathway scores (20 dimensions)
        series_uid: DICOM SeriesInstanceUID for CT feature extraction

    Returns:
        Prediction result
    """
    from .models import RadioFeatureVector

    bentoml_url = os.getenv('BENTOML_BASE_URL', '')
    endpoint = f'{bentoml_url}/predict_relapse'

    try:
        self.update_state(
            state='PROGRESS',
            meta={
                'step': 'Fetching CT feature vector',
                'series_uid': series_uid,
                'progress': 20
            }
        )

        # RadioFeatureVector에서 series_uid로 feature_vector 조회
        try:
            radio_vector = RadioFeatureVector.objects.filter(series_id=series_uid).latest('created_at')
            ct = list(radio_vector.feature_vector) if radio_vector.feature_vector is not None else []
            ct = _convert_numpy_types(ct)
        except RadioFeatureVector.DoesNotExist:
            return {
                'status': 'failed',
                'error': f'No feature vector found for series_uid: {series_uid}',
                'message': 'Feature vector not found'
            }

        if len(ct) != 512:
            return {
                'status': 'failed',
                'error': f'ct feature vector must have 512 dimensions, got {len(ct)}',
                'message': 'Invalid feature vector dimension'
            }

        self.update_state(
            state='PROGRESS',
            meta={
                'step': 'Sending request to BentoML',
                'progress': 50
            }
        )

        # BentoML API 호출
        response = requests.post(
            endpoint,
            json={
                'data': {
                    'clinical': _convert_numpy_types(clinical),
                    'mrna': _convert_numpy_types(mrna),
                    'ct_features': ct,
                }
            },
            timeout=30
        )
        if not response.ok:
            return {
                'status': 'failed',
                'error': f'{response.status_code} Client Error: {response.reason} for url: {endpoint}',
                'details': response.text,
                'message': 'Relapse prediction failed'
            }
        result = response.json()

        # Convert NumPy types to Python native types
        result = _convert_numpy_types(result)

        self.update_state(
            state='PROGRESS',
            meta={
                'step': 'Prediction completed',
                'progress': 90
            }
        )

        return {
            'status': 'success',
            'result': result,
            'message': 'Relapse prediction completed successfully'
        }

    except Exception as e:
        print(f"Error in relapse prediction: {str(e)}")
        return {
            'status': 'failed',
            'error': str(e),
            'message': 'Relapse prediction failed'
        }


@shared_task(bind=True, name='ai_model_server.process_survival_prediction', max_retries=0)
def process_survival_prediction(self, clinical, mrna, series_uid):
    """
    Task 3: 생존 분석 (Survival Analysis)

    Args:
        clinical: Clinical features (11 dimensions)
        mrna: mRNA pathway scores (20 dimensions)
        series_uid: DICOM SeriesInstanceUID for CT feature extraction

    Returns:
        Prediction result
    """
    from .models import RadioFeatureVector

    bentoml_url = os.getenv('BENTOML_BASE_URL', '')
    endpoint = f'{bentoml_url}/predict_survival'

    try:
        self.update_state(
            state='PROGRESS',
            meta={
                'step': 'Fetching CT feature vector',
                'series_uid': series_uid,
                'progress': 20
            }
        )

        # RadioFeatureVector에서 series_uid로 feature_vector 조회
        try:
            radio_vector = RadioFeatureVector.objects.filter(series_id=series_uid).latest('created_at')
            ct = list(radio_vector.feature_vector) if radio_vector.feature_vector is not None else []
            ct = _convert_numpy_types(ct)
        except RadioFeatureVector.DoesNotExist:
            return {
                'status': 'failed',
                'error': f'No feature vector found for series_uid: {series_uid}',
                'message': 'Feature vector not found'
            }

        if len(ct) != 512:
            return {
                'status': 'failed',
                'error': f'ct feature vector must have 512 dimensions, got {len(ct)}',
                'message': 'Invalid feature vector dimension'
            }

        self.update_state(
            state='PROGRESS',
            meta={
                'step': 'Sending request to BentoML',
                'progress': 50
            }
        )

        # BentoML API 호출
        response = requests.post(
            endpoint,
            json={
                'data': {
                    'clinical': _convert_numpy_types(clinical),
                    'mrna': _convert_numpy_types(mrna),
                    'ct_features': ct,
                }
            },
            timeout=30
        )
        if not response.ok:
            return {
                'status': 'failed',
                'error': f'{response.status_code} Client Error: {response.reason} for url: {endpoint}',
                'details': response.text,
                'message': 'Survival prediction failed'
            }
        result = response.json()

        # Convert NumPy types to Python native types
        result = _convert_numpy_types(result)

        self.update_state(
            state='PROGRESS',
            meta={
                'step': 'Prediction completed',
                'progress': 90
            }
        )

        return {
            'status': 'success',
            'result': result,
            'message': 'Survival prediction completed successfully'
        }

    except Exception as e:
        print(f"Error in survival prediction: {str(e)}")
        return {
            'status': 'failed',
            'error': str(e),
            'message': 'Survival prediction failed'
        }


@shared_task(bind=True, name='ai_model_server.process_all_predictions', max_retries=0)
def process_all_predictions(self, clinical, mrna, series_uid):
    """
    전체 예측 (Task 1, 2, 3)

    Args:
        clinical: Clinical features (11 dimensions)
        mrna: mRNA pathway scores (20 dimensions)
        series_uid: DICOM SeriesInstanceUID for CT feature extraction

    Returns:
        Combined prediction results
    """
    from .models import RadioFeatureVector

    bentoml_url = os.getenv('BENTOML_BASE_URL', '')
    endpoint = f'{bentoml_url}/predict'

    try:
        self.update_state(
            state='PROGRESS',
            meta={
                'step': 'Fetching CT feature vector',
                'series_uid': series_uid,
                'progress': 20
            }
        )

        # RadioFeatureVector에서 series_uid로 feature_vector 조회
        try:
            radio_vector = RadioFeatureVector.objects.filter(series_id=series_uid).latest('created_at')
            ct = list(radio_vector.feature_vector) if radio_vector.feature_vector is not None else []
            ct = _convert_numpy_types(ct)
        except RadioFeatureVector.DoesNotExist:
            return {
                'status': 'failed',
                'error': f'No feature vector found for series_uid: {series_uid}',
                'message': 'Feature vector not found'
            }

        if len(ct) != 512:
            return {
                'status': 'failed',
                'error': f'ct feature vector must have 512 dimensions, got {len(ct)}',
                'message': 'Invalid feature vector dimension'
            }

        self.update_state(
            state='PROGRESS',
            meta={
                'step': 'Sending request to BentoML',
                'progress': 50
            }
        )

        # BentoML API 호출
        response = requests.post(
            endpoint,
            json={
                'data': {
                    'clinical': _convert_numpy_types(clinical),
                    'mrna': _convert_numpy_types(mrna),
                    'ct_features': ct,
                }
            },
            timeout=60
        )
        if not response.ok:
            return {
                'status': 'failed',
                'error': f'{response.status_code} Client Error: {response.reason} for url: {endpoint}',
                'details': response.text,
                'message': 'All predictions failed'
            }
        result = response.json()

        # Convert NumPy types to Python native types
        result = _convert_numpy_types(result)

        self.update_state(
            state='PROGRESS',
            meta={
                'step': 'All predictions completed',
                'progress': 90
            }
        )

        return {
            'status': 'success',
            'result': result,
            'message': 'All predictions completed successfully'
        }

    except Exception as e:
        print(f"Error in all predictions: {str(e)}")
        return {
            'status': 'failed',
            'error': str(e),
            'message': 'Predictions failed'
        }
