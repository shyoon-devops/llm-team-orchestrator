"""결과 품질 평가 — reviewer 결과를 분석하여 재작업 필요 여부 판단."""

from __future__ import annotations

import structlog
from pydantic import BaseModel

logger = structlog.get_logger()

_REJECT_KEYWORDS = [
    "reject",
    "request_changes",
    "changes requested",
    "수정 필요",
    "수정이 필요",
    "변경 요청",
    "개선 필요",
    "재작업",
    "rework",
    "not approved",
]


class QualityVerdict(BaseModel):
    """품질 평가 결과."""

    approved: bool
    feedback: str = ""


class QualityGate:
    """subtask 결과를 평가하여 후속 작업이 필요한지 판단."""

    def evaluate(self, result: str, role: str = "reviewer") -> QualityVerdict:
        """결과를 평가한다.

        Args:
            result: subtask 실행 결과 텍스트.
            role: 평가 대상 역할 (reviewer, tester 등).

        Returns:
            QualityVerdict (approved + feedback).
        """
        if not result.strip():
            return QualityVerdict(approved=True)

        lower = result.lower()
        for kw in _REJECT_KEYWORDS:
            if kw in lower:
                logger.info(
                    "quality_gate_rejected",
                    role=role,
                    keyword=kw,
                    result_preview=result[:100],
                )
                return QualityVerdict(approved=False, feedback=result)

        return QualityVerdict(approved=True)
