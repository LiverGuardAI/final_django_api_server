from django.db import models
from django.contrib.postgres.indexes import GinIndex
from accounts.fields import GenderField, DoctorScheduleTypeField
from .managers import PatientQuerySet, DoctorQuerySet

# doctor/models.py


class Doctor(models.Model):
    """의사"""

    doctor_id = models.AutoField(primary_key=True)
    employee_no = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    date_of_birth = models.DateField(blank=True, null=True)
    license_no = models.CharField(max_length=50)
    phone = models.CharField(max_length=20, blank=True, null=True)
    room_number = models.CharField(max_length=10, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Foreign Keys
    user = models.OneToOneField('accounts.CustomUser', on_delete=models.CASCADE)
    department = models.ForeignKey('accounts.Department', on_delete=models.RESTRICT)
    
    objects = DoctorQuerySet.as_manager()
    
    class Meta:
        db_table = 'hospital"."doctor'
        verbose_name = '의사'
        verbose_name_plural = '의사'
    
    def __str__(self):
        return f"{self.name} ({self.department.dept_name})"


class ScheduleDoctor(models.Model):
    """의사 일정"""

    class DoctorScheduleType(models.TextChoices):
        OUTPATIENT = 'OUTPATIENT', '외래'
        SURGERY = 'SURGERY', '수술'

    schedule_id = models.AutoField(primary_key=True)
    schedule_date = models.DateField()
    schedule_type = DoctorScheduleTypeField(choices=DoctorScheduleType.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    notes = models.TextField(blank=True, null=True)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='schedules')
    
    class Meta:
        db_table = 'hospital"."schedule_doctor'
        verbose_name = '의사 일정'
        verbose_name_plural = '의사 일정'
        ordering = ['-schedule_date']
    
    def __str__(self):
        return f"{self.doctor.name} - {self.schedule_date} ({self.get_schedule_type_display()})"
    

class Patient(models.Model):
    """진단받는 환자"""

    class Gender(models.TextChoices):
        M = 'M', '남성'
        F = 'F', '여성'

    patient_id = models.CharField(max_length=50, primary_key=True)
    name = models.CharField(max_length=100)
    date_of_birth = models.DateField(blank=True, null=True)
    age = models.IntegerField(blank=True, null=True)
    gender = GenderField(choices=Gender.choices, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    profile = models.OneToOneField('patients.UserProfile', on_delete=models.SET_NULL, null=True, blank=True, db_column='profile_id')

    objects = PatientQuerySet.as_manager()

    class Meta:
        db_table = 'hospital"."patient'
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['patient_id']),
            # GIN index for faster text search (requires pg_trgm extension)
            GinIndex(fields=['name'], name='patient_name_gin', opclasses=['gin_trgm_ops']),
            GinIndex(fields=['patient_id'], name='patient_id_gin', opclasses=['gin_trgm_ops']),
        ]

    def __str__(self):
        return f"{self.name} ({self.patient_id})"


class DiagnosisType(models.Model):
    """진단명 마스터"""
    
    diagnosis_type_id = models.AutoField(primary_key=True)
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    detail_table = models.CharField(max_length=50, blank=True, null=True)
    
    class Meta:
        db_table = 'hospital"."diagnosis_types'


