# patients/models.py - LiverGuard 앱 관련
from django.db import models
from accounts.fields import GenderField, ScheduleTypeField, MealTimingField, MedicationStatusField


class UserProfile(models.Model):
    """앱 사용자 프로필"""

    class Gender(models.TextChoices):
        M = 'M', '남성'
        F = 'F', '여성'

    profile_id = models.BigAutoField(primary_key=True)
    nickname = models.CharField(max_length=20)
    birth_date = models.DateField(blank=True, null=True)
    gender = GenderField(choices=Gender.choices, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user_id = models.BigIntegerField(unique=True)  # 중복 방지
    password = models.CharField(max_length=128)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    linked_patient_id = models.CharField(max_length=50, blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'app"."user_profile'
    
    def __str__(self):
        return f"{self.nickname}"


class Prescription(models.Model):
    """처방전 기록"""
    
    pres_id = models.BigAutoField(primary_key=True)
    hospital_name = models.CharField(max_length=100, blank=True, null=True)
    dispense_date = models.DateField(blank=True, null=True)
    image_url = models.CharField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, db_column='profile_id')
    
    class Meta:
        db_table = 'app"."prescriptions'


class MedicationDetail(models.Model):
    """복용 약물"""

    med_id = models.BigAutoField(primary_key=True)
    item_name = models.CharField(max_length=200)
    one_dose = models.CharField(max_length=50, blank=True, null=True)
    daily_count = models.CharField(max_length=50, blank=True, null=True)
    total_days = models.CharField(max_length=50, blank=True, null=True)
    is_taking = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    pres = models.ForeignKey(Prescription, on_delete=models.CASCADE, db_column='pres_id')
    pill_info = models.ForeignKey('PillInfo', on_delete=models.RESTRICT, db_column='item_seq', to_field='item_seq')
    
    class Meta:
        db_table = 'app"."medication_detail'


class PillInfo(models.Model):
    """약품 정보"""
    
    item_seq = models.BigIntegerField(primary_key=True)
    item_name = models.CharField(max_length=200)
    entp_name = models.CharField(max_length=100, blank=True, null=True)
    item_image = models.CharField(max_length=1000, blank=True, null=True)
    print_front = models.CharField(max_length=50, blank=True, null=True)
    print_back = models.CharField(max_length=50, blank=True, null=True)
    drug_shape = models.CharField(max_length=50, blank=True, null=True)
    color_class1 = models.CharField(max_length=50, blank=True, null=True)
    color_class2 = models.CharField(max_length=50, blank=True, null=True)
    line_front = models.CharField(max_length=50, blank=True, null=True)
    line_back = models.CharField(max_length=50, blank=True, null=True)
    len_long = models.CharField(max_length=20, blank=True, null=True)
    len_short = models.CharField(max_length=20, blank=True, null=True)
    thick = models.CharField(max_length=20, blank=True, null=True)
    class_name = models.CharField(max_length=100, blank=True, null=True)
    etc_otc_name = models.CharField(max_length=20, blank=True, null=True)
    ingr_code = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'app"."pill_info'


class Allergy(models.Model):
    """알러지"""
    
    allergy_id = models.BigAutoField(primary_key=True)
    allergy_type = models.CharField(max_length=50, blank=True, null=True)
    trigger_agent = models.CharField(max_length=100, blank=True, null=True)
    reaction_desc = models.CharField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, db_column='profile_id')
    
    class Meta:
        db_table = 'app"."allergy'


class Vital(models.Model):
    """바이탈 측정"""
    
    log_id = models.BigAutoField(primary_key=True)
    record_date = models.DateTimeField()
    sbp = models.IntegerField(blank=True, null=True)
    dbp = models.IntegerField(blank=True, null=True)
    blood_sugar = models.IntegerField(blank=True, null=True)
    memo = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, db_column='profile_id')
    
    class Meta:
        db_table = 'app"."vital'


class PhysicalHistory(models.Model):
    """신체 정보"""
    
    physical_id = models.BigAutoField(primary_key=True)
    height = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    weight = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    is_pregnant = models.BooleanField(default=False)
    smoking_status = models.BooleanField(default=False)
    alcohol_freq = models.CharField(max_length=20, blank=True, null=True)
    measured_date = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, db_column='profile_id')
    
    class Meta:
        db_table = 'app"."physical_history'


class DiseaseHistory(models.Model):
    """기저질환"""
    
    history_id = models.BigAutoField(primary_key=True)
    disease_code = models.CharField(max_length=20, blank=True, null=True)
    disease_name = models.CharField(max_length=100)
    diagnosis_date = models.DateField(blank=True, null=True)
    severity_level = models.IntegerField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, db_column='profile_id')
    
    class Meta:
        db_table = 'app"."disease_history'


