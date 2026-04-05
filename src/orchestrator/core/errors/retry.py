"""RetryPolicy — tenacity-based retry for CLI adapter calls."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from orchestrator.core.errors.exceptions import (
    AuthError,
    CLIError,
    CLINotFoundError,
    CLIParseError,
)

if TYPE_CHECKING:
    from orchestrator.core.executor.base import AgentExecutor
    from orchestrator.core.models.schemas import AgentResult

logger = structlog.get_logger()


def _is_retryable_error(exc: BaseException) -> bool:
    """재시도 가능한 에러인지 판단한다.

    재시도 대상:
    - CLITimeoutError: 항상 재시도
    - CLIExecutionError: exit code 137/139 제외하고 재시도

    재시도 불가:
    - AuthError: 인증 문제는 재시도로 해결 불가
    - CLINotFoundError: 바이너리 없음은 재시도로 해결 불가
    - CLIParseError: 파싱 오류는 재시도 불가 (동일 출력 예상)

    Args:
        exc: 발생한 예외.

    Returns:
        재시도 가능하면 True.
    """
    if isinstance(exc, AuthError):
        return False
    if isinstance(exc, CLINotFoundError):
        return False
    if isinstance(exc, CLIParseError):
        return False
    if isinstance(exc, CLIError):
        return exc.retryable
    return False


def _log_retry(retry_state: RetryCallState) -> None:
    """재시도 시 로깅 콜백."""
    attempt = retry_state.attempt_number
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    logger.info(
        "retry_attempt",
        attempt=attempt,
        error=str(exc) if exc else "unknown",
        error_type=type(exc).__name__ if exc else "unknown",
    )


class RetryPolicy:
    """CLI 실행 재시도 정책.

    지수 백오프(1s, 2s, 4s)로 최대 3회 재시도한다.
    재시도 가능한 에러(CLITimeoutError, CLIExecutionError)에서만 재시도하고,
    재시도 불가 에러(AuthError, CLINotFoundError, CLIParseError)에서는 즉시 실패한다.

    Attributes:
        max_attempts: 최대 시도 횟수 (재시도 포함).
        base_delay: 기본 대기 시간 (초).
        max_delay: 최대 대기 시간 (초).
    """

    def __init__(
        self,
        *,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
    ) -> None:
        """
        Args:
            max_attempts: 최대 시도 횟수. 기본값 3.
            base_delay: 지수 백오프 기본 대기 시간 (초). 기본값 1.0.
            max_delay: 최대 대기 시간 (초). 기본값 60.0.
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay

    async def execute_with_retry(
        self,
        executor: AgentExecutor,
        prompt: str,
        *,
        timeout: int = 300,  # noqa: ASYNC109
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        """재시도 정책을 적용하여 에이전트를 실행한다.

        Args:
            executor: 에이전트 실행기.
            prompt: 프롬프트 문자열.
            timeout: 실행 타임아웃 (초).
            context: 추가 컨텍스트.

        Returns:
            AgentResult: 실행 결과.

        Raises:
            CLIError: 모든 재시도 후에도 실패한 경우 마지막 예외.
            AuthError: 재시도 불가 인증 에러.
            CLINotFoundError: CLI 바이너리 없음.
        """

        @retry(
            retry=retry_if_exception(_is_retryable_error),
            stop=stop_after_attempt(self.max_attempts),
            wait=wait_exponential(
                multiplier=self.base_delay,
                max=self.max_delay,
            ),
            before_sleep=_log_retry,
            reraise=True,
        )
        async def _run() -> AgentResult:
            return await executor.run(
                prompt,
                timeout=timeout,
                context=context,
            )

        return await _run()
