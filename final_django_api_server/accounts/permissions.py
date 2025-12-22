from rest_framework.permissions import BasePermission


class IsDoctor(BasePermission):
    """의사(Doctor)만 접근 가능"""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'doctor'


class IsRadiologist(BasePermission):
    """영상의학과(Radiologist)만 접근 가능"""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'radiologist'


class IsClerk(BasePermission):
    """원무과(Clerk)만 접근 가능"""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'clerk'


class IsPatient(BasePermission):
    """환자(Patient)만 접근 가능"""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'patient'


class IsDoctorOrRadiologist(BasePermission):
    """의사 또는 영상의학과만 접근 가능"""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['doctor', 'radiologist']
