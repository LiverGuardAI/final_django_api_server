# radiology/serializers.py
from rest_framework import serializers
from doctor.models import Patient
from .models import RadiologyPatientQueue, DICOMStudy


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
            'current_status',
            'created_at',
            'updated_at',
        ]


class RadiologyQueueSerializer(serializers.ModelSerializer):
    """촬영 대기열 정보 시리얼라이저"""
    patient = PatientWaitlistSerializer(read_only=True)

    class Meta:
        model = RadiologyPatientQueue
        fields = [
            'rqueue_id',
            'patient',
            'modality',
            'body_part',
            'scheduled_at',
            'acquired_at',
            'status',
            'created_at',
            'completed_at',
            'sample_id',
        ]