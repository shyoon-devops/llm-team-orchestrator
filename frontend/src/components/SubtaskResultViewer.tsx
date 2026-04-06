import Markdown from "react-markdown";
import type { SubtaskInfo } from "./SubtaskList";

interface SubtaskResultViewerProps {
  subtask: SubtaskInfo;
}

/**
 * SubtaskResultViewer: displays the description and result of a selected subtask.
 * Renders content as Markdown for better readability.
 */
export function SubtaskResultViewer({ subtask }: SubtaskResultViewerProps) {
  return (
    <div className="subtask-result-viewer">
      <div className="panel-header">
        [{subtask.assigned_preset}] Subtask Detail
        <span
          className={`status-badge ${subtask.state}`}
          style={{ marginLeft: 8 }}
        >
          {subtask.state}
        </span>
      </div>
      <div className="panel-body">
        <div style={{ marginBottom: 16 }}>
          <h4 style={{ margin: "0 0 8px 0", color: "var(--text-secondary, #aaa)" }}>
            Description
          </h4>
          <div className="markdown-content">
            <Markdown>{subtask.description || "No description"}</Markdown>
          </div>
        </div>

        {subtask.error && (
          <div className="error-block" style={{ color: "var(--danger, #e55)", marginBottom: 8 }}>
            Error: {subtask.error}
          </div>
        )}

        {subtask.result ? (
          <div>
            <h4 style={{ margin: "0 0 8px 0", color: "var(--text-secondary, #aaa)" }}>
              Result
            </h4>
            <div className="markdown-content">
              <Markdown>{subtask.result}</Markdown>
            </div>
          </div>
        ) : (
          <div className="empty-state">No result yet</div>
        )}
      </div>
    </div>
  );
}
