from django.contrib import admin
from django import forms
from .models import Doctor
from accounts.models import CustomUser, Department


class DoctorAdminForm(forms.ModelForm):
    """의사 계정 생성 폼"""

    class Meta:
        model = Doctor
        fields = ['employee_no', 'name', 'license_no', 'phone', 'room_number', 'department']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 부서를 드롭다운으로 표시
        self.fields['department'].queryset = Department.objects.all()
        self.fields['department'].label_from_instance = lambda obj: f"{obj.dept_name} ({obj.dept_code})"

    def save(self, commit=True):
        doctor = super().save(commit=False)

        # 신규 생성인 경우에만 CustomUser 생성
        if not doctor.pk:
            # CustomUser 생성 - username은 employee_no, password는 employee_no로 초기화
            user = CustomUser.objects.create_user(
                username=self.cleaned_data['employee_no'],
                password=self.cleaned_data['employee_no'],  # 초기 비밀번호는 사번과 동일
                role='doctor'  # ENUM 값: patient, doctor, radiologist, clerk
            )
            doctor.user = user

        if commit:
            doctor.save()

        return doctor


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    """의사 관리"""
    form = DoctorAdminForm

    list_display = ('doctor_id', 'employee_no', 'name', 'department', 'license_no',
                    'phone', 'room_number', 'created_at')
    list_filter = ('department', 'created_at')
    search_fields = ('employee_no', 'name', 'license_no', 'user__username')
    ordering = ('-created_at',)

    # 목록에서는 user 필드 제외
    list_display_links = ('doctor_id', 'name')

    fieldsets = (
        ('의사 정보', {
            'fields': ('employee_no', 'name', 'license_no', 'phone', 'room_number')
        }),
        ('소속', {
            'fields': ('department',)
        }),
    )

    def get_fieldsets(self, request, obj=None):
        """수정 시에는 계정 정보 필드 숨김"""
        if obj:  # 수정 모드
            return (
                ('의사 정보', {
                    'fields': ('employee_no', 'name', 'license_no', 'phone', 'room_number')
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


