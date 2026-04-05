import type { Pipeline } from "../types";
import { cancelTask, resumeTask } from "../hooks/useApi";

interface PipelineListProps {
  pipelines: Pipeline[];
  loading: boolean;
  onSelect: (pipeline: Pipeline) => void;
  onRefresh: () => void;
}

function formatTime(iso: string | null): string {
  if (!iso) return "--";
  const d = new Date(iso);
  return d.toLocaleTimeString();
}

/**
 * PipelineList: shows all pipelines with status.
 * Maps to GET /api/tasks endpoint.
 */
export function PipelineList({
  pipelines,
  loading,
  onSelect,
  onRefresh,
}: PipelineListProps) {
  const handleResume = async (e: React.MouseEvent, taskId: string) => {
    e.stopPropagation();
    try {
      await resumeTask(taskId);
      onRefresh();
    } catch {
      // Ignore errors (toast would be nice)
    }
  };

  const handleCancel = async (e: React.MouseEvent, taskId: string) => {
    e.stopPropagation();
    try {
      await cancelTask(taskId);
      onRefresh();
    } catch {
      // Ignore errors
    }
  };

  if (loading) {
    return (
      <div className="panel pipeline-list">
        <div className="panel-header">Pipelines</div>
        <div className="panel-body">
          <div className="empty-state">Loading...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="panel pipeline-list">
      <div className="panel-header">Pipelines</div>
      <div className="panel-body">
        {pipelines.length === 0 ? (
          <div className="empty-state">No pipelines yet. Submit a task to get started.</div>
        ) : (
          <table className="pipeline-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Task</th>
                <th>Status</th>
                <th>Preset</th>
                <th>Started</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {pipelines.map((p) => (
                <tr key={p.task_id} onClick={() => onSelect(p)} style={{ cursor: "pointer" }}>
                  <td style={{ fontFamily: "monospace", fontSize: 12 }}>
                    {p.task_id.slice(0, 16)}...
                  </td>
                  <td>{p.task.length > 60 ? p.task.slice(0, 60) + "..." : p.task}</td>
                  <td>
                    <span className={`status-badge ${p.status}`}>{p.status}</span>
                  </td>
                  <td>{p.team_preset || "auto"}</td>
                  <td style={{ fontSize: 12, color: "var(--text-muted)" }}>
                    {formatTime(p.started_at)}
                  </td>
                  <td>
                    {(p.status === "failed" || p.status === "partial_failure") && (
                      <button
                        className="btn btn-small btn-success"
                        onClick={(e) => handleResume(e, p.task_id)}
                      >
                        Resume
                      </button>
                    )}
                    {(p.status === "running" || p.status === "pending" || p.status === "planning") && (
                      <button
                        className="btn btn-small btn-danger"
                        onClick={(e) => handleCancel(e, p.task_id)}
                      >
                        Cancel
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
