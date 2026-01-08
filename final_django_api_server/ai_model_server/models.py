# ai_model_server/models.py
from django.db import models
from .fields import VectorField
from accounts.fields import StatusField, RiskGroupField


class RadioFeatureVector(models.Model):
    """CT 영상 특징 벡터"""
    
    radio_vector_id = models.AutoField(primary_key=True)
    extraction_model = models.CharField(max_length=20, blank=True, null=True)
    model_version = models.CharField(max_length=20, blank=True, null=True)
    vector_dim = models.IntegerField(default=2048)
    feature_vector = VectorField(dimensions=2048, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    series = models.ForeignKey('radiology.DICOMSeries', on_delete=models.CASCADE, to_field='series_uid', db_column='series_uid')
    run = models.ForeignKey('radiology.RadiologyAIRun', on_delete=models.CASCADE, db_column='run_id')
    
    class Meta:
        db_table = 'hospital"."radio_feature_vectors'
        verbose_name = '영상 특징 벡터'
        verbose_name_plural = '영상 특징 벡터'


class ClinicalFeatureVector(models.Model):
    """임상 데이터 특징 벡터"""
    
    clinical_vector_id = models.AutoField(primary_key=True)
    includes_lab = models.BooleanField(default=False)
    includes_diagnosis = models.BooleanField(default=False)
    includes_vital = models.BooleanField(default=False)
    includes_anthropometric = models.BooleanField(default=False)
    extraction_model = models.CharField(max_length=20, blank=True, null=True)
    model_version = models.CharField(max_length=20, blank=True, null=True)
    vector_dim = models.IntegerField(default=128)
    feature_vector = VectorField(dimensions=128, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    encounter = models.ForeignKey('doctor.Encounter', on_delete=models.CASCADE, db_column='encounter_id')
    
    class Meta:
        db_table = 'hospital"."clinical_feature_vectors'
        verbose_name = '임상 특징 벡터'
        verbose_name_plural = '임상 특징 벡터'
        

class AIAnalysisResult(models.Model):
    """통합 AI 분석 결과"""

    class RiskGroup(models.TextChoices):
        LOW = 'LOW', '저위험'
        MEDIUM = 'MEDIUM', '중위험'
        HIGH = 'HIGH', '고위험'

    class Status(models.TextChoices):
        PENDING = 'PENDING', '대기'
        PROCESSING = 'PROCESSING', '처리중'
        COMPLETED = 'COMPLETED', '완료'
        FAILED = 'FAILED', '실패'

    result_id = models.AutoField(primary_key=True)
    task_type = models.CharField(max_length=30)
    model_name = models.CharField(max_length=100)
    model_version = models.CharField(max_length=20)
    model_config = models.JSONField(blank=True, null=True)
    prediction_results = models.JSONField()
    confidence_scores = models.JSONField(blank=True, null=True)
    probabilities = models.JSONField(blank=True, null=True)
    risk_score = models.DecimalField(max_digits=8, decimal_places=4, blank=True, null=True)
    risk_group = RiskGroupField(choices=RiskGroup.choices, blank=True, null=True)
    risk_factors = models.JSONField(blank=True, null=True)
    feature_importance = models.JSONField(blank=True, null=True)
    shap_values = models.JSONField(blank=True, null=True)
    explanation = models.TextField(blank=True, null=True)
    status = StatusField(choices=Status.choices)
    error_message = models.TextField(blank=True, null=True)
    started_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    patient = models.ForeignKey('doctor.Patient', on_delete=models.CASCADE, to_field='patient_id', db_column='patient_id')
    encounter = models.ForeignKey('doctor.Encounter', on_delete=models.CASCADE, db_column='encounter_id')
    imaging_vector = models.ForeignKey(RadioFeatureVector, on_delete=models.SET_NULL, null=True, blank=True, db_column='imaging_vector_id')
    clinical_vector = models.ForeignKey(ClinicalFeatureVector, on_delete=models.SET_NULL, null=True, blank=True, db_column='clinical_vector_id')
    genomic = models.ForeignKey('doctor.GenomicData', on_delete=models.SET_NULL, null=True, blank=True, db_column='genomic_id')
    
    class Meta:
        db_table = 'hospital"."ai_analysis_results'
        verbose_name = 'AI 분석 결과'
        verbose_name_plural = 'AI 분석 결과'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['patient_id', 'task_type'], name='idx_patient_task'),
            models.Index(fields=['encounter_id', 'task_type'], name='idx_encounter_task'),
            models.Index(fields=['task_type', 'status'], name='idx_task_status'),
            models.Index(fields=['created_at'], name='idx_created'),
        ]