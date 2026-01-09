# patients/views.py
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth.hashers import check_password

from .models import UserProfile
from .serializers import SignupSerializer, LoginSerializer


@api_view(['POST'])
@permission_classes([AllowAny])
def signup_view(request):
    """
    회원가입 API

    POST /api/patients/signup/
    {
        "nickname": "홍길동",
        "phone_number": "01012345678",
        "gender": "M",
        "birth_date": "1950-01-01",
        "user_id": "hong123",
        "password": "secure_password",
        "password_confirm": "secure_password"
    }
    """
    serializer = SignupSerializer(data=request.data)

    if serializer.is_valid():
        user_profile = serializer.save()

        # 토큰 생성 (간단한 문자열로 profile_id 사용)
        token = f"token_{user_profile.profile_id}_{user_profile.user_id}"

        return Response({
            "success": True,
            "message": "회원가입이 완료되었습니다.",
            "token": token,
            "user": {
                "profile_id": user_profile.profile_id,
                "nickname": user_profile.nickname,
                "user_id": user_profile.user_id,
            }
        }, status=status.HTTP_201_CREATED)

    return Response({
        "success": False,
        "errors": serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """
    로그인 API

    POST /api/patients/login/
    {
        "user_id": "hong123",
        "password": "secure_password"
    }
    """
    serializer = LoginSerializer(data=request.data)

    if not serializer.is_valid():
        return Response({
            "success": False,
            "message": "아이디와 비밀번호를 모두 입력해주세요."
        }, status=status.HTTP_400_BAD_REQUEST)

    user_id = serializer.validated_data['user_id']
    password = serializer.validated_data['password']

    try:
        user_profile = UserProfile.objects.get(user_id=user_id)

        # 비밀번호 확인
        if check_password(password, user_profile.password):
            # 토큰 생성
            token = f"token_{user_profile.profile_id}_{user_profile.user_id}"

            return Response({
                "success": True,
                "message": "로그인 성공",
                "token": token,
                "user": {
                    "profile_id": user_profile.profile_id,
                    "nickname": user_profile.nickname,
                    "user_id": user_profile.user_id,
                }
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                "success": False,
                "message": "비밀번호가 일치하지 않습니다."
            }, status=status.HTTP_401_UNAUTHORIZED)

    except UserProfile.DoesNotExist:
        return Response({
            "success": False,
            "message": "존재하지 않는 아이디입니다."
        }, status=status.HTTP_404_NOT_FOUND)
