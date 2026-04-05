"""★ PoC 전용 — Unit tests for AgentWorker."""

from __future__ import annotations

import asyncio

import pytest

from orchestrator.events.bus import EventBus
from orchestrator.models.schemas import AdapterConfig
from orchestrator.poc.mock_adapters import FailingMockAdapter, MockCLIAdapter
from orchestrator.queue.board import TaskBoard
from orchestrator.queue.models import TaskItem, TaskState
from orchestrator.queue.worker import AgentWorker


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def board(event_bus: EventBus) -> TaskBoard:
    b = TaskBoard(event_bus)
    b.add_lane("implement")
    return b


@pytest.fixture
def config() -> AdapterConfig:
    return AdapterConfig(api_key="test-key", timeout=30)


@pytest.fixture
def mock_adapter(config: AdapterConfig) -> MockCLIAdapter:
    return MockCLIAdapter(
        config=config,
        responses={"default": "implemented successfully"},
        latency_ms=10,
    )


class TestAgentWorker:
    async def test_worker_claims_and_completes(
        self,
        board: TaskBoard,
        mock_adapter: MockCLIAdapter,
    ) -> None:
        """Worker claims a task, runs the adapter, and completes it."""
        task = TaskItem(title="build feature", lane="implement")
        await board.submit(task)

        worker = AgentWorker(
            worker_id="w1",
            lane="implement",
            adapter=mock_adapter,
            board=board,
        )
        await worker.start()

        # Give the worker time to process the task
        for _ in range(50):
            await asyncio.sleep(0.05)
            t = board.get_task(task.id)
            if t and t.state == TaskState.DONE:
                break

        await worker.stop()

        completed = board.get_task(task.id)
        assert completed is not None
        assert completed.state == TaskState.DONE
        assert completed.result == "implemented successfully"
        assert len(mock_adapter.call_log) == 1

    async def test_worker_handles_failure(
        self,
        board: TaskBoard,
        config: AdapterConfig,
    ) -> None:
        """When the adapter raises, the worker calls board.fail."""
        failing_adapter = FailingMockAdapter(config=config, error_message="boom")

        task = TaskItem(title="will fail", lane="implement", max_retries=1)
        await board.submit(task)

        worker = AgentWorker(
            worker_id="w2",
            lane="implement",
            adapter=failing_adapter,
            board=board,
        )
        await worker.start()

        # Wait for the task to fail (retries exhausted)
        for _ in range(50):
            await asyncio.sleep(0.05)
            t = board.get_task(task.id)
            if t and t.state == TaskState.FAILED:
                break

        await worker.stop()

        failed = board.get_task(task.id)
        assert failed is not None
        assert failed.state == TaskState.FAILED
        assert "boom" in failed.error

    async def test_worker_stop(
        self,
        board: TaskBoard,
        mock_adapter: MockCLIAdapter,
    ) -> None:
        """Worker stops gracefully on stop()."""
        worker = AgentWorker(
            worker_id="w3",
            lane="implement",
            adapter=mock_adapter,
            board=board,
        )
        await worker.start()
        assert worker.is_running is True

        await worker.stop()
        assert worker.is_running is False

    async def test_worker_continues_after_timeout(
        self,
        board: TaskBoard,
        mock_adapter: MockCLIAdapter,
    ) -> None:
        """Worker continues polling after claim timeout (no task available)."""
        worker = AgentWorker(
            worker_id="w4",
            lane="implement",
            adapter=mock_adapter,
            board=board,
        )
        await worker.start()

        # Let the worker experience a claim timeout (no tasks submitted yet)
        await asyncio.sleep(0.3)
        assert worker.is_running is True

        # Now submit a task — the worker should pick it up
        task = TaskItem(title="late task", lane="implement")
        await board.submit(task)

        for _ in range(50):
            await asyncio.sleep(0.05)
            t = board.get_task(task.id)
            if t and t.state == TaskState.DONE:
                break

        await worker.stop()

        completed = board.get_task(task.id)
        assert completed is not None
        assert completed.state == TaskState.DONE
