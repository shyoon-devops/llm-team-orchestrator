"""E2E 테스트: 코딩 팀 시나리오 — JWT 인증 미들웨어 구현.

Scenario:
  1. "JWT 인증 미들웨어 구현" 태스크 제출 (team_preset=feature-team)
  2. architect → implementer → reviewer + tester DAG 분해
  3. 의존성 순서대로 실행
  4. 종합 보고서 생성
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
    RealisticCodeExecutor,
    _patch_executor,
    wait_for_pipeline,
)

pytestmark = pytest.mark.e2e


# ── T6.1 Tests ──────────────────────────────────────────────────────


async def test_coding_team_jwt_middleware_full_pipeline(
    e2e_engine: OrchestratorEngine,
    feature_team_preset: TeamPreset,
    captured_events: list[OrchestratorEvent],
) -> None:
    """JWT 인증 미들웨어 구현 → 4개 에이전트 → 설계/구현/리뷰/테스트 → 완료.

    전체 파이프라인 흐름이 정상 완료되고 종합 보고서가 생성되는지 확인.
    """
    executor = RealisticCodeExecutor()
    _patch_executor(e2e_engine, executor)
    e2e_engine._preset_registry._team_presets["feature-team"] = feature_team_preset

    pipeline = await e2e_engine.submit_task(
        "JWT 인증 미들웨어를 구현해줘",
        team_preset="feature-team",
    )

    await wait_for_pipeline(e2e_engine, pipeline.task_id)

    final = await e2e_engine.get_pipeline(pipeline.task_id)
    assert final is not None
    assert final.status == PipelineStatus.COMPLETED

    # 4개 서브태스크 (design, implement, review, test)
    assert len(final.subtasks) == 4

    # 4개 결과 모두 수집
    assert len(final.results) == 4
    success_results = [r for r in final.results if not r.error]
    assert len(success_results) == 4

    # 종합 보고서 생성 확인
    assert final.synthesis != ""
    assert "종합 보고서" in final.synthesis


async def test_coding_team_subtask_dependency_order(
    e2e_engine: OrchestratorEngine,
    feature_team_preset: TeamPreset,
) -> None:
    """서브태스크가 의존성 순서대로 실행되는지 확인.

    design → implement → (review + test) 순서를 검증.
    """
    execution_log: list[str] = []

    class OrderTrackingExecutor(RealisticCodeExecutor):
        async def run(self, prompt, *, timeout=300, context=None):  # noqa: ASYNC109
            execution_log.append(prompt[:50])
            return await super().run(prompt, timeout=timeout, context=context)

    _patch_executor(e2e_engine, OrderTrackingExecutor())
    e2e_engine._preset_registry._team_presets["feature-team"] = feature_team_preset

    pipeline = await e2e_engine.submit_task(
        "JWT 인증 미들웨어를 구현해줘",
        team_preset="feature-team",
    )

    await wait_for_pipeline(e2e_engine, pipeline.task_id)

    final = await e2e_engine.get_pipeline(pipeline.task_id)
    assert final is not None
    assert final.status == PipelineStatus.COMPLETED

    # 최소 4개 태스크 실행
    assert len(execution_log) == 4

    # 첫 번째 실행은 설계(architect)이어야 한다
    assert "설계" in execution_log[0] or "아키텍처" in execution_log[0]

    # 두 번째 실행은 구현(implementer)이어야 한다
    assert "구현" in execution_log[1]

    # 세 번째, 네 번째는 리뷰와 테스트 (순서 무관 — 병렬 가능)
    remaining = set(execution_log[2:4])
    assert any("리뷰" in item for item in remaining)
    assert any("테스트" in item for item in remaining)


async def test_coding_team_event_flow(
    e2e_engine: OrchestratorEngine,
    feature_team_preset: TeamPreset,
    captured_events: list[OrchestratorEvent],
) -> None:
    """파이프라인 이벤트 흐름을 검증.

    CREATED → PLANNING → RUNNING → SYNTHESIZING → COMPLETED 이벤트 순서.
    """
    executor = RealisticCodeExecutor()
    _patch_executor(e2e_engine, executor)
    e2e_engine._preset_registry._team_presets["feature-team"] = feature_team_preset

    pipeline = await e2e_engine.submit_task(
        "JWT 인증 미들웨어를 구현해줘",
        team_preset="feature-team",
    )

    await wait_for_pipeline(e2e_engine, pipeline.task_id)

    # 이벤트 캡처 완료 대기
    await asyncio.sleep(0.1)

    event_types = [e.type for e in captured_events if e.task_id == pipeline.task_id]

    # 필수 이벤트 순서 확인
    assert EventType.PIPELINE_CREATED in event_types
    assert EventType.PIPELINE_PLANNING in event_types
    assert EventType.PIPELINE_RUNNING in event_types
    assert EventType.PIPELINE_SYNTHESIZING in event_types
    assert EventType.PIPELINE_COMPLETED in event_types

    # 순서 검증: CREATED < PLANNING < RUNNING < SYNTHESIZING < COMPLETED
    created_idx = event_types.index(EventType.PIPELINE_CREATED)
    planning_idx = event_types.index(EventType.PIPELINE_PLANNING)
    running_idx = event_types.index(EventType.PIPELINE_RUNNING)
    synth_idx = event_types.index(EventType.PIPELINE_SYNTHESIZING)
    completed_idx = event_types.index(EventType.PIPELINE_COMPLETED)

    assert created_idx < planning_idx < running_idx < synth_idx < completed_idx

    # AGENT_EXECUTING 이벤트도 발행되어야 한다
    agent_events = [e for e in captured_events if e.type == EventType.AGENT_EXECUTING]
    assert len(agent_events) >= 4


async def test_coding_team_synthesis_contains_subtask_info(
    e2e_engine: OrchestratorEngine,
    feature_team_preset: TeamPreset,
) -> None:
    """종합 보고서에 각 서브태스크 결과가 반영되는지 확인."""
    executor = RealisticCodeExecutor()
    _patch_executor(e2e_engine, executor)
    e2e_engine._preset_registry._team_presets["feature-team"] = feature_team_preset

    pipeline = await e2e_engine.submit_task(
        "JWT 인증 미들웨어를 구현해줘",
        team_preset="feature-team",
    )

    await wait_for_pipeline(e2e_engine, pipeline.task_id)

    final = await e2e_engine.get_pipeline(pipeline.task_id)
    assert final is not None
    assert final.status == PipelineStatus.COMPLETED

    # 종합 보고서에 에이전트별 결과 반영 확인
    synthesis = final.synthesis
    assert "서브태스크" in synthesis
    assert "성공" in synthesis

    # 보고서에 4개 서브태스크 ID가 반영되어야 한다
    for result in final.results:
        assert result.subtask_id in synthesis
