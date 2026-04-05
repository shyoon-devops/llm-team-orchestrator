"""★ PoC 전용 — User-scenario E2E test.

Simulates a user submitting a task through the web API,
then verifies the full pipeline completes with events, artifacts, and agent status updates.
"""

from __future__ import annotations

import asyncio

import pytest

from orchestrator.config.schema import AgentDef, OrchestratorConfig
from orchestrator.web.app import AppState


@pytest.fixture
def mock_config() -> OrchestratorConfig:
    return OrchestratorConfig(
        agents={
            "planner": AgentDef(cli="mock", role="architect", timeout=30),
            "implementer": AgentDef(cli="mock", role="engineer", timeout=30),
            "reviewer": AgentDef(cli="mock", role="reviewer", timeout=30),
        }
    )


class TestUserScenarioE2E:
    async def test_submit_task_and_wait_for_completion(
        self, mock_config: OrchestratorConfig
    ) -> None:
        """User submits a task → pipeline runs → events emitted → artifacts created."""
        state = AppState(mock_config)

        # 1. Submit task (simulates POST /api/tasks)
        task_id = "e2e-test-01"
        bg_task = asyncio.create_task(
            state.run_pipeline(task_id, "Build a REST API for user management")
        )

        # 2. Wait for pipeline to complete
        await asyncio.wait_for(bg_task, timeout=30)

        # 3. Verify pipeline status (simulates GET /api/tasks/{id})
        pipeline = state.pipelines[task_id]
        assert pipeline.status.value == "completed"
        assert pipeline.error == ""
        assert len(pipeline.messages) == 3  # plan + implement + review

        # 4. Verify artifacts created (simulates GET /api/artifacts)
        artifacts = state.artifact_store.list_artifacts()
        assert "plan.md" in artifacts
        assert "implementation.md" in artifacts
        assert "review.md" in artifacts

        # 5. Verify artifact content is non-empty
        plan = state.artifact_store.load("plan.md")
        assert len(plan) > 0

        # 6. Verify events were emitted (simulates GET /api/events)
        events = state.event_bus.history
        event_types = [e.type.value for e in events]
        assert "pipeline.started" in event_types
        assert "node.started" in event_types
        assert "node.completed" in event_types
        assert "pipeline.completed" in event_types

        # 7. Verify agent statuses were tracked (simulates GET /api/agents)
        agents = state.agent_tracker.get_all()
        assert len(agents) == 3
        # After completion, agents should be in completed state
        statuses = {a["id"]: a["status"] for a in agents}
        assert statuses["planner"] == "completed"
        assert statuses["implementer"] == "completed"
        assert statuses["reviewer"] == "completed"

    async def test_pipeline_failure_handling(
        self, mock_config: OrchestratorConfig
    ) -> None:
        """When pipeline fails, status and events should reflect the failure."""
        state = AppState(mock_config)

        # Override adapter to always fail
        from orchestrator.models.schemas import AdapterConfig
        from orchestrator.poc.mock_adapters import FailingMockAdapter

        failing = FailingMockAdapter(
            AdapterConfig(api_key="", timeout=30),
            error_message="Simulated plan failure",
        )
        state._adapters = {
            "planner": failing,
            "implementer": failing,
            "reviewer": failing,
        }

        task_id = "e2e-fail-01"
        bg_task = asyncio.create_task(
            state.run_pipeline(task_id, "This should fail")
        )
        await asyncio.wait_for(bg_task, timeout=30)

        pipeline = state.pipelines[task_id]
        assert pipeline.status.value == "failed"

        # Events should include failure
        event_types = [e.type.value for e in state.event_bus.history]
        assert "pipeline.started" in event_types
        assert "node.failed" in event_types

    async def test_multiple_tasks_sequential(
        self, mock_config: OrchestratorConfig
    ) -> None:
        """Multiple tasks can run sequentially."""
        state = AppState(mock_config)

        for i in range(3):
            task_id = f"seq-{i}"
            bg_task = asyncio.create_task(
                state.run_pipeline(task_id, f"Task {i}")
            )
            await asyncio.wait_for(bg_task, timeout=30)

        assert len(state.pipelines) == 3
        for i in range(3):
            assert state.pipelines[f"seq-{i}"].status.value == "completed"
