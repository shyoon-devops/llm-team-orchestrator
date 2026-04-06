"""Typer CLI application."""

from __future__ import annotations

import asyncio
import time

import typer
from rich.console import Console
from rich.live import Live
from rich.table import Table

console = Console()
app = typer.Typer(
    name="orchestrator",
    help="Agent Team Orchestrator — multi-LLM agent team coordination",
)
presets_app = typer.Typer(name="presets", help="프리셋 관리 명령어")
app.add_typer(presets_app)

_STATUS_ICONS = {
    "done": "\u2705",
    "in_progress": "\U0001f504",
    "backlog": "\u23f3",
    "todo": "\U0001f4cb",
    "failed": "\u274c",
}


def _build_progress_table(
    task_id: str,
    task_desc: str,
    board_state: dict,
    elapsed: int,
) -> Table:
    """Rich 테이블로 서브태스크 진행 상황을 구성한다."""
    table = Table(
        title=f"Pipeline: {task_id[:16]}",
        caption=f"Task: {task_desc[:60]}  |  Elapsed: {elapsed}s",
    )
    table.add_column("Subtask", style="cyan", min_width=12)
    table.add_column("Agent", style="green", min_width=8)
    table.add_column("Status", min_width=12)
    table.add_column("Time", justify="right", min_width=6)

    for lane_name, lane_tasks in board_state.get("lanes", {}).items():
        for state, items in lane_tasks.items():
            for item in items:
                icon = _STATUS_ICONS.get(state, "?")
                title = item.get("title", "")[:30]
                started = item.get("started_at")
                completed = item.get("completed_at")
                if completed and started:
                    from datetime import datetime

                    try:
                        t_start = datetime.fromisoformat(started)
                        t_end = datetime.fromisoformat(completed)
                        duration = f"{int((t_end - t_start).total_seconds())}s"
                    except (ValueError, TypeError):
                        duration = "-"
                elif started and state == "in_progress":
                    duration = "\U0001f504"
                else:
                    duration = "-"

                table.add_row(
                    title or lane_name,
                    lane_name,
                    f"{icon} {state.upper()}",
                    duration,
                )

    return table


@app.command()
def run(
    task: str = typer.Argument(..., help="태스크 설명"),
    repo: str | None = typer.Option(None, "--repo", "-r", help="대상 Git 저장소 경로"),
    team_preset: str | None = typer.Option(None, "--team-preset", "-t", help="팀 프리셋 이름"),
    timeout: int = typer.Option(600, "--timeout", help="타임아웃 (초)"),
    wait: bool = typer.Option(True, "--wait/--no-wait", help="완료까지 대기"),
) -> None:
    """태스크를 실행한다."""

    async def _run() -> None:
        from orchestrator.core.engine import OrchestratorEngine
        from orchestrator.core.models.pipeline import PipelineStatus

        engine = OrchestratorEngine()
        await engine.start()
        try:
            pipeline = await engine.submit_task(
                task,
                team_preset=team_preset,
                target_repo=repo,
            )
            console.print(f"[green]Pipeline created:[/green] {pipeline.task_id}")
            console.print(f"[blue]Status:[/blue] {pipeline.status}")

            if wait:
                terminal_states = {
                    PipelineStatus.COMPLETED,
                    PipelineStatus.FAILED,
                    PipelineStatus.PARTIAL_FAILURE,
                    PipelineStatus.CANCELLED,
                }
                elapsed = 0
                progress_interval = engine.config.progress_interval

                with Live(
                    _build_progress_table(pipeline.task_id, task, {}, 0),
                    refresh_per_second=1,
                    console=console,
                    transient=True,
                ) as live:
                    while elapsed < timeout:
                        await asyncio.sleep(1)
                        elapsed += 1

                        # 진행 상황 테이블 갱신
                        if elapsed % max(1, progress_interval) == 0 or elapsed <= 3:
                            board_state = engine.get_board_state()
                            table = _build_progress_table(
                                pipeline.task_id, task, board_state, elapsed,
                            )
                            live.update(table)

                        current = await engine.get_pipeline(pipeline.task_id)
                        if current and current.status in terminal_states:
                            # 최종 테이블 표시
                            board_state = engine.get_board_state()
                            live.update(
                                _build_progress_table(
                                    pipeline.task_id, task, board_state, elapsed,
                                )
                            )
                            break
                    else:
                        console.print(
                            f"[yellow]Timeout ({timeout}s) — still running[/yellow]"
                        )

                # 최종 결과 (Live 밖에서 출력)
                current = await engine.get_pipeline(pipeline.task_id)
                if current:
                    # 최종 상태 테이블 (영구 표시)
                    board_state = engine.get_board_state()
                    console.print(
                        _build_progress_table(
                            pipeline.task_id, task, board_state, elapsed,
                        )
                    )
                    console.print(f"\n[blue]Final status:[/blue] {current.status}")
                    if current.synthesis:
                        console.print("\n[bold]Synthesis Report:[/bold]")
                        console.print(current.synthesis)
        finally:
            await engine.shutdown()

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


