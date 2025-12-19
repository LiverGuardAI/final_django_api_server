# accounts/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser


class CustomUser(AbstractUser):
    """통합 사용자 계정 - auth_user 테이블"""
    
    ROLE_CHOICES = [
        ('patient', '환자'),
        ('doctor', '의사'),
        ('radiologist', '영상의학과'),
        ('clerk', '원무과'),
    ]
    
    # Primary Key를 user_id로 변경
    id = None  # AbstractUser의 기본 id 제거
    user_id = models.AutoField(primary_key=True)
    
    # AbstractUser 기본 필드: username, password, email, first_name, last_name
    # is_staff, is_active, is_superuser, last_login, date_joined
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    
    class Meta:
        db_table = 'auth_user'
        verbose_name = '사용자'
        verbose_name_plural = '사용자'
    
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"


class Department(models.Model):
    """부서"""
    
    DEPT_TYPE_CHOICES = [
        ('CLINICAL', '진료과'), # 소화기내과, 순환기내과 등
        ('SUPPORT', '진료지원부서'), # 영상의학과, 병리과, 검사의학과 등
        ('ADMIN', '행정부서'), # 외래원무과, 입원원무과, 총무과 등
    ]
    
    department_id = models.AutoField(primary_key=True)
    dept_code = models.CharField(max_length=20, unique=True)
    dept_name = models.CharField(max_length=100)
    dept_type = models.CharField(max_length=20, choices=DEPT_TYPE_CHOICES)
    phone = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'departments'
        verbose_name = '부서'
        verbose_name_plural = '부서'
    
    def __str__(self):
        return f"{self.dept_name} ({self.dept_code})"


class OnlineStatus(models.Model):
    """근무 상태"""
    
    WORK_ROLE_CHOICES = [
        ('DOCTOR', '의사'),
        ('RADIOLOGIST', '영상의학과'),
        ('CLERK', '원무과'),
    ]
    
    online_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, db_column='user_id')
    work_role = models.CharField(max_length=20, choices=WORK_ROLE_CHOICES)
    is_online = models.BooleanField(default=False)
    last_active = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'hospital"."online_status'
        verbose_name = '근무 상태'
        verbose_name_plural = '근무 상태'
    
    def __str__(self):
        return f"{self.user.username} - {'온라인' if self.is_online else '오프라인'}"


class DutySchedule(models.Model):
    """근무 일정"""
    
    STATUS_CHOICES = [
        ('CONFIRMED', '확정'),
        ('CANCELLED', '취소'),
    ]
    
    schedule_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    work_role = models.CharField(max_length=20)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    shift_type = models.CharField(max_length=10, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    schedule_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='CONFIRMED')
    
    class Meta:
        db_table = 'hospital"."duty_schedules'
        verbose_name = '근무 일정'
        verbose_name_plural = '근무 일정'
        ordering = ['-start_time']
    
    def __str__(self):
        return f"{self.user.username} - {self.start_time.date()}"