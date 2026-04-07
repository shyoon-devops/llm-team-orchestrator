import { useEffect, useState } from "react";
import Markdown from "react-markdown";

interface TaskDetail {
  id: string;
  title: string;
  description: string;
  lane: string;
  state: string;
  priority: number;
  depends_on: string[];
  assigned_to: string | null;
  result: string;
  error: string;
  retry_count: number;
  max_retries: number;
  pipeline_id: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  pipeline_task: string;
}

interface TaskDetailModalProps {
  taskId: string;
  onClose: () => void;
}

function formatElapsed(startedAt: string | null, completedAt: string | null): string {
  if (!startedAt) return "-";
  const start = new Date(startedAt).getTime();
  const end = completedAt ? new Date(completedAt).getTime() : Date.now();
  const ms = end - start;
  if (ms < 1000) return `${ms}ms`;
  const seconds = Math.round(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remainSeconds = seconds % 60;
  return `${minutes}m ${remainSeconds}s`;
}

function formatDatetime(dt: string | null): string {
  if (!dt) return "-";
  return new Date(dt).toLocaleString();
}

/**
 * TaskDetailModal: shows detailed info about a kanban task.
 * Fetched from GET /api/board/tasks/{task_id}.
 */
export function TaskDetailModal({ taskId, onClose }: TaskDetailModalProps) {
  const [detail, setDetail] = useState<TaskDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    setError("");
    fetch(`/api/board/tasks/${taskId}`)
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
        return r.json();
      })
      .then((data) => setDetail(data))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [taskId]);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-content"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="panel-header" style={{ display: "flex", justifyContent: "space-between" }}>
          <span>Task Detail</span>
          <button className="btn btn-small" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="panel-body" style={{ maxHeight: "70vh", overflowY: "auto" }}>
          {loading && <div className="empty-state">Loading...</div>}
          {error && (
            <div style={{ color: "var(--accent-red)", fontSize: 12 }}>{error}</div>
          )}
          {detail && (
            <div style={{ fontSize: 13 }}>
              {/* Title & status */}
              <div style={{ marginBottom: 12 }}>
                <h3 style={{ fontSize: 16, marginBottom: 4 }}>{detail.title}</h3>
                <span className={`status-badge ${detail.state}`}>{detail.state}</span>
                <span style={{ fontSize: 11, color: "var(--text-muted)", marginLeft: 8 }}>
                  {detail.id}
                </span>
              </div>

              {/* Metadata table */}
              <table style={{ width: "100%", fontSize: 12, marginBottom: 12 }}>
                <tbody>
                  <tr>
                    <td style={{ color: "var(--text-muted)", padding: "4px 8px 4px 0", whiteSpace: "nowrap" }}>Lane</td>
                    <td style={{ padding: "4px 0" }}>{detail.lane}</td>
                  </tr>
                  <tr>
                    <td style={{ color: "var(--text-muted)", padding: "4px 8px 4px 0", whiteSpace: "nowrap" }}>Assigned To</td>
                    <td style={{ padding: "4px 0" }}>{detail.assigned_to || "-"}</td>
                  </tr>
                  <tr>
                    <td style={{ color: "var(--text-muted)", padding: "4px 8px 4px 0", whiteSpace: "nowrap" }}>Depends On</td>
                    <td style={{ padding: "4px 0" }}>
                      {detail.depends_on.length > 0 ? detail.depends_on.join(", ") : "-"}
                    </td>
                  </tr>
                  <tr>
                    <td style={{ color: "var(--text-muted)", padding: "4px 8px 4px 0", whiteSpace: "nowrap" }}>Priority</td>
                    <td style={{ padding: "4px 0" }}>{detail.priority}</td>
                  </tr>
                  <tr>
                    <td style={{ color: "var(--text-muted)", padding: "4px 8px 4px 0", whiteSpace: "nowrap" }}>Retries</td>
                    <td style={{ padding: "4px 0" }}>{detail.retry_count} / {detail.max_retries}</td>
                  </tr>
                  <tr>
                    <td style={{ color: "var(--text-muted)", padding: "4px 8px 4px 0", whiteSpace: "nowrap" }}>Pipeline</td>
                    <td style={{ padding: "4px 0" }}>{detail.pipeline_id}</td>
                  </tr>
                  <tr>
                    <td style={{ color: "var(--text-muted)", padding: "4px 8px 4px 0", whiteSpace: "nowrap" }}>Created</td>
                    <td style={{ padding: "4px 0" }}>{formatDatetime(detail.created_at)}</td>
                  </tr>
                  <tr>
                    <td style={{ color: "var(--text-muted)", padding: "4px 8px 4px 0", whiteSpace: "nowrap" }}>Started</td>
                    <td style={{ padding: "4px 0" }}>{formatDatetime(detail.started_at)}</td>
                  </tr>
                  <tr>
                    <td style={{ color: "var(--text-muted)", padding: "4px 8px 4px 0", whiteSpace: "nowrap" }}>Completed</td>
                    <td style={{ padding: "4px 0" }}>{formatDatetime(detail.completed_at)}</td>
                  </tr>
                  <tr>
                    <td style={{ color: "var(--text-muted)", padding: "4px 8px 4px 0", whiteSpace: "nowrap" }}>Elapsed</td>
                    <td style={{ padding: "4px 0" }}>{formatElapsed(detail.started_at, detail.completed_at)}</td>
                  </tr>
                </tbody>
              </table>

              {/* Description */}
              {detail.description && (
                <div style={{ marginBottom: 12 }}>
                  <div style={{ fontWeight: 600, marginBottom: 4, fontSize: 12, color: "var(--text-secondary)" }}>
                    DESCRIPTION
                  </div>
                  <div className="result-viewer">
                    <Markdown>{detail.description}</Markdown>
                  </div>
                </div>
              )}

              {/* Result */}
              {detail.result && (
                <div style={{ marginBottom: 12 }}>
                  <div style={{ fontWeight: 600, marginBottom: 4, fontSize: 12, color: "var(--text-secondary)" }}>
                    RESULT
                  </div>
                  <div className="result-viewer">
                    <Markdown>{detail.result}</Markdown>
                  </div>
                </div>
              )}

              {/* Error */}
              {detail.error && (
                <div style={{ marginBottom: 12 }}>
                  <div style={{ fontWeight: 600, marginBottom: 4, fontSize: 12, color: "var(--accent-red)" }}>
                    ERROR
                  </div>
                  <div
                    style={{
                      background: "var(--bg-tertiary)",
                      padding: 12,
                      borderRadius: 6,
                      fontSize: 12,
                      fontFamily: "monospace",
                      color: "var(--accent-red)",
                      whiteSpace: "pre-wrap",
                    }}
                  >
                    {detail.error}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