@app.command("config")
def config_show() -> None:
    """현재 오케스트레이터 설정을 표시한다."""
    from orchestrator.core.config.schema import OrchestratorConfig

    config = OrchestratorConfig()

    table = Table(title="Orchestrator Configuration")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")
    table.add_column("Description", style="dim")

    for field_name, field_info in OrchestratorConfig.model_fields.items():
        value = getattr(config, field_name)
        desc = field_info.description or ""
        table.add_row(field_name, str(value), desc[:60])

    console.print(table)


@app.command("agents")
def agents_list() -> None:
    """등록된 에이전트 프리셋 목록과 설정을 표시한다."""
    from orchestrator.core.engine import OrchestratorEngine

    engine = OrchestratorEngine()
    agent_presets = engine.list_agent_presets()

    if not agent_presets:
        console.print("[dim]No agent presets registered.[/dim]")
        return

    for p in agent_presets:
        table = Table(title=f"Agent: {p.name}")
        table.add_column("Field", style="cyan", min_width=15)
        table.add_column("Value", style="green")
        table.add_row("CLI", p.preferred_cli or "auto")
        table.add_row("Fallback", ", ".join(p.fallback_cli) if p.fallback_cli else "-")
        table.add_row("Role", p.persona.role)
        table.add_row("Goal", p.persona.goal)
        table.add_row("Timeout", f"{p.limits.timeout}s")
        table.add_row("Max Turns", str(p.limits.max_turns))
        table.add_row("Tags", ", ".join(p.tags) if p.tags else "-")
        if p.persona.constraints:
            for i, c in enumerate(p.persona.constraints):
                table.add_row(f"Constraint {i + 1}", c[:80])
        console.print(table)
        console.print()


@app.command("subtask")
def subtask_detail(
    task_id: str = typer.Argument(..., help="파이프라인 ID"),
    subtask_id: str = typer.Argument("", help="서브태스크 ID (비우면 전체 목록)"),
) -> None:
    """서브태스크 상세를 Markdown 형식으로 표시한다."""
    from rich.markdown import Markdown

    async def _detail() -> None:
        from orchestrator.core.engine import OrchestratorEngine

        engine = OrchestratorEngine()
        pipeline = await engine.get_pipeline(task_id)
        if pipeline is None:
            console.print(f"[red]Pipeline not found:[/red] {task_id}")
            raise typer.Exit(code=1)

        if not subtask_id:
            # 전체 서브태스크 목록
            table = Table(title=f"Subtasks for {task_id[:16]}")
            table.add_column("ID", style="cyan")
            table.add_column("Preset", style="green")
            table.add_column("CLI")
            table.add_column("Status")
            for st in pipeline.subtasks:
                table.add_row(
                    st.id[:16],
                    st.assigned_preset,
                    st.assigned_cli or "-",
                    st.status or "pending",
                )
            console.print(table)
            return

        # 특정 서브태스크 상세
        found = next((st for st in pipeline.subtasks if st.id.startswith(subtask_id)), None)
        if found is None:
            console.print(f"[red]Subtask not found:[/red] {subtask_id}")
            raise typer.Exit(code=1)

        console.print(f"\n[bold]Subtask:[/bold] {found.id}")
        console.print(f"[blue]Preset:[/blue] {found.assigned_preset}")
        console.print(f"[blue]CLI:[/blue] {found.assigned_cli or '-'}")
        console.print()

        console.print("[bold]Description:[/bold]")
        console.print(Markdown(found.description))

        # Board에서 result 확인
        board_task = engine._board.get_task(found.id)
        if board_task and board_task.result:
            console.print("\n[bold]Result:[/bold]")
            console.print(Markdown(board_task.result))

    asyncio.run(_detail())


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
        table.add_column("CLI")
        for p in agent_presets:
            table.add_row(
                p.name,
                p.description,
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
