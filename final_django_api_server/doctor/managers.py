from django.db import models
from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import Q

class TrigramSearchQuerySet(models.QuerySet):
    """
    TrigramSimilarity 검색을 지원하는 기본 QuerySet
    """
    def search(self, query, fields=None, threshold=0.1):
        """
        TrigramSimilarity를 사용하여 검색
        :param query: 검색어
        :param fields: 검색할 필드 리스트 (예: ['name', 'patient_id'])
        :param threshold: 유사도 임계값 (기본 0.1)
        """
        if not query:
            return self
            
        if not fields:
            return self

        similarity_expression = None
        for field in fields:
            if similarity_expression is None:
                similarity_expression = TrigramSimilarity(field, query)
            else:
                similarity_expression += TrigramSimilarity(field, query)
        
        # annotation 이름은 'similarity'로 고정
        return self.annotate(similarity=similarity_expression)\
                   .filter(similarity__gt=threshold)\
                   .order_by('-similarity')

class PatientQuerySet(TrigramSearchQuerySet):
    """Patient 모델 전용 QuerySet"""
    def search_patient(self, query):
        return self.search(query, fields=['name', 'patient_id'])

class DoctorQuerySet(TrigramSearchQuerySet):
    """Doctor 모델 전용 QuerySet"""
    def search_doctor(self, query):
        return self.search(query, fields=['name', 'employee_no'])
