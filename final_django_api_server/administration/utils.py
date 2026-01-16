from accounts.models import CustomUser, Notification

def send_notification_to_administration(message_type, message):
    """
    모든 원무과(CLERK) 직원에게 알림을 전송하는 함수
    DB에 Notification을 생성하면, Signals나 Consumer 로직에 의해 WebSocket 전송이 될 수 있음
    """
    try:
        # 1. 원무과 직원 찾기 (role='CLERK' 조건 확인 필요)
        admins = CustomUser.objects.filter(role=CustomUser.UserRole.CLERK, is_active=True)
        
        notifications = []
        for admin in admins:
            notifications.append(
                Notification(
                    user=admin,
                    message_type=message_type,
                    message=message
                )
            )
        
        # 2. Bulk Create (성능 최적화)
        if notifications:
            Notification.objects.bulk_create(notifications)
            
        # TODO: WebSocket 실시간 전송 로직이 Notification.save() 시그널에 없다면 
        # views.py의 send_notification 처럼 채널 레이어 호출이 필요할 수 있음.
        # 기존 accounts/views.py 로직을 보면 create 후 별도 호출이 없어 보임 (확인 필요) 혹은 
        # 클라이언트가 주기적으로 polling하거나, Consumer에서 Notification 모델 감지 로직이 있을 수 있음.
        # 일단 모델 생성까지 구현.

    except Exception as e:
        print(f"Failed to send notification to administration: {e}")
