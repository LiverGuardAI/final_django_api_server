from celery import shared_task
import requests
import os


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
    mosec_url = os.getenv('MOSEC_BASE_URL', 'http://localhost:8001')
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
