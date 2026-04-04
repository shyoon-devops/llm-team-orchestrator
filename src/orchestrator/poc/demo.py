"""★ PoC 전용 — MVP 전환 시 제거

End-to-end demo using mock adapters to validate the full pipeline.
"""

from __future__ import annotations

import asyncio
import tempfile

import structlog

from orchestrator.context.artifact_store import ArtifactStore
from orchestrator.graph.builder import build_graph
from orchestrator.models.schemas import AdapterConfig
from orchestrator.poc.mock_adapters import MockCLIAdapter

logger = structlog.get_logger()


async def run_demo() -> None:
    """Run a complete plan → implement → review pipeline with mock adapters."""
    print("=" * 60)
    print("  LLM Team Orchestrator — PoC Demo")
    print("  Using mock adapters (no real CLI calls)")
    print("=" * 60)

    config = AdapterConfig(api_key="mock-key", timeout=30)

    planner = MockCLIAdapter(
        config=config,
        responses={
            "default": (
                "## Plan\n"
                "1. Create user authentication module\n"
                "2. Add JWT token generation\n"
                "3. Implement middleware\n"
                "4. Write tests"
            )
        },
        latency_ms=50,
    )
    implementer = MockCLIAdapter(
        config=config,
        responses={
            "default": (
                "```python\n"
                "from fastapi import Depends\n"
                "from jose import jwt\n\n"
                "def create_token(user_id: str) -> str:\n"
                "    return jwt.encode({'sub': user_id}, SECRET)\n"
                "```"
            )
        },
        latency_ms=100,
    )
    reviewer = MockCLIAdapter(
        config=config,
        responses={
            "default": (
                "## Review\n"
                "- **Verdict**: APPROVE\n"
                "- No critical issues found\n"
                "- Suggestion: Add token expiration"
            )
        },
        latency_ms=50,
    )

    with tempfile.TemporaryDirectory(prefix="orchestrator-demo-") as tmp_dir:
        artifact_store = ArtifactStore(tmp_dir)

        graph = build_graph(planner, implementer, reviewer, artifact_store)

        print("\n[1/3] Planning...")
        result = await graph.ainvoke(
            {
                "task": "Implement user authentication with JWT tokens",
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

        print("\n--- Results ---")
        print(f"Status: {result['status']}")
        print(f"Messages: {len(result['messages'])}")
        print(f"Plan: {result['plan_summary'][:100]}...")
        print(f"Review: {result['review_summary'][:100]}...")

        print("\n--- Artifacts ---")
        for artifact in artifact_store.list_artifacts():
            content = artifact_store.load(artifact)
            print(f"  {artifact} ({len(content)} chars)")

        print("\n--- Adapter Call Logs ---")
        print(f"  Planner calls: {len(planner.call_log)}")
        print(f"  Implementer calls: {len(implementer.call_log)}")
        print(f"  Reviewer calls: {len(reviewer.call_log)}")

        print(f"\n{'=' * 60}")
        if result["status"] == "reviewed":
            print("  PoC Demo: SUCCESS — Full pipeline completed")
        else:
            print(f"  PoC Demo: PARTIAL — Status: {result['status']}")
        print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(run_demo())
