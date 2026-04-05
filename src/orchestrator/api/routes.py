"""REST API endpoints."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from orchestrator.api.deps import get_engine
from orchestrator.core.presets.models import (
    AgentLimits,
    AgentPreset,
    MCPServerDef,
    PersonaDef,
    TeamAgentDef,
    TeamPreset,
    TeamTaskDef,
    ToolAccess,
)

router = APIRouter(prefix="/api")


# ============================================================
# Request/Response models
# ============================================================


class TaskSubmitRequest(BaseModel):
    """태스크 제출 요청."""

    task: str = Field(..., min_length=1, max_length=10000)
    team_preset: str | None = Field(default=None)
    target_repo: str | None = Field(default=None)
    config: dict[str, Any] | None = Field(default=None)


class ErrorResponse(BaseModel):
    """에러 응답."""

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class CreateAgentPresetRequest(BaseModel):
    """에이전트 프리셋 생성 요청."""

    name: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9\-]*$")
    description: str = Field(default="", max_length=500)
    tags: list[str] = Field(default_factory=list)
    persona: PersonaDef
    preferred_cli: Literal["claude", "codex", "gemini"] | None = Field(default="claude")
    fallback_cli: list[Literal["claude", "codex", "gemini"]] = Field(default_factory=list)
    model: str | None = Field(default=None)
    tools: ToolAccess = Field(default_factory=ToolAccess)
    mcp_servers: dict[str, MCPServerDef] = Field(default_factory=dict)
    limits: AgentLimits = Field(default_factory=AgentLimits)


class CreateTeamPresetRequest(BaseModel):
    """팀 프리셋 생성 요청."""

    name: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9\-]*$")
    description: str = Field(default="", max_length=500)
    agents: dict[str, TeamAgentDef] = Field(..., min_length=1)
    tasks: dict[str, TeamTaskDef] = Field(..., min_length=1)
    workflow: Literal["parallel", "sequential", "dag"] = Field(default="parallel")
    synthesis_strategy: Literal["narrative", "structured", "checklist"] = Field(
        default="narrative"
    )


# ============================================================
# Task endpoints
# ============================================================


@router.post("/tasks", status_code=201)
async def submit_task(
    body: TaskSubmitRequest,
    request: Request,
) -> dict[str, Any]:
    """새 태스크를 제출한다."""
    engine = get_engine(request)
    try:
        pipeline = await engine.submit_task(
            body.task,
            team_preset=body.team_preset,
            target_repo=body.target_repo,
        )
        return pipeline.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/tasks")
async def list_tasks(
    request: Request,
    offset: int = 0,
    limit: int = 20,
    status: str | None = None,
) -> dict[str, Any]:
    """파이프라인 목록을 조회한다."""
    engine = get_engine(request)
    pipelines = await engine.list_pipelines()

    if status:
        pipelines = [p for p in pipelines if p.status == status]

    total = len(pipelines)
    items = pipelines[offset : offset + limit]

    return {
        "items": [p.model_dump() for p in items],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/tasks/{task_id}")
async def get_task(
    task_id: str,
    request: Request,
) -> dict[str, Any]:
    """파이프라인 상세를 조회한다."""
    engine = get_engine(request)
    pipeline = await engine.get_pipeline(task_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    return pipeline.model_dump()


@router.post("/tasks/{task_id}/resume")
async def resume_task(
    task_id: str,
    request: Request,
) -> dict[str, Any]:
    """중단 태스크를 재개한다."""
    engine = get_engine(request)
    try:
        pipeline = await engine.resume_task(task_id)
        return pipeline.model_dump()
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.delete("/tasks/{task_id}", status_code=204)
async def cancel_task(
    task_id: str,
    request: Request,
) -> None:
    """태스크를 취소한다."""
    engine = get_engine(request)
    cancelled = await engine.cancel_task(task_id)
    if not cancelled:
        detail = f"Task not found or not cancellable: {task_id}"
        raise HTTPException(status_code=404, detail=detail)


# ============================================================
# Subtask detail endpoints (V2)
# ============================================================


@router.get("/tasks/{task_id}/subtasks")
async def list_subtasks(
    task_id: str,
    request: Request,
) -> dict[str, Any]:
    """파이프라인의 서브태스크 목록을 반환한다 (보드 상태 포함)."""
    engine = get_engine(request)
    pipeline = await engine.get_pipeline(task_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    subtasks = []
    for st in pipeline.subtasks:
        board_task = engine.get_board_task(st.id)
        started = (
            board_task.started_at.isoformat()
            if board_task and board_task.started_at
            else None
        )
        completed = (
            board_task.completed_at.isoformat()
            if board_task and board_task.completed_at
            else None
        )
        subtasks.append({
            "id": st.id,
            "description": st.description,
            "assigned_preset": st.assigned_preset,
            "assigned_cli": st.assigned_cli,
            "priority": st.priority,
            "depends_on": st.depends_on,
            "state": board_task.state.value if board_task else st.status,
            "result": board_task.result if board_task else "",
            "error": board_task.error if board_task else "",
            "started_at": started,
            "completed_at": completed,
        })

    return {"task_id": task_id, "subtasks": subtasks}


@router.get("/tasks/{task_id}/subtasks/{sub_id}")
async def get_subtask(
    task_id: str,
    sub_id: str,
    request: Request,
) -> dict[str, Any]:
    """개별 서브태스크 상세 (결과 포함)."""
    engine = get_engine(request)
    pipeline = await engine.get_pipeline(task_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    subtask = next((st for st in pipeline.subtasks if st.id == sub_id), None)
    if subtask is None:
        raise HTTPException(status_code=404, detail=f"Subtask not found: {sub_id}")

    board_task = engine.get_board_task(sub_id)
    # Find matching WorkerResult
    worker_result = next((r for r in pipeline.results if r.subtask_id == sub_id), None)

    started = (
        board_task.started_at.isoformat()
        if board_task and board_task.started_at
        else None
    )
    completed = (
        board_task.completed_at.isoformat()
        if board_task and board_task.completed_at
        else None
    )
    files = (
        [f.model_dump() for f in worker_result.files_changed]
        if worker_result
        else []
    )
    return {
        "id": subtask.id,
        "description": subtask.description,
        "assigned_preset": subtask.assigned_preset,
        "assigned_cli": subtask.assigned_cli,
        "priority": subtask.priority,
        "depends_on": subtask.depends_on,
        "state": board_task.state.value if board_task else subtask.status,
        "result": board_task.result if board_task else "",
        "error": board_task.error if board_task else "",
        "started_at": started,
        "completed_at": completed,
        "files_changed": files,
        "tokens_used": worker_result.tokens_used if worker_result else 0,
        "duration_ms": worker_result.duration_ms if worker_result else 0,
    }


@router.get("/tasks/{task_id}/files")
async def list_task_files(
    task_id: str,
    request: Request,
) -> dict[str, Any]:
    """파이프라인의 worktree diff 파일 목록."""
    engine = get_engine(request)
    pipeline = await engine.get_pipeline(task_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    files: list[dict[str, Any]] = []
    seen: set[str] = set()
    for wr in pipeline.results:
        for fc in wr.files_changed:
            if fc.path not in seen:
                seen.add(fc.path)
                files.append({
                    "path": fc.path,
                    "change_type": fc.change_type,
                    "subtask_id": wr.subtask_id,
                })

    return {"task_id": task_id, "files": files}


@router.get("/tasks/{task_id}/files/{path:path}")
async def get_task_file(
    task_id: str,
    path: str,
    request: Request,
) -> dict[str, Any]:
    """파이프라인의 특정 파일 내용."""

    engine = get_engine(request)
    pipeline = await engine.get_pipeline(task_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    for wr in pipeline.results:
        for fc in wr.files_changed:
            if fc.path == path:
                return {
                    "path": fc.path,
                    "change_type": fc.change_type,
                    "content": fc.content,
                    "subtask_id": wr.subtask_id,
                }

    raise HTTPException(status_code=404, detail=f"File not found: {path}")


# ============================================================
# Board endpoints
# ============================================================


@router.get("/board")
async def get_board(request: Request) -> dict[str, Any]:
    """칸반 보드 전체 상태를 조회한다."""
    engine = get_engine(request)
    return engine.get_board_state()


@router.get("/board/lanes")
async def get_lanes(request: Request) -> dict[str, Any]:
    """레인 목록을 조회한다."""
    engine = get_engine(request)
    board_state = engine.get_board_state()
    lanes = []
    for lane_name, lane_data in board_state.get("lanes", {}).items():
        task_count = sum(len(tasks) for tasks in lane_data.values() if isinstance(tasks, list))
        lanes.append(
            {
                "name": lane_name,
                "task_count": task_count,
            }
        )
    return {"lanes": lanes}


@router.get("/board/tasks/{task_id}")
async def get_board_task(task_id: str, request: Request) -> dict[str, Any]:
    """칸반 보드의 특정 태스크 상세를 조회한다."""
    engine = get_engine(request)
    task_item = engine.get_board_task(task_id)
    if task_item is None:
        raise HTTPException(status_code=404, detail=f"Board task not found: {task_id}")
    # Enrich with pipeline context
    result = task_item.model_dump()
    pipeline = await engine.get_pipeline(task_item.pipeline_id)
    result["pipeline_task"] = pipeline.task if pipeline else ""
    # Include related events (last 50)
    events = engine.get_events(task_id=task_item.pipeline_id)
    task_events = [
        e.model_dump()
        for e in events
        if e.data.get("subtask_id") == task_id or e.data.get("task_id") == task_id
    ][:50]
    result["events"] = task_events
    return result


# ============================================================
# Artifact endpoints
# ============================================================


@router.get("/artifacts/{task_id}")
async def list_artifacts(task_id: str, request: Request) -> dict[str, Any]:
    """파이프라인의 아티팩트 목록을 조회한다."""
    engine = get_engine(request)
    pipeline = await engine.get_pipeline(task_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    artifacts = await engine.list_artifacts(task_id)
    return {"task_id": task_id, "artifacts": artifacts}


@router.get("/artifacts/{task_id}/{path:path}")
async def download_artifact(
    task_id: str,
    path: str,
    request: Request,
) -> Any:
    """아티팩트 파일을 다운로드한다."""
    from fastapi.responses import Response

    engine = get_engine(request)
    pipeline = await engine.get_pipeline(task_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    content = await engine.get_artifact(task_id, path)
    if content is None:
        raise HTTPException(status_code=404, detail=f"Artifact not found: {path}")
    # Content-Type based on extension
    ext = path.rsplit(".", 1)[-1] if "." in path else ""
    content_type_map = {
        "json": "application/json",
        "md": "text/markdown",
        "py": "text/plain",
        "ts": "text/plain",
        "js": "text/plain",
    }
    ct = content_type_map.get(ext, "application/octet-stream")
    return Response(content=content, media_type=ct)


# ============================================================
# Agent endpoints
# ============================================================


@router.get("/agents")
async def list_agents(request: Request) -> dict[str, Any]:
    """에이전트 상태를 조회한다."""
    engine = get_engine(request)
    return {"agents": engine.list_agents()}


# ============================================================
# Preset endpoints
# ============================================================


@router.get("/presets/agents")
async def list_agent_presets(request: Request) -> dict[str, Any]:
    """에이전트 프리셋 목록을 조회한다."""
    engine = get_engine(request)
    presets = engine.list_agent_presets()
    return {"presets": [p.model_dump() for p in presets]}


@router.get("/presets/agents/{name}")
async def get_agent_preset(name: str, request: Request) -> dict[str, Any]:
    """에이전트 프리셋 상세를 조회한다."""
    engine = get_engine(request)
    try:
        preset = engine.load_agent_preset(name)
        return preset.model_dump()
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/presets/agents", status_code=201)
async def create_agent_preset(
    body: CreateAgentPresetRequest,
    request: Request,
) -> dict[str, Any]:
    """새로운 에이전트 프리셋을 생성한다."""
    engine = get_engine(request)
    preset = AgentPreset.model_validate(body.model_dump())
    try:
        engine.save_agent_preset(preset, overwrite=False)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return preset.model_dump()


@router.get("/presets/teams")
async def list_team_presets(request: Request) -> dict[str, Any]:
    """팀 프리셋 목록을 조회한다."""
    engine = get_engine(request)
    presets = engine.list_team_presets()
    return {"presets": [p.model_dump() for p in presets]}


@router.get("/presets/teams/{name}")
async def get_team_preset(name: str, request: Request) -> dict[str, Any]:
    """팀 프리셋 상세를 조회한다."""
    engine = get_engine(request)
    try:
        preset = engine.load_team_preset(name)
        return preset.model_dump()
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/presets/teams", status_code=201)
async def create_team_preset(
    body: CreateTeamPresetRequest,
    request: Request,
) -> dict[str, Any]:
    """새로운 팀 프리셋을 생성한다."""
    engine = get_engine(request)
    preset = TeamPreset.model_validate(body.model_dump())
    try:
        engine.save_team_preset(preset, overwrite=False)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return preset.model_dump()


# ============================================================
# Event endpoints
# ============================================================


@router.get("/events")
async def get_events(
    request: Request,
    task_id: str | None = None,
) -> dict[str, Any]:
    """이벤트 히스토리를 조회한다."""
    engine = get_engine(request)
    events = engine.get_events(task_id=task_id)
    return {"items": [e.model_dump() for e in events]}


# ============================================================
# Health check
# ============================================================


@router.get("/health")
async def health_check() -> dict[str, str]:
    """헬스 체크."""
    return {"status": "ok"}
