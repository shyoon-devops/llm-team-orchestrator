"""Tests for AgentWorker CLI output streaming (AGENT_OUTPUT events)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.core.events.types import EventType, OrchestratorEvent
from orchestrator.core.queue.models import TaskItem, TaskState
from orchestrator.core.queue.worker import AgentWorker


def _make_task(
    task_id: str = "t1",
    pipeline_id: str = "p1",
    lane: str = "implementer",
) -> TaskItem:
    return TaskItem(
        id=task_id,
        title="test task",
        description="implement something",
        lane=lane,
        state=TaskState.IN_PROGRESS,
        pipeline_id=pipeline_id,
        priority=0,
        depends_on=[],
    )


def _make_worker(executor_mock, board_mock, event_bus_mock, lane="implementer"):
    return AgentWorker(
        worker_id="w1",
        lane=lane,
        board=board_mock,
        executor=executor_mock,
        event_bus=event_bus_mock,
    )


@pytest.fixture
def event_bus():
    bus = AsyncMock()
    bus.emit = AsyncMock()
    return bus


@pytest.fixture
def board():
    b = AsyncMock()
    b.get_task = MagicMock(return_value=None)
    return b


@pytest.fixture
def executor():
    from orchestrator.core.models.schemas import AgentResult

    ex = AsyncMock()
    ex.run = AsyncMock(return_value=AgentResult(output="done", exit_code=0))
    ex._on_output = None  # CLIAgentExecutor attribute
    ex._cwd = None
    ex.config = None
    return ex


@pytest.mark.asyncio
async def test_worker_sets_on_output_callback(executor, board, event_bus):
    """worker가 executor._on_output에 콜백을 설정한다."""
    worker = _make_worker(executor, board, event_bus)
    task = _make_task()

    await worker._run_with_heartbeat(task)

    # executor._on_output이 설정되었어야 함
    assert executor._on_output is not None


@pytest.mark.asyncio
async def test_worker_callback_emits_agent_output_event(executor, board, event_bus):
    """콜백 호출 시 AGENT_OUTPUT 이벤트가 발행된다."""
    worker = _make_worker(executor, board, event_bus)
    task = _make_task()

    await worker._run_with_heartbeat(task)

    # 콜백을 직접 호출하여 이벤트 발행 테스트
    callback = executor._on_output
    await callback("test line", "stdout")

    # event_bus.emit이 AGENT_OUTPUT으로 호출되었는지 확인
    calls = event_bus.emit.call_args_list
    agent_output_calls = [
        c for c in calls
        if len(c.args) > 0
        and isinstance(c.args[0], OrchestratorEvent)
        and c.args[0].type == EventType.AGENT_OUTPUT
    ]
    assert len(agent_output_calls) >= 1

    event = agent_output_calls[0].args[0]
    assert event.data["subtask_id"] == "t1"
    assert event.data["line"] == "test line"
    assert event.data["stream"] == "stdout"
    assert event.data["lane"] == "implementer"


@pytest.mark.asyncio
async def test_worker_callback_skips_empty_lines(executor, board, event_bus):
    """빈 라인은 AGENT_OUTPUT 이벤트를 발행하지 않는다."""
    worker = _make_worker(executor, board, event_bus)
    task = _make_task()

    await worker._run_with_heartbeat(task)

    callback = executor._on_output
    # 빈 라인 호출
    await callback("", "stdout")
    await callback("   ", "stderr")

    # AGENT_OUTPUT 이벤트가 발행되지 않았어야 함
    agent_output_calls = [
        c for c in event_bus.emit.call_args_list
        if len(c.args) > 0
        and isinstance(c.args[0], OrchestratorEvent)
        and c.args[0].type == EventType.AGENT_OUTPUT
    ]
    assert len(agent_output_calls) == 0


@pytest.mark.asyncio
async def test_worker_callback_truncates_long_lines(executor, board, event_bus):
    """2000자 초과 라인이 잘린다."""
    worker = _make_worker(executor, board, event_bus)
    task = _make_task()

    await worker._run_with_heartbeat(task)

    callback = executor._on_output
    long_line = "x" * 3000
    await callback(long_line, "stdout")

    agent_output_calls = [
        c for c in event_bus.emit.call_args_list
        if len(c.args) > 0
        and isinstance(c.args[0], OrchestratorEvent)
        and c.args[0].type == EventType.AGENT_OUTPUT
    ]
    assert len(agent_output_calls) == 1
    assert len(agent_output_calls[0].args[0].data["line"]) == 2000


@pytest.mark.asyncio
async def test_worker_still_completes_task_with_streaming(executor, board, event_bus):
    """스트리밍이 태스크 완료를 방해하지 않는다."""
    worker = _make_worker(executor, board, event_bus)
    task = _make_task()

    result = await worker._run_with_heartbeat(task)
    assert result.output == "done"
