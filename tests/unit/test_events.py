"""Unit tests for event bus and event types."""

from orchestrator.events.bus import EventBus
from orchestrator.events.types import EventType, OrchestratorEvent


class TestOrchestratorEvent:
    def test_event_creation(self) -> None:
        event = OrchestratorEvent(type=EventType.NODE_STARTED, node="plan")
        assert event.type == EventType.NODE_STARTED
        assert event.node == "plan"
        assert event.timestamp > 0

    def test_event_with_data(self) -> None:
        event = OrchestratorEvent(
            type=EventType.NODE_COMPLETED, node="implement", data={"tokens": 100}
        )
        assert event.data["tokens"] == 100

    def test_event_serialization(self) -> None:
        event = OrchestratorEvent(type=EventType.PIPELINE_STARTED)
        dumped = event.model_dump()
        assert dumped["type"] == "pipeline.started"


class TestEventBus:
    async def test_publish_and_subscribe(self) -> None:
        bus = EventBus()
        received: list[OrchestratorEvent] = []

        async def handler(event: OrchestratorEvent) -> None:
            received.append(event)

        bus.subscribe(handler)
        await bus.publish(OrchestratorEvent(type=EventType.NODE_STARTED, node="plan"))

        assert len(received) == 1
        assert received[0].node == "plan"

    async def test_multiple_subscribers(self) -> None:
        bus = EventBus()
        count = [0, 0]

        async def handler1(event: OrchestratorEvent) -> None:
            count[0] += 1

        async def handler2(event: OrchestratorEvent) -> None:
            count[1] += 1

        bus.subscribe(handler1)
        bus.subscribe(handler2)
        await bus.publish(OrchestratorEvent(type=EventType.NODE_STARTED))

        assert count == [1, 1]

    async def test_history(self) -> None:
        bus = EventBus()
        await bus.publish(OrchestratorEvent(type=EventType.NODE_STARTED))
        await bus.publish(OrchestratorEvent(type=EventType.NODE_COMPLETED))

        assert len(bus.history) == 2
        assert bus.history[0].type == EventType.NODE_STARTED

    async def test_clear_history(self) -> None:
        bus = EventBus()
        await bus.publish(OrchestratorEvent(type=EventType.NODE_STARTED))
        bus.clear_history()
        assert len(bus.history) == 0

    async def test_unsubscribe(self) -> None:
        bus = EventBus()
        received: list[OrchestratorEvent] = []

        async def handler(event: OrchestratorEvent) -> None:
            received.append(event)

        bus.subscribe(handler)
        await bus.publish(OrchestratorEvent(type=EventType.NODE_STARTED))
        bus.unsubscribe(handler)
        await bus.publish(OrchestratorEvent(type=EventType.NODE_COMPLETED))

        assert len(received) == 1
