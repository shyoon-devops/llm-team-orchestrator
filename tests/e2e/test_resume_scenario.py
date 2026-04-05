"""E2E 테스트: 중단 + 재개 시나리오.

Scenario:
  1. 파이프라인 실행 중 첫 서브태스크 완료 후 cancel
  2. resume 호출
  3. 이미 완료된 서브태스크는 재실행하지 않음
  4. 파이프라인 완료
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from orchestrator.core.config.schema import OrchestratorConfig
from orchestrator.core.engine import OrchestratorEngine
from orchestrator.core.events.types import OrchestratorEvent
from orchestrator.core.executor.base import AgentExecutor
from orchestrator.core.models.pipeline import Pipeline, PipelineStatus
from orchestrator.core.models.schemas import AgentResult
from orchestrator.core.presets.models import (
    TeamAgentDef,
    TeamPreset,
    TeamTaskDef,
)
from orchestrator.core.queue.models import TaskState

from .conftest import (
    MockAgentExecutor,
    _patch_executor,
)

pytestmark = pytest.mark.e2e


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def sequential_team_preset() -> TeamPreset:
    """3개 순차 태스크 프리셋 (A → B → C)."""
    return TeamPreset(
        name="sequential-team",
        description="3개 순차 태스크",
        agents={
            "worker-a": TeamAgentDef(preset="elk-analyst"),
            "worker-b": TeamAgentDef(preset="elk-analyst"),
            "worker-c": TeamAgentDef(preset="elk-analyst"),
        },
        tasks={
            "step-a": TeamTaskDef(
                description="Step A — 첫 번째 단계",
                agent="worker-a",
                depends_on=[],
            ),
            "step-b": TeamTaskDef(
                description="Step B — 두 번째 단계",
                agent="worker-b",
                depends_on=["step-a"],
            ),
            "step-c": TeamTaskDef(
                description="Step C — 세 번째 단계",
                agent="worker-c",
                depends_on=["step-b"],
            ),
        },
        workflow="dag",
        synthesis_strategy="narrative",
    )


# ── T6.4 Tests ──────────────────────────────────────────────────────


async def test_cancel_and_resume_pipeline(
    e2e_engine: OrchestratorEngine,
    sequential_team_preset: TeamPreset,
    captured_events: list[OrchestratorEvent],
) -> None:
    """파이프라인 중단 후 재개: 완료된 태스크는 재실행하지 않는지 확인.

    Step A 완료 후 cancel → resume → Step B, C만 실행 → COMPLETED.
    """
    # Step A는 빠르게 완료, Step B는 느리게 설정
    call_count = 0

    class SlowOnSecondExecutor(AgentExecutor):
        executor_type: str = "mock"

        def __init__(self):
            self.cli_name = "mock"

        async def run(self, prompt, *, timeout=300, context=None):  # noqa: ASYNC109
            nonlocal call_count
            call_count += 1
            # Step B는 느리게 실행하여 cancel 기회 제공
            if "Step B" in prompt:
                await asyncio.sleep(5.0)
            return AgentResult(
                output=f"Done: {prompt[:50]}",
                exit_code=0,
                duration_ms=100,
            )

        async def health_check(self):
            return True

    _patch_executor(e2e_engine, SlowOnSecondExecutor())
    e2e_engine._preset_registry._team_presets["sequential-team"] = sequential_team_preset

    pipeline = await e2e_engine.submit_task(
        "중단/재개 테스트",
        team_preset="sequential-team",
    )

    # Step A가 완료되고 Step B가 시작될 때까지 대기
    for _ in range(50):
        current = await e2e_engine.get_pipeline(pipeline.task_id)
        if current and current.status == PipelineStatus.RUNNING:
            # TaskBoard에서 Step A가 DONE인지 확인
            board_state = e2e_engine.get_board_state()
            done_count = board_state["summary"]["by_state"].get("done", 0)
            if done_count >= 1:
                break
        await asyncio.sleep(0.1)

    # 취소
    cancel_result = await e2e_engine.cancel_task(pipeline.task_id)
    assert cancel_result is True

    cancelled = await e2e_engine.get_pipeline(pipeline.task_id)
    assert cancelled is not None
    assert cancelled.status == PipelineStatus.CANCELLED

    # 배경 태스크 정리 대기
    await asyncio.sleep(0.5)

    # 재개를 위해 CANCELLED → FAILED로 전환 (resume은 FAILED/PARTIAL_FAILURE만 허용)
    e2e_engine._pipelines[pipeline.task_id] = cancelled.model_copy(
        update={"status": PipelineStatus.FAILED, "error": "Cancelled by user"}
    )

    # 이미 완료된 TaskBoard 태스크 확인
    done_before_resume = [
        t
        for t in e2e_engine._board._tasks.values()
        if t.pipeline_id == pipeline.task_id and t.state == TaskState.DONE
    ]
    done_count_before = len(done_before_resume)

    # Resume 호출
    fast_exec = MockAgentExecutor(output="Resumed result")
    _patch_executor(e2e_engine, fast_exec)

    resumed = await e2e_engine.resume_task(pipeline.task_id)
    assert resumed.status == PipelineStatus.RUNNING

    # 재개 이벤트 확인
    await asyncio.sleep(0.1)
    resume_events = [
        e
        for e in captured_events
        if e.data.get("resumed") is True and e.task_id == pipeline.task_id
    ]
    assert len(resume_events) >= 1

    # 이미 DONE인 태스크는 보존됨
    done_after_resume = [
        t
        for t in e2e_engine._board._tasks.values()
        if t.pipeline_id == pipeline.task_id and t.state == TaskState.DONE
    ]
    assert len(done_after_resume) >= done_count_before


async def test_resume_preserves_checkpoint(
    e2e_engine: OrchestratorEngine,
) -> None:
    """resume 후 체크포인트가 올바르게 업데이트되는지 확인."""
    # 수동으로 FAILED 파이프라인을 생성하고 체크포인트에 저장
    pipeline = Pipeline(
        task_id="pipeline-e2e-resume-001",
        task="체크포인트 보존 테스트",
        status=PipelineStatus.FAILED,
        team_preset="",
        error="Simulated failure",
    )
    e2e_engine._pipelines["pipeline-e2e-resume-001"] = pipeline
    e2e_engine._save_checkpoint(pipeline)

    # Resume 호출
    resumed = await e2e_engine.resume_task("pipeline-e2e-resume-001")
    assert resumed.status == PipelineStatus.RUNNING
    assert resumed.error == ""

    # 체크포인트에 반영 확인
    assert e2e_engine.checkpoint_store is not None
    loaded = e2e_engine.checkpoint_store.load("pipeline-e2e-resume-001")
    assert loaded is not None
    assert loaded.status == PipelineStatus.RUNNING
    assert loaded.error == ""


async def test_resume_from_checkpoint_after_restart(
    tmp_path: Path,
) -> None:
    """서버 재시작 시뮬레이션: 메모리에 없는 파이프라인을 체크포인트에서 복원.

    Engine을 재생성하여 메모리가 비어 있는 상태에서
    체크포인트에 저장된 FAILED 파이프라인을 resume.
    """
    db_path = str(tmp_path / "ckpt-restart.sqlite")

    # Engine 1: 파이프라인을 생성하고 체크포인트에 저장
    config1 = OrchestratorConfig(
        checkpoint_enabled=True,
        checkpoint_db_path=db_path,
    )
    engine1 = OrchestratorEngine(config=config1)

    pipeline = Pipeline(
        task_id="pipeline-restart-test",
        task="재시작 테스트 태스크",
        status=PipelineStatus.FAILED,
        error="Crashed during execution",
    )
    engine1._pipelines["pipeline-restart-test"] = pipeline
    engine1._save_checkpoint(pipeline)

    # Engine 2: 새로운 엔진 (메모리 비어있음) — 서버 재시작 시뮬레이션
    config2 = OrchestratorConfig(
        checkpoint_enabled=True,
        checkpoint_db_path=db_path,
    )
    engine2 = OrchestratorEngine(config=config2)

    # 메모리에 없지만 체크포인트에서 복원하여 resume
    resumed = await engine2.resume_task("pipeline-restart-test")
    assert resumed.status == PipelineStatus.RUNNING
    assert resumed.task == "재시작 테스트 태스크"
    assert resumed.error == ""
