# administration/serializers.py
from rest_framework import serializers
from django.utils import timezone
from doctor.models import Patient, Appointment, Encounter, MedicalRecord, LabOrder, DoctorToRadiologyOrder
from datetime import date

# ---------------------------------------------------------
# 1. Patient Serializer (하나로 통합: 조회, 생성, 수정 모두 담당)
# ---------------------------------------------------------
class PatientSerializer(serializers.ModelSerializer):
    """환자 정보 직렬화 (조회, 등록, 수정 통합)"""
    
    # Annotate Fields
    total_visits = serializers.IntegerField(read_only=True)
    last_visit = serializers.DateTimeField(read_only=True)
    
    class Meta:
        model = Patient
        fields = '__all__'
        # staff: 뷰에서 자동 주입하므로 입력받지 않음
        # age: 생년월일 기반 자동 계산하므로 입력받지 않음
        # created_at, updated_at: 자동 생성
        # total_visits, last_visit: annotate로 생성
        read_only_fields = ['created_at', 'updated_at', 'age', 'total_visits', 'last_visit']

    # --- [유효성 검사 (Validation)] ---

    def validate_patient_id(self, value):
        """patient_id 중복 체크 (생성 시에만)"""
        # 현재 인스턴스가 없다면(=생성 요청이라면) 중복 체크
        if not self.instance:
            if Patient.objects.filter(patient_id=value).exists():
                raise serializers.ValidationError("이미 존재하는 환자 ID입니다.")
        return value

    def validate_gender(self, value):
        """성별 유효성 검사"""
        if value and value not in ['M', 'F']:
            raise serializers.ValidationError("성별은 'M' 또는 'F'만 가능합니다.")
        return value

    # --- [내부 로직 (Helper)] ---

    def _calculate_age(self, birth_date):
        """생년월일을 입력받아 만 나이를 계산하는 내부 함수"""
        if not birth_date:
            return None
        today = date.today()
        # (올해 - 태어난해) - (생일이 안 지났으면 1 빼기)
        return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

    # --- [저장 로직 (Create & Update)] ---

    def create(self, validated_data):
        """환자 생성 (POST)"""
        if 'date_of_birth' in validated_data:
            validated_data['age'] = self._calculate_age(validated_data['date_of_birth'])

        return super().create(validated_data)

    def update(self, instance, validated_data):
        """환자 정보 수정 (PATCH/PUT)"""
        # 1. 생년월일이 변경된 경우에만 나이 재계산
        if 'date_of_birth' in validated_data:
            validated_data['age'] = self._calculate_age(validated_data['date_of_birth'])
        
        return super().update(instance, validated_data)


# ---------------------------------------------------------
# 2. Appointment Serializers (기존 유지)
# ---------------------------------------------------------
class AppointmentSerializer(serializers.ModelSerializer):
    """예약 정보 조회용"""
    patient_name = serializers.CharField(source='patient.name', read_only=True)
    doctor_name = serializers.CharField(source='doctor.name', read_only=True)
    appointment_time = serializers.SerializerMethodField()
    has_encounter = serializers.SerializerMethodField()

    def get_appointment_time(self, obj):
        """시간을 HH:MM 형식으로 반환"""
        if obj.appointment_time:
            return obj.appointment_time.strftime('%H:%M')
        return None

    def get_has_encounter(self, obj):
        """해당 예약에 연결된 Encounter가 있는지 확인"""
        from doctor.models import Encounter
        return Encounter.objects.filter(appointment=obj).exists()

    class Meta:
        model = Appointment
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

class AppointmentCreateSerializer(serializers.ModelSerializer):
    """예약 생성용"""
    class Meta:
        model = Appointment
        fields = [
            'appointment_date', 'appointment_time', 'appointment_type',
            'status', 'department', 'notes', 'patient', 'doctor', 'staff',
        ]


