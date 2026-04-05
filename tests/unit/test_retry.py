"""Tests for RetryPolicy — tenacity-based retry for CLI adapter calls."""

from __future__ import annotations

from typing import Any

import pytest

from orchestrator.core.errors.exceptions import (
    AuthMissingKeyError,
    CLIExecutionError,
    CLINotFoundError,
    CLIParseError,
    CLITimeoutError,
)
from orchestrator.core.errors.retry import RetryPolicy
from orchestrator.core.executor.base import AgentExecutor
from orchestrator.core.models.schemas import AgentResult

# ── Mock Executors ──────────────────────────────────────────────────────


class CountingExecutor(AgentExecutor):
    """호출 횟수를 추적하는 executor.

    fail_times 횟수만큼 실패한 후 성공한다.
    """

    executor_type: str = "mock"

    def __init__(
        self,
        *,
        fail_times: int = 0,
        error_cls: type[Exception] = CLITimeoutError,
        cli_name: str = "mock",
    ) -> None:
        self.fail_times = fail_times
        self.error_cls = error_cls
        self.cli_name = cli_name
        self.call_count = 0

    async def run(
        self,
        prompt: str,
        *,
        timeout: int = 300,  # noqa: ASYNC109
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        self.call_count += 1
        if self.call_count <= self.fail_times:
            if self.error_cls is CLITimeoutError:
                raise CLITimeoutError(
                    "timed out",
                    cli=self.cli_name,
                    timeout_seconds=timeout,
                )
            elif self.error_cls is CLIExecutionError:
                raise CLIExecutionError(
                    "execution failed",
                    cli=self.cli_name,
                    exit_code=1,
                )
            elif self.error_cls is CLINotFoundError:
                raise CLINotFoundError(
                    "not found",
                    cli=self.cli_name,
                )
            elif self.error_cls is CLIParseError:
                raise CLIParseError(
                    "parse error",
                    cli=self.cli_name,
                    raw_output="invalid json",
                )
            elif self.error_cls is AuthMissingKeyError:
                raise AuthMissingKeyError(
                    provider="test",
                    env_var="TEST_KEY",
                )
            else:
                raise self.error_cls("generic error")  # type: ignore[call-arg]
        return AgentResult(output=f"success on attempt {self.call_count}", exit_code=0)

    async def health_check(self) -> bool:
        return True


# ── Tests ───────────────────────────────────────────────────────────────


async def test_retry_on_timeout() -> None:
    """CLITimeoutError 발생 시 재시도하고 성공한다."""
    executor = CountingExecutor(fail_times=2, error_cls=CLITimeoutError)
    policy = RetryPolicy(max_attempts=3, base_delay=0.01, max_delay=0.1)

    result = await policy.execute_with_retry(executor, "test prompt")
    assert result.output == "success on attempt 3"
    assert executor.call_count == 3


async def test_retry_on_execution_error() -> None:
    """CLIExecutionError 발생 시 재시도하고 성공한다."""
    executor = CountingExecutor(fail_times=1, error_cls=CLIExecutionError)
    policy = RetryPolicy(max_attempts=3, base_delay=0.01, max_delay=0.1)

    result = await policy.execute_with_retry(executor, "test prompt")
    assert result.output == "success on attempt 2"
    assert executor.call_count == 2


async def test_no_retry_on_auth_error() -> None:
    """AuthError 발생 시 재시도하지 않고 즉시 실패한다."""
    executor = CountingExecutor(fail_times=10, error_cls=AuthMissingKeyError)
    policy = RetryPolicy(max_attempts=3, base_delay=0.01, max_delay=0.1)

    with pytest.raises(AuthMissingKeyError):
        await policy.execute_with_retry(executor, "test prompt")

    # AuthError는 재시도하지 않으므로 1회만 호출
    assert executor.call_count == 1


async def test_no_retry_on_cli_not_found() -> None:
    """CLINotFoundError 발생 시 재시도하지 않고 즉시 실패한다."""
    executor = CountingExecutor(fail_times=10, error_cls=CLINotFoundError)
    policy = RetryPolicy(max_attempts=3, base_delay=0.01, max_delay=0.1)

    with pytest.raises(CLINotFoundError):
        await policy.execute_with_retry(executor, "test prompt")

    assert executor.call_count == 1


async def test_no_retry_on_parse_error() -> None:
    """CLIParseError 발생 시 재시도하지 않고 즉시 실패한다."""
    executor = CountingExecutor(fail_times=10, error_cls=CLIParseError)
    policy = RetryPolicy(max_attempts=3, base_delay=0.01, max_delay=0.1)

    with pytest.raises(CLIParseError):
        await policy.execute_with_retry(executor, "test prompt")

    assert executor.call_count == 1


async def test_max_retries_then_fail() -> None:
    """최대 재시도 횟수 초과 시 마지막 에러를 발생시킨다."""
    executor = CountingExecutor(fail_times=100, error_cls=CLITimeoutError)
    policy = RetryPolicy(max_attempts=3, base_delay=0.01, max_delay=0.1)

    with pytest.raises(CLITimeoutError):
        await policy.execute_with_retry(executor, "test prompt")

    # max_attempts=3이므로 3회 호출 후 실패
    assert executor.call_count == 3


async def test_retry_succeeds_on_first_try() -> None:
    """첫 번째 시도에 성공하면 재시도 없이 바로 반환한다."""
    executor = CountingExecutor(fail_times=0)
    policy = RetryPolicy(max_attempts=3, base_delay=0.01)

    result = await policy.execute_with_retry(executor, "test prompt")
    assert result.output == "success on attempt 1"
    assert executor.call_count == 1


async def test_retry_policy_custom_config() -> None:
    """커스텀 재시도 설정이 올바르게 적용되는지 확인한다."""
    executor = CountingExecutor(fail_times=4, error_cls=CLITimeoutError)
    policy = RetryPolicy(max_attempts=5, base_delay=0.01, max_delay=0.1)

    result = await policy.execute_with_retry(executor, "test prompt")
    assert result.output == "success on attempt 5"
    assert executor.call_count == 5


async def test_retry_context_passed() -> None:
    """context 파라미터가 executor에 올바르게 전달되는지 확인한다."""
    received_context: dict[str, Any] = {}

    class ContextCapture(AgentExecutor):
        executor_type: str = "mock"

        async def run(
            self,
            prompt: str,
            *,
            timeout: int = 300,  # noqa: ASYNC109
            context: dict[str, Any] | None = None,
        ) -> AgentResult:
            if context:
                received_context.update(context)
            return AgentResult(output="done", exit_code=0)

        async def health_check(self) -> bool:
            return True

    executor = ContextCapture()
    policy = RetryPolicy(max_attempts=3, base_delay=0.01)

    await policy.execute_with_retry(
        executor,
        "prompt",
        context={"key": "value"},
    )
    assert received_context == {"key": "value"}
