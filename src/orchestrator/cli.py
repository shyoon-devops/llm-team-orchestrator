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
presets_app = typer.Typer(name="presets", help="프리셋 관리 명령어")
app.add_typer(presets_app)


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
def resume(
    task_id: str = typer.Argument(..., help="재개할 파이프라인 ID"),
) -> None:
    """중단된 태스크를 재개한다."""

    async def _resume() -> None:
        from orchestrator.core.engine import OrchestratorEngine

        engine = OrchestratorEngine()
        try:
            pipeline = await engine.resume_task(task_id)
            console.print(f"[green]Pipeline resumed:[/green] {pipeline.task_id}")
            console.print(f"[blue]Status:[/blue] {pipeline.status}")
        except KeyError:
            console.print(f"[red]Pipeline not found:[/red] {task_id}")
            raise typer.Exit(code=1) from None
        except ValueError as e:
            console.print(f"[red]Cannot resume:[/red] {e}")
            raise typer.Exit(code=1) from None

    asyncio.run(_resume())


@presets_app.command("list")
def presets_list() -> None:
    """모든 프리셋 목록을 조회한다."""
    from orchestrator.core.engine import OrchestratorEngine

    engine = OrchestratorEngine()

    agent_presets = engine.list_agent_presets()
    team_presets = engine.list_team_presets()

    if agent_presets:
        table = Table(title="Agent Presets")
        table.add_column("Name")
        table.add_column("Description")
        table.add_column("Mode")
        table.add_column("CLI")
        for p in agent_presets:
            table.add_row(
                p.name,
                p.description,
                p.execution_mode,
                p.preferred_cli or "auto",
            )
        console.print(table)
    else:
        console.print("[dim]No agent presets registered.[/dim]")

    if team_presets:
        team_table = Table(title="Team Presets")
        team_table.add_column("Name")
        team_table.add_column("Description")
        team_table.add_column("Workflow")
        team_table.add_column("Agents")
        for tp in team_presets:
            agent_names = ", ".join(tp.agents.keys())
            team_table.add_row(tp.name, tp.description, tp.workflow, agent_names)
        console.print(team_table)
    else:
        console.print("[dim]No team presets registered.[/dim]")


@presets_app.command("show")
def presets_show(
    name: str = typer.Argument(..., help="프리셋 이름"),
) -> None:
    """프리셋 상세를 조회한다."""
    from orchestrator.core.engine import OrchestratorEngine

    engine = OrchestratorEngine()

    # Try agent preset first
    try:
        preset = engine.load_agent_preset(name)
        console.print(f"[bold]Agent Preset:[/bold] {preset.name}")
        console.print(f"[blue]Description:[/blue] {preset.description}")
        console.print(f"[blue]Mode:[/blue] {preset.execution_mode}")
        console.print(f"[blue]CLI:[/blue] {preset.preferred_cli or 'auto'}")
        if preset.fallback_cli:
            console.print(f"[blue]Fallback:[/blue] {', '.join(preset.fallback_cli)}")
        console.print(f"[blue]Tags:[/blue] {', '.join(preset.tags)}")
        console.print()
        console.print("[bold]Persona:[/bold]")
        console.print(f"  Role: {preset.persona.role}")
        console.print(f"  Goal: {preset.persona.goal}")
        if preset.persona.backstory:
            console.print(f"  Backstory: {preset.persona.backstory.strip()}")
        if preset.persona.constraints:
            console.print("  Constraints:")
            for c in preset.persona.constraints:
                console.print(f"    - {c}")
        console.print()
        console.print("[bold]Limits:[/bold]")
        console.print(f"  Timeout: {preset.limits.timeout}s")
        console.print(f"  Max turns: {preset.limits.max_turns}")
        console.print(f"  Max iterations: {preset.limits.max_iterations}")
        return
    except KeyError:
        pass

    # Try team preset
    try:
        tp = engine.load_team_preset(name)
        console.print(f"[bold]Team Preset:[/bold] {tp.name}")
        console.print(f"[blue]Description:[/blue] {tp.description}")
        console.print(f"[blue]Workflow:[/blue] {tp.workflow}")
        console.print(f"[blue]Synthesis:[/blue] {tp.synthesis_strategy}")
        console.print()
        console.print("[bold]Agents:[/bold]")
        for agent_name, agent_def in tp.agents.items():
            overrides_str = f" (overrides: {agent_def.overrides})" if agent_def.overrides else ""
            console.print(f"  {agent_name}: preset={agent_def.preset}{overrides_str}")
        console.print()
        console.print("[bold]Tasks:[/bold]")
        for task_name, task_def in tp.tasks.items():
            deps = ", ".join(task_def.depends_on)
            deps_str = f" [depends: {deps}]" if task_def.depends_on else ""
            console.print(f"  {task_name}: agent={task_def.agent}{deps_str}")
            console.print(f"    {task_def.description.strip()}")
        return
    except KeyError:
        pass

    console.print(f"[red]Preset not found:[/red] {name}")
    raise typer.Exit(code=1)


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
