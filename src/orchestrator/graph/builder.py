"""LangGraph graph builder for the orchestration pipeline."""

from __future__ import annotations

from typing import TYPE_CHECKING

from langgraph.graph import END, StateGraph

from orchestrator.graph.nodes import (
    create_implement_node,
    create_plan_node,
    create_review_node,
)
from orchestrator.graph.state import OrchestratorState

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph

    from orchestrator.adapters.base import CLIAdapter
    from orchestrator.context.artifact_store import ArtifactStore


MAX_RETRIES = 3


def _should_continue(state: OrchestratorState) -> str:
    """Determine next step based on current status."""
    status = state.get("status", "")
    retry_count = state.get("retry_count", 0)

    if retry_count >= MAX_RETRIES:
        return "end"

    if status == "planned":
        return "implement"
    elif status == "implemented":
        return "review"
    elif status == "reviewed":
        return "end"
    elif status.endswith("_failed"):
        # Retry the failed step
        step = status.replace("_failed", "")
        return step if step in ("plan", "implement", "review") else "end"
    else:
        return "end"


def build_graph(
    planner: CLIAdapter,
    implementer: CLIAdapter,
    reviewer: CLIAdapter,
    artifact_store: ArtifactStore,
) -> CompiledStateGraph:  # type: ignore[type-arg]
    """Build the plan → implement → review orchestration graph."""
    graph = StateGraph(OrchestratorState)

    graph.add_node("plan", create_plan_node(planner, artifact_store))
    graph.add_node("implement", create_implement_node(implementer, artifact_store))
    graph.add_node("review", create_review_node(reviewer, artifact_store))

    graph.set_entry_point("plan")

    graph.add_conditional_edges(
        "plan",
        _should_continue,
        {"implement": "implement", "plan": "plan", "end": END},
    )
    graph.add_conditional_edges(
        "implement",
        _should_continue,
        {"review": "review", "implement": "implement", "end": END},
    )
    graph.add_conditional_edges(
        "review",
        _should_continue,
        {"end": END, "review": "review"},
    )

    return graph.compile()
