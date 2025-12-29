# doctor/utils.py
"""
환자 ID 생성 및 비밀번호 관리 유틸리티
"""
import uuid
from datetime import datetime


def generate_patient_id():
    """
    환자 ID 자동 생성

    형식 1: P + 년도 + 월 + 일 + UUID 앞 4자리
    예: P20241229ABCD

    형식 2: UUID 기반 (선택)
    예: P-550e8400-e29b-41d4-a716-446655440000
    """
    # 형식 1: 날짜 + UUID (추천)
    today = datetime.now()
    date_str = today.strftime('%Y%m%d')
    uuid_short = str(uuid.uuid4())[:4].upper()
    return f"P{date_str}{uuid_short}"

    # 형식 2: 완전한 UUID (필요시 주석 해제)
    # return f"P-{uuid.uuid4()}"


def generate_default_password(birth_date):
    """
    생년월일 기반 기본 비밀번호 생성

    Args:
        birth_date: datetime.date 또는 'YYYY-MM-DD' 형식 문자열

    Returns:
        str: 'YYYYMMDD' 형식의 비밀번호

    Example:
        >>> generate_default_password('1980-05-15')
        '19800515'
    """
    if isinstance(birth_date, str):
        # 'YYYY-MM-DD' 형식에서 '-' 제거
        return birth_date.replace('-', '')
    else:
        # datetime.date 객체
        return birth_date.strftime('%Y%m%d')


def validate_patient_id_format(patient_id):
    """
    환자 ID 형식 검증

    허용 형식:
    - P + 8자리 숫자 + 4자리 영문/숫자 (예: P20241229ABCD)
    - P2024 + 3자리 숫자 (기존 형식, 예: P2024001)
    - P- + UUID (예: P-550e8400-e29b-41d4-a716-446655440000)
    """
    import re

    patterns = [
        r'^P\d{8}[A-Z0-9]{4}$',  # P20241229ABCD
        r'^P\d{7}$',              # P2024001
        r'^P-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',  # UUID
    ]

    return any(re.match(pattern, patient_id) for pattern in patterns)
