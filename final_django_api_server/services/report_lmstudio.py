import json
import os

import requests


LMSTUDIO_URL = os.environ["LMSTUDIO_URL"]
LMSTUDIO_MODEL = os.environ["LMSTUDIO_MODEL"]
LMSTUDIO_TEMPERATURE = float(os.environ["LMSTUDIO_TEMPERATURE"])

SYSTEM_PROMPT = """
You are a medical radiology report generator specialized in liver tumor analysis.

Rules:
- Use ONLY the provided data.
- DO NOT invent findings.
- Do not change the magnitude of any numbers. Only format them as requested.
- If a required value is missing or null, output "정보 없음".
- Write in formal radiology report style in Korean.
- Output strictly in Korean; do not use markdown bold or bullet symbols other than simple hyphen.
- Use the exact section headers shown in the Output format.
- For [종양 상세 소견], list each tumor as "Tumor {index}: ..." on a single line.
- Use units exactly as provided (mL, mm, mm², %). Do not change units or add conversions.
- Do not add interpretations, recommendations, or clinical judgments.
- Do not omit any tumor entry; include Tumor 1..N in order.
- Do not omit any field shown in the Output format.
- Use fixed decimal places in output:
  - total_tumor_volume_ml, liver_volume_ml: 2 decimals
  - tumor_burden_percent: 2 decimals
  - volume_ml, max_diameter_mm, centroid_mm, surface_area_mm2, distance_to_capsule_mm: 2 decimals
  - surface_area_to_volume_ratio, sphericity, compactness, elongation: 4 decimals
  - If a value is an integer, still show trailing zeros to match decimals.
- 종양 분석 요약은 3-5문장 이내로 간결하게 작성
- 종양 상세 소견은 각 종양을 "Tumor {index}: ..." 형식으로 항목마다 구분해서 한글로 작성
- 종합 소견은 3-5문장 이내로 상세하게 작성


Output format:

[종양 분석 요약]
[종양 상세 소견]
[종합 소견]
"""


def build_report_content(payload: dict) -> str:
    if not isinstance(payload, dict):
        return ""
    return (
        "다음 structured JSON을 기반으로 간 종양 분석 보고서를 작성하시오.\n\n"
        "JSON:\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def generate_lmstudio_report(
    payload: dict,
    content: str | None = None,
    system_content: str | None = None,
    model: str | None = None,
) -> str:
    if isinstance(content, str) and content.strip():
        report_content = content
    else:
        report_content = build_report_content(payload)
    if not report_content.strip():
        raise ValueError("content is required")

    messages = [
        {"role": "system", "content": system_content or SYSTEM_PROMPT},
        {"role": "user", "content": report_content},
    ]

    response = requests.post(
        LMSTUDIO_URL,
        json={
            "model": model or LMSTUDIO_MODEL,
            "messages": messages,
            "temperature": LMSTUDIO_TEMPERATURE,
        },
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("Invalid response from LLM server") from exc
