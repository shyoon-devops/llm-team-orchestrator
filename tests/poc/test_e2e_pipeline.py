"""★ PoC 전용 — E2E pipeline test using mock adapters."""

from __future__ import annotations

import pytest

from orchestrator.context.artifact_store import ArtifactStore
from orchestrator.graph.builder import build_graph
from orchestrator.models.schemas import AdapterConfig
from orchestrator.poc.mock_adapters import MockCLIAdapter


@pytest.fixture
def config() -> AdapterConfig:
    return AdapterConfig(api_key="test", timeout=30)


@pytest.fixture
def artifact_store(tmp_path: object) -> ArtifactStore:
    return ArtifactStore(str(tmp_path))


class TestE2EPipeline:
    async def test_full_pipeline_completes(
        self,
        config: AdapterConfig,
        artifact_store: ArtifactStore,
    ) -> None:
        planner = MockCLIAdapter(
            config=config,
            responses={"default": "Plan: step 1, step 2, step 3"},
            latency_ms=10,
        )
        implementer = MockCLIAdapter(
            config=config,
            responses={"default": "def hello(): return 'world'"},
            latency_ms=10,
        )
        reviewer = MockCLIAdapter(
            config=config,
            responses={"default": "LGTM - approved"},
            latency_ms=10,
        )

        graph = build_graph(planner, implementer, reviewer, artifact_store)
        result = await graph.ainvoke(
            {
                "task": "E2E test: build hello world API",
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

        # Verify pipeline completion
        assert result["status"] == "reviewed"
        assert len(result["messages"]) == 3

        # Verify artifacts were created
        assert artifact_store.exists("plan.md")
        assert artifact_store.exists("implementation.md")
        assert artifact_store.exists("review.md")

        # Verify each adapter was called exactly once
        assert len(planner.call_log) == 1
        assert len(implementer.call_log) == 1
        assert len(reviewer.call_log) == 1

        # Verify content
        plan = artifact_store.load("plan.md")
        assert "step 1" in plan
