"""Synthesizer — aggregate agent results into a structured report."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

import structlog

from orchestrator.core.models.pipeline import WorkerResult

logger = structlog.get_logger()

# 전략별 보고서 유형
SynthesisStrategy = Literal["narrative", "structured", "checklist"]


class Synthesizer:
    """서브태스크 결과를 종합하여 보고서를 생성한다.

    Template 기반 종합기: LLM 호출 없이 구조화된 보고서를 생성한다.
    strategy 패턴을 지원한다: narrative / structured / checklist.

    향후 LLM 기반 종합(litellm.acompletion)으로 확장 가능하도록
    strategy 패턴을 유지한다.

    Attributes:
        model: 종합에 사용할 LLM 모델 이름 (향후 LLM 종합용).
        default_strategy: 기본 종합 전략.
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        strategy: SynthesisStrategy = "narrative",
    ) -> None:
        """
        Args:
            model: LiteLLM 호환 모델 이름.
            strategy: 기본 종합 전략.
        """
        self.model = model
        self.default_strategy = strategy

    async def synthesize(
        self,
        results: list[WorkerResult],
        task: str,
        *,
        strategy: SynthesisStrategy | None = None,
    ) -> str:
        """결과를 종합하여 보고서를 생성한다.

        Args:
            results: 서브태스크 실행 결과 목록.
            task: 원본 사용자 태스크 설명.
            strategy: 종합 전략 오버라이드. None이면 기본값 사용.

        Returns:
            종합 보고서 문자열 (마크다운 형식).

        Raises:
            ValueError: results가 비어있는 경우.
        """
        if not results:
            return "결과가 없습니다."

        effective_strategy = strategy or self.default_strategy
        log = logger.bind(strategy=effective_strategy, result_count=len(results))
        log.info("synthesis_started")

        # 성공/실패 분류
        success_results = [r for r in results if not r.error]
        failed_results = [r for r in results if r.error]

        # 전략별 보고서 생성
        strategy_map = {
            "narrative": self._build_narrative,
            "structured": self._build_structured,
            "checklist": self._build_checklist,
        }

        builder = strategy_map.get(effective_strategy, self._build_narrative)
        report = builder(
            task_description=task,
            success_results=success_results,
            failed_results=failed_results,
            all_results=results,
        )

        log.info("synthesis_completed", report_length=len(report))
        return report

    def _build_narrative(
        self,
        *,
        task_description: str,
        success_results: list[WorkerResult],
        failed_results: list[WorkerResult],
        all_results: list[WorkerResult],
    ) -> str:
        """자연어 종합 보고서를 생성한다.

        배경 -> 에이전트별 결과 -> 결론 구조.
        """
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        parts: list[str] = []

        # 헤더
        parts.append(f"# 종합 보고서: {task_description}")
        parts.append(f"\n> 생성 시각: {now}")
        parts.append(
            f"> 전체 서브태스크: {len(all_results)}개"
            f" (성공: {len(success_results)}, 실패: {len(failed_results)})"
        )
        parts.append("")

        # 요약
        parts.append("## 요약")
        parts.append("")
        if not failed_results:
            parts.append(f"모든 {len(success_results)}개 서브태스크가 성공적으로 완료되었습니다.")
        elif not success_results:
            parts.append(f"모든 {len(failed_results)}개 서브태스크가 실패했습니다.")
        else:
            parts.append(
                f"{len(success_results)}개 서브태스크가 성공하고, "
                f"{len(failed_results)}개 서브태스크가 실패했습니다. "
                f"성공한 결과를 기반으로 부분 종합을 진행합니다."
            )
        parts.append("")

        # 에이전트별 결과
        parts.append("## 에이전트별 결과")
        parts.append("")
        for i, r in enumerate(all_results, 1):
            status_label = "성공" if not r.error else "실패"
            status_emoji = "[OK]" if not r.error else "[FAIL]"
            parts.append(f"### 서브태스크 {i} ({r.subtask_id}) — {status_emoji} {status_label}")
            parts.append("")

            if r.output:
                parts.append(r.output)
                parts.append("")

            if r.error:
                parts.append(f"**에러:** {r.error}")
                parts.append("")

            if r.files_changed:
                parts.append("**변경 파일:**")
                for f in r.files_changed:
                    parts.append(f"- `{f.path}` ({f.change_type})")
                parts.append("")

            if r.duration_ms > 0:
                parts.append(f"*실행 시간: {r.duration_ms}ms*")
                parts.append("")

        # 실패 노트
        if failed_results:
            parts.append("## 실패 노트")
            parts.append("")
            parts.append("| 서브태스크 | 에러 |")
            parts.append("|-----------|------|")
            for r in failed_results:
                error_short = r.error[:100] if r.error else "알 수 없는 에러"
                parts.append(f"| {r.subtask_id} | {error_short} |")
            parts.append("")

        return "\n".join(parts)

    def _build_structured(
        self,
        *,
        task_description: str,
        success_results: list[WorkerResult],
        failed_results: list[WorkerResult],
        all_results: list[WorkerResult],
    ) -> str:
        """구조화된 보고서를 생성한다.

        섹션별 정리 + 요약 표.
        """
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        parts: list[str] = []

        parts.append(f"# {task_description} — 구조화 보고서")
        parts.append(f"\n> {now}")
        parts.append("")

        # 상태 요약 표
        parts.append("## 실행 상태")
        parts.append("")
        parts.append("| 항목 | 값 |")
        parts.append("|------|-----|")
        parts.append(f"| 전체 서브태스크 | {len(all_results)} |")
        parts.append(f"| 성공 | {len(success_results)} |")
        parts.append(f"| 실패 | {len(failed_results)} |")
        total_duration = sum(r.duration_ms for r in all_results)
        parts.append(f"| 총 실행 시간 | {total_duration}ms |")
        total_tokens = sum(r.tokens_used for r in all_results)
        if total_tokens > 0:
            parts.append(f"| 총 토큰 사용 | {total_tokens} |")
        parts.append("")

        # 서브태스크별 상세 표
        parts.append("## 서브태스크 상세")
        parts.append("")
        parts.append("| # | ID | 상태 | 소요 시간 | 변경 파일 수 |")
        parts.append("|---|-----|------|-----------|-------------|")
        for i, r in enumerate(all_results, 1):
            status = "성공" if not r.error else "실패"
            duration = f"{r.duration_ms}ms" if r.duration_ms > 0 else "-"
            file_count = len(r.files_changed)
            parts.append(f"| {i} | {r.subtask_id} | {status} | {duration} | {file_count} |")
        parts.append("")

        # 성공 결과 본문
        if success_results:
            parts.append("## 성공 결과")
            parts.append("")
            for r in success_results:
                parts.append(f"### {r.subtask_id}")
                parts.append("")
                if r.output:
                    parts.append(r.output)
                    parts.append("")
                if r.files_changed:
                    for f in r.files_changed:
                        parts.append(f"- `{f.path}` ({f.change_type})")
                    parts.append("")

        # 실패 상세
        if failed_results:
            parts.append("## 실패 상세")
            parts.append("")
            for r in failed_results:
                parts.append(f"### {r.subtask_id}")
                parts.append("")
                parts.append(f"**에러:** {r.error}")
                parts.append("")

        return "\n".join(parts)

    def _build_checklist(
        self,
        *,
        task_description: str,
        success_results: list[WorkerResult],
        failed_results: list[WorkerResult],
        all_results: list[WorkerResult],
    ) -> str:
        """체크리스트 형태 보고서를 생성한다.

        각 항목의 완료/실패 상태를 체크리스트로 표시.
        """
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        parts: list[str] = []

        parts.append(f"# {task_description} — 체크리스트")
        parts.append(f"\n> {now}")
        parts.append("")

        # 체크리스트
        parts.append("## 태스크 체크리스트")
        parts.append("")
        for r in all_results:
            checkbox = "[x]" if not r.error else "[ ]"
            status = "완료" if not r.error else "실패"
            parts.append(f"- {checkbox} **{r.subtask_id}** — {status}")
            if r.output:
                # 첫 줄만 표시
                first_line = r.output.split("\n")[0][:100]
                parts.append(f"  - {first_line}")
            if r.error:
                parts.append(f"  - 에러: {r.error[:100]}")
            if r.files_changed:
                parts.append(f"  - 변경 파일: {len(r.files_changed)}개")
        parts.append("")

        # 진행률
        total = len(all_results)
        done = len(success_results)
        pct = int(done / total * 100) if total > 0 else 0
        parts.append(f"## 진행률: {done}/{total} ({pct}%)")
        parts.append("")

        # 실패 노트
        if failed_results:
            parts.append("## 실패 항목")
            parts.append("")
            for r in failed_results:
                parts.append(f"- **{r.subtask_id}**: {r.error}")
            parts.append("")

        return "\n".join(parts)
