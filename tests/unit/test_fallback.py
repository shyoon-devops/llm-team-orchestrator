"""Tests for FallbackChain — CLI provider fallback logic."""

from __future__ import annotations

from typing import Any

import pytest

from orchestrator.core.errors.exceptions import (
    AllProvidersFailedError,
    AuthMissingKeyError,
    CLIExecutionError,
    CLINotFoundError,
    CLITimeoutError,
)
from orchestrator.core.errors.fallback import FallbackChain
from orchestrator.core.events.bus import EventBus
from orchestrator.core.events.types import EventType, OrchestratorEvent
from orchestrator.core.executor.base import AgentExecutor
from orchestrator.core.models.schemas import AgentResult

# ── Mock Executors ──────────────────────────────────────────────────────


class SuccessExecutor(AgentExecutor):
    """항상 성공하는 executor."""

    executor_type: str = "mock"

    def __init__(self, cli_name: str = "mock") -> None:
        self.cli_name = cli_name

    async def run(
        self,
        prompt: str,
        *,
        timeout: int = 300,  # noqa: ASYNC109
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        return AgentResult(output=f"success from {self.cli_name}", exit_code=0)

    async def health_check(self) -> bool:
        return True


class TimeoutExecutor(AgentExecutor):
    """항상 CLITimeoutError를 발생시키는 executor."""

    executor_type: str = "mock"

    def __init__(self, cli_name: str = "mock") -> None:
        self.cli_name = cli_name

    async def run(
        self,
        prompt: str,
        *,
        timeout: int = 300,  # noqa: ASYNC109
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        raise CLITimeoutError(
            f"{self.cli_name} timed out",
            cli=self.cli_name,
            timeout_seconds=timeout,
        )

    async def health_check(self) -> bool:
        return True


class AuthFailExecutor(AgentExecutor):
    """항상 AuthError를 발생시키는 executor."""

    executor_type: str = "mock"

    def __init__(self, cli_name: str = "mock") -> None:
        self.cli_name = cli_name

    async def run(
        self,
        prompt: str,
        *,
        timeout: int = 300,  # noqa: ASYNC109
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        raise AuthMissingKeyError(provider="test", env_var="TEST_KEY")

    async def health_check(self) -> bool:
        return True


class CLIErrorExecutor(AgentExecutor):
    """항상 CLIExecutionError를 발생시키는 executor."""

    executor_type: str = "mock"

    def __init__(self, cli_name: str = "mock") -> None:
        self.cli_name = cli_name

    async def run(
        self,
        prompt: str,
        *,
        timeout: int = 300,  # noqa: ASYNC109
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        raise CLIExecutionError(
            f"{self.cli_name} failed",
            cli=self.cli_name,
            exit_code=1,
        )

    async def health_check(self) -> bool:
        return True


class CLINotFoundExecutor(AgentExecutor):
    """항상 CLINotFoundError를 발생시키는 executor."""

    executor_type: str = "mock"

    def __init__(self, cli_name: str = "mock") -> None:
        self.cli_name = cli_name

    async def run(
        self,
        prompt: str,
        *,
        timeout: int = 300,  # noqa: ASYNC109
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        raise CLINotFoundError(
            f"{self.cli_name} not found",
            cli=self.cli_name,
        )

    async def health_check(self) -> bool:
        return False


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def captured_events(event_bus: EventBus) -> list[OrchestratorEvent]:
    events: list[OrchestratorEvent] = []

    async def _capture(event: OrchestratorEvent) -> None:
        events.append(event)

    event_bus.subscribe(_capture)
    return events


@pytest.fixture
def fallback_chain(event_bus: EventBus) -> FallbackChain:
    return FallbackChain(event_bus=event_bus)


# ── Tests ───────────────────────────────────────────────────────────────


async def test_fallback_first_cli_succeeds(
    fallback_chain: FallbackChain,
) -> None:
    """첫 번째 CLI가 성공하면 바로 결과를 반환한다."""

    def factory(cli_name: str) -> AgentExecutor:
        return SuccessExecutor(cli_name)

    result, used_cli = await fallback_chain.execute_with_fallback(
        factory,
        "test prompt",
        ["claude", "codex", "gemini"],
    )
    assert result.output == "success from claude"
    assert used_cli == "claude"


async def test_fallback_tries_next_on_timeout(
    fallback_chain: FallbackChain,
    captured_events: list[OrchestratorEvent],
) -> None:
    """첫 번째 CLI가 타임아웃되면 다음 CLI로 폴백한다."""
    executors: dict[str, AgentExecutor] = {
        "claude": TimeoutExecutor("claude"),
        "codex": SuccessExecutor("codex"),
        "gemini": SuccessExecutor("gemini"),
    }

    def factory(cli_name: str) -> AgentExecutor:
        return executors[cli_name]

    result, used_cli = await fallback_chain.execute_with_fallback(
        factory,
        "test prompt",
        ["claude", "codex", "gemini"],
        task_id="task-001",
    )
    assert result.output == "success from codex"
    assert used_cli == "codex"

    # FALLBACK_TRIGGERED 이벤트 확인
    triggered = [e for e in captured_events if e.type == EventType.FALLBACK_TRIGGERED]
    assert len(triggered) == 1
    assert triggered[0].data["failed_cli"] == "claude"

    # FALLBACK_SUCCEEDED 이벤트 확인
    succeeded = [e for e in captured_events if e.type == EventType.FALLBACK_SUCCEEDED]
    assert len(succeeded) == 1
    assert succeeded[0].data["cli"] == "codex"


async def test_fallback_skips_auth_error(
    fallback_chain: FallbackChain,
    captured_events: list[OrchestratorEvent],
) -> None:
    """AuthError 발생 시 해당 CLI를 건너뛰고 다음으로 폴백한다."""
    executors: dict[str, AgentExecutor] = {
        "claude": AuthFailExecutor("claude"),
        "codex": AuthFailExecutor("codex"),
        "gemini": SuccessExecutor("gemini"),
    }

    def factory(cli_name: str) -> AgentExecutor:
        return executors[cli_name]

    result, used_cli = await fallback_chain.execute_with_fallback(
        factory,
        "test prompt",
        ["claude", "codex", "gemini"],
        task_id="task-002",
    )
    assert result.output == "success from gemini"
    assert used_cli == "gemini"

    # AuthError로 인한 FALLBACK_TRIGGERED 이벤트 확인
    triggered = [e for e in captured_events if e.type == EventType.FALLBACK_TRIGGERED]
    assert len(triggered) == 2
    assert all(e.data.get("reason") == "auth_error" for e in triggered)


async def test_fallback_all_failed_raises(
    fallback_chain: FallbackChain,
    captured_events: list[OrchestratorEvent],
) -> None:
    """모든 CLI가 실패하면 AllProvidersFailedError를 발생시킨다."""

    def factory(cli_name: str) -> AgentExecutor:
        return TimeoutExecutor(cli_name)

    with pytest.raises(AllProvidersFailedError) as exc_info:
        await fallback_chain.execute_with_fallback(
            factory,
            "test prompt",
            ["claude", "codex", "gemini"],
            task_id="task-003",
        )

    err = exc_info.value
    assert err.task_id == "task-003"
    assert len(err.attempted) == 3
    assert err.attempted[0]["cli"] == "claude"
    assert err.attempted[1]["cli"] == "codex"
    assert err.attempted[2]["cli"] == "gemini"


async def test_fallback_emits_event(
    fallback_chain: FallbackChain,
    captured_events: list[OrchestratorEvent],
) -> None:
    """폴백 과정에서 올바른 이벤트가 발행되는지 확인한다."""
    executors: dict[str, AgentExecutor] = {
        "claude": CLIErrorExecutor("claude"),
        "codex": CLINotFoundExecutor("codex"),
        "gemini": SuccessExecutor("gemini"),
    }

    def factory(cli_name: str) -> AgentExecutor:
        return executors[cli_name]

    _result, used_cli = await fallback_chain.execute_with_fallback(
        factory,
        "test prompt",
        ["claude", "codex", "gemini"],
        task_id="task-004",
    )
    assert used_cli == "gemini"

    # 이벤트 순서 확인
    event_types = [e.type for e in captured_events]
    assert EventType.FALLBACK_TRIGGERED in event_types
    assert EventType.FALLBACK_SUCCEEDED in event_types

    # 각 실패한 CLI에 대해 FALLBACK_TRIGGERED 이벤트가 발행됨
    triggered = [e for e in captured_events if e.type == EventType.FALLBACK_TRIGGERED]
    assert len(triggered) == 2
    failed_clis = [e.data["failed_cli"] for e in triggered]
    assert "claude" in failed_clis
    assert "codex" in failed_clis


async def test_fallback_exhausted_emits_event(
    fallback_chain: FallbackChain,
    captured_events: list[OrchestratorEvent],
) -> None:
    """모든 CLI 소진 시 FALLBACK_EXHAUSTED 이벤트가 발행된다."""

    def factory(cli_name: str) -> AgentExecutor:
        return CLIErrorExecutor(cli_name)

    with pytest.raises(AllProvidersFailedError):
        await fallback_chain.execute_with_fallback(
            factory,
            "test prompt",
            ["claude", "codex"],
            task_id="task-005",
        )

    exhausted = [e for e in captured_events if e.type == EventType.FALLBACK_EXHAUSTED]
    assert len(exhausted) == 1
    assert exhausted[0].data["total_attempted"] == 2


async def test_fallback_single_cli_success(
    fallback_chain: FallbackChain,
) -> None:
    """단일 CLI로 성공하면 fallback 이벤트 없이 결과를 반환한다."""

    def factory(cli_name: str) -> AgentExecutor:
        return SuccessExecutor(cli_name)

    result, used_cli = await fallback_chain.execute_with_fallback(
        factory,
        "test prompt",
        ["claude"],
    )
    assert result.output == "success from claude"
    assert used_cli == "claude"


async def test_fallback_mixed_errors(
    fallback_chain: FallbackChain,
) -> None:
    """AuthError와 CLIError가 혼합된 경우에도 올바르게 폴백한다."""
    executors: dict[str, AgentExecutor] = {
        "claude": AuthFailExecutor("claude"),
        "codex": TimeoutExecutor("codex"),
        "gemini": CLIErrorExecutor("gemini"),
    }

    def factory(cli_name: str) -> AgentExecutor:
        return executors[cli_name]

    with pytest.raises(AllProvidersFailedError) as exc_info:
        await fallback_chain.execute_with_fallback(
            factory,
            "test prompt",
            ["claude", "codex", "gemini"],
            task_id="task-006",
        )

    err = exc_info.value
    assert len(err.attempted) == 3
    assert err.attempted[0]["error_code"] == "AUTH_MISSING_KEY"
    assert err.attempted[1]["error_code"] == "CLI_TIMEOUT"
    assert err.attempted[2]["error_code"] == "CLI_EXECUTION_ERROR"
