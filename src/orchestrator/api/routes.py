"""REST API endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from orchestrator.api.deps import get_engine

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
    return {"items": [p.model_dump() for p in presets]}


@router.get("/presets/teams")
async def list_team_presets(request: Request) -> dict[str, Any]:
    """팀 프리셋 목록을 조회한다."""
    engine = get_engine(request)
    presets = engine.list_team_presets()
    return {"items": [p.model_dump() for p in presets]}


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
