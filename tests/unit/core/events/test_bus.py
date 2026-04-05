"""Tests for core/events/bus.py."""

import pytest

from orchestrator.core.events.bus import EventBus
from orchestrator.core.events.types import EventType, OrchestratorEvent


@pytest.fixture
def bus():
    return EventBus()


async def test_emit_and_subscribe(bus):
    received = []

    async def handler(event: OrchestratorEvent):
        received.append(event)

    bus.subscribe(handler)
    event = OrchestratorEvent(type=EventType.PIPELINE_CREATED, task_id="p1")
    await bus.emit(event)
    assert len(received) == 1
    assert received[0].task_id == "p1"


async def test_unsubscribe(bus):
    received = []

    async def handler(event: OrchestratorEvent):
        received.append(event)

    bus.subscribe(handler)
    bus.unsubscribe(handler)
    await bus.emit(OrchestratorEvent(type=EventType.SYSTEM_HEALTH))
    assert len(received) == 0


async def test_get_history(bus):
    await bus.emit(OrchestratorEvent(type=EventType.PIPELINE_CREATED, task_id="p1"))
    await bus.emit(OrchestratorEvent(type=EventType.PIPELINE_COMPLETED, task_id="p2"))

    all_events = bus.get_history()
    assert len(all_events) == 2

    p1_events = bus.get_history(task_id="p1")
    assert len(p1_events) == 1
    assert p1_events[0].task_id == "p1"


async def test_clear_history(bus):
    await bus.emit(OrchestratorEvent(type=EventType.SYSTEM_HEALTH))
    assert len(bus.get_history()) == 1
    bus.clear_history()
    assert len(bus.get_history()) == 0


async def test_sync_callback(bus):
    received = []

    def sync_handler(event: OrchestratorEvent):
        received.append(event)

    bus.subscribe(sync_handler)
    await bus.emit(OrchestratorEvent(type=EventType.SYSTEM_HEALTH))
    assert len(received) == 1
