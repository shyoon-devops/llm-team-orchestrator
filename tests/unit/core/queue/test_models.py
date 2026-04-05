"""Tests for core/queue/models.py."""

import pytest

from orchestrator.core.queue.models import TaskItem, TaskState


def test_task_state_values():
    assert TaskState.BACKLOG == "backlog"
    assert TaskState.TODO == "todo"
    assert TaskState.IN_PROGRESS == "in_progress"
    assert TaskState.DONE == "done"
    assert TaskState.FAILED == "failed"


def test_task_item_defaults():
    t = TaskItem(id="t1", title="test", lane="lane1")
    assert t.state == TaskState.BACKLOG
    assert t.priority == 0
    assert t.depends_on == []
    assert t.assigned_to is None
    assert t.result == ""
    assert t.retry_count == 0
    assert t.max_retries == 3


def test_task_item_self_dependency_rejected():
    with pytest.raises(ValueError, match="자기 자신에 의존"):
        TaskItem(id="t1", title="test", lane="lane1", depends_on=["t1"])


def test_task_item_with_dependency():
    t = TaskItem(id="t1", title="test", lane="lane1", depends_on=["t0"])
    assert t.depends_on == ["t0"]
