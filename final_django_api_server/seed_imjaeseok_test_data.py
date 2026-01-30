from datetime import date, datetime, time, timedelta
import random

from doctor.models import (
    Patient,
    VitalData,
    LabResult,
    GenomicData,
    MedicalRecord,
    Encounter,
    DiagnosisType,
    Doctor,
)
from administration.models import Administration

PATHWAY_NAMES = [
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

patient = Patient.objects.filter(name="임재석").first()
if not patient:
    raise SystemExit("임재석 환자를 찾지 못했습니다. patient_id 확인이 필요합니다.")

doctor = Doctor.objects.first()
staff = Administration.objects.first()
if not doctor or not staff:
    raise SystemExit("Doctor 또는 Administration 데이터가 없습니다.")

diagnosis_type = DiagnosisType.objects.first()

base_date = date.today()

encounters = []
for i in range(10):
    day = base_date - timedelta(days=i)
    encounter = Encounter.objects.create(
        patient=patient,
        status=Encounter.Status.COMPLETED,
        workflow_state=Encounter.WorkflowState.COMPLETED,
        start_time=datetime.combine(day, time(9, 0)),
        end_time=datetime.combine(day, time(9, 30)),
    )
    encounters.append(encounter)

vitals = []
for i, encounter in enumerate(encounters):
    day = base_date - timedelta(days=i)
    vitals.append(
        VitalData(
            measured_at=day,
            sbp=118 + (i % 6),
            dbp=76 + (i % 5),
            heart_rate=68 + (i % 7),
            temperature=36.4 + (i % 4) * 0.1,
            patient=patient,
            encounter=encounter,
        )
    )
VitalData.objects.bulk_create(vitals)

labs = []
for i, encounter in enumerate(encounters):
    day = base_date - timedelta(days=i)
    labs.append(
        LabResult(
            test_date=day,
            afp=5.2 + i * 0.6,
            albumin=4.3 - i * 0.03,
            bilirubin_total=0.9 + i * 0.04,
            pt_inr=1.0 + i * 0.02,
            platelet=210 - i * 4,
            creatinine=0.9 + i * 0.01,
            child_pugh_class="A" if i < 7 else "B",
            meld_score=7 + (i % 4),
            albi_score=-2.3 + i * 0.05,
            albi_grade=str(1 + (i % 3)),
            measured_at=datetime.combine(day, time(8, 30)),
            patient=patient,
            encounter=encounter,
        )
    )
LabResult.objects.bulk_create(labs)

random.seed(42)

genomics = []
for i in range(10):
    day = base_date - timedelta(days=i)
    scores = {name: round(random.uniform(-2.0, 2.0), 3) for name in PATHWAY_NAMES}
    genomics.append(
        GenomicData(
            sample_date=day,
            measured_at=datetime.combine(day, time(11, 0)),
            pathway_scores=scores,
            patient=patient,
        )
    )
GenomicData.objects.bulk_create(genomics)

records = []
for i, encounter in enumerate(encounters):
    day = base_date - timedelta(days=i)
    records.append(
        MedicalRecord(
            record_date=day,
            record_time=time(10 + (i % 4), 0),
            record_status=MedicalRecord.RecordStatus.COMPLETED,
            department=doctor.department.dept_name if hasattr(doctor, "department") else None,
            visit_start=time(9, 0),
            visit_end=time(9, 30),
            is_first_visit=(i == 9),
            chief_complaint="복부 통증",
            clinical_notes="임재석 환자 테스트 진료 기록입니다.",
            lab_recorded=True,
            ct_recorded=False,
            patient=patient,
            doctor=doctor,
            staff=staff,
            diagnosis_type=diagnosis_type,
            encounter=encounter,
        )
    )
MedicalRecord.objects.bulk_create(records)

print("생성 완료:")
print("- VitalData:", len(vitals))
print("- LabResult:", len(labs))
print("- GenomicData:", len(genomics))
print("- MedicalRecord:", len(records))
