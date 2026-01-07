from rest_framework import serializers
from .models import (
    Patient, Encounter, Doctor, Appointment, ScheduleDoctor,
    LabResult, ImagingOrder, HCCDiagnosis, VitalData, AnthropometricData
)
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
        fields = ['department_id', 'dept_name', 'dept_code', 'dept_type']


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


class LabResultSerializer(serializers.ModelSerializer):
    """혈액 검사 결과 Serializer"""
    patient_name = serializers.CharField(source='patient.name', read_only=True)

    class Meta:
        model = LabResult
        fields = '__all__'


class ImagingOrderSerializer(serializers.ModelSerializer):
    """영상 검사 오더 Serializer"""
    patient_name = serializers.CharField(source='patient.name', read_only=True)
    doctor_name = serializers.CharField(source='doctor.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = ImagingOrder
        fields = '__all__'


class HCCDiagnosisSerializer(serializers.ModelSerializer):
    """HCC 진단 Serializer"""
    patient_name = serializers.CharField(source='patient.name', read_only=True)

    class Meta:
        model = HCCDiagnosis
        fields = '__all__'


class VitalDataSerializer(serializers.ModelSerializer):
    """바이탈 데이터 Serializer"""
    class Meta:
        model = VitalData
        fields = '__all__'


class AnthropometricDataSerializer(serializers.ModelSerializer):
    """신체계측 데이터 Serializer"""
    class Meta:
        model = AnthropometricData
        fields = '__all__'


class EncounterDetailSerializer(serializers.ModelSerializer):
    """진료 기록 상세 Serializer (환자 정보, 바이탈, 검사 결과 포함)"""
    patient = PatientSerializer(read_only=True)
    doctor_name = serializers.CharField(source='doctor.name', read_only=True)
    staff_name = serializers.CharField(source='staff.name', read_only=True)
    encounter_status_display = serializers.CharField(source='get_encounter_status_display', read_only=True)
    questionnaire_status_display = serializers.CharField(source='get_questionnaire_status_display', read_only=True)
    diagnosis_name = serializers.CharField(source='diagnosis_type.name', read_only=True, allow_null=True)

    class Meta:
        model = Encounter
        fields = '__all__'
