"""Typer CLI application — HTTP client mode.

All commands communicate with the orchestrator server via REST API (httpx).
The server must be running (`orchestrator serve`) before using other commands.
"""

from __future__ import annotations

import asyncio

import httpx
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

_server_url: str = "http://localhost:8000"

_STATUS_ICONS = {
    "done": "\u2705",
    "in_progress": "\U0001f504",
    "backlog": "\u23f3",
    "todo": "\U0001f4cb",
    "failed": "\u274c",
}


@app.callback()
def main(
    server: str = typer.Option(
        "http://localhost:8000",
        "--server",
        envvar="ORCHESTRATOR_SERVER_URL",
        help="오케스트레이터 서버 URL",
    ),
) -> None:
    """Agent Team Orchestrator CLI."""
    global _server_url
    _server_url = server.rstrip("/")


def _client() -> httpx.AsyncClient:
    """서버 URL 기반 AsyncClient를 생성한다."""
    return httpx.AsyncClient(base_url=_server_url, timeout=30.0)


def _handle_error(resp: httpx.Response) -> None:
    """HTTP 에러를 CLI 에러로 변환한다.

    Args:
        resp: httpx 응답.

    Raises:
        typer.Exit: HTTP 에러 시.
    """
    if resp.is_success:
        return
    try:
        body = resp.json()
        detail = body.get("detail", resp.text)
    except Exception:
        detail = resp.text

    if resp.status_code == 404:
        console.print(f"[red]Not found:[/red] {detail}")
    elif resp.status_code == 409:
        console.print(f"[red]Conflict:[/red] {detail}")
    elif resp.status_code == 422:
        console.print(f"[red]Validation error:[/red] {detail}")
    else:
        console.print(f"[red]Server error ({resp.status_code}):[/red] {detail}")
    raise typer.Exit(code=1)


def _handle_connect_error() -> None:
    """서버 연결 실패 시 에러 메시지를 출력한다.

    Raises:
        typer.Exit: 항상.
    """
    console.print(f"[red]Cannot connect to server at {_server_url}[/red]")
    console.print("[dim]Hint: Start the server with 'orchestrator serve'[/dim]")
    raise typer.Exit(code=1)


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
        try:
            async with _client() as client:
                # Submit task
                payload: dict = {"task": task}
                if team_preset:
                    payload["team_preset"] = team_preset
                if repo:
                    payload["target_repo"] = repo

                resp = await client.post("/api/tasks", json=payload)
                _handle_error(resp)
                pipeline = resp.json()
                task_id = pipeline["task_id"]

                console.print(f"[green]Pipeline created:[/green] {task_id}")
                console.print(f"[blue]Status:[/blue] {pipeline.get('status', 'unknown')}")

                if not wait:
                    return

                terminal_states = {
                    "completed", "failed", "partial_failure", "cancelled",
                }
                elapsed = 0

                with Live(
                    _build_progress_table(task_id, task, {}, 0),
                    refresh_per_second=1,
                    console=console,
                    transient=True,
                ) as live:
                    while elapsed < timeout:
                        await asyncio.sleep(1)
                        elapsed += 1

                        # Board state for progress table
                        board_resp = await client.get("/api/board")
                        board_state = board_resp.json() if board_resp.is_success else {}
                        table = _build_progress_table(
                            task_id, task, board_state, elapsed,
                        )
                        live.update(table)

                        # Check pipeline status
                        status_resp = await client.get(f"/api/tasks/{task_id}")
                        if status_resp.is_success:
                            current = status_resp.json()
                            if current.get("status") in terminal_states:
                                # Final table update
                                board_resp2 = await client.get("/api/board")
                                if board_resp2.is_success:
                                    board_state = board_resp2.json()
                                live.update(
                                    _build_progress_table(
                                        task_id, task, board_state, elapsed,
                                    )
                                )
                                break
                    else:
                        console.print(
                            f"[yellow]Timeout ({timeout}s) — still running[/yellow]"
                        )

                # Final result (outside Live)
                status_resp = await client.get(f"/api/tasks/{task_id}")
                if status_resp.is_success:
                    current = status_resp.json()
                    board_resp = await client.get("/api/board")
                    board_state = board_resp.json() if board_resp.is_success else {}
                    console.print(
                        _build_progress_table(
                            task_id, task, board_state, elapsed,
                        )
                    )
                    console.print(f"\n[blue]Final status:[/blue] {current.get('status')}")
                    synthesis = current.get("synthesis")
                    if synthesis:
                        console.print("\n[bold]Synthesis Report:[/bold]")
                        console.print(synthesis)
        except httpx.ConnectError:
            _handle_connect_error()

    asyncio.run(_run())


