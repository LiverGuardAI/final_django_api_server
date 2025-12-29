from django.contrib import admin
from django import forms
from .models import Radiology
from accounts.models import CustomUser, Department


class RadiologyAdminForm(forms.ModelForm):
    """영상의학과 계정 생성 폼"""

    # 신규 생성 시에만 사용할 필드
    last_name = forms.CharField(
        max_length=50,
        required=False,
        label='성 (Last Name)',
    )
    first_name = forms.CharField(
        max_length=50,
        required=False,
        label='이름 (First Name)',
    )
    email = forms.EmailField(
        max_length=254,
        required=False,
        label='이메일',
        help_text='예: lee.sunyoung@hospital.com'
    )

    class Meta:
        model = Radiology
        fields = ['employee_no', 'name', 'date_of_birth', 'license_no', 'phone', 'department']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 부서를 드롭다운으로 표시
        self.fields['department'].queryset = Department.objects.all()
        self.fields['department'].label_from_instance = lambda obj: f"{obj.dept_name} ({obj.dept_code})"

        # 수정 모드일 때는 성/이름/이메일 필드 숨김
        if self.instance.pk:
            self.fields['last_name'].widget = forms.HiddenInput()
            self.fields['first_name'].widget = forms.HiddenInput()
            self.fields['email'].widget = forms.HiddenInput()
        else:
            # 신규 생성 시에는 성/이름 필수, 이메일은 선택
            self.fields['last_name'].required = True
            self.fields['first_name'].required = True
            self.fields['email'].required = False  # 이메일은 선택사항

    def save(self, commit=True):
        radiology = super().save(commit=False)

        # 신규 생성인 경우에만 CustomUser 생성
        if not radiology.pk:
            # 폼에서 입력받은 성/이름/이메일 사용
            last_name = self.cleaned_data.get('last_name', '')
            first_name = self.cleaned_data.get('first_name', '')
            email = self.cleaned_data.get('email', '')
            date_of_birth = self.cleaned_data.get('date_of_birth')

            # 초기 비밀번호는 생년월일(YYYYMMDD) 또는 사번
            if date_of_birth:
                initial_password = date_of_birth.strftime('%Y%m%d')
            else:
                initial_password = self.cleaned_data['employee_no']

            # CustomUser 생성 - username은 employee_no, password는 생년월일로 초기화
            user = CustomUser.objects.create_user(
                username=self.cleaned_data['employee_no'],
                password=initial_password,
                first_name=first_name,
                last_name=last_name,
                email=email,  # ✅ 이메일 추가
                role='RADIOLOGIST',
                is_staff=True,  # ✅ Admin 로그인 가능하도록
                is_active=True,  # ✅ 활성 계정
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
            'fields': ('employee_no', 'name', 'date_of_birth', 'license_no', 'phone')
        }),
        ('계정 정보 (신규 생성 시)', {
            'fields': ('last_name', 'first_name', 'email'),
            'description': '성, 이름, 이메일을 입력하세요. 이메일은 선택사항입니다. 초기 비밀번호는 생년월일(YYYYMMDD)로 설정됩니다.'
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
                    'fields': ('employee_no', 'name', 'date_of_birth', 'license_no', 'phone')
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