class Encounter(models.Model):
    """방문/진료 세션 (워크플로우 관리)"""

    class Status(models.TextChoices):
        """FHIR 수준 상태"""
        PLANNED = 'PLANNED', '계획됨'
        IN_PROGRESS = 'IN_PROGRESS', '진행중'
        COMPLETED = 'COMPLETED', '완료'
        CANCELLED = 'CANCELLED', '취소'
        ENTERED_IN_ERROR = 'ENTERED_IN_ERROR', '오류입력'

    class WorkflowState(models.TextChoices):
        """상세 워크플로우 상태"""
        REQUESTED = 'REQUESTED', '요청됨'
        REGISTERED = 'REGISTERED', '접수완료'
        WAITING_CLINIC = 'WAITING_CLINIC', '진료대기'
        IN_CLINIC = 'IN_CLINIC', '진료중'
        WAITING_RESULTS = 'WAITING_RESULTS', '결과대기'
        WAITING_IMAGING = 'WAITING_IMAGING', '촬영대기'
        IN_IMAGING = 'IN_IMAGING', '촬영중'
        WAITING_PAYMENT = 'WAITING_PAYMENT', '수납대기'
        COMPLETED = 'COMPLETED', '완료'
        CANCELLED = 'CANCELLED', '취소'

    # Backward compatibility alias
    EncounterStatus = WorkflowState

    encounter_id = models.AutoField(primary_key=True)

    # 상태 관리
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PLANNED
    )
    workflow_state = models.CharField(
        max_length=30,
        choices=WorkflowState.choices,
        default=WorkflowState.REQUESTED
    )

    # 시간 관리
    start_time = models.DateTimeField(blank=True, null=True)        # 방문 시작 (접수 시점)
    end_time = models.DateTimeField(blank=True, null=True)          # 방문 종료 (완료/취소 시점)
    state_entered_at = models.DateTimeField(auto_now_add=True)      # ⭐ 현재 상태 진입 시간 (대기열 순서용)

    # 위치 및 유형
    current_location = models.CharField(max_length=50, blank=True, null=True)  # ROOM_403, CT, XRAY 등

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Foreign Keys
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, db_column='patient_id')
    appointment = models.ForeignKey(
        'Appointment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='appointment_id'
    )
    assigned_doctor = models.ForeignKey(
        'Doctor',
        on_delete=models.SET_NULL,
        null=True, # 대기열 배정을 위해 필요하지만, 초기 단계나 에러의 경우 없을 수 있음.
        blank=True,
        db_column='assigned_doctor_id', # DB 컬럼명 명시
        related_name='assigned_encounters'
    )

    class Meta:
        db_table = 'hospital"."encounters'

    def transition_to(self, new_state, current_location=None):
        """
        상태 변경 통합 메서드
        - workflow_state 변경
        - FHIR status 자동 매핑
        - timestamp 업데이트
        - Redis 대기열 카운트 업데이트
        """
        from django.utils import timezone
        from administration.cache_manager import cache_manager

        old_state = self.workflow_state
        
        # 1. 상태 변경
        self.workflow_state = new_state
        self.state_entered_at = timezone.now()

        # 2. 위치 변경 (옵션)
        if current_location:
            self.current_location = current_location

        # 3. FHIR Status 매핑
        if new_state in [self.WorkflowState.REQUESTED, self.WorkflowState.REGISTERED]:
            self.status = self.Status.PLANNED
        elif new_state in [self.WorkflowState.WAITING_CLINIC, self.WorkflowState.IN_CLINIC,
                           self.WorkflowState.WAITING_IMAGING, self.WorkflowState.IN_IMAGING,
                           self.WorkflowState.WAITING_RESULTS, self.WorkflowState.WAITING_PAYMENT]:
            self.status = self.Status.IN_PROGRESS
        elif new_state == self.WorkflowState.COMPLETED:
            self.status = self.Status.COMPLETED
            if not self.end_time:
                self.end_time = timezone.now()
            # 연결된 Appointment 상태도 '진료완료'로 변경
            if self.appointment:
                self.appointment.status = '진료완료'
                self.appointment.save()
        elif new_state == self.WorkflowState.CANCELLED:
            self.status = self.Status.CANCELLED
            if not self.end_time:
                self.end_time = timezone.now()

        self.save()

        # 4. Redis Cache 업데이트 (상태 변화에 따른 카운트 조정)
        try:
            # === 진료 대기열 (Clinic) ===
            # 진료 대기 -> 진료 중
            if old_state == self.WorkflowState.WAITING_CLINIC and new_state == self.WorkflowState.IN_CLINIC:
                cache_manager.decrement_waiting_count('clinic')
                cache_manager.increment_in_progress_count('clinic')
            # 진료 중 -> 완료 (또는 수납대기/결과대기 등으로 나감)
            elif old_state == self.WorkflowState.IN_CLINIC and new_state != self.WorkflowState.IN_CLINIC:
                cache_manager.decrement_in_progress_count('clinic')

            # === 영상의학과 대기열 (Imaging) ===
            # 이전 상태가 촬영 대기였다면 카운트 감소
            if old_state == self.WorkflowState.WAITING_IMAGING:
                cache_manager.decrement_waiting_count('imaging')
            # 이전 상태가 촬영 중이었다면 카운트 감소
            elif old_state == self.WorkflowState.IN_IMAGING:
                cache_manager.decrement_in_progress_count('imaging')

            # 새로운 상태가 촬영 대기라면 카운트 증가
            if new_state == self.WorkflowState.WAITING_IMAGING:
                cache_manager.increment_waiting_count('imaging')
            # 새로운 상태가 촬영 중이라면 카운트 증가
            elif new_state == self.WorkflowState.IN_IMAGING:
                cache_manager.increment_in_progress_count('imaging')
                
            # WebSocket 알림 전송 (대기열 목록 갱신용)
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                'clinic_dashboard',
                {
                    'type': 'update_queue',
                    'message': 'Encounter status changed',
                    'data': {
                        'encounter_id': self.encounter_id,
                        'old_state': old_state,
                        'new_state': new_state
                    }
                }
            )

        except Exception as e:
            print(f"Redis/WebSocket update failed: {e}")
            # 캐시 업데이트 실패가 트랜잭션을 롤백시키면 안 됨 (로그만 남김)

        # 5. 원무과 알림 전송 (수납 대기 / 오더 대기)
        try:
            from administration.utils import send_notification_to_administration
            
            patient_name = self.patient.name if self.patient else "환자"
            
            if new_state == self.WorkflowState.WAITING_RESULTS:
                 # 오더 대기 (검사 결과 대기 포함이지만, 진입 시점은 '새 오더 발생' 시점임)
                send_notification_to_administration(
                    'new_order', 
                    f"새로운 오더가 도착했습니다: {patient_name}"
                )
            elif new_state == self.WorkflowState.WAITING_PAYMENT:
                # 수납 대기
                send_notification_to_administration(
                    'payment_waiting', 
                    f"수납 대기 환자가 발생했습니다: {patient_name}"
                )
        except Exception as e:
            print(f"Notification sending failed: {e}")
        ordering = ['state_entered_at']  # FIFO 대기열

    def __str__(self):
        return f"{self.patient.name} - {self.get_workflow_state_display()}"


