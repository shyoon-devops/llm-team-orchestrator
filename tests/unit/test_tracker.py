"""Unit tests for AgentTracker."""

from __future__ import annotations

import pytest

from orchestrator.events.bus import EventBus
from orchestrator.events.tracker import AgentTracker
from orchestrator.events.types import EventType, OrchestratorEvent
from orchestrator.models.schemas import AgentStatus


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def tracker(event_bus: EventBus) -> AgentTracker:
    t = AgentTracker(event_bus)
    t.register("planner", "claude")
    t.register("implementer", "codex")
    t.register("reviewer", "gemini")
    return t


class TestAgentTracker:
    def test_register_and_get_all(self, tracker: AgentTracker) -> None:
        agents = tracker.get_all()
        assert len(agents) == 3
        names = {a["id"] for a in agents}
        assert names == {"planner", "implementer", "reviewer"}

    def test_initial_status_is_idle(self, tracker: AgentTracker) -> None:
        agents = tracker.get_all()
        for agent in agents:
            assert agent["status"] == AgentStatus.IDLE

    async def test_node_started_updates_status(
        self, tracker: AgentTracker, event_bus: EventBus
    ) -> None:
        await event_bus.publish(OrchestratorEvent(type=EventType.NODE_STARTED, node="plan"))
        agent = tracker.get("planner")
        assert agent is not None
        assert agent["status"] == AgentStatus.WORKING

    async def test_node_completed_updates_status(
        self, tracker: AgentTracker, event_bus: EventBus
    ) -> None:
        await event_bus.publish(OrchestratorEvent(type=EventType.NODE_COMPLETED, node="implement"))
        agent = tracker.get("implementer")
        assert agent is not None
        assert agent["status"] == AgentStatus.COMPLETED

    async def test_node_failed_updates_status(
        self, tracker: AgentTracker, event_bus: EventBus
    ) -> None:
        await event_bus.publish(
            OrchestratorEvent(
                type=EventType.NODE_FAILED, node="review", data={"error": "timeout"}
            )
        )
        agent = tracker.get("reviewer")
        assert agent is not None
        assert agent["status"] == AgentStatus.ERROR
        assert "timeout" in agent["last_event"]

    async def test_reset_all(self, tracker: AgentTracker, event_bus: EventBus) -> None:
        await event_bus.publish(OrchestratorEvent(type=EventType.NODE_STARTED, node="plan"))
        tracker.reset_all()
        agent = tracker.get("planner")
        assert agent is not None
        assert agent["status"] == AgentStatus.IDLE

    def test_get_nonexistent(self, tracker: AgentTracker) -> None:
        assert tracker.get("nonexistent") is None

    async def test_unknown_node_ignored(
        self, tracker: AgentTracker, event_bus: EventBus
    ) -> None:
        """Events for unregistered nodes should be safely ignored."""
        await event_bus.publish(OrchestratorEvent(type=EventType.NODE_STARTED, node="unknown"))
        # No error, statuses unchanged
        for agent in tracker.get_all():
            assert agent["status"] == AgentStatus.IDLE

    def test_register_for_task(self, event_bus: EventBus) -> None:
        """Agents registered under different task_ids are isolated."""
        tracker = AgentTracker(event_bus)
        tracker.register_for_task("task-A", "planner", "claude")
        tracker.register_for_task("task-B", "planner", "gemini")

        a_agents = tracker.get_all(task_id="task-A")
        b_agents = tracker.get_all(task_id="task-B")

        assert len(a_agents) == 1
        assert a_agents[0]["provider"] == "claude"
        assert len(b_agents) == 1
        assert b_agents[0]["provider"] == "gemini"

        # Default task is empty
        assert tracker.get_all() == []

    async def test_events_per_task(self, event_bus: EventBus) -> None:
        """Events with task_id only affect agents registered under that task."""
        tracker = AgentTracker(event_bus)
        tracker.register_for_task("t1", "planner", "claude")
        tracker.register_for_task("t2", "planner", "gemini")

        # Emit event for task t1 only
        await event_bus.publish(
            OrchestratorEvent(type=EventType.NODE_STARTED, node="plan", task_id="t1")
        )

        t1_agent = tracker.get("planner", task_id="t1")
        t2_agent = tracker.get("planner", task_id="t2")
        assert t1_agent is not None
        assert t1_agent["status"] == AgentStatus.WORKING
        assert t2_agent is not None
        assert t2_agent["status"] == AgentStatus.IDLE

    def test_reset_all_per_task(self, event_bus: EventBus) -> None:
        """reset_all only resets agents for the specified task."""
        tracker = AgentTracker(event_bus)
        tracker.register_for_task("t1", "planner", "claude")
        tracker.register_for_task("t2", "planner", "gemini")

        # Manually set both to WORKING
        tracker._tasks["t1"]["planner"].status = AgentStatus.WORKING
        tracker._tasks["t2"]["planner"].status = AgentStatus.WORKING

        tracker.reset_all(task_id="t1")

        t1 = tracker.get("planner", task_id="t1")
        t2 = tracker.get("planner", task_id="t2")
        assert t1 is not None
        assert t1["status"] == AgentStatus.IDLE
        assert t2 is not None
        assert t2["status"] == AgentStatus.WORKING
