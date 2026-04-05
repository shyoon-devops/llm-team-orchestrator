"""Tests for core/queue/worker.py."""

import pytest

from orchestrator.core.events.bus import EventBus
from orchestrator.core.executor.base import AgentExecutor
from orchestrator.core.models.schemas import AgentResult
from orchestrator.core.queue.board import TaskBoard
from orchestrator.core.queue.worker import AgentWorker


class MockExecutor(AgentExecutor):
    executor_type = "mock"

    async def run(self, prompt, *, timeout=300, context=None):  # noqa: ASYNC109
        return AgentResult(output=f"done: {prompt[:20]}")

    async def health_check(self):
        return True


@pytest.fixture
def mock_executor():
    return MockExecutor()


@pytest.fixture
def worker_components(mock_executor):
    board = TaskBoard()
    bus = EventBus()
    worker = AgentWorker(
        worker_id="w-1",
        lane="dev",
        board=board,
        executor=mock_executor,
        event_bus=bus,
        poll_interval=0.1,
    )
    return board, bus, worker


def test_worker_status_stopped(worker_components):
    _, _, worker = worker_components
    status = worker.get_status()
    assert status["status"] == "stopped"
    assert status["worker_id"] == "w-1"
    assert status["lane"] == "dev"


async def test_worker_start_stop(worker_components):
    _, _, worker = worker_components
    await worker.start()
    assert worker._running is True
    await worker.stop()
    assert worker._running is False


async def test_worker_double_start_raises(worker_components):
    _, _, worker = worker_components
    await worker.start()
    with pytest.raises(RuntimeError, match="already running"):
        await worker.start()
    await worker.stop()
