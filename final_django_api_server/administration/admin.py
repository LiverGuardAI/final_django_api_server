from django.contrib import admin
from django import forms
from .models import Administration
from accounts.models import CustomUser, Department


class AdministrationAdminForm(forms.ModelForm):
    """원무과 계정 생성 폼"""

    class Meta:
        model = Administration
        fields = ['employee_no', 'name', 'phone', 'department']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 부서를 드롭다운으로 표시
        self.fields['department'].queryset = Department.objects.all()
        self.fields['department'].label_from_instance = lambda obj: f"{obj.dept_name} ({obj.dept_code})"

    def save(self, commit=True):
        administration = super().save(commit=False)

        # 신규 생성인 경우에만 CustomUser 생성
        if not administration.pk:
            # CustomUser 생성 - username은 employee_no, password는 employee_no로 초기화
            user = CustomUser.objects.create_user(
                username=self.cleaned_data['employee_no'],
                password=self.cleaned_data['employee_no'],  # 초기 비밀번호는 사번과 동일
                role='clerk'  # ENUM 값: patient, doctor, radiologist, clerk
            )
            administration.user = user

        if commit:
            administration.save()

        return administration


@admin.register(Administration)
class AdministrationAdmin(admin.ModelAdmin):
    """원무과 관리"""
    form = AdministrationAdminForm

    list_display = ('staff_id', 'employee_no', 'name', 'department',
                    'phone', 'created_at')
    list_filter = ('department', 'created_at')
    search_fields = ('employee_no', 'name', 'user__username')
    ordering = ('-created_at',)

    list_display_links = ('staff_id', 'name')

    fieldsets = (
        ('원무과 정보', {
            'fields': ('employee_no', 'name', 'phone')
        }),
        ('소속', {
            'fields': ('department',)
        }),
    )

    def get_fieldsets(self, request, obj=None):
        """수정 시에는 계정 정보 필드 숨김"""
        if obj:  # 수정 모드
            return (
                ('원무과 정보', {
                    'fields': ('employee_no', 'name', 'phone')
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
