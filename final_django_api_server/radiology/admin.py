from django.contrib import admin
from django import forms
from .models import Radiology
from accounts.models import CustomUser, Department


class RadiologyAdminForm(forms.ModelForm):
    """영상의학과 계정 생성 폼"""

    class Meta:
        model = Radiology
        fields = ['employee_no', 'name', 'license_no', 'phone', 'department']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 부서를 드롭다운으로 표시
        self.fields['department'].queryset = Department.objects.all()
        self.fields['department'].label_from_instance = lambda obj: f"{obj.dept_name} ({obj.dept_code})"

    def save(self, commit=True):
        radiology = super().save(commit=False)

        # 신규 생성인 경우에만 CustomUser 생성
        if not radiology.pk:
            # CustomUser 생성 - username은 employee_no, password는 employee_no로 초기화
            user = CustomUser.objects.create_user(
                username=self.cleaned_data['employee_no'],
                password=self.cleaned_data['employee_no'],  # 초기 비밀번호는 사번과 동일
                role='radiologist'  # ENUM 값: patient, doctor, radiologist, clerk
            )
            radiology.user = user

        if commit:
            radiology.save()

        return radiology


@admin.register(Radiology)
class RadiologyAdmin(admin.ModelAdmin):
    """영상의학과 관리"""
    form = RadiologyAdminForm

    list_display = ('radiologic_id', 'employee_no', 'name', 'license_no', 'department',
                    'phone', 'created_at')
    list_filter = ('department', 'created_at')
    search_fields = ('employee_no', 'license_no', 'user__username')
    ordering = ('-created_at',)

    list_display_links = ('radiologic_id', 'employee_no')

    fieldsets = (
        ('영상의학과 정보', {
            'fields': ('employee_no', 'name', 'license_no', 'phone')
        }),
        ('소속', {
            'fields': ('department',)
        }),
    )

    def get_fieldsets(self, request, obj=None):
        """수정 시 연결된 계정 표시"""
        if obj:  # 수정 모드
            return (
                ('영상의학과 정보', {
                    'fields': ('employee_no', 'name', 'license_no', 'phone')
                }),
                ('소속', {
                    'fields': ('department',)
                }),
                ('연결된 계정', {
                    'fields': ('user',),
                    'classes': ('collapse',)
                }),
            )
        return super().get_fieldsets(request, obj)

    def get_readonly_fields(self, request, obj=None):
        """수정 시 user 필드는 읽기 전용"""
        if obj:
            return ('user',)
        return ()


