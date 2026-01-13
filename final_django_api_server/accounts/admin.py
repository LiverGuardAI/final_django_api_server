from django.contrib import admin
from .models import Department, CustomUser


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    """부서 관리"""

    list_display = ('department_id', 'dept_code', 'dept_name', 'dept_type', 'phone', 'created_at')
    list_filter = ('dept_type',)
    search_fields = ('dept_code', 'dept_name')
    ordering = ('dept_code',)

    # PostgreSQL ENUM을 사용하는 필드는 Django가 자동으로 처리
    # 별도의 Form 정의 불필요

    fieldsets = (
        ('기본 정보', {
            'fields': ('dept_code', 'dept_name', 'dept_type', 'phone')
        }),
    )


@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    """사용자 관리"""

    list_display = ('user_id', 'username', 'get_full_name', 'email', 'role', 'is_active', 'date_joined')
    list_filter = ('role', 'is_active', 'is_staff')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('-date_joined',)

    fieldsets = (
        ('계정 정보', {
            'fields': ('username', 'password', 'email')
        }),
        ('개인 정보', {
            'fields': ('first_name', 'last_name', 'role')
        }),
        ('권한', {
            'fields': ('is_active', 'is_staff', 'is_superuser')
        }),
    )

from .models import DutySchedule

@admin.register(DutySchedule)
class DutyScheduleAdmin(admin.ModelAdmin):
    """근무 일정 관리"""
    change_list_template = 'admin/accounts/dutyschedule/change_list.html'
    
    list_display = ('schedule_id', 'user', 'work_role', 'start_time', 'end_time', 'shift_type', 'schedule_status')
    list_filter = ('schedule_status', 'work_role', 'shift_type')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
    ordering = ('-start_time',)