@app.command()
def status(
    task_id: str = typer.Argument(..., help="파이프라인 ID"),
) -> None:
    """파이프라인 상태를 조회한다."""

    async def _status() -> None:
        try:
            async with _client() as client:
                resp = await client.get(f"/api/tasks/{task_id}")
                _handle_error(resp)
                pipeline = resp.json()
                console.print(f"[blue]Task:[/blue] {pipeline.get('task', '')}")
                console.print(f"[blue]Status:[/blue] {pipeline.get('status', '')}")
        except httpx.ConnectError:
            _handle_connect_error()

    asyncio.run(_status())


@app.command()
def cancel(
    task_id: str = typer.Argument(..., help="취소할 파이프라인 ID"),
) -> None:
    """태스크를 취소한다."""

    async def _cancel() -> None:
        try:
            async with _client() as client:
                resp = await client.delete(f"/api/tasks/{task_id}")
                if resp.status_code == 204:
                    console.print(f"[green]Pipeline cancelled:[/green] {task_id}")
                else:
                    _handle_error(resp)
        except httpx.ConnectError:
            _handle_connect_error()

    asyncio.run(_cancel())


@app.command()
def resume(
    task_id: str = typer.Argument(..., help="재개할 파이프라인 ID"),
) -> None:
    """중단된 태스크를 재개한다."""

    async def _resume() -> None:
        try:
            async with _client() as client:
                resp = await client.post(f"/api/tasks/{task_id}/resume")
                _handle_error(resp)
                pipeline = resp.json()
                console.print(f"[green]Pipeline resumed:[/green] {pipeline.get('task_id', task_id)}")
                console.print(f"[blue]Status:[/blue] {pipeline.get('status', '')}")
        except httpx.ConnectError:
            _handle_connect_error()

    asyncio.run(_resume())


@app.command("config")
def config_show() -> None:
    """현재 오케스트레이터 설정을 표시한다."""

    async def _config() -> None:
        try:
            async with _client() as client:
                resp = await client.get("/api/config")
                _handle_error(resp)
                data = resp.json()

                table = Table(title="Orchestrator Configuration")
                table.add_column("Field", style="cyan")
                table.add_column("Value", style="green")
                table.add_column("Description", style="dim")

                for field_name, field_info in data.get("fields", {}).items():
                    value = field_info.get("value", "")
                    desc = field_info.get("description", "")
                    table.add_row(field_name, str(value), desc[:60])

                console.print(table)
        except httpx.ConnectError:
            _handle_connect_error()

    asyncio.run(_config())


