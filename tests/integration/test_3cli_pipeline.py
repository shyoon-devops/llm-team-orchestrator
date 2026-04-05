"""★ PoC 전용 — Real 3-CLI mixed pipeline integration test.

Runs plan(Claude) → implement(Codex) → review(Gemini) against test-target-repo.
Requires all 3 CLIs installed and authenticated.

Run with: uv run pytest tests/integration/test_3cli_pipeline.py -v -m integration
"""

from __future__ import annotations

import tempfile

import pytest

from orchestrator.adapters.claude import ClaudeAdapter
from orchestrator.adapters.codex import CodexAdapter
from orchestrator.adapters.gemini import GeminiAdapter
from orchestrator.context.artifact_store import ArtifactStore
from orchestrator.events.bus import EventBus
from orchestrator.graph.builder import build_graph
from orchestrator.models.schemas import AdapterConfig


@pytest.mark.integration
class TestReal3CLIPipeline:
    async def test_full_pipeline_3cli(self) -> None:
        """Run plan→implement→review with real Claude, Codex, Gemini CLIs."""
        planner = ClaudeAdapter(AdapterConfig(api_key="firstparty", timeout=120))
        implementer = CodexAdapter(AdapterConfig(timeout=120))
        reviewer = GeminiAdapter(AdapterConfig(timeout=120))

        artifact_store = ArtifactStore(tempfile.mkdtemp(prefix="3cli-test-"))
        event_bus = EventBus()

        graph = build_graph(
            planner,
            implementer,
            reviewer,
            artifact_store,
            event_bus,
            task_id="3cli-e2e",
        )

        result = await graph.ainvoke(
            {
                "task": "Write a Python function that adds two numbers and returns the result",
                "plan_summary": "",
                "plan_artifact": "",
                "code_artifact": "",
                "review_summary": "",
                "review_artifact": "",
                "status": "",
                "error": "",
                "retry_count": 0,
                "messages": [],
            }
        )

        # Verify pipeline completed
        assert result["status"] == "reviewed", f"Pipeline ended with: {result['status']}, error: {result.get('error', '')}"
        assert len(result["messages"]) == 3

        # Verify artifacts
        assert artifact_store.exists("plan.md")
        assert artifact_store.exists("implementation.md")
        assert artifact_store.exists("review.md")

        # Verify artifact content is real LLM output (not mock)
        plan = artifact_store.load("plan.md")
        assert len(plan) > 20, "Plan should be non-trivial LLM output"

        impl = artifact_store.load("implementation.md")
        assert len(impl) > 20, "Implementation should be non-trivial LLM output"

        review = artifact_store.load("review.md")
        assert len(review) > 20, "Review should be non-trivial LLM output"

        # Verify events
        event_types = [e.type.value for e in event_bus.history]
        assert "node.started" in event_types
        assert "node.completed" in event_types
