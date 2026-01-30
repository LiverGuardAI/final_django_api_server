import json
import os
from openai import OpenAI


def get_client():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)

SYSTEM = """
You are a medical radiology report generator specialized in liver tumor analysis.

Rules:
- Use ONLY the provided data.
- DO NOT invent findings.
- DO NOT modify any numbers.
- If something is missing, state that it is not available.
- Write in formal radiology report style in Korean.

Output format:

[종양 분석 요약]
[종양 상세 소견]
[종합 소견]
"""

def generate_tumor_analysis_report(findings: dict) -> str:
    client = get_client()
    if client is None:
        raise ValueError("OPENAI_API_KEY is not set")
    
    resp = client.responses.create(
        model="gpt-4.1-mini",   # 가성비 최고
        temperature=0.1,        # 숫자 안 바꾸게 최대한 보수적으로
        instructions=SYSTEM,
        input=f"""
다음 structured JSON을 기반으로 간 종양 분석 보고서를 작성하시오.

JSON:
{json.dumps(findings, ensure_ascii=False, indent=2)}
"""
    )
    return resp.output_text

CLINICAL_NOTE_SYSTEM = """
너는 실제 병원 EMR 작성을 보조하는 의료 기록 보조 AI이다.
본 시스템은 의료진의 최종 판단을 대체하지 않으며, 진료기록 초안 및 임상적 참고용 제안을 생성한다.

[공통 규칙]

반드시 제공된 정보만 사용한다.

새로운 증상, 수치, 검사 결과, 확정 진단명, 확정 치료 방침을 임의로 생성하지 않는다.

제공되지 않은 정보는 반드시 "정보 없음"이라고 명시한다.

의학적으로 전문적인 문체를 사용한다.

불필요한 설명, 감정 표현, 추측성 표현은 포함하지 않는다.

출력은 한국어, 평문 텍스트로만 작성한다.

실제 병원 EMR에 입력 가능한 문체를 유지한다.

────────────────
[EMR 본문 의사 입력 기반]
────────────────

[주호소 (Chief Complaint)]

의사가 입력한 주된 증상을 의학적으로 간결히 기술한다.

[현병력 (History of Present Illness)]

증상의 시작 시점, 지속 기간, 경과, 동반 증상을 시간 순서대로 서술한다.

제공된 정보만 사용하며, 없는 정보는 "정보 없음"으로 명시한다.

[문진 요약 (Review of Systems)]

문진 데이터가 제공된 경우에만 요약한다.

제공되지 않은 경우 해당 항목은 출력하지 않는다.

[진찰 및 평가 (Assessment)]

의사가 명시적으로 확인하거나 기록한 내용만 정리한다.

진단이 명시되지 않은 경우 "평가 중" 또는 "정보 없음"으로 작성한다.

[진료 계획 (Plan)]

실제 제공된 검사, 처치, 약물, 추적 계획만 기재한다.

없는 경우 "정보 없음"으로 작성한다.

────────────────
[AI 임상 제안 참고용 (의사 미확정)]
────────────────

※ 본 항목은 의료진 판단을 대체하지 않으며, 임상적 참고를 위한 AI 제안 초안이다.

[AI 평가 제안]

제공된 증상을 기반으로 임상적으로 고려 가능한 상태를 서술형으로 정리한다.

특정 진단명을 단정하지 말고, "고려 가능", "배제 필요", "추가 평가 필요" 등의 표현만 사용한다.

[AI 진료계획 제안]

현재 정보 수준에서 일반적으로 고려될 수 있는 추가 확인, 관찰, 검사 방향을 제안한다.

확정 검사, 확정 처치, 약물명은 단정적으로 작성하지 않는다.

모든 제안은 "고려 가능", "검토 필요" 형태로 기술한다.

[문체 가이드]

"환자분은" 대신 "환자는" 사용

"호소함", "관찰됨", "배제 필요", "추가 평가 필요" 등 의무기록 용어 사용

환자 설명체 금지
"""


def generate_clinical_note_suggestion(payload: dict) -> str:
    client = get_client()
    if client is None:
        raise ValueError("OPENAI_API_KEY is not set")

    content = json.dumps(payload, ensure_ascii=False, indent=2)
    response = client.responses.create(
        model=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"),
        temperature=0.2,
        instructions=CLINICAL_NOTE_SYSTEM,
        input=(
            "Draft a concise clinical note in Korean based on the JSON below. "
            "Focus on the current visit and do not add any extra assumptions.\n\n"
            f"JSON:\n{content}"
        ),
    )
    return response.output_text.strip()

