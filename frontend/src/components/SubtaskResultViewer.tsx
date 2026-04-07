import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
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
            <Markdown remarkPlugins={[remarkGfm]}>{subtask.description || "No description"}</Markdown>
          </div>
        </div>

        {subtask.checklist && subtask.checklist.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <h4 style={{ margin: "0 0 8px 0", color: "var(--text-secondary, #aaa)" }}>
              Checklist ({subtask.checklist.filter(c => c.status === "done").length}/{subtask.checklist.length})
            </h4>
            <div style={{ fontSize: 13 }}>
              {subtask.checklist.map((item, idx) => (
                <div key={item.id || idx} style={{
                  padding: "4px 0",
                  display: "flex",
                  gap: 8,
                  color: item.status === "done" ? "var(--accent-green, #3fb950)" : "var(--text-primary, #e6edf3)",
                }}>
                  <span>{item.status === "done" ? "\u2705" : item.status === "in_progress" ? "\uD83D\uDD04" : "\u2B1C"}</span>
                  <span style={{ textDecoration: item.status === "done" ? "line-through" : "none", opacity: item.status === "done" ? 0.7 : 1 }}>
                    {item.title}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

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
              <Markdown remarkPlugins={[remarkGfm]}>{subtask.result}</Markdown>
            </div>
          </div>
        ) : (
          <div className="empty-state">No result yet</div>
        )}
      </div>
    </div>
  );
}
