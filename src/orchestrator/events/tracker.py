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

    _DEFAULT_TASK: str = ""

    def __init__(self, event_bus: EventBus) -> None:
        self._tasks: dict[str, dict[str, AgentInfo]] = {self._DEFAULT_TASK: {}}
        self._event_bus = event_bus
        event_bus.subscribe(self._on_event)

    # --- backwards-compatible helpers (default task) ---

    @property
    def _agents(self) -> dict[str, AgentInfo]:
        """Shortcut to the default-task agent dict (backwards compat)."""
        return self._tasks[self._DEFAULT_TASK]

    def register(self, name: str, provider: str) -> None:
        """Register an agent in the default task (backwards compatible)."""
        self.register_for_task(self._DEFAULT_TASK, name, provider)

    def get_all(self, task_id: str = "") -> list[dict[str, str]]:
        """Return all agent statuses as dicts for a given task."""
        agents = self._tasks.get(task_id, {})
        return [a.to_dict() for a in agents.values()]

    def get(self, name: str, *, task_id: str = "") -> dict[str, str] | None:
        agents = self._tasks.get(task_id, {})
        agent = agents.get(name)
        return agent.to_dict() if agent else None

    # --- per-task API ---

    def register_for_task(self, task_id: str, name: str, provider: str) -> None:
        """Register an agent to track under a specific task_id."""
        if task_id not in self._tasks:
            self._tasks[task_id] = {}
        self._tasks[task_id][name] = AgentInfo(name, provider)

    async def _on_event(self, event: OrchestratorEvent) -> None:
        """Handle EventBus events to update agent status."""
        if not event.node:
            return

        task_id = event.task_id
        role = _NODE_ROLE_MAP.get(event.node, event.node)

        agents = self._tasks.get(task_id, {})
        agent = agents.get(role)
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

    def reset_all(self, task_id: str = "") -> None:
        """Reset all agents for a given task to IDLE."""
        for agent in self._tasks.get(task_id, {}).values():
            agent.status = AgentStatus.IDLE
            agent.last_event = ""
