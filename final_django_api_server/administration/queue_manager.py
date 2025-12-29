# administration/queue_manager.py
"""
RabbitMQ를 사용한 진료 대기열 관리
- 진료 대기 → 진료 중 → 진료 완료 상태 관리
"""
import pika
import json
from django.conf import settings
from datetime import datetime


class WaitingQueueManager:
    """진료 대기열 관리 클래스"""

    def __init__(self):
        # RabbitMQ 연결 설정
        self.connection = None
        self.channel = None
        self.queue_name = 'medical_waiting_queue'

    def connect(self):
        """RabbitMQ 서버 연결"""
        try:
            # RabbitMQ 연결 파라미터
            credentials = pika.PlainCredentials(
                getattr(settings, 'RABBITMQ_USER', 'guest'),
                getattr(settings, 'RABBITMQ_PASSWORD', 'guest')
            )
            parameters = pika.ConnectionParameters(
                host=getattr(settings, 'RABBITMQ_HOST', 'localhost'),
                port=getattr(settings, 'RABBITMQ_PORT', 5672),
                virtual_host=getattr(settings, 'RABBITMQ_VHOST', '/'),
                credentials=credentials
            )

            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()

            # 큐 선언 (durable=True로 영구 저장)
            self.channel.queue_declare(queue=self.queue_name, durable=True)

            return True
        except Exception as e:
            print(f"RabbitMQ 연결 실패: {e}")
            return False

    def disconnect(self):
        """RabbitMQ 연결 종료"""
        if self.connection and not self.connection.is_closed:
            self.connection.close()

    def add_to_queue(self, encounter_id, patient_id, patient_name, priority=5):
        """
        진료 대기열에 추가

        Args:
            encounter_id: 진료 기록 ID
            patient_id: 환자 ID
            patient_name: 환자 이름
            priority: 우선순위 (1-10, 낮을수록 높은 우선순위)
        """
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

            print(f"✓ 대기열 추가: {patient_name} (Encounter #{encounter_id})")
            return True

        except Exception as e:
            print(f"대기열 추가 실패: {e}")
            return False
        finally:
            self.disconnect()

    def get_next_patient(self):
        """
        다음 대기 환자 가져오기

        Returns:
            dict: 환자 정보 또는 None
        """
        if not self.connect():
            return None

        try:
            method_frame, header_frame, body = self.channel.basic_get(
                queue=self.queue_name,
                auto_ack=False
            )

            if method_frame:
                message = json.loads(body)

                # 메시지 확인 (큐에서 제거)
                self.channel.basic_ack(delivery_tag=method_frame.delivery_tag)

                print(f"✓ 다음 환자: {message['patient_name']}")
                return message
            else:
                print("대기 중인 환자가 없습니다.")
                return None

        except Exception as e:
            print(f"환자 가져오기 실패: {e}")
            return None
        finally:
            self.disconnect()

    def get_queue_length(self):
        """
        현재 대기열 길이 조회

        Returns:
            int: 대기 중인 환자 수
        """
        if not self.connect():
            return 0

        try:
            queue_state = self.channel.queue_declare(
                queue=self.queue_name,
                durable=True,
                passive=True  # 큐 상태만 확인
            )
            count = queue_state.method.message_count
            return count

        except Exception as e:
            print(f"대기열 길이 조회 실패: {e}")
            return 0
        finally:
            self.disconnect()

    def peek_queue(self, max_count=10):
        """
        대기열 미리보기 (제거하지 않고 조회)

        Args:
            max_count: 최대 조회 건수

        Returns:
            list: 대기 환자 목록
        """
        if not self.connect():
            return []

        try:
            waiting_list = []

            # 메시지를 가져오되 확인하지 않음 (다시 큐에 넣기)
            for i in range(max_count):
                method_frame, header_frame, body = self.channel.basic_get(
                    queue=self.queue_name,
                    auto_ack=False
                )

                if method_frame:
                    message = json.loads(body)
                    waiting_list.append(message)

                    # 메시지를 다시 큐에 넣기 (nack)
                    self.channel.basic_nack(
                        delivery_tag=method_frame.delivery_tag,
                        requeue=True
                    )
                else:
                    break

            return waiting_list

        except Exception as e:
            print(f"대기열 미리보기 실패: {e}")
            return []
        finally:
            self.disconnect()

    def clear_queue(self):
        """대기열 전체 삭제 (테스트용)"""
        if not self.connect():
            return False

        try:
            self.channel.queue_purge(queue=self.queue_name)
            print("✓ 대기열 초기화 완료")
            return True
        except Exception as e:
            print(f"대기열 초기화 실패: {e}")
            return False
        finally:
            self.disconnect()


# 싱글톤 인스턴스
queue_manager = WaitingQueueManager()
