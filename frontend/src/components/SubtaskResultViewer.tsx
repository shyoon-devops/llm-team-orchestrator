import type { SubtaskInfo } from "./SubtaskList";

interface SubtaskResultViewerProps {
  subtask: SubtaskInfo;
}

/**
 * SubtaskResultViewer: displays the result text of a selected subtask.
 */
export function SubtaskResultViewer({ subtask }: SubtaskResultViewerProps) {
  return (
    <div className="subtask-result-viewer">
      <div className="panel-header">
        [{subtask.assigned_preset}] Result
        <span
          className={`status-badge ${subtask.state}`}
          style={{ marginLeft: 8 }}
        >
          {subtask.state}
        </span>
      </div>
      <div className="panel-body">
        {subtask.error && (
          <div className="error-block" style={{ color: "var(--danger, #e55)", marginBottom: 8 }}>
            Error: {subtask.error}
          </div>
        )}
        {subtask.result ? (
          <pre className="result-text" style={{ whiteSpace: "pre-wrap", fontSize: 13 }}>
            {subtask.result}
          </pre>
        ) : (
          <div className="empty-state">No result yet</div>
        )}
      </div>
    </div>
  );
}
