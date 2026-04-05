"""Typer CLI application."""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.table import Table

console = Console()
app = typer.Typer(
    name="orchestrator",
    help="Agent Team Orchestrator — multi-LLM agent team coordination",
)


@app.command()
def run(
    task: str = typer.Argument(..., help="태스크 설명"),
    repo: str | None = typer.Option(None, "--repo", "-r", help="대상 Git 저장소 경로"),
    team_preset: str | None = typer.Option(None, "--team-preset", "-t", help="팀 프리셋 이름"),
    timeout: int = typer.Option(300, "--timeout", help="타임아웃 (초)"),
) -> None:
    """태스크를 실행한다."""

    async def _run() -> None:
        from orchestrator.core.engine import OrchestratorEngine

        engine = OrchestratorEngine()
        pipeline = await engine.submit_task(
            task,
            team_preset=team_preset,
            target_repo=repo,
        )
        console.print(f"[green]Pipeline created:[/green] {pipeline.task_id}")
        console.print(f"[blue]Status:[/blue] {pipeline.status}")

    asyncio.run(_run())


@app.command()
def status(
    task_id: str = typer.Argument(..., help="파이프라인 ID"),
) -> None:
    """파이프라인 상태를 조회한다."""

    async def _status() -> None:
        from orchestrator.core.engine import OrchestratorEngine

        engine = OrchestratorEngine()
        pipeline = await engine.get_pipeline(task_id)
        if pipeline is None:
            console.print(f"[red]Pipeline not found:[/red] {task_id}")
            raise typer.Exit(code=1)
        console.print(f"[blue]Task:[/blue] {pipeline.task}")
        console.print(f"[blue]Status:[/blue] {pipeline.status}")

    asyncio.run(_status())


@app.command()
def cancel(
    task_id: str = typer.Argument(..., help="취소할 파이프라인 ID"),
) -> None:
    """태스크를 취소한다."""

    async def _cancel() -> None:
        from orchestrator.core.engine import OrchestratorEngine

        engine = OrchestratorEngine()
        cancelled = await engine.cancel_task(task_id)
        if cancelled:
            console.print(f"[green]Pipeline cancelled:[/green] {task_id}")
        else:
            console.print(f"[red]Cannot cancel:[/red] {task_id}")
            raise typer.Exit(code=1)

    asyncio.run(_cancel())


@app.command()
def presets() -> None:
    """프리셋 목록을 조회한다."""
    from orchestrator.core.engine import OrchestratorEngine

    engine = OrchestratorEngine()

    agent_presets = engine.list_agent_presets()
    team_presets = engine.list_team_presets()

    if agent_presets:
        table = Table(title="Agent Presets")
        table.add_column("Name")
        table.add_column("Description")
        table.add_column("CLI")
        for p in agent_presets:
            table.add_row(p.name, p.description, p.preferred_cli or "auto")
        console.print(table)
    else:
        console.print("[dim]No agent presets registered.[/dim]")

    if team_presets:
        team_table = Table(title="Team Presets")
        team_table.add_column("Name")
        team_table.add_column("Description")
        team_table.add_column("Workflow")
        for tp in team_presets:
            team_table.add_row(tp.name, tp.description, tp.workflow)
        console.print(team_table)
    else:
        console.print("[dim]No team presets registered.[/dim]")


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", help="바인드 호스트"),
    port: int = typer.Option(8000, "--port", help="바인드 포트"),
    reload: bool = typer.Option(False, "--reload", help="리로드 모드"),
) -> None:
    """API 서버를 실행한다."""
    import uvicorn

    uvicorn.run(
        "orchestrator.api.app:app",
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    app()
