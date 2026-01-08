# administration/cache_manager.py
"""
Redis를 사용한 실시간 캐싱 및 통계 관리
- 대기 인원 카운트
- 환자 상태 캐싱
- 실시간 대시보드 데이터
"""
import redis
import json
from django.conf import settings
from datetime import datetime, timedelta


class RedisCacheManager:
    """Redis 캐시 관리 클래스"""

    def __init__(self):
        # Redis 연결 설정
        self.redis_client = None
        self._connect()

    def _connect(self):
        """Redis 서버 연결"""
        try:
            self.redis_client = redis.Redis(
                host=getattr(settings, 'REDIS_HOST', 'localhost'),
                port=getattr(settings, 'REDIS_PORT', 6379),
                db=getattr(settings, 'REDIS_DB', 0),
                decode_responses=True  # 자동으로 bytes를 str로 변환
            )
            # 연결 테스트
            self.redis_client.ping()
            print("[OK] Redis connection successful")
        except Exception as e:
            print(f"[ERROR] Redis connection failed: {e}")
            self.redis_client = None

    def is_connected(self):
        """Redis 연결 상태 확인"""
        if not self.redis_client:
            return False
        try:
            self.redis_client.ping()
            return True
        except:
            return False

    # ========================================
    # 대기 인원 카운트 관리
    # ========================================

    def increment_waiting_count(self, queue_type='clinic'):
        """
        대기 인원 증가

        Args:
            queue_type: 'clinic', 'imaging', 'lab'
        """
        if not self.is_connected():
            return

        key = f'{queue_type}:waiting_count'
        self.redis_client.incr(key)

    def decrement_waiting_count(self, queue_type='clinic'):
        """대기 인원 감소"""
        if not self.is_connected():
            return

        key = f'{queue_type}:waiting_count'
        count = self.redis_client.get(key)
        if count and int(count) > 0:
            self.redis_client.decr(key)

    def get_waiting_count(self, queue_type='clinic'):
        """
        현재 대기 인원 조회

        Returns:
            int: 대기 인원 수
        """
        if not self.is_connected():
            return 0

        key = f'{queue_type}:waiting_count'
        count = self.redis_client.get(key)
        return int(count) if count else 0

    def set_waiting_count(self, count, queue_type='clinic'):
        """대기 인원 직접 설정 (초기화 또는 동기화용)"""
        if not self.is_connected():
            return

        key = f'{queue_type}:waiting_count'
        self.redis_client.set(key, count)

    # ========================================
    # 진행 중 카운트 관리
    # ========================================

    def increment_in_progress_count(self, process_type='clinic'):
        """
        진행 중 카운트 증가

        Args:
            process_type: 'clinic', 'imaging', 'lab'
        """
        if not self.is_connected():
            return

        key = f'{process_type}:in_progress_count'
        self.redis_client.incr(key)

    def decrement_in_progress_count(self, process_type='clinic'):
        """진행 중 카운트 감소"""
        if not self.is_connected():
            return

        key = f'{process_type}:in_progress_count'
        count = self.redis_client.get(key)
        if count and int(count) > 0:
            self.redis_client.decr(key)

    def get_in_progress_count(self, process_type='clinic'):
        """진행 중 카운트 조회"""
        if not self.is_connected():
            return 0

        key = f'{process_type}:in_progress_count'
        count = self.redis_client.get(key)
        return int(count) if count else 0

    # ========================================
    # 환자 상태 캐싱
    # ========================================

    def set_patient_status(self, patient_id, status, ttl=3600):
        """
        환자 상태 캐싱 (TTL 1시간)

        Args:
            patient_id: 환자 ID
            status: 환자 상태 (Patient.PatientStatus 값)
            ttl: Time To Live (초) - 기본 1시간
        """
        if not self.is_connected():
            return

        key = f'patient:{patient_id}:status'
        self.redis_client.setex(key, ttl, status)

    def get_patient_status(self, patient_id):
        """
        환자 상태 조회 (캐시에서)

        Returns:
            str: 환자 상태 또는 None
        """
        if not self.is_connected():
            return None

        key = f'patient:{patient_id}:status'
        return self.redis_client.get(key)

    def set_patient_info(self, patient_id, patient_data, ttl=3600):
        """
        환자 전체 정보 캐싱 (Hash)

        Args:
            patient_id: 환자 ID
            patient_data: dict - 환자 정보
            ttl: Time To Live (초)
        """
        if not self.is_connected():
            return

        key = f'patient:{patient_id}:info'
        # dict를 Redis Hash로 저장
        self.redis_client.hset(key, mapping=patient_data)
        self.redis_client.expire(key, ttl)

    def get_patient_info(self, patient_id):
        """
        환자 전체 정보 조회

        Returns:
            dict: 환자 정보 또는 None
        """
        if not self.is_connected():
            return None

        key = f'patient:{patient_id}:info'
        data = self.redis_client.hgetall(key)
        return data if data else None

    # ========================================
    # 대시보드 통계
    # ========================================

    def get_dashboard_stats(self):
        """
        실시간 대시보드 통계 조회

        Returns:
            dict: 전체 통계 데이터
        """
        if not self.is_connected():
            return {
                'clinic': {'waiting': 0, 'in_progress': 0},
                'imaging': {'waiting': 0, 'in_progress': 0},
                'lab': {'waiting': 0, 'in_progress': 0},
            }

        return {
            'clinic': {
                'waiting': self.get_waiting_count('clinic'),
                'in_progress': self.get_in_progress_count('clinic'),
            },
            'imaging': {
                'waiting': self.get_waiting_count('imaging'),
                'in_progress': self.get_in_progress_count('imaging'),
            },
            'lab': {
                'waiting': self.get_waiting_count('lab'),
                'in_progress': self.get_in_progress_count('lab'),
            },
        }

    def set_dashboard_cache(self, data, ttl=60):
        """
        대시보드 전체 데이터 캐싱 (1분 TTL)

        Args:
            data: dict - 대시보드 데이터
            ttl: Time To Live (초) - 기본 1분
        """
        if not self.is_connected():
            return

        key = 'dashboard:stats'
        self.redis_client.setex(key, ttl, json.dumps(data))

    def get_dashboard_cache(self):
        """대시보드 캐시 조회"""
        if not self.is_connected():
            return None

        key = 'dashboard:stats'
        data = self.redis_client.get(key)
        return json.loads(data) if data else None

    # ========================================
    # 유틸리티
    # ========================================

    def clear_all_stats(self):
        """모든 통계 초기화 (테스트용)"""
        if not self.is_connected():
            return

        # 대기/진행중 카운트 초기화
        for queue_type in ['clinic', 'imaging', 'lab']:
            self.redis_client.set(f'{queue_type}:waiting_count', 0)
            self.redis_client.set(f'{queue_type}:in_progress_count', 0)

        print("[OK] Redis stats cleared")

    def sync_counts_from_db(self):
        """
        DB에서 실제 카운트를 가져와 Redis 동기화
        (서버 재시작 시 사용)
        """
        if not self.is_connected():
            return

        from doctor.models import Encounter

        # 진료 대기
        clinic_waiting = Encounter.objects.filter(
            workflow_state=Encounter.WorkflowState.WAITING_CLINIC
        ).count()
        self.set_waiting_count(clinic_waiting, 'clinic')

        # 진료 중
        clinic_in_progress = Encounter.objects.filter(
            workflow_state=Encounter.WorkflowState.IN_CLINIC
        ).count()
        self.redis_client.set('clinic:in_progress_count', clinic_in_progress)

        # 촬영 대기
        imaging_waiting = Encounter.objects.filter(
            workflow_state=Encounter.WorkflowState.WAITING_IMAGING
        ).count()
        self.set_waiting_count(imaging_waiting, 'imaging')

        # 촬영 중
        imaging_in_progress = Encounter.objects.filter(
            workflow_state=Encounter.WorkflowState.IN_IMAGING
        ).count()
        self.redis_client.set('imaging:in_progress_count', imaging_in_progress)

        print(f"[OK] Redis synced - Clinic waiting: {clinic_waiting}, in progress: {clinic_in_progress}, "
              f"Imaging waiting: {imaging_waiting}, in progress: {imaging_in_progress}")


# 싱글톤 인스턴스
cache_manager = RedisCacheManager()