@app.command("agents")
def agents_list() -> None:
    """등록된 에이전트 프리셋 목록과 설정을 표시한다."""

    async def _agents() -> None:
        try:
            async with _client() as client:
                resp = await client.get("/api/presets/agents")
                _handle_error(resp)
                data = resp.json()
                presets = data.get("presets", [])

                if not presets:
                    console.print("[dim]No agent presets registered.[/dim]")
                    return

                for p in presets:
                    table = Table(title=f"Agent: {p.get('name', '')}")
                    table.add_column("Field", style="cyan", min_width=15)
                    table.add_column("Value", style="green")
                    table.add_row("CLI", p.get("preferred_cli") or "auto")
                    fallback = p.get("fallback_cli", [])
                    table.add_row("Fallback", ", ".join(fallback) if fallback else "-")
                    persona = p.get("persona", {})
                    table.add_row("Role", persona.get("role", ""))
                    table.add_row("Goal", persona.get("goal", ""))
                    limits = p.get("limits", {})
                    table.add_row("Timeout", f"{limits.get('timeout', 300)}s")
                    table.add_row("Max Turns", str(limits.get("max_turns", 0)))
                    tags = p.get("tags", [])
                    table.add_row("Tags", ", ".join(tags) if tags else "-")
                    constraints = persona.get("constraints", [])
                    if constraints:
                        for i, c in enumerate(constraints):
                            table.add_row(f"Constraint {i + 1}", str(c)[:80])
                    console.print(table)
                    console.print()
        except httpx.ConnectError:
            _handle_connect_error()

    asyncio.run(_agents())


@app.command("subtask")
def subtask_detail(
    task_id: str = typer.Argument(..., help="파이프라인 ID"),
    subtask_id: str = typer.Argument("", help="서브태스크 ID (비우면 전체 목록)"),
) -> None:
    """서브태스크 상세를 Markdown 형식으로 표시한다."""
    from rich.markdown import Markdown

    async def _detail() -> None:
        try:
            async with _client() as client:
                if not subtask_id:
                    # Full subtask list
                    resp = await client.get(f"/api/tasks/{task_id}/subtasks")
                    _handle_error(resp)
                    data = resp.json()
                    subtasks = data.get("subtasks", [])

                    table = Table(title=f"Subtasks for {task_id[:16]}")
                    table.add_column("ID", style="cyan")
                    table.add_column("Preset", style="green")
                    table.add_column("CLI")
                    table.add_column("Status")
                    for st in subtasks:
                        table.add_row(
                            st.get("id", "")[:16],
                            st.get("assigned_preset", ""),
                            st.get("assigned_cli") or "-",
                            st.get("state") or "pending",
                        )
                    console.print(table)
                    return

                # Specific subtask detail
                resp = await client.get(
                    f"/api/tasks/{task_id}/subtasks/{subtask_id}"
                )
                _handle_error(resp)
                found = resp.json()

                console.print(f"\n[bold]Subtask:[/bold] {found.get('id', '')}")
                console.print(f"[blue]Preset:[/blue] {found.get('assigned_preset', '')}")
                console.print(f"[blue]CLI:[/blue] {found.get('assigned_cli') or '-'}")
                console.print()

                description = found.get("description", "")
                console.print("[bold]Description:[/bold]")
                console.print(Markdown(description))

                result = found.get("result", "")
                if result:
                    console.print("\n[bold]Result:[/bold]")
                    console.print(Markdown(result))
        except httpx.ConnectError:
            _handle_connect_error()

    asyncio.run(_detail())


@presets_app.command("list")
def presets_list() -> None:
    """모든 프리셋 목록을 조회한다."""

    async def _list() -> None:
        try:
            async with _client() as client:
                # Fetch agents and teams in parallel
                agents_resp, teams_resp = await asyncio.gather(
                    client.get("/api/presets/agents"),
                    client.get("/api/presets/teams"),
                )

                if agents_resp.is_success:
                    agent_presets = agents_resp.json().get("presets", [])
                    if agent_presets:
                        table = Table(title="Agent Presets")
                        table.add_column("Name")
                        table.add_column("Description")
                        table.add_column("CLI")
                        for p in agent_presets:
                            table.add_row(
                                p.get("name", ""),
                                p.get("description", ""),
                                p.get("preferred_cli") or "auto",
                            )
                        console.print(table)
                    else:
                        console.print("[dim]No agent presets registered.[/dim]")

                if teams_resp.is_success:
                    team_presets = teams_resp.json().get("presets", [])
                    if team_presets:
                        team_table = Table(title="Team Presets")
                        team_table.add_column("Name")
                        team_table.add_column("Description")
                        team_table.add_column("Workflow")
                        team_table.add_column("Agents")
                        for tp in team_presets:
                            agents = tp.get("agents", {})
                            agent_names = ", ".join(agents.keys())
                            team_table.add_row(
                                tp.get("name", ""),
                                tp.get("description", ""),
                                tp.get("workflow", ""),
                                agent_names,
                            )
                        console.print(team_table)
                    else:
                        console.print("[dim]No team presets registered.[/dim]")
        except httpx.ConnectError:
            _handle_connect_error()

    asyncio.run(_list())


