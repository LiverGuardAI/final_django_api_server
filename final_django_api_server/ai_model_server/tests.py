
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch

class AIModelServerTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    @patch('requests.post')
    def test_create_segmentation_task(self, mock_post):
        """Segmentation 작업 생성 API 테스트"""
        # Mock 응답 설정
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"task_id": "test-task-123"}
        
        url = '/api/ai/segmentation/create/' # URL 설정에 맞게 수정 필요
        data = {"series_id": "test-series-uuid"}
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertIn('task_id', response.data)

    def test_clinical_vector_validation(self):
        """임상 데이터 벡터 유효성 검증 테스트"""
        from .feature_mapping import validate_clinical_vector
        
        # 정상 데이터 (9개)
        valid_vector = [60, 1, 2, 0, 1, 10.5, 3.5, 1.2, 250]
        is_valid, error = validate_clinical_vector(valid_vector)
        self.assertTrue(is_valid)
        
        # 잘못된 데이터 (길이 부족 등)
        invalid_vector = [60, 1]
        is_valid, error = validate_clinical_vector(invalid_vector)
        self.assertFalse(is_valid)

    @patch('requests.post')
    def test_predict_all_synchronous(self, mock_post):
        """전체 예측 동기 API 테스트 (현재 views.py 로직)"""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "stage": "I", "relapse": 0.2, "survival": {"risk": 0.1}
        }
        
        url = '/api/ai/predict/all/'
        payload = {
            "clinical": [0]*9,
            "mrna": [0]*20,
            "ct": [0]*512
        }
        
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, 200)