"""E2E 테스트: 장애 분석 시나리오 — 프로덕션 API 500 에러 원인 분석.

Scenario:
  1. "프로덕션 API 500 에러 원인 분석" 태스크 제출 (team_preset=incident-analysis-team)
  2. 3개 MCP 에이전트 (ELK, Grafana, K8s) 병렬 실행
  3. 모든 3개 완료 (의존성 없음 = 병렬)
  4. 종합 보고서에 3개 분석 결과 반영
  5. pipeline status = COMPLETED
"""

from __future__ import annotations

import asyncio

import pytest

from orchestrator.core.engine import OrchestratorEngine
from orchestrator.core.events.types import EventType, OrchestratorEvent
from orchestrator.core.models.pipeline import PipelineStatus
from orchestrator.core.presets.models import TeamPreset

from .conftest import (
    MockAgentExecutor,
    RealisticCodeExecutor,
    _patch_executor,
    wait_for_pipeline,
)

pytestmark = pytest.mark.e2e


# ── T6.2 Tests ──────────────────────────────────────────────────────


async def test_incident_analysis_parallel_completion(
    e2e_engine: OrchestratorEngine,
    incident_team_preset: TeamPreset,
    captured_events: list[OrchestratorEvent],
) -> None:
    """3개 MCP 에이전트가 병렬 실행되고 모두 완료되는지 확인."""
    executor = RealisticCodeExecutor()
    _patch_executor(e2e_engine, executor)
    e2e_engine._preset_registry._team_presets["incident-analysis-team"] = incident_team_preset

    pipeline = await e2e_engine.submit_task(
        "프로덕션 API 500 에러 원인 분석",
        team_preset="incident-analysis-team",
    )

    await wait_for_pipeline(e2e_engine, pipeline.task_id)

    final = await e2e_engine.get_pipeline(pipeline.task_id)
    assert final is not None
    assert final.status == PipelineStatus.COMPLETED

    # 3개 서브태스크 (ELK, Grafana, K8s)
    assert len(final.subtasks) == 3

    # 모든 서브태스크에 의존성이 없어야 한다 (병렬)
    for st in final.subtasks:
        assert len(st.depends_on) == 0

    # 3개 결과 모두 수집
    assert len(final.results) == 3
    success_results = [r for r in final.results if not r.error]
    assert len(success_results) == 3


async def test_incident_analysis_synthesis_contains_all_analyses(
    e2e_engine: OrchestratorEngine,
    incident_team_preset: TeamPreset,
) -> None:
    """종합 보고서에 3개 에이전트 분석 결과가 모두 반영되는지 확인."""
    executor = RealisticCodeExecutor()
    _patch_executor(e2e_engine, executor)
    e2e_engine._preset_registry._team_presets["incident-analysis-team"] = incident_team_preset

    pipeline = await e2e_engine.submit_task(
        "프로덕션 API 500 에러 원인 분석",
        team_preset="incident-analysis-team",
    )

    await wait_for_pipeline(e2e_engine, pipeline.task_id)

    final = await e2e_engine.get_pipeline(pipeline.task_id)
    assert final is not None

    # structured 전략의 종합 보고서 확인
    synthesis = final.synthesis
    assert synthesis != ""

    # 보고서에 3개 서브태스크 결과가 반영되어야 한다
    assert "서브태스크" in synthesis or "실행 상태" in synthesis

    # 모든 서브태스크 ID가 보고서에 포함
    for result in final.results:
        assert result.subtask_id in synthesis

    # structured 전략이므로 표 형식 포함
    assert "성공" in synthesis


async def test_incident_analysis_events_and_timing(
    e2e_engine: OrchestratorEngine,
    incident_team_preset: TeamPreset,
    captured_events: list[OrchestratorEvent],
) -> None:
    """병렬 실행 이벤트 흐름 및 타이밍 확인."""
    executor = MockAgentExecutor(output="Incident analysis result", delay=0.05)
    _patch_executor(e2e_engine, executor)
    e2e_engine._preset_registry._team_presets["incident-analysis-team"] = incident_team_preset

    pipeline = await e2e_engine.submit_task(
        "프로덕션 API 500 에러 원인 분석",
        team_preset="incident-analysis-team",
    )

    await wait_for_pipeline(e2e_engine, pipeline.task_id)
    await asyncio.sleep(0.1)

    # 파이프라인 완료 확인
    final = await e2e_engine.get_pipeline(pipeline.task_id)
    assert final is not None
    assert final.status == PipelineStatus.COMPLETED

    # 이벤트 흐름 확인
    event_types = [e.type for e in captured_events if e.task_id == pipeline.task_id]
    assert EventType.PIPELINE_CREATED in event_types
    assert EventType.PIPELINE_COMPLETED in event_types

    # 각 에이전트에 대한 실행 이벤트 확인
    agent_executing_events = [
        e
        for e in captured_events
        if e.type == EventType.AGENT_EXECUTING and e.task_id == pipeline.task_id
    ]
    assert len(agent_executing_events) == 3

    # 각 에이전트에 대한 완료 이벤트 확인
    task_completed_events = [
        e
        for e in captured_events
        if e.type == EventType.TASK_COMPLETED and e.task_id == pipeline.task_id
    ]
    assert len(task_completed_events) == 3
