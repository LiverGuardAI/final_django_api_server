"""PostgreSQL ENUM 타입을 사용하는 커스텀 필드들"""
from django.db import models


class EnumField(models.CharField):
    """PostgreSQL ENUM 타입을 사용하는 필드"""

    def __init__(self, enum_type, *args, **kwargs):
        self.enum_type = enum_type
        super().__init__(*args, **kwargs)

    def db_type(self, connection):
        return self.enum_type


# User & Authentication
class UserRoleField(EnumField):
    """User Role ENUM 필드"""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 20)
        super().__init__('user_role_type', *args, **kwargs)


class WorkRoleField(EnumField):
    """Work Role ENUM 필드"""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 20)
        super().__init__('work_role_type', *args, **kwargs)


class DeptTypeField(EnumField):
    """Department Type ENUM 필드"""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 20)
        super().__init__('dept_type', *args, **kwargs)


class DutyStatusField(EnumField):
    """Duty Status ENUM 필드"""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 20)
        super().__init__('duty_status_type', *args, **kwargs)


# Common
class GenderField(EnumField):
    """Gender ENUM 필드"""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 10)
        super().__init__('gender_type', *args, **kwargs)


class StatusField(EnumField):
    """Status ENUM 필드"""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 20)
        super().__init__('status_type', *args, **kwargs)


# AI & Analysis
class RiskGroupField(EnumField):
    """Risk Group ENUM 필드"""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 10)
        super().__init__('risk_group_type', *args, **kwargs)


# Medication
class ScheduleTypeField(EnumField):
    """Schedule Type ENUM 필드"""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 20)
        super().__init__('schedule_type', *args, **kwargs)


class MealTimingField(EnumField):
    """Meal Timing ENUM 필드"""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 20)
        super().__init__('meal_timing_type', *args, **kwargs)


class MedicationStatusField(EnumField):
    """Medication Status ENUM 필드"""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 20)
        super().__init__('medication_status_type', *args, **kwargs)


# Doctor
class DoctorScheduleTypeField(EnumField):
    """Doctor Schedule Type ENUM 필드"""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 30)
        super().__init__('doctor_schedule_type', *args, **kwargs)
