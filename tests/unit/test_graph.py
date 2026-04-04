"""Unit tests for LangGraph orchestration using mock adapters."""

import pytest

from orchestrator.context.artifact_store import ArtifactStore
from orchestrator.graph.builder import build_graph
from orchestrator.models.schemas import AdapterConfig
from orchestrator.poc.mock_adapters import FailingMockAdapter, MockCLIAdapter


@pytest.fixture
def config() -> AdapterConfig:
    return AdapterConfig(api_key="test", timeout=30)


@pytest.fixture
def artifact_store(tmp_path: object) -> ArtifactStore:
    return ArtifactStore(str(tmp_path))


@pytest.fixture
def mock_adapter(config: AdapterConfig) -> MockCLIAdapter:
    return MockCLIAdapter(
        config=config,
        responses={"default": "Mock output for testing"},
        latency_ms=10,
    )


class TestGraphBuilder:
    async def test_full_pipeline_success(
        self,
        mock_adapter: MockCLIAdapter,
        artifact_store: ArtifactStore,
    ) -> None:
        graph = build_graph(
            planner=mock_adapter,
            implementer=mock_adapter,
            reviewer=mock_adapter,
            artifact_store=artifact_store,
        )
        result = await graph.ainvoke(
            {
                "task": "Implement hello world",
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
        assert result["status"] == "reviewed"
        assert len(result["messages"]) == 3  # plan + implement + review
        assert mock_adapter.call_log  # adapter was actually called

    async def test_pipeline_with_plan_failure_retries(
        self,
        config: AdapterConfig,
        artifact_store: ArtifactStore,
    ) -> None:
        failing = FailingMockAdapter(config=config, error_message="plan exploded")
        mock_ok = MockCLIAdapter(config=config, responses={"default": "ok"}, latency_ms=10)

        graph = build_graph(
            planner=failing,
            implementer=mock_ok,
            reviewer=mock_ok,
            artifact_store=artifact_store,
        )
        result = await graph.ainvoke(
            {
                "task": "will fail planning",
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
        # Should have exhausted retries
        assert result["retry_count"] >= 3
        assert "failed" in result["status"]

    async def test_artifacts_created(
        self,
        mock_adapter: MockCLIAdapter,
        artifact_store: ArtifactStore,
    ) -> None:
        graph = build_graph(
            planner=mock_adapter,
            implementer=mock_adapter,
            reviewer=mock_adapter,
            artifact_store=artifact_store,
        )
        await graph.ainvoke(
            {
                "task": "create artifacts test",
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
        assert artifact_store.exists("plan.md")
        assert artifact_store.exists("implementation.md")
        assert artifact_store.exists("review.md")
