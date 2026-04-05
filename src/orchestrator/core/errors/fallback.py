"""FallbackChain — CLI provider fallback logic."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import structlog

from orchestrator.core.errors.exceptions import (
    AllProvidersFailedError,
    AuthError,
    CLIError,
)
from orchestrator.core.events.types import EventType, OrchestratorEvent

if TYPE_CHECKING:
    from orchestrator.core.events.bus import EventBus
    from orchestrator.core.executor.base import AgentExecutor
    from orchestrator.core.models.schemas import AgentResult

logger = structlog.get_logger()

# CLI 이름을 받아 AgentExecutor를 생성하는 callable 타입
ExecutorFactory = Callable[[str], "AgentExecutor"]


class FallbackChain:
    """CLI 폴백 체인.

    cli_priority 순서대로 시도하여 첫 번째 성공 결과를 반환한다.
    CLIError/CLITimeoutError 시 다음 CLI로 폴백하고,
    AuthError 시 해당 CLI를 건너뛴다 (재시도 없음).
    모든 CLI가 실패하면 AllProvidersFailedError를 발생시킨다.
    """

    def __init__(
        self,
        event_bus: EventBus,
    ) -> None:
        """
        Args:
            event_bus: 이벤트 버스 (fallback 이벤트 발행용).
        """
        self._event_bus = event_bus

    async def execute_with_fallback(
        self,
        executor_factory: ExecutorFactory,
        prompt: str,
        cli_priority: list[str],
        *,
        task_id: str = "",
        timeout: int = 300,  # noqa: ASYNC109
        context: dict[str, Any] | None = None,
    ) -> tuple[AgentResult, str]:
        """CLI 우선순위 순서대로 실행을 시도하고 첫 번째 성공 결과를 반환한다.

        Args:
            executor_factory: CLI 이름을 받아 AgentExecutor를 생성하는 callable.
            prompt: 에이전트에 전달할 프롬프트.
            cli_priority: CLI 우선순위 목록 (예: ["claude", "codex", "gemini"]).
            task_id: 파이프라인/태스크 ID (이벤트용).
            timeout: 실행 타임아웃 (초).
            context: 추가 컨텍스트.

        Returns:
            (AgentResult, 성공한 cli_name) 튜플.

        Raises:
            AllProvidersFailedError: 모든 CLI가 실패한 경우.
        """
        attempted: list[dict[str, str]] = []

        for cli_name in cli_priority:
            try:
                executor = executor_factory(cli_name)
                result = await executor.run(
                    prompt,
                    timeout=timeout,
                    context=context,
                )

                # 폴백이 발생한 경우 성공 이벤트 발행
                if attempted:
                    await self._event_bus.emit(
                        OrchestratorEvent(
                            type=EventType.FALLBACK_SUCCEEDED,
                            task_id=task_id,
                            node=f"fallback-{cli_name}",
                            data={
                                "cli": cli_name,
                                "attempted_count": len(attempted),
                                "attempted": attempted,
                            },
                        )
                    )

                return result, cli_name

            except AuthError as e:
                # AuthError는 재시도 불가 — 즉시 건너뜀
                logger.warning(
                    "fallback_skip_auth_error",
                    cli=cli_name,
                    error_code=e.error_code,
                    error=str(e),
                )
                attempted.append(
                    {
                        "cli": cli_name,
                        "error_code": e.error_code,
                        "message": str(e),
                    }
                )
                await self._event_bus.emit(
                    OrchestratorEvent(
                        type=EventType.FALLBACK_TRIGGERED,
                        task_id=task_id,
                        node=f"fallback-{cli_name}",
                        data={
                            "failed_cli": cli_name,
                            "error_code": e.error_code,
                            "reason": "auth_error",
                            "skip": True,
                        },
                    )
                )

            except CLIError as e:
                # CLIError → 다음 CLI로 폴백
                logger.warning(
                    "fallback_cli_error",
                    cli=cli_name,
                    error_code=e.error_code,
                    error=str(e),
                )
                attempted.append(
                    {
                        "cli": cli_name,
                        "error_code": e.error_code,
                        "message": str(e),
                    }
                )
                await self._event_bus.emit(
                    OrchestratorEvent(
                        type=EventType.FALLBACK_TRIGGERED,
                        task_id=task_id,
                        node=f"fallback-{cli_name}",
                        data={
                            "failed_cli": cli_name,
                            "error_code": e.error_code,
                            "reason": "cli_error",
                        },
                    )
                )

        # 모든 CLI 소진
        await self._event_bus.emit(
            OrchestratorEvent(
                type=EventType.FALLBACK_EXHAUSTED,
                task_id=task_id,
                node="fallback",
                data={
                    "attempted": attempted,
                    "total_attempted": len(attempted),
                },
            )
        )

        raise AllProvidersFailedError(
            task_id=task_id,
            attempted=attempted,
        )
