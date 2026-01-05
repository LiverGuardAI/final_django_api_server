from django.db import models
from accounts.fields import GenderField, DoctorScheduleTypeField

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
        CONFERENCE = 'CONFERENCE', '회의'
        VACATION = 'VACATION', '휴가'
        OTHER = 'OTHER', '기타'

    schedule_id = models.AutoField(primary_key=True)
    schedule_date = models.DateField()
    schedule_type = DoctorScheduleTypeField(choices=DoctorScheduleType.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    clinic_room = models.CharField(max_length=20, blank=True, null=True)
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

    class PatientStatus(models.TextChoices):
        """환자의 현재 물리적 위치/상태"""
        REGISTERED = 'REGISTERED', '접수완료'
        WAITING_CLINIC = 'WAITING_CLINIC', '진료대기'
        IN_CLINIC = 'IN_CLINIC', '진료중'
        WAITING_IMAGING = 'WAITING_IMAGING', '촬영대기'
        IN_IMAGING = 'IN_IMAGING', '촬영중'
        WAITING_LAB = 'WAITING_LAB', '검사대기'
        IN_LAB = 'IN_LAB', '검사중'
        COMPLETED = 'COMPLETED', '당일진료완료'
        DISCHARGED = 'DISCHARGED', '퇴원'

    patient_id = models.CharField(max_length=50, primary_key=True)
    sample_id = models.CharField(max_length=100, blank=True, null=True)
    name = models.CharField(max_length=100)
    date_of_birth = models.DateField(blank=True, null=True)
    age = models.IntegerField(blank=True, null=True)
    gender = GenderField(choices=Gender.choices, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    current_status = models.CharField(
        max_length=30,
        choices=PatientStatus.choices,
        default=PatientStatus.REGISTERED,
        blank=True,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # doctor 필드 제거: 담당 의사는 Encounter를 통해 관리 (당직의/대진의/협진 지원)
    profile = models.OneToOneField('patients.UserProfile', on_delete=models.SET_NULL, null=True, blank=True, db_column='profile_id')
    
    class Meta:
        db_table = 'hospital"."patient'
    
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
    """진료 기록"""

    class EncounterStatus(models.TextChoices):
        """진료 건의 처리 상태"""
        SCHEDULED = 'SCHEDULED', '예약됨'
        WAITING = 'WAITING', '대기중'
        IN_PROGRESS = 'IN_PROGRESS', '진료중'
        COMPLETED = 'COMPLETED', '완료'
        CANCELLED = 'CANCELLED', '취소'
        NO_SHOW = 'NO_SHOW', '노쇼'

    encounter_id = models.AutoField(primary_key=True)
    clinic_room = models.CharField(max_length=20, blank=True, null=True)
    encounter_date = models.DateField()
    encounter_time = models.TimeField()
    encounter_status = models.CharField(
        max_length=30,
        choices=EncounterStatus.choices,
        default=EncounterStatus.SCHEDULED,
        blank=True,
        null=True
    )
    department = models.CharField(max_length=100, blank=True, null=True)
    checkin_time = models.DateTimeField(blank=True, null=True)
    encounter_start = models.TimeField(blank=True, null=True)
    encounter_end = models.TimeField(blank=True, null=True)
    is_first_visit = models.BooleanField(default=False)
    chief_complaint = models.TextField(blank=True, null=True)
    clinical_notes = models.TextField(blank=True, null=True)
    lab_recorded = models.BooleanField(default=False)
    ct_recorded = models.BooleanField(default=False)
    next_visit_date = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, db_column='patient_id')
    doctor = models.ForeignKey('doctor.Doctor', on_delete=models.RESTRICT, db_column='doctor_id')
    staff = models.ForeignKey('administration.Administration', on_delete=models.RESTRICT, db_column='staff_id')
    diagnosis_type = models.ForeignKey(DiagnosisType, on_delete=models.SET_NULL, null=True, blank=True, db_column='diagnosis_type_id')
    
    class Meta:
        db_table = 'hospital"."encounters'
        ordering = ['-encounter_date', '-encounter_time']


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
    encounter = models.ForeignKey(Encounter, on_delete=models.SET_NULL, null=True, blank=True, db_column='encounter_id')
    
    class Meta:
        db_table = 'hospital"."anthropometric_data'


class VitalData(models.Model):
    """바이탈"""
    
    vital_id = models.AutoField(primary_key=True)
    measured_at = models.DateField()
    sbp = models.IntegerField(blank=True, null=True)
    dbp = models.IntegerField(blank=True, null=True)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, db_column='patient_id')
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, db_column='encounter_id')
    
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
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, db_column='encounter_id')
    
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
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, db_column='encounter_id')
    
    class Meta:
        db_table = 'hospital"."hcc_diagnosis'


class GenomicData(models.Model):
    """유전체 검사"""
    
    genomic_id = models.AutoField(primary_key=True)
    sample_date = models.DateField(blank=True, null=True)
    pathway_scores = models.JSONField(blank=True, null=True)
    lasso_coefficients = models.JSONField(blank=True, null=True)
    risk_genes = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    measured_at = models.DateTimeField(blank=True, null=True)
    
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, db_column='patient_id')
    sample_id = models.CharField(max_length=100, blank=True, null=True)
    
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
        
class ImagingOrder(models.Model):
    """영상 검사 처방"""

    class ImagingStatus(models.TextChoices):
        """영상 검사 상태"""
        REQUESTED = 'REQUESTED', '요청됨'
        WAITING = 'WAITING', '촬영대기'
        IN_PROGRESS = 'IN_PROGRESS', '촬영중'
        COMPLETED = 'COMPLETED', '완료'
        REPORTED = 'REPORTED', '판독완료'
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
    encounter = models.ForeignKey('Encounter', on_delete=models.CASCADE, db_column='encounter_id')
    doctor = models.ForeignKey('Doctor', on_delete=models.RESTRICT, db_column='doctor_id')
    
    class Meta:
        db_table = 'hospital"."imaging_orders'
