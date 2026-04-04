"""★ PoC 전용 — Simple usage example for the orchestrator.

Usage:
    uv run python examples/simple_pipeline.py
"""

from __future__ import annotations

import asyncio
import tempfile

from orchestrator.context.artifact_store import ArtifactStore
from orchestrator.graph.builder import build_graph
from orchestrator.models.schemas import AdapterConfig
from orchestrator.poc.mock_adapters import MockCLIAdapter


async def main() -> None:
    config = AdapterConfig(api_key="mock", timeout=30)
    adapter = MockCLIAdapter(config=config, latency_ms=10)

    with tempfile.TemporaryDirectory() as tmp:
        store = ArtifactStore(tmp)
        graph = build_graph(adapter, adapter, adapter, store)

        result = await graph.ainvoke(
            {
                "task": "Add a health check endpoint to the API",
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
        print(f"Pipeline finished with status: {result['status']}")
        print(f"Total messages: {len(result['messages'])}")


if __name__ == "__main__":
    asyncio.run(main())
