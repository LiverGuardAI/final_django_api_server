"""
VitalData 테스트 데이터 생성 스크립트
patient_id P20240009의 바이탈 데이터 10개 생성
"""
from datetime import datetime, timedelta
from doctor.models import VitalData, Patient
import random

# 환자 확인
try:
    patient = Patient.objects.get(patient_id='P20240009')
    print(f"환자 확인: {patient.name} ({patient.patient_id})")
except Patient.DoesNotExist:
    print("❌ 환자 P20240009를 찾을 수 없습니다.")
    exit(1)

# 기존 바이탈 데이터 삭제 (선택사항)
print(f"\n기존 바이탈 데이터 삭제 중...")
deleted_count = VitalData.objects.filter(patient_id='P20240009').delete()[0]
print(f"삭제된 데이터: {deleted_count}개")

# 테스트 바이탈 데이터 생성
print("\n새 바이탈 데이터 생성 중...")
created_count = 0
base_date = datetime.now().date()

# 최근 10일간의 데이터 생성
for i in range(10):
    measured_date = base_date - timedelta(days=9-i)

    # 정상 범위의 혈압 데이터 생성 (약간의 변동성 포함)
    base_sbp = 120  # 수축기 혈압 기준
    base_dbp = 80   # 이완기 혈압 기준

    sbp = base_sbp + random.randint(-10, 15)
    dbp = base_dbp + random.randint(-5, 10)

    vital = VitalData.objects.create(
        patient=patient,
        measured_at=measured_date,
        sbp=sbp,
        dbp=dbp,
        encounter=None  # encounter는 null로 설정
    )
    created_count += 1
    print(f"✅ {created_count}. {measured_date} - SBP: {sbp}, DBP: {dbp}")

print(f"\n총 {created_count}개의 바이탈 데이터가 생성되었습니다.")
