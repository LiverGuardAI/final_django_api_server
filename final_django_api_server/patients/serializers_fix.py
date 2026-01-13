# DoctorListSerializer 수정
# 기존: fields = ['doctor_id', 'doctor_name', 'specialty', 'phone']
# 수정: fields = ['doctor_id', 'name', 'phone'] + specialty 계산 필드

import re

with open('serializers.py', 'r', encoding='utf-8') as f:
    content = f.read()

# DoctorListSerializer 수정
old_serializer = '''# 의사 목록 Serializer  
class DoctorListSerializer(serializers.ModelSerializer):
    """의사 목록 (앱용)"""
    class Meta:
        model = Doctor
        fields = ['doctor_id', 'doctor_name', 'specialty', 'phone']'''

new_serializer = '''# 의사 목록 Serializer  
class DoctorListSerializer(serializers.ModelSerializer):
    """의사 목록 (앱용)"""
    specialty = serializers.CharField(source='department.dept_name', read_only=True)
    
    class Meta:
        model = Doctor
        fields = ['doctor_id', 'name', 'specialty', 'phone']'''

content = content.replace(old_serializer, new_serializer)

with open('serializers.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Serializer 수정 완료")
