# administration/serializers.py
from rest_framework import serializers
from doctor.models import Patient, Appointment, Encounter


class PatientSerializer(serializers.ModelSerializer):
    """환자 정보 직렬화"""

    class Meta:
        model = Patient
        fields = [
            'patient_id',
            'name',
            'date_of_birth',
            'age',
            'gender',
            'current_status',
            'created_at',
            'updated_at',
            'sample_id',
            'doctor_id',
        ]
        read_only_fields = ['created_at', 'updated_at']


class PatientCreateSerializer(serializers.ModelSerializer):
    """환자 등록용 직렬화"""

    class Meta:
        model = Patient
        fields = [
            'patient_id',
            'name',
            'date_of_birth',
            'age',
            'gender',
            'sample_id',
            'doctor_id',
        ]


class AppointmentSerializer(serializers.ModelSerializer):
    """예약 정보 직렬화"""

    patient_name = serializers.CharField(source='patient.name', read_only=True)
    doctor_name = serializers.CharField(source='doctor.name', read_only=True)

    class Meta:
        model = Appointment
        fields = [
            'appointment_id',
            'appointment_date',
            'appointment_time',
            'appointment_type',
            'status',
            'department',
            'notes',
            'patient',
            'patient_name',
            'doctor',
            'doctor_name',
            'staff',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class AppointmentCreateSerializer(serializers.ModelSerializer):
    """예약 생성용 직렬화"""

    class Meta:
        model = Appointment
        fields = [
            'appointment_date',
            'appointment_time',
            'appointment_type',
            'status',
            'department',
            'notes',
            'patient',
            'doctor',
            'staff',
        ]


class EncounterSerializer(serializers.ModelSerializer):
    """진료 기록 직렬화"""

    patient_name = serializers.CharField(source='patient.name', read_only=True)
    doctor_name = serializers.CharField(source='doctor.name', read_only=True)

    class Meta:
        model = Encounter
        fields = [
            'encounter_id',
            'encounter_date',
            'encounter_time',
            'encounter_status',
            'department',
            'clinic_room',
            'checkin_time',
            'encounter_start',
            'encounter_end',
            'is_first_visit',
            'chief_complaint',
            'clinical_notes',
            'patient',
            'patient_name',
            'doctor',
            'doctor_name',
            'staff',
            'diagnosis_type',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class EncounterCreateSerializer(serializers.ModelSerializer):
    """진료 기록 생성용 직렬화"""

    class Meta:
        model = Encounter
        fields = [
            'encounter_date',
            'encounter_time',
            'encounter_status',
            'department',
            'clinic_room',
            'is_first_visit',
            'chief_complaint',
            'patient',
            'doctor',
            'staff',
        ]
