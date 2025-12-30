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
            'phone',
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
            'gender',
            'phone',
            'sample_id',
        ]

    def validate_patient_id(self, value):
        """patient_id 중복 체크"""
        if Patient.objects.filter(patient_id=value).exists():
            raise serializers.ValidationError("이미 존재하는 환자 ID입니다.")
        return value

    def validate_gender(self, value):
        """성별 유효성 검사"""
        if value and value not in ['M', 'F']:
            raise serializers.ValidationError("성별은 'M' 또는 'F'만 가능합니다.")
        return value

    def create(self, validated_data):
        """환자 생성 - 기본 상태는 REGISTERED, 나이 자동 계산"""
        validated_data['current_status'] = 'REGISTERED'

        # 생년월일로부터 나이 자동 계산
        if validated_data.get('date_of_birth'):
            from datetime import date
            birth_date = validated_data['date_of_birth']
            today = date.today()
            age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
            validated_data['age'] = age

        return super().create(validated_data)


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
