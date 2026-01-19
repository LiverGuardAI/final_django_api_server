# patients/serializers.py
from rest_framework import serializers
from .models import UserProfile, AppSyncRequest, Allergy, DiseaseHistory
from django.contrib.auth.hashers import make_password
from doctor.models import Doctor


class SignupSerializer(serializers.ModelSerializer):
    """회원가입용 Serializer"""
    password_confirm = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = UserProfile
        fields = [
            'nickname',
            'phone_number',
            'gender',
            'birth_date',
            'user_id',
            'password',
            'password_confirm',
        ]
        extra_kwargs = {
            'password': {'write_only': True},
        }

    def validate_user_id(self, value):
        """user_id 중복 검사"""
        if UserProfile.objects.filter(user_id=value).exists():
            raise serializers.ValidationError("이미 존재하는 아이디입니다.")
        return value

    def validate(self, data):
        """비밀번호 확인 검증"""
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({
                "password_confirm": "비밀번호가 일치하지 않습니다."
            })
        return data

    def create(self, validated_data):
        """회원가입 처리 (비밀번호 해싱)"""
        validated_data.pop('password_confirm')
        validated_data['password'] = make_password(validated_data['password'])
        return super().create(validated_data)


class LoginSerializer(serializers.Serializer):
    """로그인용 Serializer"""
    user_id = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)


class AppSyncRequestSerializer(serializers.ModelSerializer):
    """앱 연동 신청 Serializer"""
    profile_nickname = serializers.CharField(source='profile.nickname', read_only=True)
    profile_phone_number = serializers.CharField(source='profile.phone_number', read_only=True)
    profile_birth_date = serializers.DateField(source='profile.birth_date', read_only=True)
    profile_gender = serializers.CharField(source='profile.gender', read_only=True)
    processed_by_name = serializers.CharField(source='processed_by.admin_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = AppSyncRequest
        fields = [
            'request_id',
            'status',
            'status_display',
            'requested_at',
            'processed_at',
            'processed_by',
            'processed_by_name',
            'profile',
            'profile_nickname',
            'profile_phone_number',
            'profile_birth_date',
            'profile_gender',
            'assigned_patient_id',
        ]
        read_only_fields = [
            'request_id',
            'requested_at',
            'processed_at',
            'processed_by',
        ]


# 진료과 목록 Serializer
class DepartmentSerializer(serializers.Serializer):
    """진료과 목록"""
    department_name = serializers.CharField()


# 의사 목록 Serializer
class DoctorListSerializer(serializers.ModelSerializer):
    """의사 목록 (앱용)"""
    specialty = serializers.CharField(source='department.dept_name', read_only=True)
    doctor_name = serializers.CharField(source='name', read_only=True)

    class Meta:
        model = Doctor
        fields = ['doctor_id', 'doctor_name', 'specialty', 'phone']


# 예약 생성 Serializer
class AppointmentCreateSerializer(serializers.Serializer):
    """당일 예약 생성 (앱용)"""
    profile_id = serializers.IntegerField(required=True)
    doctor_id = serializers.IntegerField(required=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate_profile_id(self, value):
        """프로필 검증"""
        try:
            profile = UserProfile.objects.get(profile_id=value)
            if not profile.is_verified or not profile.linked_patient_id:
                raise serializers.ValidationError("병원 연동이 필요합니다.")
            return value
        except UserProfile.DoesNotExist:
            raise serializers.ValidationError("존재하지 않는 프로필입니다.")
    
    def validate_doctor_id(self, value):
        """의사 검증"""
        if not Doctor.objects.filter(doctor_id=value).exists():
            raise serializers.ValidationError("존재하지 않는 의사입니다.")
        return value


# 알러지 Serializer
class AllergySerializer(serializers.ModelSerializer):
    """알러지 Serializer"""

    class Meta:
        model = Allergy
        fields = [
            'allergy_id',
            'allergy_type',
            'trigger_agent',
            'reaction_desc',
            'profile',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['allergy_id', 'created_at', 'updated_at']


# 기저질환 Serializer
class DiseaseHistorySerializer(serializers.ModelSerializer):
    """기저질환 Serializer"""

    class Meta:
        model = DiseaseHistory
        fields = [
            'history_id',
            'disease_code',
            'disease_name',
            'diagnosis_date',
            'severity_level',
            'is_active',
            'profile',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['history_id', 'created_at', 'updated_at']