class DURLog(models.Model):
    """DUR 검색 기록"""
    
    log_id = models.BigAutoField(primary_key=True)
    detected_at = models.DateTimeField(auto_now_add=True)
    input_drug_name = models.CharField(max_length=200, blank=True, null=True)
    conflict_drug_name = models.CharField(max_length=200, blank=True, null=True)
    
    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, db_column='profile_id')
    violated_dur = models.ForeignKey('DURContraindication', on_delete=models.RESTRICT, db_column='violated_dur_id')
    
    class Meta:
        db_table = 'app"."dur_log'


class DURContraindication(models.Model):
    """DUR 병용금기"""
    
    dur_id = models.BigAutoField(primary_key=True)
    dur_seq = models.IntegerField(blank=True, null=True)
    ingr_code_a = models.CharField(max_length=20, blank=True, null=True)
    ingr_code_b = models.CharField(max_length=20, blank=True, null=True)
    contraindication_data = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'app"."dur_contraindication'


class MedicationSchedule(models.Model):
    """복약 일정 관리"""

    class ScheduleType(models.TextChoices):
        DAILY = 'DAILY', '매일'
        WEEKLY = 'WEEKLY', '매주'
        CUSTOM = 'CUSTOM', '사용자 정의'

    class MealTiming(models.TextChoices):
        BEFORE_MEAL = 'BEFORE_MEAL', '식전'
        AFTER_MEAL = 'AFTER_MEAL', '식후'
        WITH_MEAL = 'WITH_MEAL', '식사와 함께'
        ANYTIME = 'ANYTIME', '상관없음'

    schedule_id = models.BigAutoField(primary_key=True)
    schedule_type = ScheduleTypeField(choices=ScheduleType.choices, blank=True, null=True)
    times_per_day = models.IntegerField(blank=True, null=True)
    time_slots = models.JSONField(blank=True, null=True)
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    total_days = models.IntegerField(blank=True, null=True)
    meal_timing = MealTimingField(choices=MealTiming.choices, blank=True, null=True)
    reminder_enabled = models.BooleanField(default=True)
    reminder_advance_minutes = models.IntegerField(default=30)
    is_active = models.BooleanField(default=True)
    paused_at = models.DateTimeField(blank=True, null=True)
    pause_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, db_column='profile_id')
    med = models.ForeignKey(MedicationDetail, on_delete=models.CASCADE, db_column='med_id')
    
    class Meta:
        db_table = 'app"."medication_schedule'


class MedicationLog(models.Model):
    """복약 기록"""

    class MedicationStatus(models.TextChoices):
        TAKEN = 'TAKEN', '복용함'
        SKIPPED = 'SKIPPED', '건너뜀'
        MISSED = 'MISSED', '누락'
        SCHEDULED = 'SCHEDULED', '예정'

    log_id = models.BigAutoField(primary_key=True)
    scheduled_date = models.DateField()
    scheduled_time = models.TimeField()
    taken_at = models.DateTimeField(blank=True, null=True)
    status = MedicationStatusField(choices=MedicationStatus.choices)
    skip_reason = models.TextField(blank=True, null=True)
    scheduled_dosage = models.CharField(max_length=50, blank=True, null=True)
    actual_dosage = models.CharField(max_length=50, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    side_effects = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    schedule = models.ForeignKey(MedicationSchedule, on_delete=models.CASCADE, db_column='schedule_id')
    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, db_column='profile_id')
    med = models.ForeignKey(MedicationDetail, on_delete=models.CASCADE, db_column='med_id')
    
    class Meta:
        db_table = 'app"."medication_log'


class MedicationNotification(models.Model):
    """복약 알림 설정"""
    
    notification_id = models.BigAutoField(primary_key=True)
    notifications_enabled = models.BooleanField(default=True)
    push_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=False)
    email_enabled = models.BooleanField(default=False)
    first_reminder_minutes = models.IntegerField(default=30)
    second_reminder_minutes = models.IntegerField(default=0)
    late_reminder_minutes = models.IntegerField(default=30)
    quiet_hours_enabled = models.BooleanField(default=False)
    quiet_start_time = models.TimeField(blank=True, null=True)
    quiet_end_time = models.TimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, db_column='profile_id')
    
    class Meta:
        db_table = 'app"."medication_notification'


class MedicationAdherence(models.Model):
    """복약 순응도 통계"""
    
    adherence_id = models.BigAutoField(primary_key=True)
    period_start = models.DateField()
    period_end = models.DateField()
    total_scheduled = models.IntegerField(blank=True, null=True)
    total_taken = models.IntegerField(blank=True, null=True)
    total_skipped = models.IntegerField(blank=True, null=True)
    total_missed = models.IntegerField(blank=True, null=True)
    adherence_rate = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    on_time_rate = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    current_streak_days = models.IntegerField(blank=True, null=True)
    longest_streak_days = models.IntegerField(blank=True, null=True)
    calculated_at = models.DateTimeField(auto_now_add=True)
    
    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, db_column='profile_id')
    med = models.ForeignKey(MedicationDetail, on_delete=models.CASCADE, db_column='med_id')
    
    class Meta:
        db_table = 'app"."medication_adherence'