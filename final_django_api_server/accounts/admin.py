from django.contrib import admin
from django import forms
from .models import Department


class DepartmentAdminForm(forms.ModelForm):
    """부서 생성/수정 폼"""

    DEPT_TYPE_CHOICES = [
        ('CLINICAL', '임상 부서'),
        ('SUPPORT', '지원 부서'),
        ('ADMIN', '관리 부서'),
    ]

    dept_type = forms.ChoiceField(
        choices=DEPT_TYPE_CHOICES,
        label='부서 유형',
        widget=forms.Select
    )

    class Meta:
        model = Department
        fields = ['dept_code', 'dept_name', 'dept_type', 'phone']


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    """부서 관리"""
    form = DepartmentAdminForm

    list_display = ('department_id', 'dept_code', 'dept_name', 'dept_type', 'phone', 'created_at')
    list_filter = ('dept_type',)
    search_fields = ('dept_code', 'dept_name')
    ordering = ('dept_code',)

    fieldsets = (
        ('기본 정보', {
            'fields': ('dept_code', 'dept_name', 'dept_type', 'phone')
        }),
    )
