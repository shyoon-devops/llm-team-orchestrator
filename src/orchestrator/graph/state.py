"""LangGraph orchestrator state definition."""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict


class OrchestratorState(TypedDict):
    """State shared across the orchestration graph."""

    task: str
    plan_summary: str
    plan_artifact: str
    code_artifact: str
    review_summary: str
    review_artifact: str
    status: str
    error: str
    retry_count: int
    messages: Annotated[list[dict[str, object]], operator.add]