@presets_app.command("show")
def presets_show(
    name: str = typer.Argument(..., help="프리셋 이름"),
) -> None:
    """프리셋 상세를 조회한다."""

    async def _show() -> None:
        try:
            async with _client() as client:
                # Try agent preset first
                resp = await client.get(f"/api/presets/agents/{name}")
                if resp.status_code == 200:
                    preset = resp.json()
                    console.print(f"[bold]Agent Preset:[/bold] {preset.get('name', '')}")
                    console.print(f"[blue]Description:[/blue] {preset.get('description', '')}")
                    console.print(f"[blue]CLI:[/blue] {preset.get('preferred_cli') or 'auto'}")
                    fallback = preset.get("fallback_cli", [])
                    if fallback:
                        console.print(f"[blue]Fallback:[/blue] {', '.join(fallback)}")
                    tags = preset.get("tags", [])
                    console.print(f"[blue]Tags:[/blue] {', '.join(tags)}")
                    console.print()
                    persona = preset.get("persona", {})
                    console.print("[bold]Persona:[/bold]")
                    console.print(f"  Role: {persona.get('role', '')}")
                    console.print(f"  Goal: {persona.get('goal', '')}")
                    backstory = persona.get("backstory", "")
                    if backstory:
                        console.print(f"  Backstory: {backstory.strip()}")
                    constraints = persona.get("constraints", [])
                    if constraints:
                        console.print("  Constraints:")
                        for c in constraints:
                            console.print(f"    - {c}")
                    console.print()
                    limits = preset.get("limits", {})
                    console.print("[bold]Limits:[/bold]")
                    console.print(f"  Timeout: {limits.get('timeout', 300)}s")
                    console.print(f"  Max turns: {limits.get('max_turns', 0)}")
                    console.print(f"  Max iterations: {limits.get('max_iterations', 0)}")
                    return

                # Try team preset
                resp = await client.get(f"/api/presets/teams/{name}")
                if resp.status_code == 200:
                    tp = resp.json()
                    console.print(f"[bold]Team Preset:[/bold] {tp.get('name', '')}")
                    console.print(f"[blue]Description:[/blue] {tp.get('description', '')}")
                    console.print(f"[blue]Workflow:[/blue] {tp.get('workflow', '')}")
                    console.print(f"[blue]Synthesis:[/blue] {tp.get('synthesis_strategy', '')}")
                    console.print()
                    console.print("[bold]Agents:[/bold]")
                    for agent_name, agent_def in tp.get("agents", {}).items():
                        overrides = agent_def.get("overrides")
                        overrides_str = f" (overrides: {overrides})" if overrides else ""
                        preset_name = agent_def.get("preset", "")
                        console.print(f"  {agent_name}: preset={preset_name}{overrides_str}")
                    console.print()
                    console.print("[bold]Tasks:[/bold]")
                    for task_name, task_def in tp.get("tasks", {}).items():
                        deps = task_def.get("depends_on", [])
                        deps_str = f" [depends: {', '.join(deps)}]" if deps else ""
                        agent = task_def.get("agent", "")
                        console.print(f"  {task_name}: agent={agent}{deps_str}")
                        description = task_def.get("description", "").strip()
                        console.print(f"    {description}")
                    return

                console.print(f"[red]Preset not found:[/red] {name}")
                raise typer.Exit(code=1)
        except httpx.ConnectError:
            _handle_connect_error()

    asyncio.run(_show())


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
