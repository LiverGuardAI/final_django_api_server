"""커스텀 필드들 - Django에서 choices로 관리, DB는 VARCHAR 사용"""
from django.db import models


# PostgreSQL ENUM 대신 일반 VARCHAR를 사용
# choices는 각 모델에서 TextChoices로 정의하면 됩니다.


# User & Authentication
class UserRoleField(models.CharField):
    """User Role 필드 - DB는 VARCHAR(20)"""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 20)
        super().__init__(*args, **kwargs)


class WorkRoleField(models.CharField):
    """Work Role 필드 - DB는 VARCHAR(20)"""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 20)
        super().__init__(*args, **kwargs)


class DeptTypeField(models.CharField):
    """Department Type 필드 - DB는 VARCHAR(20)"""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 20)
        super().__init__(*args, **kwargs)


class DutyStatusField(models.CharField):
    """Duty Status 필드 - DB는 VARCHAR(20)"""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 20)
        super().__init__(*args, **kwargs)


# Common
class GenderField(models.CharField):
    """Gender 필드 - DB는 VARCHAR(10)"""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 10)
        super().__init__(*args, **kwargs)


class StatusField(models.CharField):
    """Status 필드 - DB는 VARCHAR(20)"""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 20)
        super().__init__(*args, **kwargs)


# AI & Analysis
class RiskGroupField(models.CharField):
    """Risk Group 필드 - DB는 VARCHAR(10)"""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 10)
        super().__init__(*args, **kwargs)


# Medication
class ScheduleTypeField(models.CharField):
    """Schedule Type 필드 - DB는 VARCHAR(20)"""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 20)
        super().__init__(*args, **kwargs)


class MealTimingField(models.CharField):
    """Meal Timing 필드 - DB는 VARCHAR(20)"""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 20)
        super().__init__(*args, **kwargs)


class MedicationStatusField(models.CharField):
    """Medication Status 필드 - DB는 VARCHAR(20)"""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 20)
        super().__init__(*args, **kwargs)


# Doctor
class DoctorScheduleTypeField(models.CharField):
    """Doctor Schedule Type 필드 - DB는 VARCHAR(30)"""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 30)
        super().__init__(*args, **kwargs)
