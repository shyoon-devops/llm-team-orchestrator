"""Typer CLI entrypoint for the orchestrator."""

from __future__ import annotations

import asyncio

import structlog
import typer

from orchestrator.auth.provider import EnvAuthProvider
from orchestrator.context.artifact_store import ArtifactStore
from orchestrator.graph.builder import build_graph
from orchestrator.models.schemas import AdapterConfig
from orchestrator.poc.mock_adapters import MockCLIAdapter

app = typer.Typer(
    name="orchestrator",
    help="Multi-LLM CLI team coding orchestrator",
)
logger = structlog.get_logger()


@app.command()
def run(
    task: str = typer.Argument(..., help="Task description to orchestrate"),
    artifact_dir: str = typer.Option("/tmp/orchestrator-poc", help="Artifact storage directory"),
    mock: bool = typer.Option(False, help="Use mock adapters (no real CLI calls)"),
    timeout: int = typer.Option(300, help="Timeout per CLI call in seconds"),
) -> None:
    """Run the plan → implement → review pipeline."""
    asyncio.run(_run_pipeline(task, artifact_dir, mock, timeout))


async def _run_pipeline(task: str, artifact_dir: str, mock: bool, timeout: int) -> None:
    config = AdapterConfig(timeout=timeout)
    artifact_store = ArtifactStore(artifact_dir)

    if mock:
        adapter = MockCLIAdapter(
            config=config,
            responses={"default": "Mock response for orchestrator demo"},
            latency_ms=100,
        )
        planner = implementer = reviewer = adapter
        typer.echo("Using mock adapters (no real CLI calls)")
    else:
        # Use real adapters based on available providers
        auth = EnvAuthProvider()
        available = auth.available_providers()
        if not available:
            typer.echo("No API keys found. Use --mock for testing, or set environment variables.")
            typer.echo("See .env.example for required variables.")
            raise typer.Exit(1)

        # For PoC, use mock as fallback
        typer.echo(f"Available providers: {', '.join(available)}")
        adapter = MockCLIAdapter(config=config, responses={"default": "Mock fallback"})
        planner = implementer = reviewer = adapter

    graph = build_graph(planner, implementer, reviewer, artifact_store)

    typer.echo(f"\nTask: {task}")
    typer.echo("Pipeline: plan → implement → review\n")

    result = await graph.ainvoke(
        {
            "task": task,
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

    typer.echo(f"\nStatus: {result['status']}")
    typer.echo(f"Messages: {len(result['messages'])}")
    if result.get("error"):
        typer.echo(f"Error: {result['error']}")
    typer.echo(f"\nArtifacts saved to: {artifact_dir}")


@app.command()
def adapters() -> None:
    """List available CLI adapters and their status."""
    auth = EnvAuthProvider()
    available = auth.available_providers()

    provider_info = [
        ("anthropic", "Claude Code", "claude --version"),
        ("openai", "Codex CLI", "codex --version"),
        ("google", "Gemini CLI", "gemini --version"),
    ]

    for provider_id, name, _cmd in provider_info:
        has_key = provider_id in available
        status = "API key set" if has_key else "No API key"
        typer.echo(f"  {name:15s} [{provider_id:10s}] — {status}")


@app.command()
def status() -> None:
    """Show orchestrator status and configuration."""
    typer.echo("Orchestrator v0.1.0 (PoC)")
    typer.echo("Python: 3.12+")
    adapters()


if __name__ == "__main__":
    app()
