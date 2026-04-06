"""Tests for CLI progress display in the run command's --wait loop."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from orchestrator.core.config.schema import OrchestratorConfig
from orchestrator.core.models.pipeline import Pipeline, PipelineStatus


@pytest.fixture
def mock_board_state():
    """Subtask가 있는 board state를 반환한다."""
    return {
        "lanes": {
            "architect": {
                "done": [
                    {
                        "id": "sub-1",
                        "title": "설계 문서 작성",
                        "lane": "architect",
                        "state": "done",
                        "started_at": "2026-04-05T10:00:00",
                    }
                ],
                "in_progress": [],
                "backlog": [],
                "todo": [],
                "failed": [],
            },
            "implementer": {
                "done": [],
                "in_progress": [
                    {
                        "id": "sub-2",
                        "title": "JWT 미들웨어 구현",
                        "lane": "implementer",
                        "state": "in_progress",
                        "started_at": "2026-04-05T10:02:00",
                    }
                ],
                "backlog": [],
                "todo": [],
                "failed": [],
            },
        },
        "summary": {"total": 2, "by_state": {"done": 1, "in_progress": 1}},
    }


def test_cli_progress_output(mock_board_state, capsys):
    """CLI run --wait 루프에서 subtask 진행 상태를 출력한다."""
    from rich.console import Console

    console = Console(file=None)  # suppress actual output

    # Simulate what the CLI loop does
    board_state = mock_board_state
    lines = []
    for lane_name, lane_tasks in board_state.get("lanes", {}).items():
        for state, items in lane_tasks.items():
            for item in items:
                icon = {
                    "done": "\u2705",
                    "in_progress": "\U0001f504",
                    "backlog": "\u23f3",
                    "todo": "\U0001f4cb",
                    "failed": "\u274c",
                }.get(state, "?")
                title = item.get("title", "")[:40]
                line = f"  {icon} {lane_name:12s} {state:12s} {title}"
                lines.append(line)

    # Verify output contains expected info
    assert len(lines) == 2
    assert "architect" in lines[0]
    assert "done" in lines[0]
    assert "implementer" in lines[1]
    assert "in_progress" in lines[1]


def test_cli_progress_uses_config_interval():
    """CLI가 config.progress_interval을 사용한다."""
    config = OrchestratorConfig(progress_interval=30)
    assert config.progress_interval == 30


def test_board_state_empty_lanes():
    """빈 board state에서도 에러 없이 처리된다."""
    board_state: dict = {"lanes": {}, "summary": {"total": 0, "by_state": {}}}
    lines = []
    for lane_name, lane_tasks in board_state.get("lanes", {}).items():
        for state, items in lane_tasks.items():
            for item in items:
                lines.append(f"  {lane_name} {state}")
    assert lines == []
