# patients/serializers.py
from rest_framework import serializers
from .models import UserProfile
from django.contrib.auth.hashers import make_password


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
