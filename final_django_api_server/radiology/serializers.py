# radiology/serializers.py
from rest_framework import serializers
from doctor.models import Patient, DoctorToRadiologyOrder, Encounter
from .models import DICOMStudy


class PatientWaitlistSerializer(serializers.ModelSerializer):
    """촬영 대기 환자 정보 시리얼라이저"""

    class Meta:
        model = Patient
        fields = [
            'patient_id',
            'sample_id',
            'name',
            'date_of_birth',
            'age',
            'gender',
            'created_at',
            'updated_at',
        ]


class EncounterWaitlistSerializer(serializers.ModelSerializer):
    """촬영 대기/촬영중 환자 정보 (Encounter 기반)"""

    patient_id = serializers.CharField(source='patient.patient_id', read_only=True)
    sample_id = serializers.CharField(source='patient.sample_id', read_only=True)
    name = serializers.CharField(source='patient.name', read_only=True)
    date_of_birth = serializers.DateField(source='patient.date_of_birth', read_only=True)
    age = serializers.IntegerField(source='patient.age', read_only=True)
    gender = serializers.CharField(source='patient.gender', read_only=True)
    current_status = serializers.SerializerMethodField()

    class Meta:
        model = Encounter
        fields = [
            'encounter_id',
            'patient_id',
            'sample_id',
            'name',
            'date_of_birth',
            'age',
            'gender',
            'workflow_state',
            'current_status',
            'state_entered_at',
        ]

    def get_current_status(self, obj):
        mapping = {
            Encounter.WorkflowState.WAITING_IMAGING: '촬영대기중',
            Encounter.WorkflowState.IN_IMAGING: '촬영중',
            Encounter.WorkflowState.COMPLETED: '촬영완료',
        }
        return mapping.get(obj.workflow_state, obj.workflow_state)


class RadiologyQueueSerializer(serializers.ModelSerializer):
    """촬영 대기열 정보 시리얼라이저 (DoctorToRadiologyOrder 기반)"""
    patient = PatientWaitlistSerializer(read_only=True)

    class Meta:
        model = DoctorToRadiologyOrder
        fields = [
            'order_id',
            'patient',
            'modality',
            'body_part',
            'scheduled_at',
            'status',
            'ordered_at',
            'study_uid',
        ]
