"""E2E 테스트: 실패 + 폴백 시나리오.

Scenario:
  1. primary CLI 타임아웃 → 폴백 → 부분 완료
  2. 일부 에이전트 실패, 나머지 성공
  3. 전체 실패 시 FAILED 상태
"""

from __future__ import annotations

import asyncio

import pytest

from orchestrator.core.engine import OrchestratorEngine
from orchestrator.core.events.types import EventType, OrchestratorEvent
from orchestrator.core.models.pipeline import PipelineStatus
from orchestrator.core.presets.models import (
    TeamAgentDef,
    TeamPreset,
    TeamTaskDef,
)

from .conftest import (
    FailingMockExecutor,
    PartialFailExecutor,
    _patch_executor,
    wait_for_pipeline,
)

pytestmark = pytest.mark.e2e


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def two_task_preset() -> TeamPreset:
    """2개 태스크 프리셋 (의존성 없음, 병렬)."""
    return TeamPreset(
        name="two-task-team",
        description="2개 병렬 태스크 팀",
        agents={
            "agent-a": TeamAgentDef(preset="elk-analyst"),
            "agent-b": TeamAgentDef(preset="elk-analyst"),
        },
        tasks={
            "task-a": TeamTaskDef(
                description="태스크 A — 분석 작업",
                agent="agent-a",
                depends_on=[],
            ),
            "task-b": TeamTaskDef(
                description="태스크 B — 분석 작업",
                agent="agent-b",
                depends_on=[],
            ),
        },
        workflow="parallel",
        synthesis_strategy="narrative",
    )


@pytest.fixture
def three_task_preset() -> TeamPreset:
    """3개 태스크 프리셋 (의존성 없음, 병렬)."""
    return TeamPreset(
        name="three-task-team",
        description="3개 병렬 태스크 팀",
        agents={
            "agent-a": TeamAgentDef(preset="elk-analyst"),
            "agent-b": TeamAgentDef(preset="elk-analyst"),
            "agent-c": TeamAgentDef(preset="elk-analyst"),
        },
        tasks={
            "task-a": TeamTaskDef(
                description="태스크 A — 분석 작업",
                agent="agent-a",
                depends_on=[],
            ),
            "task-b": TeamTaskDef(
                description="태스크 B — 분석 작업",
                agent="agent-b",
                depends_on=[],
            ),
            "task-c": TeamTaskDef(
                description="태스크 C — 분석 작업",
                agent="agent-c",
                depends_on=[],
            ),
        },
        workflow="parallel",
        synthesis_strategy="narrative",
    )


# ── T6.3 Tests ──────────────────────────────────────────────────────


async def test_all_subtasks_fail_pipeline_fails(
    e2e_engine: OrchestratorEngine,
    two_task_preset: TeamPreset,
    captured_events: list[OrchestratorEvent],
) -> None:
    """모든 서브태스크가 실패하면 pipeline이 FAILED 상태가 되는지 확인."""
    failing_exec = FailingMockExecutor(error_msg="Simulated CLI timeout")
    _patch_executor(e2e_engine, failing_exec)
    e2e_engine._preset_registry._team_presets["two-task-team"] = two_task_preset

    pipeline = await e2e_engine.submit_task(
        "전체 실패 시나리오",
        team_preset="two-task-team",
    )

    await wait_for_pipeline(e2e_engine, pipeline.task_id, max_wait=15.0)

    final = await e2e_engine.get_pipeline(pipeline.task_id)
    assert final is not None
    assert final.status == PipelineStatus.FAILED
    assert final.error != ""

    # PIPELINE_FAILED 이벤트 확인
    await asyncio.sleep(0.1)
    failed_events = [
        e
        for e in captured_events
        if e.type == EventType.PIPELINE_FAILED and e.task_id == pipeline.task_id
    ]
    assert len(failed_events) >= 1


async def test_partial_failure_some_succeed_some_fail(
    e2e_engine: OrchestratorEngine,
    three_task_preset: TeamPreset,
    captured_events: list[OrchestratorEvent],
) -> None:
    """일부 서브태스크 성공, 일부 실패 시 부분 실패 처리 확인.

    3개 병렬 태스크 중 1개만 실패하면 (33%) PARTIAL_FAILURE 또는 COMPLETED.
    """
    # "태스크 C" 키워드가 포함된 prompt만 실패하도록 설정
    partial_exec = PartialFailExecutor(fail_keywords=["태스크 C"])
    _patch_executor(e2e_engine, partial_exec)
    e2e_engine._preset_registry._team_presets["three-task-team"] = three_task_preset

    pipeline = await e2e_engine.submit_task(
        "부분 실패 시나리오",
        team_preset="three-task-team",
    )

    await wait_for_pipeline(e2e_engine, pipeline.task_id, max_wait=15.0)

    final = await e2e_engine.get_pipeline(pipeline.task_id)
    assert final is not None

    # 1/3 실패 = 33% → PARTIAL_FAILURE (< 50%)
    assert final.status in (PipelineStatus.PARTIAL_FAILURE, PipelineStatus.COMPLETED)

    # 실패한 결과와 성공한 결과 모두 존재
    assert len(final.results) == 3
    success_results = [r for r in final.results if not r.error]
    failed_results = [r for r in final.results if r.error]
    assert len(success_results) >= 2
    assert len(failed_results) >= 1


async def test_majority_failure_pipeline_fails(
    e2e_engine: OrchestratorEngine,
    three_task_preset: TeamPreset,
) -> None:
    """과반수(50% 이상) 서브태스크가 실패하면 FAILED 상태가 되는지 확인."""
    # "태스크 A"와 "태스크 B"가 실패 (2/3 = 67%)
    partial_exec = PartialFailExecutor(fail_keywords=["태스크 A", "태스크 B"])
    _patch_executor(e2e_engine, partial_exec)
    e2e_engine._preset_registry._team_presets["three-task-team"] = three_task_preset

    pipeline = await e2e_engine.submit_task(
        "과반수 실패 시나리오",
        team_preset="three-task-team",
    )

    await wait_for_pipeline(e2e_engine, pipeline.task_id, max_wait=15.0)

    final = await e2e_engine.get_pipeline(pipeline.task_id)
    assert final is not None
    assert final.status == PipelineStatus.FAILED


async def test_failure_with_retry_exhaustion(
    e2e_engine: OrchestratorEngine,
    captured_events: list[OrchestratorEvent],
) -> None:
    """실패 시 재시도(max_retries)까지 시도 후 최종 실패 확인.

    단일 태스크가 반복 실패하여 retry가 소진되는 과정.
    """
    failing_exec = FailingMockExecutor(error_msg="Persistent error")
    _patch_executor(e2e_engine, failing_exec)

    pipeline = await e2e_engine.submit_task("재시도 소진 시나리오")

    await wait_for_pipeline(e2e_engine, pipeline.task_id, max_wait=15.0)
    await asyncio.sleep(0.1)

    final = await e2e_engine.get_pipeline(pipeline.task_id)
    assert final is not None
    assert final.status == PipelineStatus.FAILED

    # 재시도 이벤트 확인 (max_retries=2이므로 최소 1회 TASK_RETRYING)
    retry_events = [
        e
        for e in captured_events
        if e.type == EventType.TASK_RETRYING and e.task_id == pipeline.task_id
    ]
    # 최소 1회 재시도 발생해야 한다
    assert len(retry_events) >= 1

    # 최종 TASK_FAILED 이벤트 확인
    task_failed_events = [
        e
        for e in captured_events
        if e.type == EventType.TASK_FAILED and e.task_id == pipeline.task_id
    ]
    assert len(task_failed_events) >= 1
