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
You are a medical assistant that drafts clinical notes for a patient encounter.

Rules:
- Use only the provided data.
- Do not invent findings.
- If information is missing, say "\uC815\uBCF4 \uC5C6\uC74C".
- Output in Korean.
- Output plain text without markdown.
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

