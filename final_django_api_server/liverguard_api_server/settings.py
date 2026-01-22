"""
Django settings for liverguard_api_server project.
"""

from pathlib import Path
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get("SECRET_KEY", "")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# [수정] Docker/GCP 환경에서 외부 접속을 허용하기 위해 전체 허용
ALLOWED_HOSTS = ['*'] 


# Application definition
INSTALLED_APPS = [
    'daphne',  # MUST be before django.contrib.staticfiles for WebSocket support
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.postgres',

    'accounts',
    'administration',
    'doctor',
    'radiology',
    'patients',
    'ai_model_server',
    'orthanc_server',
    'lis',
    'cdss_channels_redis',  # 채팅 기능
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'liverguard_api_server.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# [1] 일반 웹 요청용 (삭제 금지)
WSGI_APPLICATION = 'liverguard_api_server.wsgi.application'

# [2] 웹소켓/Channels용 (필수 추가)
ASGI_APPLICATION = 'liverguard_api_server.asgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRES_DB', ''),
        'USER': os.environ.get('POSTGRES_USER', ''),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', ''),
        'HOST': os.environ.get('POSTGRES_HOST', ''),
        'PORT': os.environ.get('POSTGRES_PORT', ''),
        'CONN_MAX_AGE': 0,
        'OPTIONS': {
            'options': '-c timezone=Asia/Seoul'
        },
    }
}

# ------------------------------------------------------------------------------
# Redis Configuration
# ------------------------------------------------------------------------------
REDIS_HOST = os.environ.get('REDIS_HOST', '')  # 기본값 redis로 변경
REDIS_PORT = int(os.environ.get('REDIS_PORT', 0))
REDIS_DB = int(os.environ.get('REDIS_DB', 0))

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(REDIS_HOST, REDIS_PORT)],
            "capacity": 1500,  # 채널당 최대 메시지 수
            "expiry": 10,  # 메시지 만료 시간(초)
        },
    },
}

# Daphne/ASGI 설정
ASGI_THREADS = 4  # ASGI 워커 스레드 수

# ------------------------------------------------------------------------------
# RabbitMQ Configuration (진료 대기열 관리)
# 403 에러 방지를 위해 User/Pass를 명확히 환경변수에서 가져오고 기본값 설정
# ------------------------------------------------------------------------------
RABBITMQ_HOST = os.environ.get('RABBITMQ_HOST', '') # 기본값 rabbitmq로 변경
RABBITMQ_PORT = int(os.environ.get('RABBITMQ_PORT', 0))
RABBITMQ_USER = os.environ.get('RABBITMQ_USER', '')
RABBITMQ_PASSWORD = os.environ.get('RABBITMQ_PASSWORD', '')
RABBITMQ_VHOST = os.environ.get('RABBITMQ_VHOST', '/')


# ------------------------------------------------------------------------------
# Celery Configuration
# RabbitMQ를 브로커로 사용하도록 URL을 명시적으로 구성합니다.
# ------------------------------------------------------------------------------
# 기존: Redis를 Broker로 사용 중이었음 -> 변경: RabbitMQ 사용 (AMQP)
CELERY_BROKER_URL = os.environ.get(
    'CELERY_BROKER_URL', 
    f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}@{RABBITMQ_HOST}:{RABBITMQ_PORT}/{RABBITMQ_VHOST.lstrip('/')}"
)

# 결과 백엔드는 Redis를 계속 사용 (속도 유리)
CELERY_RESULT_BACKEND = os.environ.get(
    'CELERY_RESULT_BACKEND', 
    f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
)

CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Seoul'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 3600  # 1 hour

# Custom user 
AUTH_USER_MODEL = 'accounts.CustomUser'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

# CORS 설정
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
    os.environ.get("AWS_IP_ADDRESS", ""),
]
CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000",
    os.environ.get("AWS_IP_ADDRESS", ""),
]

# REST Framework 설정
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

# Simple JWT 설정
from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': False,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'USER_ID_FIELD': 'user_id',
    'USER_ID_CLAIM': 'user_id',
}

# Internationalization
LANGUAGE_CODE = 'ko-kr'
TIME_ZONE = 'Asia/Seoul'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = []

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# BentoML Server URL
BENTOML_BASE_URL = os.environ.get("BENTOML_BASE_URL", "")

DATA_DIR = os.path.join(BASE_DIR, 'data')
MEDICINE_MASTER_PATH = os.path.join(DATA_DIR, 'medicine_master_v3.csv')