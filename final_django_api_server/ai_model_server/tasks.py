from celery import shared_task
import requests
import os
import msgpack


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

        # Send request to Mosec server
        response = requests.post(
            endpoint,
            json={'series_id': series_id},
            headers={'Content-Type': 'application/json'},
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

    try:
        self.update_state(
            state='PROGRESS',
            meta={
                'step': 'Sending request to AI server',
                'seriesinstanceuid': series_instance_uid,
                'progress': 10
            }
        )

        packed_data = msgpack.packb({'seriesinstanceuid': series_instance_uid}, use_bin_type=True)
        response = requests.post(
            endpoint,
            data=packed_data,
            headers={'Content-Type': 'application/msgpack'},
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