class MedicalRecord(models.Model):
    """진료 기록"""

    class RecordStatus(models.TextChoices):
        """기록 상태"""
        DRAFT = 'DRAFT', '작성중'
        COMPLETED = 'COMPLETED', '완료'
        AMENDED = 'AMENDED', '수정됨'

    # QuestionnaireStatus 제거됨 (별도 모델로 분리)

    record_id = models.AutoField(primary_key=True)
    clinic_room = models.CharField(max_length=20, blank=True, null=True)
    record_date = models.DateField()
    record_time = models.TimeField()
    record_status = models.CharField(
        max_length=30,
        choices=RecordStatus.choices,
        default=RecordStatus.DRAFT,
        blank=True,
        null=True
    )
    department = models.CharField(max_length=100, blank=True, null=True)
    visit_start = models.TimeField(blank=True, null=True)
    visit_end = models.TimeField(blank=True, null=True)
    is_first_visit = models.BooleanField(default=False)
    chief_complaint = models.TextField(blank=True, null=True)
    clinical_notes = models.TextField(blank=True, null=True)
    lab_recorded = models.BooleanField(default=False)
    ct_recorded = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Foreign Keys
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, db_column='patient_id')
    doctor = models.ForeignKey('doctor.Doctor', on_delete=models.RESTRICT, db_column='doctor_id')
    staff = models.ForeignKey('administration.Administration', on_delete=models.RESTRICT, db_column='staff_id')
    diagnosis_type = models.ForeignKey(DiagnosisType, on_delete=models.SET_NULL, null=True, blank=True, db_column='diagnosis_type_id')
    encounter = models.ForeignKey(
        Encounter,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='encounter_id',
        related_name='medical_records'
    )

    class Meta:
        db_table = 'hospital"."medical_records'
        ordering = ['-record_date', '-record_time']

    def __str__(self):
        return f"{self.patient.name} - {self.record_date}"


class Appointment(models.Model):
    """예약"""
    
    appointment_id = models.AutoField(primary_key=True)
    appointment_date = models.DateField()
    appointment_time = models.TimeField()
    appointment_type = models.CharField(max_length=30, blank=True, null=True)
    status = models.CharField(max_length=30, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, db_column='patient_id')
    doctor = models.ForeignKey('doctor.Doctor', on_delete=models.SET_NULL, null=True, blank=True, db_column='doctor_id')
    staff = models.ForeignKey('administration.Administration', on_delete=models.SET_NULL, null=True, blank=True, db_column='staff_id')
    
    class Meta:
        db_table = 'hospital"."appointments'


class AnthropometricData(models.Model):
    """신체계측"""

    anthro_id = models.AutoField(primary_key=True)
    measured_at = models.DateField(blank=True, null=True)
    height = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    weight = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    bmi = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    is_pregnant = models.BooleanField(default=False)
    smoking_status = models.BooleanField(default=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, db_column='patient_id')
    medical_record = models.ForeignKey(MedicalRecord, on_delete=models.SET_NULL, null=True, blank=True, db_column='record_id')

    class Meta:
        db_table = 'hospital"."anthropometric_data'


