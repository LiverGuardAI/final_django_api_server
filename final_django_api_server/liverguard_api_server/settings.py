"""
Django settings for liverguard_api_server project.
"""

from pathlib import Path
import os
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env.local
load_dotenv(os.path.join(BASE_DIR.parent, '.env.local'))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-kh(mfpuldkd&5r9^!_$9lh02df7-ky017#&&$wi0_d-3l518ok'

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
        'NAME': os.environ.get('POSTGRES_DB', 'liverguard_db'),
        'USER': os.environ.get('POSTGRES_USER', 'postgres'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', 'postgres1234'),
        'HOST': os.environ.get('POSTGRES_HOST', '34.67.62.238'),
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
        'OPTIONS': {
            'options': '-c timezone=Asia/Seoul'
        },
    }
}

# ------------------------------------------------------------------------------
# Redis Configuration
# ------------------------------------------------------------------------------
REDIS_HOST = os.environ.get('REDIS_HOST', 'redis')  # 기본값 redis로 변경
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
REDIS_DB = int(os.environ.get('REDIS_DB', 0))

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(REDIS_HOST, REDIS_PORT)],
        },
    },
}

# ------------------------------------------------------------------------------
# RabbitMQ Configuration (진료 대기열 관리)
# 403 에러 방지를 위해 User/Pass를 명확히 환경변수에서 가져오고 기본값 설정
# ------------------------------------------------------------------------------
RABBITMQ_HOST = os.environ.get('RABBITMQ_HOST', 'rabbitmq') # 기본값 rabbitmq로 변경
RABBITMQ_PORT = int(os.environ.get('RABBITMQ_PORT', 5672))
RABBITMQ_USER = os.environ.get('RABBITMQ_USER', 'admin')
RABBITMQ_PASSWORD = os.environ.get('RABBITMQ_PASSWORD', 'admin123')
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
    "http://34.67.62.238:5173",
    "http://34.67.62.238:3000",
    "http://localhost:5173",
    "http://localhost:3000", # 로컬 개발용 추가
]
CORS_ALLOW_CREDENTIALS = True 

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
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60), # 개발 편의를 위해 60분으로 늘림 (필요시 10분 복구)
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
BENTOML_SERVER_URL = "http://localhost:3001"

# Docker Compose 사용 시:
# BENTOML_SERVER_URL = "http://bentoml_server:3000"