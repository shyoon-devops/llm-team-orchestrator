import type { Pipeline } from "../types";

interface ResultViewerProps {
  pipeline: Pipeline | null;
  onClose: () => void;
}

/**
 * ResultViewer: displays the synthesized report for a selected pipeline.
 * Renders markdown content as simple formatted text.
 */
export function ResultViewer({ pipeline, onClose }: ResultViewerProps) {
  if (!pipeline) {
    return null;
  }

  return (
    <div className="panel" style={{ gridColumn: "1 / -1" }}>
      <div className="panel-header">
        <span>
          Result: {pipeline.task.length > 60 ? pipeline.task.slice(0, 60) + "..." : pipeline.task}
        </span>
        <button className="btn btn-small" onClick={onClose}>
          Close
        </button>
      </div>
      <div className="panel-body">
        <div style={{ marginBottom: 12, display: "flex", gap: 16, fontSize: 12 }}>
          <span>
            Status: <span className={`status-badge ${pipeline.status}`}>{pipeline.status}</span>
          </span>
          <span style={{ color: "var(--text-muted)" }}>
            Subtasks: {pipeline.subtasks.length}
          </span>
          {pipeline.error && (
            <span style={{ color: "var(--accent-red)" }}>
              Error: {pipeline.error}
            </span>
          )}
        </div>

        {pipeline.synthesis ? (
          <div className="result-viewer">
            <pre style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
              {pipeline.synthesis}
            </pre>
          </div>
        ) : (
          <div className="empty-state">
            {pipeline.status === "completed" || pipeline.status === "partial_failure"
              ? "No synthesis report available."
              : "Pipeline has not completed yet."}
          </div>
        )}

        {pipeline.results.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <h4 style={{ fontSize: 13, marginBottom: 8, color: "var(--text-secondary)" }}>
              Subtask Results ({pipeline.results.length})
            </h4>
            {pipeline.results.map((r) => (
              <div
                key={r.subtask_id}
                style={{
                  background: "var(--bg-tertiary)",
                  borderRadius: 6,
                  padding: 10,
                  marginBottom: 8,
                  fontSize: 12,
                }}
              >
                <div style={{ fontWeight: 500, marginBottom: 4 }}>
                  {r.subtask_id} ({r.executor_type}
                  {r.cli ? ` / ${r.cli}` : ""})
                </div>
                {r.output && (
                  <pre
                    style={{
                      whiteSpace: "pre-wrap",
                      wordBreak: "break-word",
                      color: "var(--text-secondary)",
                      maxHeight: 100,
                      overflow: "auto",
                    }}
                  >
                    {r.output}
                  </pre>
                )}
                {r.error && (
                  <div style={{ color: "var(--accent-red)", marginTop: 4 }}>
                    {r.error}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
