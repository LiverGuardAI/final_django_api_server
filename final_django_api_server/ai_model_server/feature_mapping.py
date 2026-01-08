"""
Clinical Feature Mapping & Extraction

DB 테이블 컬럼 → 모델 입력 변수 매핑
여러 테이블에서 데이터를 조합하여 Clinical Feature Vector 생성
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import numpy as np

# ============================================================
# 모델이 사용하는 Clinical Features (순서 중요!)
# ============================================================

MODEL_CLINICAL_FEATURES = [
    "AGE",
    "SEX",
    "GRADE",
    "VASCULAR_INVASION",
    "ISHAK_FIBROSIS_SCORE",
    "AFP_AT_PROCUREMENT",
    "SERUM_ALBUMIN_PRERESECTION",
    "BILIRUBIN_TOTAL",
    "PLATELET_COUNT_PRERESECTION"
]

# ============================================================
# DB 테이블 → 모델 변수 매핑
# ============================================================

# patient 테이블 매핑
PATIENT_MAPPING = {
    "age": "AGE",
    "gender": "SEX",  # 값 변환 필요: Male→1, Female→0
}

# hcc_diagnosis 테이블 매핑
HCC_DIAGNOSIS_MAPPING = {
    "grade": "GRADE",  # 값 변환 필요: G1→1, G2→2, G3→3, G4→4
    "vascular_invasion": "VASCULAR_INVASION",  # None→0, Micro→1, Macro→2
    "ishak_score": "ISHAK_FIBROSIS_SCORE",  # 값 변환 필요
}

# lab_results 테이블 매핑
LAB_RESULTS_MAPPING = {
    "afp": "AFP_AT_PROCUREMENT",
    "albumin": "SERUM_ALBUMIN_PRERESECTION",
    "bilirubin_total": "BILIRUBIN_TOTAL",
    "platelet": "PLATELET_COUNT_PRERESECTION",
}

# ============================================================
# 값 변환 함수들
# ============================================================

def convert_sex(value: Any) -> Optional[int]:
    """성별 변환: Male→1, Female→0"""
    if value is None:
        return None
    value_str = str(value).lower().strip()
    if value_str in ['male', 'm', '1', 'true']:
        return 1
    elif value_str in ['female', 'f', '0', 'false']:
        return 0
    return None


def convert_grade(value: Any) -> Optional[int]:
    """종양 등급 변환: G1→1, G2→2, G3→3, G4→4"""
    if value is None:
        return None
    value_str = str(value).upper().strip()
    grade_map = {'G1': 1, 'G2': 2, 'G3': 3, 'G4': 4, '1': 1, '2': 2, '3': 3, '4': 4}
    return grade_map.get(value_str)


def convert_vascular_invasion(value: Any) -> Optional[int]:
    """혈관 침범 변환: None→0, Micro→1, Macro→2"""
    if value is None:
        return None
    value_str = str(value).lower().strip()
    if value_str in ['none', 'no', '0', 'absent']:
        return 0
    elif value_str in ['micro', 'microscopic', '1']:
        return 1
    elif value_str in ['macro', 'macroscopic', '2']:
        return 2
    return None


def convert_ishak_score(value: Any) -> Optional[int]:
    """Ishak 섬유화 점수 변환"""
    if value is None:
        return None
    
    # 이미 숫자인 경우
    if isinstance(value, (int, float)):
        return int(value)
    
    value_str = str(value).strip()
    
    # TCGA 형식: "0 - No Fibrosis", "6 - Established Cirrhosis" 등
    ishak_map = {
        '0 - no fibrosis': 0,
        '1,2 - portal fibrosis': 1,
        '3,4 - fibrous speta': 2,
        '5 - nodular formation and incomplete cirrhosis': 3,
        '6 - established cirrhosis': 4,
    }
    
    value_lower = value_str.lower()
    for pattern, score in ishak_map.items():
        if pattern in value_lower:
            return score
    
    # 단순 숫자 문자열
    try:
        return int(value_str)
    except:
        return None


# ============================================================
# Feature Vector 생성
# ============================================================

@dataclass
class ClinicalData:
    """여러 테이블에서 수집한 임상 데이터"""
    # patient 테이블
    age: Optional[int] = None
    gender: Optional[str] = None
    
    # hcc_diagnosis 테이블
    grade: Optional[str] = None
    vascular_invasion: Optional[str] = None
    ishak_score: Optional[Any] = None
    
    # lab_results 테이블
    afp: Optional[float] = None
    albumin: Optional[float] = None
    bilirubin_total: Optional[float] = None
    platelet: Optional[float] = None


def create_clinical_feature_vector(data: ClinicalData) -> List[Optional[float]]:
    """
    ClinicalData → 모델 입력 벡터 (9차원)
    
    순서:
    [AGE, SEX, GRADE, VASCULAR_INVASION, ISHAK_FIBROSIS_SCORE,
     AFP, ALBUMIN, BILIRUBIN, PLATELET]
    """
    return [
        float(data.age) if data.age is not None else None,
        float(convert_sex(data.gender)) if data.gender is not None else None,
        float(convert_grade(data.grade)) if data.grade is not None else None,
        float(convert_vascular_invasion(data.vascular_invasion)) if data.vascular_invasion is not None else None,
        float(convert_ishak_score(data.ishak_score)) if data.ishak_score is not None else None,
        float(data.afp) if data.afp is not None else None,
        float(data.albumin) if data.albumin is not None else None,
        float(data.bilirubin_total) if data.bilirubin_total is not None else None,
        float(data.platelet) if data.platelet is not None else None,
    ]


def create_clinical_feature_vector_from_dict(
    patient_data: Dict[str, Any],
    hcc_data: Dict[str, Any],
    lab_data: Dict[str, Any]
) -> List[Optional[float]]:
    """
    딕셔너리에서 Clinical Feature Vector 생성
    
    Args:
        patient_data: patient 테이블 데이터 (age, gender)
        hcc_data: hcc_diagnosis 테이블 데이터 (grade, vascular_invasion, ishak_score)
        lab_data: lab_results 테이블 데이터 (afp, albumin, bilirubin_total, platelet)
    
    Returns:
        9차원 리스트 [AGE, SEX, GRADE, VASCULAR_INVASION, ISHAK, AFP, ALBUMIN, BILIRUBIN, PLATELET]
    """
    data = ClinicalData(
        age=patient_data.get('age'),
        gender=patient_data.get('gender'),
        grade=hcc_data.get('grade'),
        vascular_invasion=hcc_data.get('vascular_invasion'),
        ishak_score=hcc_data.get('ishak_score'),
        afp=lab_data.get('afp'),
        albumin=lab_data.get('albumin'),
        bilirubin_total=lab_data.get('bilirubin_total'),
        platelet=lab_data.get('platelet'),
    )
    
    return create_clinical_feature_vector(data)


# ============================================================
# Reverse Mapping (모델 출력 → DB 저장)
# ============================================================

MODEL_TO_DB_MAPPING = {
    "AGE": ("patient", "age"),
    "SEX": ("patient", "gender"),
    "GRADE": ("hcc_diagnosis", "grade"),
    "VASCULAR_INVASION": ("hcc_diagnosis", "vascular_invasion"),
    "ISHAK_FIBROSIS_SCORE": ("hcc_diagnosis", "ishak_score"),
    "AFP_AT_PROCUREMENT": ("lab_results", "afp"),
    "SERUM_ALBUMIN_PRERESECTION": ("lab_results", "albumin"),
    "BILIRUBIN_TOTAL": ("lab_results", "bilirubin_total"),
    "PLATELET_COUNT_PRERESECTION": ("lab_results", "platelet"),
}


# ============================================================
# mRNA Pathway 매핑 (ssGSEA 20 pathways)
# ============================================================

MRNA_PATHWAY_NAMES = [
    "Myc Targets V1",
    "G2-M Checkpoint",
    "Glycolysis",
    "Spermatogenesis",
    "mTORC1 Signaling",
    "E2F Targets",
    "Unfolded Protein Response",
    "Mitotic Spindle",
    "Bile Acid Metabolism",
    "PI3K/AKT/mTOR Signaling",
    "KRAS Signaling Dn",
    "Myc Targets V2",
    "UV Response Up",
    "Xenobiotic Metabolism",
    "Coagulation",
    "Fatty Acid Metabolism",
    "Adipogenesis",
    "Reactive Oxygen Species Pathway",
    "DNA Repair",
    "Oxidative Phosphorylation",
]


def validate_genomic_vector(vector: List[float]) -> bool:
    """mRNA feature vector 유효성 검사"""
    return isinstance(vector, list) and len(vector) == 20


def validate_radio_vector(vector: List[float]) -> bool:
    """CT feature vector 유효성 검사 (512-dim)"""
    return isinstance(vector, list) and len(vector) == 512


def validate_clinical_vector(vector: List[Optional[float]]) -> Dict[str, Any]:
    """
    Clinical feature vector 유효성 검사
    
    Returns:
        {
            "valid": bool,
            "missing_count": int,
            "missing_fields": List[str]
        }
    """
    missing = []
    for i, (val, name) in enumerate(zip(vector, MODEL_CLINICAL_FEATURES)):
        if val is None:
            missing.append(name)
    
    return {
        "valid": len(missing) == 0,
        "missing_count": len(missing),
        "missing_fields": missing
    }