# ---------------------------------------------------------
# 3. Encounter Serializers (방문 세션 관리)
# ---------------------------------------------------------
class EncounterSerializer(serializers.ModelSerializer):
    """방문/진료 세션 조회용"""
    patient_name = serializers.CharField(source='patient.name', read_only=True)
    patient_id = serializers.CharField(source='patient.patient_id', read_only=True)
    date_of_birth = serializers.DateField(source='patient.date_of_birth', read_only=True)
    age = serializers.IntegerField(source='patient.age', read_only=True)
    gender = serializers.CharField(source='patient.gender', read_only=True)
    phone = serializers.CharField(source='patient.phone', read_only=True)
    doctor_name = serializers.CharField(source='assigned_doctor.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    workflow_state_display = serializers.CharField(source='get_workflow_state_display', read_only=True)
    questionnaire_status = serializers.SerializerMethodField()
    questionnaire_data = serializers.SerializerMethodField()
    is_returning_patient = serializers.SerializerMethodField()
    orders_status = serializers.SerializerMethodField()
    result_waiting_label = serializers.SerializerMethodField()
    result_waiting_started_at = serializers.SerializerMethodField()
    waiting_duration_seconds = serializers.SerializerMethodField()
    
    def get_questionnaire_status(self, obj):
        if hasattr(obj, 'questionnaire'):
            return obj.questionnaire.status
        return 'NOT_STARTED'

    def get_questionnaire_data(self, obj):
        if hasattr(obj, 'questionnaire'):
            return obj.questionnaire.data
        return None

    def get_is_returning_patient(self, obj):
        """
        현재 Encounter에 진료 기록(MedicalRecord)이 연결되어 있는지 확인.
        True면 이미 의사를 만나 진료를 보고 검사를 하러 나간 '재진(추가진료)' 환자임.
        """
        return MedicalRecord.objects.filter(encounter=obj).exists()

    def get_orders_status(self, obj):
        """
        현재 Encounter에 연결된 모든 오더의 상태 요약 반환.
        """
        orders = []
        
        # 1. Lab Orders
        lab_orders = LabOrder.objects.filter(encounter=obj)
        for order in lab_orders:
            orders.append({
                'id': f'lab_{order.order_id}',
                'name': order.get_order_type_display(),
                'status': order.status,
                'status_display': order.get_status_display(),
                'type': 'LAB'
            })
            
        # 2. Imaging Orders
        img_orders = DoctorToRadiologyOrder.objects.filter(encounter=obj)
        for order in img_orders:
            orders.append({
                'id': f'img_{order.order_id}',
                'name': f"{order.modality} ({order.body_part or '전신'})",
                'status': order.status,
                'status_display': order.get_status_display(),
                'type': 'IMAGING'
            })
            
        return orders

    def get_result_waiting_label(self, obj):
        if obj.workflow_state != Encounter.WorkflowState.WAITING_RESULTS:
            return None

        labels = []

        lab_orders = LabOrder.objects.filter(encounter=obj)
        for order in lab_orders:
            label = order.get_order_type_display()
            if label and label not in labels:
                labels.append(label)

        img_orders = DoctorToRadiologyOrder.objects.filter(encounter=obj)
        for order in img_orders:
            name = f"{order.modality} ({order.body_part or 'ALL'})"
            if name not in labels:
                labels.append(name)

        if labels:
            return ' / '.join(labels)
        return None

    def get_result_waiting_started_at(self, obj):
        if obj.workflow_state == Encounter.WorkflowState.WAITING_RESULTS:
            return obj.state_entered_at
        return None

    def get_waiting_duration_seconds(self, obj):
        if obj.workflow_state == Encounter.WorkflowState.WAITING_RESULTS and obj.state_entered_at:
            return int((timezone.now() - obj.state_entered_at).total_seconds())
        return None

    class Meta:
        model = Encounter
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class EncounterCreateSerializer(serializers.ModelSerializer):
    """방문 세션 생성용 (접수 시 사용)"""
    class Meta:
        model = Encounter
        fields = [
            'patient', 'appointment', 'status', 'workflow_state',
            'current_location'
        ]


# ---------------------------------------------------------
# 4. MedicalRecord Serializers (진료 기록)
# ---------------------------------------------------------
class MedicalRecordSerializer(serializers.ModelSerializer):
    """진료 기록 조회용"""
    patient_name = serializers.CharField(source='patient.name', read_only=True)
    patient_id = serializers.CharField(source='patient.patient_id', read_only=True)
    date_of_birth = serializers.DateField(source='patient.date_of_birth', read_only=True)
    age = serializers.IntegerField(source='patient.age', read_only=True)
    gender = serializers.CharField(source='patient.gender', read_only=True)
    phone = serializers.CharField(source='patient.phone', read_only=True)
    doctor_name = serializers.CharField(source='doctor.name', read_only=True)
    questionnaire_status_display = serializers.CharField(source='get_questionnaire_status_display', read_only=True)

    class Meta:
        model = MedicalRecord
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class MedicalRecordCreateSerializer(serializers.ModelSerializer):
    """진료 기록 생성용"""
    class Meta:
        model = MedicalRecord
        fields = [
            'record_date', 'record_time', 'record_status',
            'department', 'clinic_room', 'is_first_visit', 'chief_complaint',
            'patient', 'doctor', 'staff', 'encounter',
        ]
        read_only_fields = ['staff']
