"""
Django Serializers for LiverGuard AI Analysis

"""

from rest_framework import serializers
from .models import (
    RadioFeatureVector,
    ClinicalFeatureVector,
    AIAnalysisResult
)
from doctor.models import GenomicData


class RadioFeatureSerializer(serializers.ModelSerializer):
    """CT 특징 벡터 Serializer"""
    
    study_date = serializers.SerializerMethodField()
    study_description = serializers.SerializerMethodField()
    
    class Meta:
        model = RadioFeatureVector
        fields = [
            'radio_vector_id',
            'feature_vector',
            'model_name',
            'model_version',
            'study_date',
            'study_description',
            'created_at'
        ]
    
    def get_study_date(self, obj):
        if obj.series and obj.series.study:
            return obj.series.study.study_date
        return None
    
    def get_study_description(self, obj):
        if obj.series and obj.series.study:
            return obj.series.study.study_description
        return None


class ClinicalFeatureSerializer(serializers.ModelSerializer):
    """임상 특징 벡터 Serializer"""
    
    class Meta:
        model = ClinicalFeatureVector
        fields = [
            'clinical_vector_id',
            'feature_vector',
            'lab_date',
            'age',
            'sex',
            'grade',
            'vascular_invasion',
            'ishak_score',
            'afp',
            'albumin',
            'bilirubin',
            'platelet',
            'created_at'
        ]


class GenomicFeatureSerializer(serializers.ModelSerializer):
    """유전체 특징 벡터 Serializer"""
    
    class Meta:
        model = GenomicData
        fields = [
            'genomic_id',
            'pathway_scores',
            'sample_date',
            'sample_id',
            'created_at',
        ]


class AIAnalysisResultSerializer(serializers.ModelSerializer):
    """AI 분석 결과 Serializer"""
    
    created_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = AIAnalysisResult
        fields = [
            'analysis_id',
            'patient_id',
            'radio_vector_id',
            'clinical_vector_id',
            '',
            'stage_prediction',
            'relapse_prediction',
            'survival_prediction',
            'warnings',
            'model_version',
            'created_by',
            'created_by_name',
            'created_at'
        ]
    
    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return None


# ============================================================
# 요청/응답 Serializers
# ============================================================

class PredictionRequestSerializer(serializers.Serializer):
    """AI 예측 요청"""
    
    clinical_vector = serializers.ListField(
        child=serializers.FloatField(),
        min_length=5,
        max_length=20,
        help_text="Clinical features (9 values)"
    )
    ct_vector = serializers.ListField(
        child=serializers.FloatField(),
        min_length=512,
        max_length=512,
        help_text="CT features (512 values)"
    )
    mrna_vector = serializers.ListField(
        child=serializers.FloatField(),
        min_length=20,
        max_length=20,
        required=False,
        help_text="mRNA pathway scores (20 values)"
    )
    use_mrna = serializers.BooleanField(required=False, default=None)


class PredictionByIdsRequestSerializer(serializers.Serializer):
    """ID 기반 예측 요청"""
    
    radio_vector_id = serializers.UUIDField()
    clinical_vector_id = serializers.UUIDField()
    genomic_id = serializers.UUIDField(required=False, allow_null=True)


class SaveAnalysisRequestSerializer(serializers.Serializer):
    """분석 결과 저장 요청"""
    
    patient_id = serializers.UUIDField()
    radio_vector_id = serializers.UUIDField(required=False, allow_null=True)
    clinical_vector_id = serializers.UUIDField(required=False, allow_null=True)
    genomic_id = serializers.UUIDField(required=False, allow_null=True)
    stage_prediction = serializers.JSONField(required=False, default=dict)
    relapse_prediction = serializers.JSONField(required=False, default=dict)
    survival_prediction = serializers.JSONField(required=False, default=dict)
    warnings = serializers.JSONField(required=False, default=dict)
    model_version = serializers.CharField(default="v11.6")
