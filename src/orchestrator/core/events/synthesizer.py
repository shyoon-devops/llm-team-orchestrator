"""Synthesizer — aggregate agent results into a report (stub for Phase 1)."""

from __future__ import annotations

from typing import Literal

import structlog

from orchestrator.core.models.pipeline import WorkerResult

logger = structlog.get_logger()


class Synthesizer:
    """서브태스크 결과를 종합하여 보고서를 생성한다.

    Phase 1에서는 단순 concat 방식으로 종합한다.
    Phase 2+에서 LLM 기반 종합으로 전환한다.

    Attributes:
        model: 종합에 사용할 LLM 모델 이름.
    """

    def __init__(self, model: str = "claude-sonnet-4-20250514") -> None:
        """
        Args:
            model: LiteLLM 호환 모델 이름.
        """
        self.model = model

    async def synthesize(
        self,
        results: list[WorkerResult],
        *,
        strategy: Literal["narrative", "structured", "checklist"] = "narrative",
        task_description: str = "",
    ) -> str:
        """결과를 종합하여 보고서를 생성한다.

        Args:
            results: 서브태스크 실행 결과 목록.
            strategy: 종합 전략.
            task_description: 원본 태스크 설명.

        Returns:
            종합 보고서 문자열.
        """
        if not results:
            return "결과가 없습니다."

        log = logger.bind(strategy=strategy, result_count=len(results))
        log.info("synthesis_started")

        # Phase 1: simple concatenation
        parts = [f"# 종합 보고서: {task_description}\n"]

        for i, r in enumerate(results, 1):
            status = "성공" if not r.error else "실패"
            parts.append(f"## 서브태스크 {i} ({r.subtask_id}) — {status}")
            if r.output:
                parts.append(r.output)
            if r.error:
                parts.append(f"**에러:** {r.error}")
            if r.files_changed:
                files = ", ".join(f.path for f in r.files_changed)
                parts.append(f"**변경 파일:** {files}")
            parts.append("")

        report = "\n".join(parts)
        log.info("synthesis_completed", report_length=len(report))
        return report
