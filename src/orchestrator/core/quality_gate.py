"""결과 품질 평가 — reviewer 결과를 분석하여 재작업 필요 여부 판단."""

from __future__ import annotations

import json

import structlog
from pydantic import BaseModel

logger = structlog.get_logger()

_REJECT_KEYWORDS = [
    "reject", "request_changes", "changes requested",
    "수정 필요", "수정이 필요", "변경 요청", "개선 필요",
    "재작업", "rework", "not approved",
]


class QualityVerdict(BaseModel):
    """품질 평가 결과."""
    approved: bool
    feedback: str = ""


class QualityGate:
    """subtask 결과를 평가하여 후속 작업이 필요한지 판단.

    1차: JSON verdict 파싱 ({"verdict": "approve"|"reject", "feedback": "..."})
    2차: 키워드 fallback
    """

    def evaluate(self, result: str, role: str = "reviewer") -> QualityVerdict:
        if not result.strip():
            return QualityVerdict(approved=True)

        # 1차: JSON verdict
        for line in result.strip().split("\n")[:3]:
            line = line.strip()
            if line.startswith("{"):
                try:
                    data = json.loads(line)
                    if "verdict" in data:
                        approved = data["verdict"].lower() in ("approve", "approved", "lgtm")
                        logger.info(
                            "quality_gate_json_verdict",
                            role=role,
                            verdict=data["verdict"],
                            approved=approved,
                        )
                        return QualityVerdict(
                            approved=approved,
                            feedback=data.get("feedback", ""),
                        )
                except (json.JSONDecodeError, AttributeError):
                    continue

        # 2차: 키워드 fallback
        lower = result.lower()
        for kw in _REJECT_KEYWORDS:
            if kw in lower:
                logger.info(
                    "quality_gate_keyword_rejected",
                    role=role,
                    keyword=kw,
                )
                return QualityVerdict(approved=False, feedback=result)

        return QualityVerdict(approved=True)
