import os
from celery import Celery

# Django settings module 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'liverguard_api_server.settings')

# Celery app 생성
app = Celery('liverguard_api_server')

# Django settings를 사용하여 Celery 설정
app.config_from_object('django.conf:settings', namespace='CELERY')

# Django app들에서 task 자동 발견
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
