# administration/queue_manager.py

import pika
import json
from django.conf import settings
from datetime import datetime

class WaitingQueueManager:
    """진료 대기열 관리 클래스 (Singleton Pattern 추천)"""

    def __init__(self):
        self.queue_name = 'medical_waiting_queue'
        self.connection = None
        self.channel = None
        # 초기화 시 바로 연결 시도하지 않음 (사용할 때 연결)

    def _get_connection_params(self):
        """설정 파일에서 RabbitMQ 연결 정보 가져오기"""
        return pika.ConnectionParameters(
            host=getattr(settings, 'RABBITMQ_HOST', 'rabbitmq'), # Docker 서비스명 기본값
            port=int(getattr(settings, 'RABBITMQ_PORT', 5672)),
            virtual_host=getattr(settings, 'RABBITMQ_VHOST', '/'),
            credentials=pika.PlainCredentials(
                getattr(settings, 'RABBITMQ_USER', 'admin'),
                getattr(settings, 'RABBITMQ_PASSWORD', 'admin123')
            ),
            # 연결 타임아웃 설정 (렉 방지)
            socket_timeout=5,
            blocked_connection_timeout=5
        )

    def connect(self):
        """RabbitMQ 연결 (연결이 살아있으면 재사용)"""
        try:
            if self.connection and not self.connection.is_closed and self.channel and self.channel.is_open:
                return True

            # 새 연결 생성
            self.connection = pika.BlockingConnection(self._get_connection_params())
            self.channel = self.connection.channel()
            self.channel.queue_declare(queue=self.queue_name, durable=True)
            return True

        except Exception as e:
            print(f"!!! RabbitMQ 연결 실패: {e}")
            self.connection = None
            self.channel = None
            return False

    def add_to_queue(self, encounter_id, patient_id, patient_name, priority=5):
        """진료 대기열에 환자 추가 (Producer)"""
        if not self.connect():
            return False

        try:
            message = {
                'encounter_id': encounter_id,
                'patient_id': patient_id,
                'patient_name': patient_name,
                'priority': priority,
                'queued_at': datetime.now().isoformat(),
                'status': 'waiting'
            }

            self.channel.basic_publish(
                exchange='',
                routing_key=self.queue_name,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # 메시지 영구 저장
                    priority=priority
                )
            )
            print(f"✓ 대기열 추가 성공: {patient_name}")
            return True

        except Exception as e:
            print(f"!!! 대기열 추가 중 에러: {e}")
            # 에러 발생 시 연결 초기화 (다음 시도 때 재연결)
            self.connection = None 
            return False

    def get_next_patient(self):
        """다음 환자 호출 (Consumer)"""
        if not self.connect():
            return None

        try:
            # basic_get은 큐에서 하나를 꺼냅니다.
            method_frame, header_frame, body = self.channel.basic_get(
                queue=self.queue_name,
                auto_ack=False
            )

            if method_frame:
                message = json.loads(body)
                # 처리 완료 도장 찍기 (큐에서 영구 삭제)
                self.channel.basic_ack(delivery_tag=method_frame.delivery_tag)
                print(f"✓ 진료실 호출: {message['patient_name']}")
                return message
            else:
                return None  # 대기 환자 없음

        except Exception as e:
            print(f"!!! 환자 호출 실패: {e}")
            self.connection = None
            return None

    def get_queue_length(self):
        """현재 대기 인원 수 조회"""
        if not self.connect():
            return 0
        try:
            res = self.channel.queue_declare(queue=self.queue_name, durable=True, passive=True)
            return res.method.message_count
        except Exception:
            return 0
            
    # 대기열 목록은 RabbitMQ로 보여주면 중복 문제가 생기므로, views.py에서 DB(Encounter)나 Redis를 조회

    def clear_queue(self):
        """테스트용: 대기열 초기화"""
        if not self.connect(): return False
        try:
            self.channel.queue_purge(queue=self.queue_name)
            return True
        except: return False

queue_manager = WaitingQueueManager()