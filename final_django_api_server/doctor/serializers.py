from rest_framework import serializers
from .models import (
    Patient, Encounter, MedicalRecord, Doctor, Appointment, ScheduleDoctor,
    LabResult, DoctorToRadiologyOrder, HCCDiagnosis, VitalData, AnthropometricData, Questionnaire, LabOrder
)
from accounts.models import Department
from datetime import datetime


class PatientSerializer(serializers.ModelSerializer):
    """환자 정보 Serializer"""
    gender_display = serializers.CharField(source='get_gender_display', read_only=True)

    class Meta:
        model = Patient
        fields = '__all__'


class QuestionnaireSerializer(serializers.ModelSerializer):
    """문진표 Serializer"""
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Questionnaire
        fields = ['questionnaire_id', 'status', 'status_display', 'data', 'created_at', 'updated_at']


class EncounterSerializer(serializers.ModelSerializer):
    """방문/진료 세션 Serializer (대기열 관리용)"""
    patient = PatientSerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    workflow_state_display = serializers.CharField(source='get_workflow_state_display', read_only=True)
    patient_name = serializers.CharField(source='patient.name', read_only=True)
    questionnaire = QuestionnaireSerializer(read_only=True)  # 문진표 데이터 포함

    class Meta:
        model = Encounter
        fields = '__all__'


class MedicalRecordSerializer(serializers.ModelSerializer):
    """진료 기록 Serializer"""
    patient = PatientSerializer(read_only=True)
    record_status_display = serializers.CharField(source='get_record_status_display', read_only=True)
    doctor_name = serializers.CharField(source='doctor.name', read_only=True)
    staff_name = serializers.CharField(source='staff.name', read_only=True)

    class Meta:
        model = MedicalRecord
        fields = '__all__'


class UpdateEncounterStatusSerializer(serializers.Serializer):
    """Encounter 상태 변경용 Serializer"""
    # Backward compatibility: 'status' field는 실제로 workflow_state를 의미
    status = serializers.ChoiceField(
        choices=Encounter.WorkflowState.choices,
        required=False
    )
    workflow_state = serializers.ChoiceField(
        choices=Encounter.WorkflowState.choices,
        required=False
    )
    current_location = serializers.CharField(required=False, allow_null=True, allow_blank=True)


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


class DoctorToRadiologyOrderSerializer(serializers.ModelSerializer):
    """영상 검사 오더 Serializer (의사 -> 영상의학과)"""
    patient_name = serializers.CharField(source='patient.name', read_only=True)
    doctor_name = serializers.CharField(source='doctor.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = DoctorToRadiologyOrder
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


class MedicalRecordDetailSerializer(serializers.ModelSerializer):
    """진료 기록 상세 Serializer (환자 정보, 바이탈, 검사 결과 포함)"""
    patient = PatientSerializer(read_only=True)
    doctor_name = serializers.CharField(source='doctor.name', read_only=True)
    staff_name = serializers.CharField(source='staff.name', read_only=True)
    record_status_display = serializers.CharField(source='get_record_status_display', read_only=True)
    questionnaire_status_display = serializers.CharField(source='get_questionnaire_status_display', read_only=True)
    diagnosis_name = serializers.CharField(source='diagnosis_type.name', read_only=True, allow_null=True)
    questionnaire = QuestionnaireSerializer(source='encounter.questionnaire', read_only=True)

    class Meta:
        model = MedicalRecord
        fields = '__all__'


# Backward compatibility alias
EncounterDetailSerializer = MedicalRecordDetailSerializer
ImagingOrderSerializer = DoctorToRadiologyOrderSerializer


class CreateLabOrderSerializer(serializers.ModelSerializer):
    """LabOrder 생성 Serializer"""
    class Meta:
        model = LabOrder
        fields = ['patient', 'encounter', 'doctor', 'order_type', 'order_notes']



class LabOrderSerializer(serializers.ModelSerializer):
    """LabOrder 목록 조회 Serializer"""
    patient_name = serializers.CharField(source='patient.name', read_only=True)
    doctor_name = serializers.CharField(source='doctor.name', read_only=True)
    order_type_display = serializers.CharField(source='get_order_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = LabOrder
        fields = '__all__'


class CreateDoctorToRadiologyOrderSerializer(serializers.ModelSerializer):
    """영상 검사 오더 생성 Serializer"""
    class Meta:
        model = DoctorToRadiologyOrder
        fields = ['patient', 'encounter', 'doctor', 'modality', 'body_part', 'order_notes']
