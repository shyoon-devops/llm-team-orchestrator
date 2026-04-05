"""Tests for Phase 3 — hybrid orchestration pipeline (engine integration)."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import pytest

from orchestrator.core.config.schema import OrchestratorConfig
from orchestrator.core.engine import OrchestratorEngine
from orchestrator.core.events.types import EventType, OrchestratorEvent
from orchestrator.core.executor.base import AgentExecutor
from orchestrator.core.models.pipeline import PipelineStatus
from orchestrator.core.models.schemas import AgentResult
from orchestrator.core.presets.models import (
    TeamAgentDef,
    TeamPreset,
    TeamTaskDef,
)

# ── Mock Executor ────────────────────────────────────────────────────


class MockAgentExecutor(AgentExecutor):
    """테스트용 mock agent executor.

    실제 CLI 호출 없이 즉시 AgentResult를 반환한다.
    """

    executor_type: str = "mock"

    def __init__(
        self,
        *,
        output: str = "Mock output",
        fail: bool = False,
        delay: float = 0.0,
    ) -> None:
        self.output = output
        self.fail = fail
        self.delay = delay
        self.cli_name: str = "mock"
        self.run_count = 0

    async def run(
        self,
        prompt: str,
        *,
        timeout: int = 300,  # noqa: ASYNC109
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        self.run_count += 1
        if self.delay > 0:
            await asyncio.sleep(self.delay)
        if self.fail:
            msg = "MockAgentExecutor forced failure"
            raise RuntimeError(msg)
        return AgentResult(
            output=f"{self.output}: {prompt[:50]}",
            exit_code=0,
            duration_ms=100,
            tokens_used=50,
        )

    async def health_check(self) -> bool:
        return True


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def mock_config() -> OrchestratorConfig:
    return OrchestratorConfig(
        default_timeout=10,
        default_max_retries=2,
        log_level="DEBUG",
        cli_priority=["claude", "codex", "gemini"],
        worktree_base_dir="/tmp/test-worktrees",
        api_host="127.0.0.1",
        api_port=8888,
        preset_dirs=["tests/mocks/fixtures"],
    )


@pytest.fixture
def engine(mock_config: OrchestratorConfig) -> OrchestratorEngine:
    return OrchestratorEngine(config=mock_config)


@pytest.fixture
def sample_team_preset() -> TeamPreset:
    return TeamPreset(
        name="test-team",
        description="테스트 팀",
        agents={
            "architect": TeamAgentDef(preset="architect"),
            "implementer": TeamAgentDef(preset="implementer"),
        },
        tasks={
            "design": TeamTaskDef(
                description="시스템 설계",
                agent="architect",
                depends_on=[],
            ),
            "implement": TeamTaskDef(
                description="코드 구현",
                agent="implementer",
                depends_on=["design"],
            ),
        },
        workflow="dag",
        synthesis_strategy="narrative",
    )


@pytest.fixture
def captured_events(engine: OrchestratorEngine) -> list[OrchestratorEvent]:
    events: list[OrchestratorEvent] = []

    async def _capture(event: OrchestratorEvent) -> None:
        events.append(event)

    engine.subscribe(_capture)
    return events


# ── Helper ───────────────────────────────────────────────────────────


def _patch_executor(engine: OrchestratorEngine, executor: AgentExecutor) -> None:
    """Engine의 _create_executor_for_preset을 mock으로 교체한다."""
    engine._create_executor_for_preset = lambda *_args, **_kwargs: executor  # type: ignore[assignment]


# ── T3.4 Tests ───────────────────────────────────────────────────────


async def test_submit_task_creates_pipeline(
    engine: OrchestratorEngine,
    captured_events: list[OrchestratorEvent],
) -> None:
    """submit_task()가 Pipeline을 생성하고 PENDING 상태로 반환하는지 확인."""
    mock_exec = MockAgentExecutor(output="designed result")
    _patch_executor(engine, mock_exec)

    pipeline = await engine.submit_task("JWT 인증 구현")

    assert pipeline.task_id.startswith("pipeline-")
    assert pipeline.task == "JWT 인증 구현"
    assert pipeline.status == PipelineStatus.PENDING

    # PIPELINE_CREATED 이벤트 확인
    created_events = [e for e in captured_events if e.type == EventType.PIPELINE_CREATED]
    assert len(created_events) >= 1
    assert created_events[0].task_id == pipeline.task_id

    # Background task가 pipeline을 완료할 때까지 대기
    await asyncio.sleep(0.5)


async def test_pipeline_decomposes_and_distributes(
    engine: OrchestratorEngine,
    sample_team_preset: TeamPreset,
    captured_events: list[OrchestratorEvent],
) -> None:
    """submit_task()가 TeamPlanner로 분해 후 TaskBoard에 투입하는 전체 흐름을 확인."""
    mock_exec = MockAgentExecutor(output="implemented")
    _patch_executor(engine, mock_exec)

    # 팀 프리셋 등록
    engine._preset_registry._team_presets["test-team"] = sample_team_preset

    pipeline = await engine.submit_task(
        "JWT 인증 미들웨어 구현",
        team_preset="test-team",
    )

    # 파이프라인 완료 대기
    for _ in range(50):
        current = await engine.get_pipeline(pipeline.task_id)
        if current and current.status in (
            PipelineStatus.COMPLETED,
            PipelineStatus.PARTIAL_FAILURE,
            PipelineStatus.FAILED,
        ):
            break
        await asyncio.sleep(0.1)

    final = await engine.get_pipeline(pipeline.task_id)
    assert final is not None
    assert final.status == PipelineStatus.COMPLETED

    # 서브태스크가 분해되었는지 확인
    assert len(final.subtasks) == 2

    # 결과가 수집되었는지 확인
    assert len(final.results) == 2

    # 종합 보고서가 생성되었는지 확인
    assert final.synthesis != ""
    assert "종합 보고서" in final.synthesis

    # 이벤트 흐름 확인
    event_types = [e.type for e in captured_events]
    assert EventType.PIPELINE_CREATED in event_types
    assert EventType.PIPELINE_PLANNING in event_types
    assert EventType.PIPELINE_RUNNING in event_types


async def test_pipeline_respects_dependencies(
    engine: OrchestratorEngine,
    sample_team_preset: TeamPreset,
) -> None:
    """서브태스크 의존성(depends_on)이 올바르게 처리되는지 확인."""
    execution_order: list[str] = []
    original_output = "done"

    class OrderTrackingExecutor(AgentExecutor):
        executor_type: str = "mock"

        def __init__(self) -> None:
            self.cli_name: str = "mock"

        async def run(
            self,
            prompt: str,
            *,
            timeout: int = 300,  # noqa: ASYNC109
            context: dict[str, Any] | None = None,
        ) -> AgentResult:
            execution_order.append(prompt[:20])
            return AgentResult(output=original_output, exit_code=0)

        async def health_check(self) -> bool:
            return True

    _patch_executor(engine, OrderTrackingExecutor())
    engine._preset_registry._team_presets["test-team"] = sample_team_preset

    pipeline = await engine.submit_task(
        "의존성 테스트 태스크",
        team_preset="test-team",
    )

    # 파이프라인 완료 대기
    for _ in range(50):
        current = await engine.get_pipeline(pipeline.task_id)
        if current and current.status in (
            PipelineStatus.COMPLETED,
            PipelineStatus.FAILED,
        ):
            break
        await asyncio.sleep(0.1)

    final = await engine.get_pipeline(pipeline.task_id)
    assert final is not None
    assert final.status == PipelineStatus.COMPLETED

    # "설계" 태스크가 "구현" 태스크보다 먼저 실행되어야 한다
    # 최소한 설계가 완료되어야 구현이 시작되므로, 2개 태스크가 실행되어야 한다
    assert len(execution_order) == 2
    # 첫 실행은 설계(design)이어야 한다 — "시스템 설계"
    assert "시스템 설계" in execution_order[0]


async def test_pipeline_synthesizes_results(
    engine: OrchestratorEngine,
) -> None:
    """파이프라인 완료 후 Synthesizer가 종합 보고서를 생성하는지 확인."""
    mock_exec = MockAgentExecutor(output="implementation complete")
    _patch_executor(engine, mock_exec)

    pipeline = await engine.submit_task("간단한 태스크")

    # 자동 팀 구성 → 단일 implementer로 1개 서브태스크
    for _ in range(50):
        current = await engine.get_pipeline(pipeline.task_id)
        if current and current.status in (
            PipelineStatus.COMPLETED,
            PipelineStatus.FAILED,
        ):
            break
        await asyncio.sleep(0.1)

    final = await engine.get_pipeline(pipeline.task_id)
    assert final is not None
    assert final.status == PipelineStatus.COMPLETED
    assert final.synthesis != ""
    assert len(final.results) >= 1

    # WorkerResult에 output이 있는지 확인
    success_results = [r for r in final.results if r.output]
    assert len(success_results) >= 1


async def test_pipeline_with_target_repo(
    engine: OrchestratorEngine,
    captured_events: list[OrchestratorEvent],
) -> None:
    """target_repo 설정 시 worktree 생성/정리 흐름을 확인."""
    mock_exec = MockAgentExecutor(output="worktree result")
    _patch_executor(engine, mock_exec)

    # WorktreeManager를 mock으로 교체
    engine._worktree_manager.create = AsyncMock(return_value="/tmp/fake-worktree")  # type: ignore[method-assign]
    engine._worktree_manager.cleanup = AsyncMock()  # type: ignore[method-assign]
    engine._worktree_manager.merge_to_target = AsyncMock(return_value=True)  # type: ignore[method-assign]

    pipeline = await engine.submit_task(
        "worktree 태스크",
        target_repo="/tmp/fake-repo",
    )

    # 완료 대기
    for _ in range(50):
        current = await engine.get_pipeline(pipeline.task_id)
        if current and current.status in (
            PipelineStatus.COMPLETED,
            PipelineStatus.FAILED,
        ):
            break
        await asyncio.sleep(0.1)

    final = await engine.get_pipeline(pipeline.task_id)
    assert final is not None
    assert final.status == PipelineStatus.COMPLETED

    # Worktree 생성이 호출되었는지 확인
    engine._worktree_manager.create.assert_called()  # type: ignore[union-attr]

    # Worktree merge가 호출되었는지 확인 (auto_merge=True)
    engine._worktree_manager.merge_to_target.assert_called()  # type: ignore[union-attr]

    # Cleanup이 호출되었는지 확인
    engine._worktree_manager.cleanup.assert_called()  # type: ignore[union-attr]

    # WORKTREE_CREATED 이벤트 확인
    wt_events = [e for e in captured_events if e.type == EventType.WORKTREE_CREATED]
    assert len(wt_events) >= 1


async def test_pipeline_handles_all_subtasks_failed(
    engine: OrchestratorEngine,
) -> None:
    """모든 서브태스크가 실패할 경우 Pipeline이 FAILED로 전이되는지 확인."""
    mock_exec = MockAgentExecutor(fail=True)
    _patch_executor(engine, mock_exec)

    pipeline = await engine.submit_task("실패하는 태스크")

    for _ in range(100):
        current = await engine.get_pipeline(pipeline.task_id)
        if current and current.status in (
            PipelineStatus.COMPLETED,
            PipelineStatus.FAILED,
        ):
            break
        await asyncio.sleep(0.1)

    final = await engine.get_pipeline(pipeline.task_id)
    assert final is not None
    assert final.status == PipelineStatus.FAILED


async def test_cancel_during_execution(
    engine: OrchestratorEngine,
) -> None:
    """실행 중 cancel_task()가 파이프라인을 취소하는지 확인."""
    mock_exec = MockAgentExecutor(output="slow task", delay=5.0)
    _patch_executor(engine, mock_exec)

    pipeline = await engine.submit_task("취소할 태스크")

    # 잠시 실행 대기
    await asyncio.sleep(0.2)

    # 취소
    result = await engine.cancel_task(pipeline.task_id)
    assert result is True

    final = await engine.get_pipeline(pipeline.task_id)
    assert final is not None
    assert final.status == PipelineStatus.CANCELLED

    # Background task 정리 대기
    await asyncio.sleep(0.5)


async def test_submit_empty_task_raises(engine: OrchestratorEngine) -> None:
    """빈 태스크 제출 시 ValueError가 발생하는지 확인."""
    with pytest.raises(ValueError, match="empty"):
        await engine.submit_task("")


async def test_submit_task_invalid_preset_raises(engine: OrchestratorEngine) -> None:
    """존재하지 않는 팀 프리셋 지정 시 KeyError가 발생하는지 확인."""
    with pytest.raises(KeyError):
        await engine.submit_task("task", team_preset="nonexistent-preset")


async def test_pipeline_auto_team_creates_single_subtask(
    engine: OrchestratorEngine,
) -> None:
    """team_preset 없이 제출하면 자동 팀(단일 implementer)이 구성되는지 확인."""
    mock_exec = MockAgentExecutor(output="auto result")
    _patch_executor(engine, mock_exec)

    pipeline = await engine.submit_task("자동 팀 태스크")

    for _ in range(50):
        current = await engine.get_pipeline(pipeline.task_id)
        if current and current.status in (
            PipelineStatus.COMPLETED,
            PipelineStatus.FAILED,
        ):
            break
        await asyncio.sleep(0.1)

    final = await engine.get_pipeline(pipeline.task_id)
    assert final is not None
    assert final.status == PipelineStatus.COMPLETED
    # 자동 팀은 1개 서브태스크 생성
    assert len(final.subtasks) == 1
    assert final.subtasks[0].assigned_preset == "implementer"


async def test_board_state_after_pipeline(
    engine: OrchestratorEngine,
    sample_team_preset: TeamPreset,
) -> None:
    """파이프라인 완료 후 TaskBoard 상태를 확인."""
    mock_exec = MockAgentExecutor(output="result")
    _patch_executor(engine, mock_exec)

    engine._preset_registry._team_presets["test-team"] = sample_team_preset

    pipeline = await engine.submit_task(
        "보드 상태 태스크",
        team_preset="test-team",
    )

    for _ in range(50):
        current = await engine.get_pipeline(pipeline.task_id)
        if current and current.status in (
            PipelineStatus.COMPLETED,
            PipelineStatus.FAILED,
        ):
            break
        await asyncio.sleep(0.1)

    # 보드에서 해당 파이프라인의 태스크가 모두 DONE인지 확인
    board_state = engine.get_board_state()
    assert board_state["summary"]["total"] >= 2

    # 모든 태스크가 터미널 상태
    assert engine._board.is_all_done(pipeline.task_id)
