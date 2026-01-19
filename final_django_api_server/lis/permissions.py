from rest_framework import permissions

class IsLisStaff(permissions.BasePermission):
    """
    진단검사의학과 직원 권한 (role='LIS')
    """

    def has_permission(self, request, view):
        # 1. 로그인 여부 확인
        if not request.user or not request.user.is_authenticated:
            return False
            
        # 2. 역할 확인
        return request.user.role == 'LIS'
