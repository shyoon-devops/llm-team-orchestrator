"""LangGraph node functions for plan → implement → review pipeline."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import structlog

from orchestrator.errors.exceptions import CLIError
from orchestrator.events.types import EventType, OrchestratorEvent

if TYPE_CHECKING:
    from orchestrator.adapters.base import CLIAdapter
    from orchestrator.context.artifact_store import ArtifactStore
    from orchestrator.events.bus import EventBus
    from orchestrator.graph.state import OrchestratorState

logger = structlog.get_logger()


def _make_message(role: str, content: str) -> dict[str, object]:
    return {"role": role, "content": content, "timestamp": time.time()}


def create_plan_node(
    adapter: CLIAdapter,
    artifact_store: ArtifactStore,
    event_bus: EventBus | None = None,
    task_id: str = "",
) -> Any:
    """Create a plan node that generates a task plan."""

    async def plan_node(state: OrchestratorState) -> dict[str, Any]:
        log = logger.bind(node="plan", task=state["task"][:80])
        log.info("planning_started")
        if event_bus:
            await event_bus.publish(
                OrchestratorEvent(type=EventType.NODE_STARTED, node="plan", task_id=task_id)
            )

        prompt = (
            "You are a software architect. "
            "Analyze this task and create a detailed implementation plan.\n\n"
            f"Task: {state['task']}\n\n"
            "Output a structured plan with:\n"
            "1. Key requirements\n"
            "2. Implementation steps\n"
            "3. Files to create/modify\n"
            "4. Potential risks"
        )

        try:
            result = await adapter.run(prompt, timeout=adapter.config.timeout)
            artifact_path = artifact_store.save(
                "plan.md",
                result.output,
                metadata={"provider": adapter.provider_name, "tokens": result.tokens_used},
            )
            log.info("planning_completed", tokens=result.tokens_used)
            if event_bus:
                await event_bus.publish(
                    OrchestratorEvent(
                        type=EventType.NODE_COMPLETED,
                        node="plan",
                        task_id=task_id,
                        data={"tokens": result.tokens_used},
                    )
                )
            return {
                "plan_summary": result.output[:500],
                "plan_artifact": str(artifact_path),
                "status": "planned",
                "messages": [_make_message("plan", f"Plan created: {result.output[:200]}")],
            }
        except CLIError as e:
            log.error("planning_failed", error=str(e))
            if event_bus:
                await event_bus.publish(
                    OrchestratorEvent(
                        type=EventType.NODE_FAILED,
                        node="plan",
                        task_id=task_id,
                        data={"error": str(e)},
                    )
                )
            return {
                "status": "plan_failed",
                "error": str(e),
                "retry_count": state.get("retry_count", 0) + 1,
                "messages": [_make_message("plan", f"Plan failed: {e}")],
            }

    return plan_node


def create_implement_node(
    adapter: CLIAdapter,
    artifact_store: ArtifactStore,
    event_bus: EventBus | None = None,
    task_id: str = "",
) -> Any:
    """Create an implement node that generates code based on the plan."""

    async def implement_node(state: OrchestratorState) -> dict[str, Any]:
        log = logger.bind(node="implement", task=state["task"][:80])
        log.info("implementation_started")
        if event_bus:
            await event_bus.publish(
                OrchestratorEvent(
                    type=EventType.NODE_STARTED, node="implement", task_id=task_id
                )
            )

        plan = state.get("plan_summary", "")
        prompt = f"""You are a software engineer. Implement the following plan.

Task: {state["task"]}

Plan:
{plan}

Write clean, well-tested code. Include type annotations."""

        try:
            result = await adapter.run(prompt, timeout=adapter.config.timeout)
            artifact_path = artifact_store.save(
                "implementation.md",
                result.output,
                metadata={"provider": adapter.provider_name, "tokens": result.tokens_used},
            )
            log.info("implementation_completed", tokens=result.tokens_used)
            if event_bus:
                await event_bus.publish(
                    OrchestratorEvent(
                        type=EventType.NODE_COMPLETED,
                        node="implement",
                        task_id=task_id,
                        data={"tokens": result.tokens_used},
                    )
                )
            return {
                "code_artifact": str(artifact_path),
                "status": "implemented",
                "messages": [
                    _make_message("implement", f"Implementation done: {result.output[:200]}")
                ],
            }
        except CLIError as e:
            log.error("implementation_failed", error=str(e))
            if event_bus:
                await event_bus.publish(
                    OrchestratorEvent(
                        type=EventType.NODE_FAILED,
                        node="implement",
                        task_id=task_id,
                        data={"error": str(e)},
                    )
                )
            return {
                "status": "implement_failed",
                "error": str(e),
                "retry_count": state.get("retry_count", 0) + 1,
                "messages": [_make_message("implement", f"Implementation failed: {e}")],
            }

    return implement_node


def create_review_node(
    adapter: CLIAdapter,
    artifact_store: ArtifactStore,
    event_bus: EventBus | None = None,
    task_id: str = "",
) -> Any:
    """Create a review node that reviews the implementation."""

    async def review_node(state: OrchestratorState) -> dict[str, Any]:
        log = logger.bind(node="review", task=state["task"][:80])
        log.info("review_started")
        if event_bus:
            await event_bus.publish(
                OrchestratorEvent(type=EventType.NODE_STARTED, node="review", task_id=task_id)
            )

        # Load implementation if available
        impl_content = ""
        code_artifact = state.get("code_artifact", "")
        if code_artifact and artifact_store.exists("implementation.md"):
            impl_content = artifact_store.load("implementation.md")

        prompt = f"""You are a code reviewer. Review this implementation.

Task: {state["task"]}

Implementation:
{impl_content[:3000]}

Provide:
1. Issues found (critical/warning/info)
2. Suggestions for improvement
3. Overall verdict (approve/request_changes)"""

        try:
            result = await adapter.run(prompt, timeout=adapter.config.timeout)
            artifact_path = artifact_store.save(
                "review.md",
                result.output,
                metadata={"provider": adapter.provider_name, "tokens": result.tokens_used},
            )
            log.info("review_completed", tokens=result.tokens_used)
            if event_bus:
                await event_bus.publish(
                    OrchestratorEvent(
                        type=EventType.NODE_COMPLETED,
                        node="review",
                        task_id=task_id,
                        data={"tokens": result.tokens_used},
                    )
                )
            return {
                "review_summary": result.output[:500],
                "review_artifact": str(artifact_path),
                "status": "reviewed",
                "messages": [_make_message("review", f"Review done: {result.output[:200]}")],
            }
        except CLIError as e:
            log.error("review_failed", error=str(e))
            if event_bus:
                await event_bus.publish(
                    OrchestratorEvent(
                        type=EventType.NODE_FAILED,
                        node="review",
                        task_id=task_id,
                        data={"error": str(e)},
                    )
                )
            return {
                "status": "review_failed",
                "error": str(e),
                "retry_count": state.get("retry_count", 0) + 1,
                "messages": [_make_message("review", f"Review failed: {e}")],
            }

    return review_node
