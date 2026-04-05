"""Tests for core/engine.py."""

import asyncio

import pytest

from orchestrator.core.engine import OrchestratorEngine
from orchestrator.core.models.pipeline import PipelineStatus


@pytest.fixture
def engine():
    return OrchestratorEngine()


async def test_submit_task(engine):
    pipeline = await engine.submit_task("test task")
    assert pipeline.task == "test task"
    assert pipeline.status == PipelineStatus.PENDING
    assert pipeline.task_id.startswith("pipeline-")
    # Allow background task to run
    await asyncio.sleep(0.1)


async def test_submit_empty_task_raises(engine):
    with pytest.raises(ValueError, match="empty"):
        await engine.submit_task("")


async def test_get_pipeline(engine):
    pipeline = await engine.submit_task("test task")
    found = await engine.get_pipeline(pipeline.task_id)
    assert found is not None
    await asyncio.sleep(0.1)


async def test_get_pipeline_not_found(engine):
    found = await engine.get_pipeline("nonexistent")
    assert found is None


async def test_list_pipelines(engine):
    await engine.submit_task("task 1")
    await engine.submit_task("task 2")
    pipelines = await engine.list_pipelines()
    assert len(pipelines) == 2
    await asyncio.sleep(0.1)


async def test_cancel_task(engine):
    pipeline = await engine.submit_task("task")
    result = await engine.cancel_task(pipeline.task_id)
    assert result is True
    cancelled = await engine.get_pipeline(pipeline.task_id)
    assert cancelled is not None
    assert cancelled.status == PipelineStatus.CANCELLED


async def test_cancel_nonexistent(engine):
    result = await engine.cancel_task("nonexistent")
    assert result is False


async def test_list_agent_presets(engine):
    presets = engine.list_agent_presets()
    assert isinstance(presets, list)


async def test_list_team_presets(engine):
    presets = engine.list_team_presets()
    assert isinstance(presets, list)


async def test_get_board_state(engine):
    state = engine.get_board_state()
    assert "lanes" in state
    assert "summary" in state


async def test_list_agents(engine):
    agents = engine.list_agents()
    assert isinstance(agents, list)


async def test_subscribe_and_get_events(engine):
    events = []

    async def handler(event):
        events.append(event)

    engine.subscribe(handler)
    await engine.submit_task("task with events")
    await asyncio.sleep(0.2)
    assert len(events) >= 1

    history = engine.get_events()
    assert len(history) >= 1
