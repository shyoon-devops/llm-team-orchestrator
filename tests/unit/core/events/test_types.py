"""Tests for core/events/types.py."""

from orchestrator.core.events.types import EventType, OrchestratorEvent


def test_event_type_count():
    """All 28+2 event types are defined."""
    assert len(EventType) >= 28


def test_event_type_values():
    assert EventType.PIPELINE_CREATED == "pipeline.created"
    assert EventType.TASK_COMPLETED == "task.completed"
    assert EventType.WORKER_STARTED == "worker.started"
    assert EventType.AGENT_EXECUTING == "agent.executing"
    assert EventType.SYSTEM_ERROR == "system.error"


def test_orchestrator_event_creation():
    event = OrchestratorEvent(
        type=EventType.PIPELINE_CREATED,
        task_id="pipe-001",
        node="orchestrator",
        data={"task": "build JWT"},
    )
    assert event.type == EventType.PIPELINE_CREATED
    assert event.task_id == "pipe-001"
    assert event.node == "orchestrator"
    assert event.data["task"] == "build JWT"


def test_orchestrator_event_defaults():
    event = OrchestratorEvent(type=EventType.SYSTEM_HEALTH)
    assert event.task_id == ""
    assert event.node == ""
    assert event.data == {}
    assert event.timestamp is not None
