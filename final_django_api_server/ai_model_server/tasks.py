from celery import shared_task
import requests
import os
import msgpack


def _get_series_instance_uid(orthanc_base_url, orthanc_series_id):
    if not orthanc_series_id:
        return None
    try:
        response = requests.get(
            f"{orthanc_base_url}/series/{orthanc_series_id}",
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
    mosec_url = os.getenv('MOSEC_BASE_URL', 'http://host.docker.internal:8001')
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

            orthanc_url = os.getenv('ORTHANC_BASE_URL', 'http://34.67.62.238/orthanc')
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
    mosec_url = os.getenv('MOSEC_FEATURE_BASE_URL', 'http://host.docker.internal:8002')
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
