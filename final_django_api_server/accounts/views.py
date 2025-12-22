from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
# 로그인 API
class LoginView(APIView):
    permission_classes = [AllowAny]  # 인증 없이 접근 가능
    
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        
        # 사용자 인증
        user = authenticate(username=username, password=password)
        
        if user is None:
            return Response(
                {'error': '아이디 또는 비밀번호가 올바르지 않습니다.'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # JWT 토큰 발급
        refresh = RefreshToken.for_user(user)
        
        # 사용자 역할 확인 (CustomUser 모델의 role 필드)
        user_role = user.role  # 'doctor', 'radiologist', 'clerk', 'patient'
        
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'id': user.id,
                'username': user.username,
                'role': user_role,
                'first_name': user.first_name,
                'last_name': user.last_name,
            }
        }, status=status.HTTP_200_OK)

# 로그아웃 API (블랙리스트 미사용 - 프론트엔드에서 토큰 삭제)
class LogoutView(APIView):
    permission_classes = [AllowAny]  # 인증 불필요

    def post(self, request):
        # 프론트엔드에서 토큰을 삭제하는 방식으로 로그아웃 처리
        return Response(
            {'message': '로그아웃 되었습니다.'},
            status=status.HTTP_200_OK
        )
