"""Tests for partial failure handling + synthesizer failure notes."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from orchestrator.core.config.schema import OrchestratorConfig
from orchestrator.core.engine import OrchestratorEngine
from orchestrator.core.events.synthesizer import Synthesizer
from orchestrator.core.events.types import EventType, OrchestratorEvent
from orchestrator.core.executor.base import AgentExecutor
from orchestrator.core.models.pipeline import PipelineStatus, WorkerResult
from orchestrator.core.models.schemas import AgentResult
from orchestrator.core.presets.models import (
    TeamAgentDef,
    TeamPreset,
    TeamTaskDef,
)

# ── Mock Executors ──────────────────────────────────────────────────────


class SelectiveFailExecutor(AgentExecutor):
    """특정 프롬프트에 대해서만 실패하는 executor.

    fail_keywords에 포함된 키워드가 프롬프트에 있으면 실패한다.
    """

    executor_type: str = "mock"

    def __init__(
        self,
        *,
        fail_keywords: list[str] | None = None,
    ) -> None:
        self.fail_keywords = fail_keywords or []
        self.cli_name: str = "mock"

    async def run(
        self,
        prompt: str,
        *,
        timeout: int = 300,  # noqa: ASYNC109
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        for keyword in self.fail_keywords:
            if keyword in prompt:
                msg = f"Forced failure for keyword: {keyword}"
                raise RuntimeError(msg)
        return AgentResult(
            output=f"success: {prompt[:50]}",
            exit_code=0,
            duration_ms=100,
        )

    async def health_check(self) -> bool:
        return True


class AlwaysFailExecutor(AgentExecutor):
    """항상 실패하는 executor."""

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
        msg = "Always fails"
        raise RuntimeError(msg)

    async def health_check(self) -> bool:
        return True


class AlwaysSuccessExecutor(AgentExecutor):
    """항상 성공하는 executor."""

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
        return AgentResult(
            output=f"done: {prompt[:50]}",
            exit_code=0,
            duration_ms=50,
        )

    async def health_check(self) -> bool:
        return True


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def mock_config() -> OrchestratorConfig:
    return OrchestratorConfig(
        default_timeout=10,
        default_max_retries=1,  # 빠른 실패를 위해 1로 설정
        log_level="DEBUG",
        cli_priority=["claude", "codex", "gemini"],
        worktree_base_dir="/tmp/test-worktrees",
        api_host="127.0.0.1",
        api_port=8888,
        preset_dirs=["tests/mocks/fixtures"],
        planner_use_llm=False,
    )


@pytest.fixture
def engine(mock_config: OrchestratorConfig) -> OrchestratorEngine:
    return OrchestratorEngine(config=mock_config)


@pytest.fixture
def captured_events(engine: OrchestratorEngine) -> list[OrchestratorEvent]:
    events: list[OrchestratorEvent] = []

    async def _capture(event: OrchestratorEvent) -> None:
        events.append(event)

    engine.subscribe(_capture)
    return events


@pytest.fixture
def three_task_preset() -> TeamPreset:
    """3개 서브태스크가 있는 팀 프리셋 (모두 같은 에이전트)."""
    return TeamPreset(
        name="three-task-team",
        description="3개 태스크 팀",
        agents={
            "worker": TeamAgentDef(preset="implementer"),
        },
        tasks={
            "task-a": TeamTaskDef(
                description="태스크 A 구현",
                agent="worker",
                depends_on=[],
            ),
            "task-b": TeamTaskDef(
                description="태스크 B 구현",
                agent="worker",
                depends_on=[],
            ),
            "task-c": TeamTaskDef(
                description="태스크 C 구현",
                agent="worker",
                depends_on=[],
            ),
        },
        workflow="parallel",
        synthesis_strategy="narrative",
    )


@pytest.fixture
def four_task_preset() -> TeamPreset:
    """4개 서브태스크가 있는 팀 프리셋."""
    return TeamPreset(
        name="four-task-team",
        description="4개 태스크 팀",
        agents={
            "worker": TeamAgentDef(preset="implementer"),
        },
        tasks={
            "task-a": TeamTaskDef(
                description="태스크 A 구현",
                agent="worker",
                depends_on=[],
            ),
            "task-b": TeamTaskDef(
                description="태스크 B 구현",
                agent="worker",
                depends_on=[],
            ),
            "task-c": TeamTaskDef(
                description="태스크 C 실패",
                agent="worker",
                depends_on=[],
            ),
            "task-d": TeamTaskDef(
                description="태스크 D 실패",
                agent="worker",
                depends_on=[],
            ),
        },
        workflow="parallel",
        synthesis_strategy="narrative",
    )


def _patch_executor(engine: OrchestratorEngine, executor: AgentExecutor) -> None:
    engine._create_executor_for_preset = lambda *_args, **_kwargs: executor  # type: ignore[assignment]


async def _wait_pipeline(
    engine: OrchestratorEngine,
    task_id: str,
    *,
    max_iterations: int = 100,
) -> None:
    for _ in range(max_iterations):
        current = await engine.get_pipeline(task_id)
        if current and current.status in (
            PipelineStatus.COMPLETED,
            PipelineStatus.PARTIAL_FAILURE,
            PipelineStatus.FAILED,
        ):
            break
        await asyncio.sleep(0.1)


# ── Partial Failure Pipeline Tests ──────────────────────────────────────


async def test_all_success_pipeline(
    engine: OrchestratorEngine,
    three_task_preset: TeamPreset,
) -> None:
    """모든 서브태스크가 성공하면 COMPLETED 상태가 된다."""
    executor = AlwaysSuccessExecutor()
    _patch_executor(engine, executor)
    engine._preset_registry._team_presets["three-task-team"] = three_task_preset

    pipeline = await engine.submit_task(
        "전체 성공 태스크",
        team_preset="three-task-team",
    )
    await _wait_pipeline(engine, pipeline.task_id)

    final = await engine.get_pipeline(pipeline.task_id)
    assert final is not None
    assert final.status == PipelineStatus.COMPLETED
    assert final.synthesis != ""
    # 모든 결과가 성공
    success_results = [r for r in final.results if not r.error]
    assert len(success_results) == 3


async def test_partial_success_pipeline(
    engine: OrchestratorEngine,
    three_task_preset: TeamPreset,
) -> None:
    """일부 서브태스크만 실패(50% 미만)하면 PARTIAL_FAILURE + 종합 보고서가 생성된다."""
    # "태스크 C"에서만 실패
    executor = SelectiveFailExecutor(fail_keywords=["태스크 C"])
    _patch_executor(engine, executor)
    engine._preset_registry._team_presets["three-task-team"] = three_task_preset

    pipeline = await engine.submit_task(
        "부분 실패 태스크",
        team_preset="three-task-team",
    )
    await _wait_pipeline(engine, pipeline.task_id)

    final = await engine.get_pipeline(pipeline.task_id)
    assert final is not None
    # 1/3 실패 = 33% < 50% → PARTIAL_FAILURE (부분 종합 진행)
    assert final.status == PipelineStatus.PARTIAL_FAILURE
    # 종합 보고서가 생성됨
    assert final.synthesis != ""
    assert "종합 보고서" in final.synthesis


async def test_majority_fail_pipeline(
    engine: OrchestratorEngine,
    four_task_preset: TeamPreset,
) -> None:
    """50% 이상 서브태스크가 실패하면 FAILED 상태가 된다."""
    # "실패" 키워드가 포함된 태스크 2개 실패 (2/4 = 50%)
    executor = SelectiveFailExecutor(fail_keywords=["실패"])
    _patch_executor(engine, executor)
    engine._preset_registry._team_presets["four-task-team"] = four_task_preset

    pipeline = await engine.submit_task(
        "과반 실패 태스크",
        team_preset="four-task-team",
    )
    await _wait_pipeline(engine, pipeline.task_id)

    final = await engine.get_pipeline(pipeline.task_id)
    assert final is not None
    # 2/4 실패 = 50% >= 50% → FAILED
    assert final.status == PipelineStatus.FAILED
    assert ">= 50%" in final.error or "subtasks failed" in final.error


async def test_all_fail_pipeline(
    engine: OrchestratorEngine,
    three_task_preset: TeamPreset,
) -> None:
    """모든 서브태스크가 실패하면 FAILED 상태가 된다."""
    executor = AlwaysFailExecutor()
    _patch_executor(engine, executor)
    engine._preset_registry._team_presets["three-task-team"] = three_task_preset

    pipeline = await engine.submit_task(
        "전체 실패 태스크",
        team_preset="three-task-team",
    )
    await _wait_pipeline(engine, pipeline.task_id)

    final = await engine.get_pipeline(pipeline.task_id)
    assert final is not None
    assert final.status == PipelineStatus.FAILED
    assert "subtasks failed" in final.error.lower() or "all" in final.error.lower()


async def test_partial_failure_events(
    engine: OrchestratorEngine,
    three_task_preset: TeamPreset,
    captured_events: list[OrchestratorEvent],
) -> None:
    """부분 실패 시 올바른 이벤트가 발행되는지 확인한다."""
    executor = SelectiveFailExecutor(fail_keywords=["태스크 C"])
    _patch_executor(engine, executor)
    engine._preset_registry._team_presets["three-task-team"] = three_task_preset

    pipeline = await engine.submit_task(
        "이벤트 확인 태스크",
        team_preset="three-task-team",
    )
    await _wait_pipeline(engine, pipeline.task_id)

    event_types = [e.type for e in captured_events]
    assert EventType.PIPELINE_COMPLETED in event_types

    completed = [e for e in captured_events if e.type == EventType.PIPELINE_COMPLETED]
    assert len(completed) >= 1
    assert completed[-1].data.get("fail_count", 0) > 0


# ── Synthesizer Failure Notes Tests ─────────────────────────────────────


async def test_synthesizer_includes_failures() -> None:
    """Synthesizer가 실패한 서브태스크 정보를 보고서에 포함하는지 확인한다."""
    synthesizer = Synthesizer()

    results = [
        WorkerResult(
            subtask_id="sub-001",
            executor_type="cli",
            output="JWT 구현 완료",
            duration_ms=5000,
        ),
        WorkerResult(
            subtask_id="sub-002",
            executor_type="cli",
            error="CLITimeoutError: timed out after 300s",
        ),
    ]

    report = await synthesizer.synthesize(
        results,
        "JWT 인증 구현",
    )

    # 보고서에 실패 정보가 포함되어야 함
    assert "sub-002" in report
    assert "실패" in report
    assert "timed out" in report.lower() or "CLITimeoutError" in report


async def test_synthesizer_narrative_all_success() -> None:
    """narrative 전략에서 모든 성공 시 올바른 보고서가 생성되는지 확인한다."""
    synthesizer = Synthesizer(strategy="narrative")

    results = [
        WorkerResult(
            subtask_id="sub-001",
            executor_type="cli",
            output="Result A",
        ),
        WorkerResult(
            subtask_id="sub-002",
            executor_type="cli",
            output="Result B",
        ),
    ]

    report = await synthesizer.synthesize(
        results,
        "테스트 태스크",
        strategy="narrative",
    )

    assert "종합 보고서" in report
    assert "성공적으로 완료" in report
    assert "sub-001" in report
    assert "sub-002" in report


async def test_synthesizer_structured_strategy() -> None:
    """structured 전략에서 구조화된 보고서가 생성되는지 확인한다."""
    synthesizer = Synthesizer()

    results = [
        WorkerResult(
            subtask_id="sub-001",
            executor_type="cli",
            output="implementation done",
            duration_ms=3000,
            tokens_used=500,
        ),
        WorkerResult(
            subtask_id="sub-002",
            executor_type="cli",
            error="execution failed",
        ),
    ]

    report = await synthesizer.synthesize(
        results,
        "구조화 테스트",
        strategy="structured",
    )

    assert "구조화 보고서" in report
    assert "실행 상태" in report
    assert "성공" in report
    assert "실패" in report
    # 표 형식
    assert "|" in report


async def test_synthesizer_checklist_strategy() -> None:
    """checklist 전략에서 체크리스트 형태 보고서가 생성되는지 확인한다."""
    synthesizer = Synthesizer()

    results = [
        WorkerResult(
            subtask_id="sub-001",
            executor_type="cli",
            output="done",
        ),
        WorkerResult(
            subtask_id="sub-002",
            executor_type="cli",
            output="done",
        ),
        WorkerResult(
            subtask_id="sub-003",
            executor_type="cli",
            error="failed",
        ),
    ]

    report = await synthesizer.synthesize(
        results,
        "체크리스트 테스트",
        strategy="checklist",
    )

    assert "체크리스트" in report
    assert "[x]" in report
    assert "[ ]" in report
    assert "진행률" in report
    assert "2/3" in report


async def test_synthesizer_empty_results() -> None:
    """빈 결과 목록에 대해 적절한 메시지를 반환한다."""
    synthesizer = Synthesizer()
    report = await synthesizer.synthesize([], "")
    assert report == "결과가 없습니다."
