# accounts/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from .fields import UserRoleField, DeptTypeField, WorkRoleField, DutyStatusField


class CustomUser(AbstractUser):
    """통합 사용자 계정 - auth_user 테이블"""

    class UserRole(models.TextChoices):
        PATIENT = 'PATIENT', '환자'
        DOCTOR = 'DOCTOR', '의사'
        RADIOLOGIST = 'RADIOLOGIST', '영상의학과'
        CLERK = 'CLERK', '원무과'

    # Primary Key를 user_id로 변경
    id = None  # AbstractUser의 기본 id 제거
    user_id = models.AutoField(primary_key=True)

    # AbstractUser 기본 필드: username, password, email, first_name, last_name
    # is_staff, is_active, is_superuser, last_login, date_joined
    role = UserRoleField(choices=UserRole.choices, null=True, blank=True)
    
    class Meta:
        db_table = 'auth_user'
        verbose_name = '사용자'
        verbose_name_plural = '사용자'
    
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"


# accounts/models.py

class Department(models.Model):
    """부서"""

    # Admin 화면에 보여질 선택지 정의 (DB ENUM 값과 스펠링 일치해야 함)
    class DeptType(models.TextChoices):
        CLINICAL = 'CLINICAL', '임상 부서'
        SUPPORT = 'SUPPORT', '지원 부서'
        ADMIN = 'ADMIN', '관리 부서'

    department_id = models.AutoField(primary_key=True)
    dept_code = models.CharField(max_length=20, unique=True)
    dept_name = models.CharField(max_length=100)
    
    # DB는 ENUM을 쓰고, Admin 화면은 이 choices를 보고 드롭다운을 그림
    dept_type = DeptTypeField(choices=DeptType.choices) 
    
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

    class WorkRole(models.TextChoices):
        DOCTOR = 'DOCTOR', '의사'
        RADIOLOGIST = 'RADIOLOGIST', '영상의학과'
        CLERK = 'CLERK', '원무과'

    online_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, db_column='user_id')
    work_role = WorkRoleField(choices=WorkRole.choices)
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

    class DutyStatus(models.TextChoices):
        CONFIRMED = 'CONFIRMED', '확정'
        PENDING = 'PENDING', '대기'
        CANCELLED = 'CANCELLED', '취소'

    schedule_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    work_role = WorkRoleField(choices=OnlineStatus.WorkRole.choices)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    shift_type = models.CharField(max_length=10, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    schedule_status = DutyStatusField(choices=DutyStatus.choices, default='CONFIRMED')
    
    class Meta:
        db_table = 'hospital"."duty_schedules'
        verbose_name = '근무 일정'
        verbose_name_plural = '근무 일정'
        ordering = ['-start_time']
    
    def __str__(self):
        return f"{self.user.username} - {self.start_time.date()}"