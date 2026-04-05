"""★ PoC 전용 — Agent status tracker via EventBus."""

from __future__ import annotations

from typing import TYPE_CHECKING

from orchestrator.events.types import EventType, OrchestratorEvent
from orchestrator.models.schemas import AgentStatus

if TYPE_CHECKING:
    from orchestrator.events.bus import EventBus


class AgentInfo:
    """Mutable agent state tracked by AgentTracker."""

    __slots__ = ("last_event", "name", "provider", "status")

    def __init__(self, name: str, provider: str) -> None:
        self.name = name
        self.provider = provider
        self.status: AgentStatus = AgentStatus.IDLE
        self.last_event: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.name,
            "provider": self.provider,
            "status": self.status.value,
            "last_event": self.last_event,
        }


# Map node names to role names
_NODE_ROLE_MAP: dict[str, str] = {
    "plan": "planner",
    "implement": "implementer",
    "review": "reviewer",
}


class AgentTracker:
    """Tracks agent statuses by subscribing to EventBus events."""

    def __init__(self, event_bus: EventBus) -> None:
        self._agents: dict[str, AgentInfo] = {}
        self._event_bus = event_bus
        event_bus.subscribe(self._on_event)

    def register(self, name: str, provider: str) -> None:
        """Register an agent to track."""
        self._agents[name] = AgentInfo(name, provider)

    def get_all(self) -> list[dict[str, str]]:
        """Return all agent statuses as dicts."""
        return [a.to_dict() for a in self._agents.values()]

    def get(self, name: str) -> dict[str, str] | None:
        agent = self._agents.get(name)
        return agent.to_dict() if agent else None

    async def _on_event(self, event: OrchestratorEvent) -> None:
        """Handle EventBus events to update agent status."""
        if not event.node:
            return

        role = _NODE_ROLE_MAP.get(event.node, event.node)
        agent = self._agents.get(role)
        if agent is None:
            return

        if event.type == EventType.NODE_STARTED:
            agent.status = AgentStatus.WORKING
            agent.last_event = f"started at {event.timestamp:.0f}"
        elif event.type == EventType.NODE_COMPLETED:
            agent.status = AgentStatus.COMPLETED
            agent.last_event = f"completed at {event.timestamp:.0f}"
        elif event.type == EventType.NODE_FAILED:
            agent.status = AgentStatus.ERROR
            error = event.data.get("error", "unknown")
            agent.last_event = f"failed: {str(error)[:100]}"

    def reset_all(self) -> None:
        """Reset all agents to IDLE."""
        for agent in self._agents.values():
            agent.status = AgentStatus.IDLE
            agent.last_event = ""
