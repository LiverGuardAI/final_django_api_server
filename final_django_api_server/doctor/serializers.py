from rest_framework import serializers
from .models import Patient, Encounter, Doctor, Appointment, ScheduleDoctor
from accounts.models import Department
from datetime import datetime


class PatientSerializer(serializers.ModelSerializer):
    """환자 정보 Serializer"""
    gender_display = serializers.CharField(source='get_gender_display', read_only=True)
    current_status_display = serializers.CharField(source='get_current_status_display', read_only=True)
    # doctor_name 제거: 담당 의사는 Encounter를 통해 조회

    class Meta:
        model = Patient
        fields = '__all__'


class EncounterSerializer(serializers.ModelSerializer):
    """진료 기록 Serializer (Queue에 사용)"""
    patient = PatientSerializer(read_only=True)
    encounter_status_display = serializers.CharField(source='get_encounter_status_display', read_only=True)
    doctor_name = serializers.CharField(source='doctor.name', read_only=True)
    staff_name = serializers.CharField(source='staff.name', read_only=True)

    class Meta:
        model = Encounter
        fields = '__all__'


class UpdateEncounterStatusSerializer(serializers.Serializer):
    """Encounter 상태 변경용 Serializer"""
    encounter_status = serializers.ChoiceField(
        choices=Encounter.EncounterStatus.choices,
        required=True
    )
    encounter_start = serializers.TimeField(required=False, allow_null=True)
    encounter_end = serializers.TimeField(required=False, allow_null=True)


class DepartmentSerializer(serializers.ModelSerializer):
    """부서 정보 Serializer"""
    class Meta:
        model = Department
        fields = ['dept_id', 'dept_name', 'description']


class DoctorListSerializer(serializers.ModelSerializer):
    """의사 목록 Serializer (원무과 접수용)"""
    department = DepartmentSerializer(read_only=True)

    class Meta:
        model = Doctor
        fields = [
            'doctor_id',
            'name',
            'employee_no',
            'department',
            'room_number',
            'phone',
        ]
