"""Tests for pipeline resume functionality."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from orchestrator.core.config.schema import OrchestratorConfig
from orchestrator.core.engine import OrchestratorEngine
from orchestrator.core.models.pipeline import Pipeline, PipelineStatus


@pytest.fixture
def engine_with_checkpoint(tmp_path: Path) -> OrchestratorEngine:
    """체크포인트가 활성화된 OrchestratorEngine."""
    config = OrchestratorConfig(
        checkpoint_enabled=True,
        checkpoint_db_path=str(tmp_path / "checkpoints.sqlite"),
    )
    return OrchestratorEngine(config=config)


@pytest.fixture
def engine_no_checkpoint() -> OrchestratorEngine:
    """체크포인트가 비활성화된 OrchestratorEngine."""
    config = OrchestratorConfig(checkpoint_enabled=False)
    return OrchestratorEngine(config=config)


async def test_resume_from_checkpoint(engine_with_checkpoint: OrchestratorEngine) -> None:
    """체크포인트에서 파이프라인을 복원하여 재개할 수 있다."""
    # 먼저 파이프라인을 생성하고 체크포인트에 저장
    pipeline = Pipeline(
        task_id="pipeline-resume-001",
        task="Resume 테스트 태스크",
        status=PipelineStatus.FAILED,
        team_preset="feature-team",
        error="All subtasks failed",
    )
    # 엔진 메모리에 저장
    engine_with_checkpoint._pipelines["pipeline-resume-001"] = pipeline
    # 체크포인트에도 저장
    assert engine_with_checkpoint.checkpoint_store is not None
    engine_with_checkpoint.checkpoint_store.save("pipeline-resume-001", pipeline)

    # 메모리에서 제거 (서버 재시작 시뮬레이션)
    del engine_with_checkpoint._pipelines["pipeline-resume-001"]

    # 체크포인트에서 복원하여 재개
    resumed = await engine_with_checkpoint.resume_task("pipeline-resume-001")
    assert resumed.status == PipelineStatus.RUNNING
    assert resumed.task_id == "pipeline-resume-001"
    assert resumed.error == ""


async def test_resume_nonexistent(engine_with_checkpoint: OrchestratorEngine) -> None:
    """존재하지 않는 파이프라인 재개 시 KeyError를 발생시킨다."""
    with pytest.raises(KeyError, match="Pipeline not found"):
        await engine_with_checkpoint.resume_task("nonexistent-pipeline")


async def test_resume_already_completed(engine_with_checkpoint: OrchestratorEngine) -> None:
    """이미 완료된 파이프라인은 재개할 수 없다."""
    pipeline = Pipeline(
        task_id="pipeline-completed",
        task="완료된 태스크",
        status=PipelineStatus.COMPLETED,
    )
    engine_with_checkpoint._pipelines["pipeline-completed"] = pipeline

    with pytest.raises(ValueError, match="cannot be resumed"):
        await engine_with_checkpoint.resume_task("pipeline-completed")


async def test_resume_running_pipeline(engine_with_checkpoint: OrchestratorEngine) -> None:
    """실행 중인 파이프라인은 재개할 수 없다."""
    pipeline = Pipeline(
        task_id="pipeline-running",
        task="실행 중 태스크",
        status=PipelineStatus.RUNNING,
    )
    engine_with_checkpoint._pipelines["pipeline-running"] = pipeline

    with pytest.raises(ValueError, match="cannot be resumed"):
        await engine_with_checkpoint.resume_task("pipeline-running")


async def test_resume_partial_failure(engine_with_checkpoint: OrchestratorEngine) -> None:
    """PARTIAL_FAILURE 상태 파이프라인을 재개할 수 있다."""
    pipeline = Pipeline(
        task_id="pipeline-partial",
        task="부분 실패 태스크",
        status=PipelineStatus.PARTIAL_FAILURE,
    )
    engine_with_checkpoint._pipelines["pipeline-partial"] = pipeline

    resumed = await engine_with_checkpoint.resume_task("pipeline-partial")
    assert resumed.status == PipelineStatus.RUNNING


async def test_resume_emits_event(engine_with_checkpoint: OrchestratorEngine) -> None:
    """재개 시 이벤트가 발행된다."""
    events: list = []

    async def handler(event):
        events.append(event)

    engine_with_checkpoint.subscribe(handler)

    pipeline = Pipeline(
        task_id="pipeline-event-test",
        task="이벤트 테스트",
        status=PipelineStatus.FAILED,
        error="test error",
    )
    engine_with_checkpoint._pipelines["pipeline-event-test"] = pipeline

    await engine_with_checkpoint.resume_task("pipeline-event-test")
    await asyncio.sleep(0.05)

    assert len(events) >= 1
    resume_events = [e for e in events if e.data.get("resumed")]
    assert len(resume_events) == 1


async def test_resume_saves_checkpoint(engine_with_checkpoint: OrchestratorEngine) -> None:
    """재개 후 체크포인트가 업데이트된다."""
    pipeline = Pipeline(
        task_id="pipeline-ckpt-update",
        task="체크포인트 업데이트 테스트",
        status=PipelineStatus.FAILED,
        error="failed",
    )
    engine_with_checkpoint._pipelines["pipeline-ckpt-update"] = pipeline

    await engine_with_checkpoint.resume_task("pipeline-ckpt-update")

    assert engine_with_checkpoint.checkpoint_store is not None
    restored = engine_with_checkpoint.checkpoint_store.load("pipeline-ckpt-update")
    assert restored is not None
    assert restored.status == PipelineStatus.RUNNING
    assert restored.error == ""


async def test_resume_no_checkpoint_store(engine_no_checkpoint: OrchestratorEngine) -> None:
    """체크포인트 비활성화 시 메모리에서만 재개한다."""
    pipeline = Pipeline(
        task_id="pipeline-no-ckpt",
        task="체크포인트 없는 태스크",
        status=PipelineStatus.FAILED,
    )
    engine_no_checkpoint._pipelines["pipeline-no-ckpt"] = pipeline

    resumed = await engine_no_checkpoint.resume_task("pipeline-no-ckpt")
    assert resumed.status == PipelineStatus.RUNNING
