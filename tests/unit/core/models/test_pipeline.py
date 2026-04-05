"""Tests for core/models/pipeline.py."""

from orchestrator.core.models.pipeline import (
    FileChange,
    Pipeline,
    PipelineStatus,
    SubTask,
    WorkerResult,
)


def test_pipeline_status_values():
    assert PipelineStatus.PENDING == "pending"
    assert PipelineStatus.COMPLETED == "completed"
    assert PipelineStatus.FAILED == "failed"


def test_pipeline_defaults():
    p = Pipeline(task_id="p-001", task="test task")
    assert p.status == PipelineStatus.PENDING
    assert p.subtasks == []
    assert p.results == []
    assert p.synthesis == ""
    assert not p.merged
    assert p.error == ""


def test_subtask_creation():
    st = SubTask(id="sub-001", description="design API")
    assert st.task_id == ""
    assert st.status == PipelineStatus.PENDING
    assert st.depends_on == []


def test_file_change():
    fc = FileChange(path="src/app.py", change_type="added", content="print('hello')")
    assert fc.path == "src/app.py"
    assert fc.change_type == "added"


def test_worker_result():
    wr = WorkerResult(subtask_id="sub-001", executor_type="cli", cli="claude", output="done")
    assert wr.output == "done"
    assert wr.files_changed == []
