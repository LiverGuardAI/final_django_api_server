# radiology/models.py
from django.db import models


class Radiology(models.Model):
    """영상의학과"""
    
    radiologic_id = models.AutoField(primary_key=True)
    employee_no = models.CharField(max_length=50, unique=True)
    license_no = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    user = models.OneToOneField('accounts.CustomUser', on_delete=models.CASCADE, db_column='user_id')
    department = models.ForeignKey('accounts.Department', on_delete=models.RESTRICT, db_column='department_id')
    
    class Meta:
        db_table = 'hospital"."radiology'


class DICOMStudy(models.Model):
    """DICOM 스터디"""

    study_uid = models.CharField(max_length=64, primary_key=True)
    order_id = models.BigIntegerField(blank=True, null=True)
    orthanc_study_id = models.CharField(max_length=64, blank=True, null=True)
    accession_number = models.CharField(max_length=64, blank=True, null=True)
    modality = models.CharField(max_length=16, blank=True, null=True)
    body_part = models.CharField(max_length=64, blank=True, null=True)
    study_description = models.CharField(max_length=255, blank=True, null=True)
    study_datetime = models.DateTimeField(blank=True, null=True)
    institution_name = models.CharField(max_length=64, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    patient = models.ForeignKey('doctor.Patient', on_delete=models.CASCADE, to_field='patient_id', db_column='patient_id')
    
    class Meta:
        db_table = 'hospital"."dicom_studies'


class DICOMSeries(models.Model):
    """DICOM 시리즈"""

    series_uid = models.CharField(max_length=64, primary_key=True)
    orthanc_series_id = models.CharField(max_length=64, blank=True, null=True)
    modality = models.CharField(max_length=16, blank=True, null=True)
    series_number = models.IntegerField(blank=True, null=True)
    series_description = models.CharField(max_length=255, blank=True, null=True)
    acquisition_datetime = models.DateTimeField(blank=True, null=True)
    image_count = models.IntegerField(blank=True, null=True)
    slice_thickness = models.DecimalField(max_digits=10, decimal_places=4, blank=True, null=True)
    pixel_spacing = models.CharField(max_length=64, blank=True, null=True)
    protocol_name = models.CharField(max_length=128, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    study = models.ForeignKey(DICOMStudy, on_delete=models.CASCADE, to_field='study_uid', db_column='study_uid')
    
    class Meta:
        db_table = 'hospital"."dicom_series'


class RadiologyPatientQueue(models.Model):
    """촬영 이력"""

    rqueue_id = models.AutoField(primary_key=True)
    modality = models.CharField(max_length=16, blank=True, null=True)
    body_part = models.CharField(max_length=64, blank=True, null=True)
    scheduled_at = models.DateTimeField(blank=True, null=True)
    acquired_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=30, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    sample_id = models.CharField(max_length=100, blank=True, null=True)

    radiologic = models.ForeignKey(Radiology, on_delete=models.RESTRICT, db_column='radiologic_id')
    patient = models.ForeignKey('doctor.Patient', on_delete=models.CASCADE, to_field='patient_id', db_column='patient_id')
    study = models.ForeignKey(DICOMStudy, on_delete=models.SET_NULL, null=True, blank=True, to_field='study_uid', db_column='study_uid')
    
    class Meta:
        db_table = 'hospital"."radiology_patient_queue'


class RadiologyAIRun(models.Model):
    """AI 실행 기록"""

    run_id = models.AutoField(primary_key=True)
    task_type = models.CharField(max_length=30, blank=True, null=True)
    model_name = models.CharField(max_length=128, blank=True, null=True)
    request_payload = models.JSONField(blank=True, null=True)
    status = models.CharField(max_length=20, blank=True, null=True)
    started_at = models.DateTimeField(blank=True, null=True)
    finished_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    series = models.ForeignKey(DICOMSeries, on_delete=models.CASCADE, to_field='series_uid', db_column='series_uid')
    
    class Meta:
        db_table = 'hospital"."radiology_ai_runs'
        indexes = [
            models.Index(fields=['series']),
            models.Index(fields=['status']),
        ]