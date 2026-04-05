"""Tests for core/queue/board.py."""

import pytest

from orchestrator.core.queue.board import TaskBoard
from orchestrator.core.queue.models import TaskItem, TaskState


@pytest.fixture
def board():
    return TaskBoard(max_retries=3)


async def test_submit_task(board):
    task = TaskItem(id="t1", title="test", lane="dev")
    task_id = await board.submit(task)
    assert task_id == "t1"
    stored = board.get_task("t1")
    assert stored is not None
    # no deps -> auto TODO
    assert stored.state == TaskState.TODO


async def test_submit_duplicate_rejected(board):
    task = TaskItem(id="t1", title="test", lane="dev")
    await board.submit(task)
    with pytest.raises(ValueError, match="already exists"):
        await board.submit(task)


async def test_claim_task(board):
    await board.submit(TaskItem(id="t1", title="test", lane="dev"))
    claimed = await board.claim("dev", "w1")
    assert claimed is not None
    assert claimed.state == TaskState.IN_PROGRESS
    assert claimed.assigned_to == "w1"


async def test_claim_empty_lane(board):
    result = await board.claim("empty", "w1")
    assert result is None


async def test_complete_task(board):
    await board.submit(TaskItem(id="t1", title="test", lane="dev"))
    await board.claim("dev", "w1")
    await board.complete("t1", "done!")
    stored = board.get_task("t1")
    assert stored is not None
    assert stored.state == TaskState.DONE
    assert stored.result == "done!"


async def test_fail_with_retry(board):
    await board.submit(TaskItem(id="t1", title="test", lane="dev", max_retries=3))
    await board.claim("dev", "w1")
    await board.fail("t1", "error!")
    stored = board.get_task("t1")
    assert stored is not None
    assert stored.state == TaskState.TODO  # retried
    assert stored.retry_count == 1


async def test_fail_permanent(board):
    await board.submit(TaskItem(id="t1", title="test", lane="dev", max_retries=1))
    await board.claim("dev", "w1")
    await board.fail("t1", "error!")
    stored = board.get_task("t1")
    assert stored is not None
    assert stored.state == TaskState.FAILED


async def test_dependency_chain(board):
    t1 = TaskItem(id="t1", title="design", lane="arch", pipeline_id="p1")
    t2 = TaskItem(id="t2", title="impl", lane="dev", depends_on=["t1"], pipeline_id="p1")
    await board.submit(t1)
    await board.submit(t2)

    # t2 should be BACKLOG
    assert board.get_task("t2").state == TaskState.BACKLOG

    # Complete t1
    await board.claim("arch", "w1")
    await board.complete("t1", "designed")

    # t2 should now be TODO
    assert board.get_task("t2").state == TaskState.TODO


async def test_get_board_state(board):
    await board.submit(TaskItem(id="t1", title="test", lane="dev"))
    state = board.get_board_state()
    assert "lanes" in state
    assert "summary" in state
    assert state["summary"]["total"] == 1


async def test_is_all_done(board):
    await board.submit(TaskItem(id="t1", title="test", lane="dev", pipeline_id="p1"))
    assert not board.is_all_done("p1")
    await board.claim("dev", "w1")
    await board.complete("t1", "done")
    assert board.is_all_done("p1")