class VitalData(models.Model):
    """바이탈"""

    vital_id = models.AutoField(primary_key=True)
    measured_at = models.DateField()
    sbp = models.IntegerField(blank=True, null=True)  # 수축기 혈압
    dbp = models.IntegerField(blank=True, null=True)  # 이완기 혈압
    heart_rate = models.IntegerField(blank=True, null=True)  # 심박수 (bpm)
    temperature = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)  # 체온 (°C)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, db_column='patient_id')
    medical_record = models.ForeignKey(
        MedicalRecord,
        on_delete=models.CASCADE,
        db_column='record_id',
        null=True,
        blank=True
    )

    class Meta:
        db_table = 'hospital"."vital_data'


class LabResult(models.Model):
    """혈액검사"""

    lab_id = models.AutoField(primary_key=True)
    test_date = models.DateField()
    afp = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    albumin = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    bilirubin_total = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    pt_inr = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    platelet = models.IntegerField(blank=True, null=True)
    creatinine = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    child_pugh_class = models.CharField(max_length=1, blank=True, null=True)
    meld_score = models.IntegerField(blank=True, null=True)
    albi_score = models.DecimalField(max_digits=5, decimal_places=3, blank=True, null=True)
    albi_grade = models.CharField(max_length=1, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    measured_at = models.DateTimeField(blank=True, null=True)

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, db_column='patient_id')
    medical_record = models.ForeignKey(MedicalRecord, on_delete=models.SET_NULL, null=True, blank=True, db_column='record_id')

    class Meta:
        db_table = 'hospital"."lab_results'


class HCCDiagnosis(models.Model):
    """간암 진단"""

    hcc_id = models.AutoField(primary_key=True)
    hcc_diagnosis_date = models.DateField()
    ajcc_stage = models.CharField(max_length=10, blank=True, null=True)
    ajcc_t = models.CharField(max_length=10, blank=True, null=True)
    ajcc_n = models.CharField(max_length=10, blank=True, null=True)
    ajcc_m = models.CharField(max_length=10, blank=True, null=True)
    grade = models.CharField(max_length=5, blank=True, null=True)
    vascular_invasion = models.CharField(max_length=20, blank=True, null=True)
    ishak_score = models.IntegerField(blank=True, null=True)
    hepatic_inflammation = models.CharField(max_length=50, blank=True, null=True)
    ecog_score = models.IntegerField(blank=True, null=True)
    tumor_status = models.CharField(max_length=50, blank=True, null=True)
    measured_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, db_column='patient_id')
    medical_record = models.ForeignKey(
        MedicalRecord,
        on_delete=models.SET_NULL,
        db_column='record_id',
        null=True,
        blank=True
    )

    class Meta:
        db_table = 'hospital"."hcc_diagnosis'


class GenomicData(models.Model):
    """유전체 검사"""
    
    genomic_id = models.AutoField(primary_key=True)
    sample_date = models.DateField(blank=True, null=True)
    pathway_scores = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    measured_at = models.DateTimeField(blank=True, null=True)
    
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, db_column='patient_id')
    
    class Meta:
        db_table = 'hospital"."genomic_data'


class Prescription(models.Model):
    """처방"""

    prescription_id = models.AutoField(primary_key=True)
    prescription_date = models.DateField()
    item_seq = models.BigIntegerField()
    medication_name = models.CharField(max_length=200)
    dosage = models.CharField(max_length=50, blank=True, null=True)
    frequency = models.CharField(max_length=50, blank=True, null=True)
    duration_days = models.IntegerField(blank=True, null=True)
    pharmacy_notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    measured_at = models.DateTimeField(blank=True, null=True)

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, db_column='patient_id')
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, db_column='encounter_id')
    doctor = models.ForeignKey('doctor.Doctor', on_delete=models.RESTRICT, db_column='doctor_id')
    department = models.ForeignKey('accounts.Department', on_delete=models.RESTRICT, db_column='department_id')

    class Meta:
        db_table = 'hospital"."prescriptions'
        
