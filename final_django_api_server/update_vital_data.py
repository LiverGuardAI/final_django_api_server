"""
VitalData 테스트 데이터 업데이트 스크립트
P20240009의 바이탈 데이터에 심박수, 체온 값 추가
"""
from doctor.models import VitalData
from decimal import Decimal
import random

# P20240009 환자의 바이탈 데이터 조회
vital_data_list = VitalData.objects.filter(patient_id='P20240009').order_by('measured_at')

print(f"총 {vital_data_list.count()}개의 바이탈 데이터를 업데이트합니다.\n")

updated_count = 0
for vital in vital_data_list:
    # 심박수: 정상 범위 60-100 bpm
    base_hr = 75
    heart_rate = base_hr + random.randint(-10, 15)

    # 체온: 정상 범위 36.0-37.5°C
    base_temp = 36.5
    temperature = Decimal(base_temp + random.uniform(-0.5, 0.8)).quantize(Decimal('0.1'))

    # 업데이트
    vital.heart_rate = heart_rate
    vital.temperature = temperature
    vital.save()

    updated_count += 1
    print(f"✅ {updated_count}. {vital.measured_at} - HR: {heart_rate} bpm, Temp: {temperature}°C")

print(f"\n총 {updated_count}개의 바이탈 데이터가 업데이트되었습니다.")
