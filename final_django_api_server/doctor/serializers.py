# doctor/serializers.py
from rest_framework import serializers
from .models import Doctor


class DepartmentSerializer(serializers.Serializer):
    """부서 정보 직렬화"""
    department_id = serializers.IntegerField()
    dept_name = serializers.CharField()
    dept_code = serializers.CharField()


class DoctorListSerializer(serializers.ModelSerializer):
    """의사 목록 직렬화 (원무과 접수용)"""

    department = DepartmentSerializer(read_only=True)

    class Meta:
        model = Doctor
        fields = [
            'doctor_id',
            'name',
            'license_no',
            'phone',
            'room_number',
            'department',
        ]
        read_only_fields = ['doctor_id']