class DoctorToRadiologyOrder(models.Model):
    """영상 검사 처방 (의사 -> 영상의학과)"""

    class ImagingStatus(models.TextChoices):
        """영상 검사 상태"""
        REQUESTED = 'REQUESTED', '요청됨'
        WAITING = 'WAITING', '촬영대기'
        IN_PROGRESS = 'IN_PROGRESS', '촬영중'
        COMPLETED = 'COMPLETED', '완료' # 촬영 완료 - dicom 폴더 업로드
        CANCELLED = 'CANCELLED', '취소'

    order_id = models.AutoField(primary_key=True)
    modality = models.CharField(max_length=16)
    body_part = models.CharField(max_length=64, blank=True, null=True)
    order_notes = models.TextField(blank=True, null=True)
    priority = models.CharField(max_length=10, default='ROUTINE')

    status = models.CharField(
        max_length=20,
        choices=ImagingStatus.choices,
        default=ImagingStatus.REQUESTED
    )

    ordered_at = models.DateTimeField(auto_now_add=True)
    scheduled_at = models.DateTimeField(blank=True, null=True)
    study_uid = models.CharField(max_length=64, blank=True, null=True)

    patient = models.ForeignKey('Patient', on_delete=models.CASCADE, db_column='patient_id')
    encounter = models.ForeignKey('Encounter', on_delete=models.CASCADE, db_column='encounter_id', null=True, blank=True)
    doctor = models.ForeignKey('Doctor', on_delete=models.RESTRICT, db_column='doctor_id')

    class Meta:
        db_table = 'hospital"."doctor_to_radiology_orders'


# Alias for backward compatibility
ImagingOrder = DoctorToRadiologyOrder




class LabOrder(models.Model):
    """
    검사 처방 오더
    - 혈액검사, 유전체검사 등 종류별로 각각의 Row가 생성됩니다.
    """
    class OrderType(models.TextChoices):
        BLOOD_LIVER = 'BLOOD_LIVER', '간기능 혈액검사'  # LFT, CBC 등
        GENOMIC = 'GENOMIC', '유전체 분석'          # 유전자 3개 분석
        PHYSICAL = 'PHYSICAL', '신체 계측'          # 키, 몸무게 등
        VITAL = 'VITAL', '바이탈 측정'              # 혈압, 맥박, 체온 등

    class OrderStatus(models.TextChoices):
        REQUESTED = 'REQUESTED', '요청됨'
        IN_PROGRESS = 'IN_PROGRESS', '검사중'
        COMPLETED = 'COMPLETED', '완료'
        CANCELLED = 'CANCELLED', '취소'

    order_id = models.AutoField(primary_key=True)
    
    # [핵심] 이 오더가 어떤 검사인지 명시
    order_type = models.CharField(max_length=20, choices=OrderType.choices)
    
    # 특이사항 (JSON으로 유연하게 저장)
    order_notes = models.JSONField(default=dict, blank=True)
    
    status = models.CharField(
        max_length=20, 
        choices=OrderStatus.choices, 
        default=OrderStatus.REQUESTED
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Foreign Keys
    patient = models.ForeignKey('Patient', on_delete=models.CASCADE)
    encounter = models.ForeignKey('Encounter', on_delete=models.CASCADE)
    doctor = models.ForeignKey('Doctor', on_delete=models.RESTRICT)

    class Meta:
        db_table = 'hospital"."lab_orders'


class Questionnaire(models.Model):
    """문진표"""

    class QStatus(models.TextChoices):
        NOT_STARTED = 'NOT_STARTED', '미작성'
        IN_PROGRESS = 'IN_PROGRESS', '작성중'
        COMPLETED = 'COMPLETED', '완료'

    questionnaire_id = models.AutoField(primary_key=True)

    # 상태 및 데이터
    status = models.CharField(max_length=20, choices=QStatus.choices, default=QStatus.NOT_STARTED)
    data = models.JSONField(default=dict, blank=True)  # 질문-답변 데이터

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # 관계
    encounter = models.OneToOneField('Encounter', on_delete=models.CASCADE, related_name='questionnaire')
    patient = models.ForeignKey('Patient', on_delete=models.CASCADE)

    class Meta:
        db_table = 'hospital"."questionnaires'


class Announcement(models.Model):
    """병원 내 공지사항"""

    class AnnouncementType(models.TextChoices):
        GENERAL = 'GENERAL', '일반'
        URGENT = 'URGENT', '긴급'
        EVENT = 'EVENT', '행사'
        MAINTENANCE = 'MAINTENANCE', '시스템점검'

    announcement_id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=200)
    content = models.TextField()
    announcement_type = models.CharField(
        max_length=20,
        choices=AnnouncementType.choices,
        default=AnnouncementType.GENERAL
    )
    is_important = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    published_at = models.DateTimeField(blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Foreign Keys
    author = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='author_id',
        related_name='announcements'
    )

    class Meta:
        db_table = 'hospital"."announcements'
        verbose_name = '공지사항'
        verbose_name_plural = '공지사항'
        ordering = ['-is_important', '-created_at']

    def __str__(self):
        return f"{self.title} ({self.get_announcement_type_display()})"
